"""
sillo.users.commands — user management as plain functions.

These are the operations the ``sillo`` CLI exposes for user management. They are
covered here because a project's tooling calls them directly, which makes them
public API in the way a private helper is not.
"""

import inspect

import pytest
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from sillo.users.commands import (
    create_admin,
    create_user,
    find_user,
    list_users,
    set_active,
    set_password,
    set_staff,
)

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)

PASSWORD = "Str0ng!pass"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["sillo.users.base"]},
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


class TestCreating:
    async def test_create_user_makes_an_ordinary_account(self):
        user = await create_user("ada@example.com", "ada", PASSWORD)

        assert user.email == "ada@example.com"
        assert user.is_staff is False
        # The password is hashed, never stored as given.
        assert user.password != PASSWORD
        assert user.check_password(PASSWORD)

    async def test_create_admin_marks_the_account_as_staff(self):
        """The admin panel admits accounts with is_staff, and nothing else."""
        user = await create_admin("root@example.com", "root", PASSWORD)

        assert user.is_staff is True

    async def test_extra_fields_are_passed_through(self):
        user = await create_user(
            "e@example.com", "ext", PASSWORD, is_superuser=True
        )

        assert user.is_superuser is True

    @pytest.mark.parametrize(
        "email, username, expected",
        [
            ("ada@example.com", "other", "already registered"),
            ("other@example.com", "ada", "is taken"),
        ],
    )
    async def test_duplicates_are_refused_before_writing(self, email, username, expected):
        """A database constraint would name a column, not the value at fault."""
        await create_user("ada@example.com", "ada", PASSWORD)

        with pytest.raises(ValueError) as error:
            await create_user(email, username, PASSWORD)
        assert expected in str(error.value)

    async def test_only_create_admin_enforces_the_password_policy(self):
        """A real asymmetry in the framework, pinned here rather than assumed.

        ``create_superuser`` validates the password — length, an uppercase
        letter, a digit, a special character — and ``create_user`` does not. So
        an ordinary account can hold a password an administrator could not.
        Worth closing; until it is, this records what actually happens.
        """
        weak = await create_user("weak@example.com", "weak", "short")
        assert weak.check_password("short")

        with pytest.raises(ValueError) as error:
            await create_admin("boss@example.com", "boss", "short")
        assert "8 characters" in str(error.value)


class TestFinding:
    async def test_finds_by_email_or_username(self):
        await create_user("ada@example.com", "ada", PASSWORD)

        assert (await find_user("ada@example.com")).username == "ada"
        assert (await find_user("ada")).email == "ada@example.com"

    async def test_missing_users_are_none_not_an_error(self):
        assert await find_user("nobody") is None

    async def test_a_deactivated_user_is_still_findable(self):
        """Otherwise deactivating an account would be irreversible.

        The manager's own lookups filter on is_active, so going through them
        would leave a disabled user impossible to find and therefore impossible
        to re-enable.
        """
        await create_user("ada@example.com", "ada", PASSWORD)
        await set_active("ada", False)

        assert await find_user("ada") is not None
        assert await find_user("ada", include_inactive=False) is None


class TestManaging:
    async def test_set_password_changes_the_credential(self):
        await create_user("ada@example.com", "ada", PASSWORD)

        user = await set_password("ada", "An0ther!pass")

        assert user.check_password("An0ther!pass")
        assert not user.check_password(PASSWORD)

    async def test_set_active_disables_and_re_enables(self):
        await create_user("ada@example.com", "ada", PASSWORD)

        assert (await set_active("ada", False)).is_active is False
        assert (await set_active("ada", True)).is_active is True

    async def test_set_staff_grants_and_withdraws_admin_access(self):
        await create_user("ada@example.com", "ada", PASSWORD)

        assert (await set_staff("ada", True)).is_staff is True
        assert (await set_staff("ada", False)).is_staff is False

    @pytest.mark.parametrize("command", [set_password, set_active, set_staff])
    async def test_managing_an_unknown_user_says_so(self, command):
        with pytest.raises(LookupError) as error:
            await command("nobody", "An0ther!pass" if command is set_password else True)
        assert "nobody" in str(error.value)


class TestListing:
    async def test_lists_newest_first(self):
        await create_user("one@example.com", "one", PASSWORD)
        await create_user("two@example.com", "two", PASSWORD)

        assert [user.username for user in await list_users()] == ["two", "one"]

    async def test_staff_only_narrows_to_admins(self):
        await create_user("one@example.com", "one", PASSWORD)
        await create_admin("root@example.com", "root", PASSWORD)

        assert [user.username for user in await list_users(staff_only=True)] == ["root"]

    async def test_limit_and_offset_page_through(self):
        for index in range(3):
            await create_user(f"{index}@example.com", f"user{index}", PASSWORD)

        assert len(await list_users(limit=2)) == 2
        assert len(await list_users(limit=2, offset=2)) == 1
