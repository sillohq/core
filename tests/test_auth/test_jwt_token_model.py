"""Direct coverage of JWTToken/TokenBlacklist model methods: revocation,
family/user-wide revocation, and expired-record cleanup. These are exercised
by real backend flows in other tests only indirectly (if at all), so they are
covered here against a real in-memory database.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from sillo.auth.jwt_auth.models import JWTToken, TokenBlacklist

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


@pytest.fixture(autouse=True)
async def jwt_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["sillo.auth.jwt_auth.models"]},
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


def _future():
    return datetime.now(timezone.utc) + timedelta(hours=1)


def _past():
    return datetime.now(timezone.utc) - timedelta(hours=1)


async def test_revoke_sets_flag():
    token = await JWTToken.create(
        user_id=1, token_jti="t1", token_family="f1", expires_at=_future()
    )
    assert token.is_active is True

    await token.revoke()

    refreshed = await JWTToken.get(id=token.id)
    assert refreshed.revoked is True
    assert refreshed.is_active is False


async def test_revoke_family_revokes_only_that_family():
    await JWTToken.create(
        user_id=1, token_jti="a1", token_family="fam-a", expires_at=_future()
    )
    await JWTToken.create(
        user_id=1, token_jti="a2", token_family="fam-a", expires_at=_future()
    )
    await JWTToken.create(
        user_id=1, token_jti="b1", token_family="fam-b", expires_at=_future()
    )

    count = await JWTToken.revoke_family("fam-a")

    assert count == 2
    fam_a = await JWTToken.filter(token_family="fam-a").all()
    fam_b = await JWTToken.filter(token_family="fam-b").all()
    assert all(t.revoked for t in fam_a)
    assert all(not t.revoked for t in fam_b)


async def test_revoke_all_for_user_revokes_only_that_user():
    await JWTToken.create(
        user_id=10, token_jti="u1", token_family="f", expires_at=_future()
    )
    await JWTToken.create(
        user_id=10, token_jti="u2", token_family="f", expires_at=_future()
    )
    await JWTToken.create(
        user_id=20, token_jti="u3", token_family="f", expires_at=_future()
    )

    count = await JWTToken.revoke_all_for_user(10)

    assert count == 2
    user_10 = await JWTToken.filter(user_id=10).all()
    user_20 = await JWTToken.filter(user_id=20).all()
    assert all(t.revoked for t in user_10)
    assert all(not t.revoked for t in user_20)


async def test_cleanup_expired_removes_only_expired_tokens():
    await JWTToken.create(
        user_id=1, token_jti="old", token_family="f", expires_at=_past()
    )
    await JWTToken.create(
        user_id=1, token_jti="fresh", token_family="f", expires_at=_future()
    )

    count = await JWTToken.cleanup_expired()

    assert count == 1
    remaining = await JWTToken.all()
    assert [t.token_jti for t in remaining] == ["fresh"]


async def test_token_blacklist_prune_expired_removes_only_expired_entries():
    await TokenBlacklist.create(token_jti="old", expires_at=_past())
    await TokenBlacklist.create(token_jti="fresh", expires_at=_future())

    count = await TokenBlacklist.prune_expired()

    assert count == 1
    remaining = await TokenBlacklist.all()
    assert [e.token_jti for e in remaining] == ["fresh"]
