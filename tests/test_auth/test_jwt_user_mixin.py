"""
``JWTUserMixin``: issuing, rotating, revoking, and blacklisting tokens.

Refresh rotation is the security-critical part. Presenting a refresh token
twice means one of the two holders is an attacker, so the second use must
burn the whole family rather than quietly hand out another pair — those
reuse paths are covered explicitly.
"""

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.auth.jwt_auth.mixins import JWTUserMixin
from sillo.auth.jwt_auth.models import JWTToken, TokenBlacklist
from sillo.record import Model

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)

SECRET = "a-test-signing-secret-value"


class TokenUser(Model, JWTUserMixin):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255)

    class Meta:
        table = "jwt_mixin_users"

    @property
    def identity(self) -> str:
        return str(self.id)

    @property
    def display_name(self) -> str:
        return self.email


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={
            "models": [
                "sillo.auth.jwt_auth.models",
                "tests.test_auth.test_jwt_user_mixin",
            ]
        },
    )
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas()
    yield
    try:
        await Tortoise._drop_databases()
    except ConfigurationError:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass


@pytest.fixture
async def user():
    return await TokenUser.create(email="ada@example.com")


# ── issuing ──────────────────────────────────────────────────────────────


async def test_a_pair_contains_both_tokens(user):
    pair = await user.issue_token_pair(SECRET)
    assert pair["access_token"]
    assert pair["refresh_token"]


async def test_the_pair_is_a_bearer_pair(user):
    assert (await user.issue_token_pair(SECRET))["token_type"] == "bearer"


async def test_the_two_tokens_differ(user):
    pair = await user.issue_token_pair(SECRET)
    assert pair["access_token"] != pair["refresh_token"]


async def test_a_family_links_the_pair(user):
    assert len((await user.issue_token_pair(SECRET))["token_family"]) == 64


async def test_two_tracking_rows_are_written(user):
    await user.issue_token_pair(SECRET)
    assert await JWTToken.all().count() == 2


async def test_one_row_of_each_type_is_written(user):
    await user.issue_token_pair(SECRET)
    assert await JWTToken.filter(token_type="access").count() == 1
    assert await JWTToken.filter(token_type="refresh").count() == 1


async def test_both_rows_share_the_family(user):
    pair = await user.issue_token_pair(SECRET)
    rows = await JWTToken.all()
    assert {r.token_family for r in rows} == {pair["token_family"]}


async def test_the_rows_belong_to_the_user(user):
    await user.issue_token_pair(SECRET)
    assert await JWTToken.filter(user_id=user.id).count() == 2


async def test_each_issue_starts_a_new_family(user):
    first = await user.issue_token_pair(SECRET)
    second = await user.issue_token_pair(SECRET)
    assert first["token_family"] != second["token_family"]


async def test_custom_lifetimes_are_honoured(user):
    await user.issue_token_pair(
        SECRET, access_expires=timedelta(minutes=1), refresh_expires=timedelta(hours=1)
    )
    access = await JWTToken.get(token_type="access")
    refresh = await JWTToken.get(token_type="refresh")
    assert access.expires_at < refresh.expires_at


async def test_the_default_refresh_outlives_the_default_access(user):
    await user.issue_token_pair(SECRET)
    access = await JWTToken.get(token_type="access")
    refresh = await JWTToken.get(token_type="refresh")
    assert refresh.expires_at > access.expires_at


async def test_a_freshly_issued_token_is_active(user):
    await user.issue_token_pair(SECRET)
    assert (await JWTToken.get(token_type="access")).is_active is True


async def test_an_alternative_algorithm_is_accepted(user):
    pair = await user.issue_token_pair(SECRET, algorithm="HS512")
    assert pair["access_token"]


# ── rotation ─────────────────────────────────────────────────────────────


async def test_rotation_returns_a_new_pair(user):
    original = await user.issue_token_pair(SECRET)
    rotated = await user.refresh_token_pair(original["refresh_token"], SECRET)
    assert rotated["access_token"]
    assert rotated["refresh_token"]


