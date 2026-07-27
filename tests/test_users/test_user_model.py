"""
The user model and its manager: creation, credential checks, permissions.

``verify_credentials`` is the front door for every auth backend in the
framework, so the ways it must say "no" — wrong password, unknown identifier,
deactivated account — get as much attention as the success path.
"""

import inspect

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.users.base import AnonymousUser, User, UserBaseModel
from sillo.users.managers import UserManager
from sillo.users.password import UNUSABLE_PASSWORD_PREFIX

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class Member(UserBaseModel):
    """A concrete user model of our own, to prove the base class is usable."""

    nickname = fields.CharField(max_length=50, default="")

    class Meta:
        table = "test_members"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["sillo.users.base", "tests.test_users.test_user_model"]},
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
def manager():
    m = UserManager()
    m.model = User
    return m


# ── creating users ───────────────────────────────────────────────────────


async def test_a_user_is_created(manager):
    user = await manager.create_user("ada@example.com", "ada", "correct-horse")
    assert user.id is not None


async def test_the_password_is_stored_hashed(manager):
    user = await manager.create_user("ada@example.com", "ada", "correct-horse")
    assert "correct-horse" not in user.password


async def test_the_stored_password_verifies(manager):
    user = await manager.create_user("ada@example.com", "ada", "correct-horse")
    assert user.check_password("correct-horse") is True


async def test_a_wrong_password_does_not_verify(manager):
    user = await manager.create_user("ada@example.com", "ada", "correct-horse")
    assert user.check_password("wrong") is False


async def test_a_new_user_is_active_by_default(manager):
    user = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert user.is_active is True


async def test_extra_fields_are_passed_through(manager):
    user = await manager.create_user(
        "ada@example.com", "ada", "pw-long-enough", is_staff=True
    )
    assert user.is_staff is True


async def test_is_active_can_be_overridden(manager):
    user = await manager.create_user(
        "ada@example.com", "ada", "pw-long-enough", is_active=False
    )
    assert user.is_active is False


async def test_a_user_without_a_password_gets_an_unusable_one(manager):
    """Invite flows create the row first; no password must mean no login,
    not an empty one that anything matches."""
    user = await manager.create_user("ada@example.com", "ada")
    assert user.has_usable_password() is False


async def test_an_unusable_password_rejects_every_attempt(manager):
    user = await manager.create_user("ada@example.com", "ada")
    assert user.check_password("") is False
    assert user.check_password(UNUSABLE_PASSWORD_PREFIX) is False


async def test_the_manager_falls_back_to_the_default_model():
    """An unattached manager still knows which model to write to."""
    unattached = UserManager()
    user = await unattached.create_user("solo@example.com", "solo", "pw-long-enough")
    assert isinstance(user, User)


def test_contribute_to_class_binds_the_model():
    m = UserManager()
    m.contribute_to_class(Member, "objects")
    assert m.model is Member


async def test_the_manager_writes_to_a_custom_model():
    m = UserManager()
    m.contribute_to_class(Member, "objects")
    member = await m.create_user("m@example.com", "member", "pw-long-enough")
    assert isinstance(member, Member)


# ── superusers ───────────────────────────────────────────────────────────


async def test_a_superuser_is_flagged(manager):
    user = await manager.create_superuser("root@example.com", "root", "Str0ng-Pass!23")
    assert user.is_superuser is True
    assert user.is_staff is True


async def test_a_superuser_is_active(manager):
    user = await manager.create_superuser("root@example.com", "root", "Str0ng-Pass!23")
    assert user.is_active is True


async def test_a_superuser_must_have_a_password(manager):
    with pytest.raises(ValueError, match="password"):
        await manager.create_superuser("root@example.com", "root", "")


async def test_a_weak_superuser_password_is_rejected(manager):
    """The account with every permission is the one worth being strict about."""
    with pytest.raises(ValueError):
        await manager.create_superuser("root@example.com", "root", "abc")


