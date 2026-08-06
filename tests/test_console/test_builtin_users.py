"""The account commands, driven through a console against a real database."""

from __future__ import annotations

import inspect
import io

import pytest
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from sillo.console import Console, strip_ansi
from sillo.users.commands import create_admin, create_user, find_user
from sillo.users.console import PASSWORD_VARIABLE, user_commands

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)

PASSWORD = "Str0ng!pass"


@pytest.fixture(autouse=True)
async def record_db():
    """The built-in user model, on an in-memory database."""
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


@pytest.fixture
def console():
    """A console with the account commands and a captured stream."""
    stream = io.StringIO()
    built = Console(
        prog="console.py",
        output=stream,
        error=stream,
        input=io.StringIO(),
        color=False,
        interactive=False,
    )
    built.add_many(user_commands())
    return built, stream


@pytest.fixture(autouse=True)
def password_in_the_environment(monkeypatch):
    """Supply the password the way a CI job would."""
    monkeypatch.setenv(PASSWORD_VARIABLE, PASSWORD)


def written(stream) -> str:
    """What the console wrote, unstyled."""
    return strip_ansi(stream.getvalue())


# -- no custom model needed --------------------------------------------


async def test_the_commands_work_without_a_project_model(console):
    # user_commands() was called with no model at all: sillo.users.commands
    # falls back to its own User, so a project that has not defined one still
    # gets working account management.
    built, stream = console

    assert await built.run_async(["user:admin", "ada@example.com", "ada"]) == 0

    user = await find_user("ada@example.com")
    assert user is not None
    assert user.is_staff is True


async def test_a_project_model_can_be_named_instead():
    from sillo.users.base import User

    stream = io.StringIO()
    built = Console(output=stream, error=stream, color=False, interactive=False)
    built.add_many(user_commands(model=User))

    assert await built.run_async(["user:admin", "grace@example.com", "grace"]) == 0
    assert await find_user("grace@example.com") is not None


# -- creating ----------------------------------------------------------


async def test_creating_an_admin_reports_where_to_sign_in(console):
    built, stream = console

    await built.run_async(["user:admin", "ada@example.com", "ada"])

    assert "Created ada@example.com." in written(stream)
    assert "/admin/" in written(stream)


async def test_the_username_defaults_to_the_mailbox(console):
    built, _ = console

    await built.run_async(["user:admin", "ada@example.com"])

    user = await find_user("ada")
    assert user is not None
    assert user.email == "ada@example.com"


async def test_creating_a_user_makes_an_ordinary_account(console):
    built, _ = console

    assert await built.run_async(["user:create", "linus@example.com", "linus"]) == 0

    user = await find_user("linus@example.com")
    assert user.is_staff is False


async def test_the_admin_flag_promotes_a_created_user(console):
    built, _ = console

    await built.run_async(["user:create", "grace@example.com", "grace", "--admin"])

    user = await find_user("grace@example.com")
    assert user.is_staff is True


async def test_a_duplicate_address_fails_with_the_frameworks_wording(console):
    built, stream = console
    await create_user("ada@example.com", "ada", PASSWORD)

    assert await built.run_async(["user:admin", "ada@example.com", "second"]) == 1
    assert "ada@example.com" in written(stream)


async def test_the_password_is_never_stored_as_given(console):
    built, _ = console

    await built.run_async(["user:admin", "ada@example.com", "ada"])

    user = await find_user("ada@example.com")
    assert user.password != PASSWORD


# -- reading the password ----------------------------------------------


async def test_without_a_terminal_or_a_variable_it_refuses_rather_than_hangs(
    console, monkeypatch
):
    monkeypatch.delenv(PASSWORD_VARIABLE, raising=False)
    built, stream = console

    assert await built.run_async(["user:admin", "ada@example.com", "ada"]) == 1
    assert PASSWORD_VARIABLE in written(stream)
    assert await find_user("ada@example.com") is None


async def test_a_typed_password_is_used_when_there_is_a_terminal(monkeypatch):
    monkeypatch.delenv(PASSWORD_VARIABLE, raising=False)
    monkeypatch.setattr("getpass.getpass", lambda *a, **k: PASSWORD)

    stream = io.StringIO()
    built = Console(output=stream, error=stream, color=False, interactive=True)
    built.add_many(user_commands())

    assert await built.run_async(["user:admin", "ada@example.com", "ada"]) == 0
    assert await find_user("ada@example.com") is not None