async def test_rotation_stays_in_the_same_family(user):
    original = await user.issue_token_pair(SECRET)
    rotated = await user.refresh_token_pair(original["refresh_token"], SECRET)
    assert rotated["token_family"] == original["token_family"]


async def test_rotation_writes_two_more_rows(user):
    original = await user.issue_token_pair(SECRET)
    await user.refresh_token_pair(original["refresh_token"], SECRET)
    assert await JWTToken.all().count() == 4


async def test_the_old_refresh_token_is_marked_consumed(user):
    original = await user.issue_token_pair(SECRET)
    await user.refresh_token_pair(original["refresh_token"], SECRET)
    consumed = await JWTToken.filter(
        token_type="refresh", consumed_at__not_isnull=True
    ).count()
    assert consumed == 1


async def test_a_garbage_refresh_token_is_rejected(user):
    with pytest.raises(ValueError, match="Invalid refresh token"):
        await user.refresh_token_pair("not-a-jwt", SECRET)


async def test_a_token_signed_with_another_secret_is_rejected(user):
    original = await user.issue_token_pair("some-other-secret-entirely")
    with pytest.raises(ValueError, match="Invalid refresh token"):
        await user.refresh_token_pair(original["refresh_token"], SECRET)


async def test_an_untracked_token_is_rejected(user):
    """A validly signed token with no tracking row was issued by something
    else, or its row was purged; either way it cannot be rotated."""
    original = await user.issue_token_pair(SECRET)
    await JWTToken.all().delete()
    with pytest.raises(ValueError, match="Unknown refresh token"):
        await user.refresh_token_pair(original["refresh_token"], SECRET)


async def test_an_access_token_cannot_be_used_to_refresh(user):
    original = await user.issue_token_pair(SECRET)
    with pytest.raises(ValueError, match="Unknown refresh token"):
        await user.refresh_token_pair(original["access_token"], SECRET)


async def test_reusing_a_refresh_token_is_refused(user):
    original = await user.issue_token_pair(SECRET)
    await user.refresh_token_pair(original["refresh_token"], SECRET)
    with pytest.raises(ValueError, match="already consumed"):
        await user.refresh_token_pair(original["refresh_token"], SECRET)


async def test_reuse_burns_the_whole_family(user):
    """If a refresh token is presented twice, one of the two callers stole it
    — so every token in the family is revoked, not just the replayed one."""
    original = await user.issue_token_pair(SECRET)
    await user.refresh_token_pair(original["refresh_token"], SECRET)
    with pytest.raises(ValueError):
        await user.refresh_token_pair(original["refresh_token"], SECRET)

    family = original["token_family"]
    remaining = await JWTToken.filter(token_family=family, revoked=False).count()
    assert remaining == 0


async def test_a_revoked_token_cannot_be_rotated(user):
    original = await user.issue_token_pair(SECRET)
    row = await JWTToken.get(token_type="refresh")
    row.revoked = True
    await row.save()
    with pytest.raises(ValueError, match="revoked"):
        await user.refresh_token_pair(original["refresh_token"], SECRET)


async def test_rotating_a_revoked_token_burns_the_family(user):
    original = await user.issue_token_pair(SECRET)
    row = await JWTToken.get(token_type="refresh")
    row.revoked = True
    await row.save()
    with pytest.raises(ValueError):
        await user.refresh_token_pair(original["refresh_token"], SECRET)
    assert (
        await JWTToken.filter(
            token_family=original["token_family"], revoked=False
        ).count()
        == 0
    )


async def test_an_expired_refresh_token_can_still_be_rotated(user):
    """Rotation verifies the signature without the expiry check, so a client
    that comes back late gets a new pair rather than a forced re-login."""
    original = await user.issue_token_pair(
        SECRET, refresh_expires=timedelta(seconds=-1)
    )
    rotated = await user.refresh_token_pair(original["refresh_token"], SECRET)
    assert rotated["access_token"]


async def test_rotation_can_be_chained(user):
    pair = await user.issue_token_pair(SECRET)
    for _ in range(3):
        pair = await user.refresh_token_pair(pair["refresh_token"], SECRET)
    assert pair["access_token"]