async def test_superuser_flags_can_be_overridden(manager):
    user = await manager.create_superuser(
        "root@example.com", "root", "Str0ng-Pass!23", is_staff=False
    )
    assert user.is_staff is False


# ── lookups ──────────────────────────────────────────────────────────────


async def test_lookup_by_id(manager):
    created = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert (await manager.get_by_id(created.id)).email == "ada@example.com"


async def test_lookup_by_email(manager):
    await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert (await manager.get_by_email("ada@example.com")).username == "ada"


async def test_lookup_by_username(manager):
    await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert (await manager.get_by_username("ada")).email == "ada@example.com"


async def test_an_unknown_id_gives_none(manager):
    assert await manager.get_by_id(99999) is None


async def test_an_unknown_email_gives_none(manager):
    assert await manager.get_by_email("nobody@example.com") is None


async def test_an_unknown_username_gives_none(manager):
    assert await manager.get_by_username("nobody") is None


async def test_an_inactive_user_is_not_found(manager):
    """Deactivation has to take effect at lookup, not only at login."""
    created = await manager.create_user(
        "gone@example.com", "gone", "pw-long-enough", is_active=False
    )
    assert await manager.get_by_id(created.id) is None
    assert await manager.get_by_email("gone@example.com") is None


async def test_the_natural_key_matches_an_email(manager):
    await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert (await manager.get_by_natural_key("ada@example.com")) is not None


async def test_the_natural_key_falls_back_to_the_username(manager):
    await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert (await manager.get_by_natural_key("ada")) is not None


async def test_an_unknown_natural_key_gives_none(manager):
    assert await manager.get_by_natural_key("nobody") is None


async def test_unattached_lookups_use_the_default_model():
    await UserManager().create_user("solo@example.com", "solo", "pw-long-enough")
    assert await UserManager().get_by_email("solo@example.com") is not None
    assert await UserManager().get_by_username("solo") is not None


# ── verify_credentials ───────────────────────────────────────────────────


async def test_correct_credentials_return_the_user(manager):
    await manager.create_user("ada@example.com", "ada", "correct-horse")
    user = await User.verify_credentials("ada@example.com", "correct-horse")
    assert user is not None


async def test_a_username_works_as_the_identifier(manager):
    await manager.create_user("ada@example.com", "ada", "correct-horse")
    assert await User.verify_credentials("ada", "correct-horse") is not None


async def test_a_wrong_password_is_refused(manager):
    await manager.create_user("ada@example.com", "ada", "correct-horse")
    assert await User.verify_credentials("ada@example.com", "wrong") is None


async def test_an_unknown_identifier_is_refused():
    assert await User.verify_credentials("nobody@example.com", "whatever") is None


async def test_an_inactive_user_cannot_authenticate(manager):
    await manager.create_user(
        "gone@example.com", "gone", "correct-horse", is_active=False
    )
    assert await User.verify_credentials("gone@example.com", "correct-horse") is None


async def test_a_successful_login_stamps_last_login(manager):
    await manager.create_user("ada@example.com", "ada", "correct-horse")
    user = await User.verify_credentials("ada@example.com", "correct-horse")
    assert user.last_login is not None


async def test_a_failed_login_does_not_stamp_last_login(manager):
    created = await manager.create_user("ada@example.com", "ada", "correct-horse")
    await User.verify_credentials("ada@example.com", "wrong")
    assert (await User.get(id=created.id)).last_login is None


async def test_a_user_with_an_unusable_password_cannot_authenticate(manager):
    await manager.create_user("invited@example.com", "invited")
    assert await User.verify_credentials("invited@example.com", "") is None


# ── loading and identity ─────────────────────────────────────────────────


async def test_load_user_by_identity(manager):
    created = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert (await User.load_user(str(created.id))).id == created.id


async def test_load_user_accepts_an_integer_identity(manager):
    created = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert (await User.load_user(created.id)) is not None


async def test_load_user_with_a_non_numeric_identity_gives_none():
    assert await User.load_user("not-a-number") is None