# -- listing and showing -----------------------------------------------


async def test_listing_draws_a_table(console):
    built, stream = console
    await create_admin("ada@example.com", "ada", PASSWORD)
    await create_user("linus@example.com", "linus", PASSWORD)

    assert await built.run_async(["user:list"]) == 0
    text = written(stream)

    assert "ada@example.com" in text
    assert "linus@example.com" in text
    assert "2 shown" in text


async def test_listing_says_so_when_there_is_nobody(console):
    built, stream = console

    await built.run_async(["user:list"])

    assert "No users yet." in written(stream)


async def test_the_staff_flag_narrows_the_list(console):
    built, stream = console
    await create_admin("ada@example.com", "ada", PASSWORD)
    await create_user("linus@example.com", "linus", PASSWORD)

    await built.run_async(["user:list", "--staff"])
    text = written(stream)

    assert "ada@example.com" in text
    assert "linus@example.com" not in text


async def test_the_limit_is_honoured(console):
    built, stream = console
    for number in range(4):
        await create_user(f"user{number}@example.com", f"user{number}", PASSWORD)

    await built.run_async(["user:list", "-l", "2"])

    assert "2 shown" in written(stream)


async def test_showing_reports_the_accounts_state(console):
    built, stream = console
    await create_admin("ada@example.com", "ada", PASSWORD)

    assert await built.run_async(["user:show", "ada@example.com"]) == 0
    text = written(stream)

    assert "ada@example.com" in text
    assert "admin" in text


async def test_showing_a_stranger_fails(console):
    built, stream = console

    assert await built.run_async(["user:show", "nobody@example.com"]) == 1
    assert "No user matches" in written(stream)


async def test_an_account_is_findable_by_username_too(console):
    built, stream = console
    await create_user("ada@example.com", "ada", PASSWORD)

    assert await built.run_async(["user:show", "ada"]) == 0
    assert "ada@example.com" in written(stream)


# -- changing accounts -------------------------------------------------


async def test_the_password_can_be_changed(console):
    built, stream = console
    user = await create_user("ada@example.com", "ada", PASSWORD)
    before = user.password

    assert await built.run_async(["user:password", "ada@example.com"]) == 0
    assert "Password changed." in written(stream)

    after = await find_user("ada@example.com")
    assert after.password != before


async def test_changing_a_strangers_password_fails(console):
    built, stream = console

    assert await built.run_async(["user:password", "nobody@example.com"]) == 1
    assert "nobody@example.com" in written(stream)


async def test_an_account_can_be_deactivated_and_reactivated(console):
    built, _ = console
    await create_user("ada@example.com", "ada", PASSWORD)

    await built.run_async(["user:active", "ada@example.com", "--off"])
    assert (await find_user("ada@example.com")).is_active is False

    await built.run_async(["user:active", "ada@example.com"])
    assert (await find_user("ada@example.com")).is_active is True


async def test_deactivating_keeps_the_row(console):
    # Deactivation is the reversible alternative to deletion; the account has
    # to still be findable afterwards or it could never be turned back on.
    built, _ = console
    await create_user("ada@example.com", "ada", PASSWORD)

    await built.run_async(["user:active", "ada@example.com", "--off"])

    assert await find_user("ada@example.com") is not None


async def test_admin_access_can_be_granted_and_revoked(console):
    built, _ = console
    await create_user("ada@example.com", "ada", PASSWORD)

    await built.run_async(["user:staff", "ada@example.com"])
    assert (await find_user("ada@example.com")).is_staff is True

    await built.run_async(["user:staff", "ada@example.com", "--revoke"])
    assert (await find_user("ada@example.com")).is_staff is False


# -- selecting which commands to register ------------------------------


def test_only_registers_the_named_commands():
    stream = io.StringIO()
    built = Console(output=stream, error=stream, color=False, interactive=False)
    built.add_many(user_commands(only=["user:admin", "user:list"]))

    assert set(built.commands) == {"user:admin", "user:list"}


def test_only_rejects_a_name_it_does_not_define():
    with pytest.raises(ValueError, match="user_commands has no 'user:nope'"):
        user_commands(only=["user:nope"])


def test_two_consoles_can_bind_different_models():
    from sillo.users.base import User

    first = user_commands(model=User)[0]
    second = user_commands(model=None)[0]

    # A subclass per registration, so the second binding does not overwrite
    # the first.
    assert first.config.model is User
    assert second.config.model is None