# ── revocation ───────────────────────────────────────────────────────────


async def test_revoking_all_tokens_reports_a_count(user):
    await user.issue_token_pair(SECRET)
    assert await user.revoke_all_tokens() == 2


async def test_revoking_leaves_nothing_active(user):
    await user.issue_token_pair(SECRET)
    await user.revoke_all_tokens()
    assert await JWTToken.filter(user_id=user.id, revoked=False).count() == 0


async def test_revoking_twice_reports_nothing_the_second_time(user):
    await user.issue_token_pair(SECRET)
    await user.revoke_all_tokens()
    assert await user.revoke_all_tokens() == 0


async def test_revoking_with_no_tokens_is_zero(user):
    assert await user.revoke_all_tokens() == 0


async def test_revoking_does_not_touch_another_user(user):
    other = await TokenUser.create(email="grace@example.com")
    await user.issue_token_pair(SECRET)
    await other.issue_token_pair(SECRET)
    await user.revoke_all_tokens()
    assert await JWTToken.filter(user_id=other.id, revoked=False).count() == 2


# ── counting ─────────────────────────────────────────────────────────────


async def test_a_fresh_pair_counts_as_two_active(user):
    await user.issue_token_pair(SECRET)
    assert await user.active_token_count() == 2


async def test_the_count_starts_at_zero(user):
    assert await user.active_token_count() == 0


async def test_revoked_tokens_are_not_counted(user):
    await user.issue_token_pair(SECRET)
    await user.revoke_all_tokens()
    assert await user.active_token_count() == 0


async def test_expired_tokens_are_not_counted(user):
    await user.issue_token_pair(
        SECRET,
        access_expires=timedelta(seconds=-10),
        refresh_expires=timedelta(seconds=-10),
    )
    assert await user.active_token_count() == 0


async def test_the_count_is_per_user(user):
    other = await TokenUser.create(email="grace@example.com")
    await user.issue_token_pair(SECRET)
    assert await other.active_token_count() == 0


# ── blacklisting ─────────────────────────────────────────────────────────


async def test_a_token_can_be_blacklisted(user):
    pair = await user.issue_token_pair(SECRET)
    assert await user.blacklist_token(pair["access_token"], SECRET) is True


async def test_blacklisting_writes_a_row(user):
    pair = await user.issue_token_pair(SECRET)
    await user.blacklist_token(pair["access_token"], SECRET)
    assert await TokenBlacklist.all().count() == 1


async def test_a_garbage_token_is_not_blacklisted(user):
    assert await user.blacklist_token("not-a-jwt", SECRET) is False
    assert await TokenBlacklist.all().count() == 0


async def test_a_token_signed_elsewhere_is_not_blacklisted(user):
    pair = await user.issue_token_pair("some-other-secret-entirely")
    assert await user.blacklist_token(pair["access_token"], SECRET) is False


async def test_blacklisting_the_same_token_twice_writes_one_row(user):
    pair = await user.issue_token_pair(SECRET)
    await user.blacklist_token(pair["access_token"], SECRET)
    await user.blacklist_token(pair["access_token"], SECRET)
    assert await TokenBlacklist.all().count() == 1


async def test_the_blacklist_entry_expires_with_the_token(user):
    pair = await user.issue_token_pair(SECRET, access_expires=timedelta(minutes=5))
    await user.blacklist_token(pair["access_token"], SECRET)
    entry = await TokenBlacklist.all().first()
    assert entry.expires_at < datetime.now(timezone.utc) + timedelta(minutes=10)


async def test_an_expired_token_can_still_be_blacklisted(user):
    pair = await user.issue_token_pair(SECRET, access_expires=timedelta(seconds=-10))
    assert await user.blacklist_token(pair["access_token"], SECRET) is True


async def test_both_tokens_of_a_pair_can_be_blacklisted(user):
    pair = await user.issue_token_pair(SECRET)
    await user.blacklist_token(pair["access_token"], SECRET)
    await user.blacklist_token(pair["refresh_token"], SECRET)
    assert await TokenBlacklist.all().count() == 2