async def test_load_user_with_none_gives_none():
    assert await User.load_user(None) is None


async def test_load_user_skips_inactive_accounts(manager):
    created = await manager.create_user(
        "gone@example.com", "gone", "pw-long-enough", is_active=False
    )
    assert await User.load_user(str(created.id)) is None


async def test_the_identity_is_the_primary_key(manager):
    created = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert created.identity == str(created.id)


async def test_the_display_name_is_the_username(manager):
    created = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert created.display_name == "ada"


async def test_an_active_user_is_authenticated(manager):
    created = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert created.is_authenticated is True


async def test_a_deactivated_user_is_not_authenticated(manager):
    created = await manager.create_user(
        "gone@example.com", "gone", "pw-long-enough", is_active=False
    )
    assert created.is_authenticated is False


def test_the_email_field_name_is_reported():
    assert User.get_email_field_name() == "email"


async def test_marking_the_email_verified(manager):
    created = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    await created.mark_email_verified()
    assert (await User.get(id=created.id)).email_verified_at is not None


async def test_set_last_login_persists(manager):
    created = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    await created.set_last_login()
    assert (await User.get(id=created.id)).last_login is not None


# ── permissions ──────────────────────────────────────────────────────────


async def test_a_superuser_has_every_permission(manager):
    root = await manager.create_superuser("root@example.com", "root", "Str0ng-Pass!23")
    assert root.has_perm("anything.at.all") is True


async def test_an_ordinary_user_has_no_permissions_by_default(manager):
    user = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert user.has_perm("users.delete") is False


async def test_granted_permissions_are_honoured(manager):
    user = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    user._permissions = ["users.view"]
    assert user.has_perm("users.view") is True
    assert user.has_perm("users.delete") is False


async def test_has_permission_is_an_alias(manager):
    root = await manager.create_superuser("root@example.com", "root", "Str0ng-Pass!23")
    assert root.has_permission("anything") is True


async def test_has_perms_requires_all_of_them(manager):
    user = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    user._permissions = ["a", "b"]
    assert user.has_perms(["a", "b"]) is True
    assert user.has_perms(["a", "c"]) is False


async def test_an_empty_permission_list_is_satisfied(manager):
    user = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert user.has_perms([]) is True


async def test_module_permissions_need_staff_and_active(manager):
    staff = await manager.create_user(
        "staff@example.com", "staff", "pw-long-enough", is_staff=True
    )
    plain = await manager.create_user("plain@example.com", "plain", "pw-long-enough")
    assert staff.has_module_perms("users") is True
    assert plain.has_module_perms("users") is False


# ── password helpers ─────────────────────────────────────────────────────


async def test_setting_a_password_replaces_the_hash(manager):
    user = await manager.create_user("ada@example.com", "ada", "first-password")
    user.set_password("second-password")
    assert user.check_password("second-password") is True
    assert user.check_password("first-password") is False


async def test_marking_a_password_unusable(manager):
    user = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    user.set_unusable_password()
    assert user.has_usable_password() is False


async def test_a_normal_password_is_usable(manager):
    user = await manager.create_user("ada@example.com", "ada", "pw-long-enough")
    assert user.has_usable_password() is True


# ── the anonymous user ───────────────────────────────────────────────────


def test_the_anonymous_user_is_not_authenticated():
    assert AnonymousUser().is_authenticated is False


def test_the_anonymous_user_is_anonymous():
    assert AnonymousUser().is_anonymous is True


def test_the_anonymous_user_has_no_permissions():
    assert AnonymousUser().has_perm("anything") is False


def test_the_anonymous_user_has_an_empty_identity():
    assert AnonymousUser().get_id() in ("", None)


def test_anonymous_users_compare_equal():
    assert AnonymousUser() == AnonymousUser()


def test_the_anonymous_user_is_hashable():
    assert len({AnonymousUser(), AnonymousUser()}) == 1


def test_the_anonymous_user_has_a_readable_repr():
    assert "Anonymous" in repr(AnonymousUser())
