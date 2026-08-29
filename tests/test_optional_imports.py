"""``import sillo`` must work without the optional extras installed.

The extras are optional at install time. They were not optional at *import*
time: a package re-exporting ``RecordBackend`` for convenience pulled Tortoise
into ``import sillo``, so ``pip install sillo-framework`` produced a package
that could not be imported at all, and the ``sillo`` command died before
printing its help.

These run in a subprocess with the optional dependencies blocked at the import
system, which is the only way to reproduce that in an environment where they
happen to be installed. They fail the moment somebody adds an eager import back.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

#: Every extra sillo declares, by the module that provides it.
OPTIONAL = ["tortoise", "redis", "jwt", "jinja2", "strawberry", "bcrypt", "argon2"]


BLOCKER = '''
import sys

BLOCKED_NAMES = __NAMES__


class Blocked:
    """Refuse to import the named top-level packages."""

    def __init__(self, names):
        self.names = set(names)

    def find_module(self, name, path=None):
        return self if name.split(".")[0] in self.names else None

    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in self.names:
            raise ImportError(f"No module named {name!r}")
        return None


for name in list(sys.modules):
    if name.split(".")[0] in BLOCKED_NAMES:
        del sys.modules[name]

sys.meta_path.insert(0, Blocked(BLOCKED_NAMES))
'''


def run_without(names, body: str) -> subprocess.CompletedProcess:
    """Run *body* in a subprocess where *names* cannot be imported.

    Args:
        names: Top-level module names to block.
        body: The Python to run once they are blocked.

    Returns:
        The finished process.
    """
    # A plain replace, not .format: the template contains an f-string with
    # braces of its own.
    script = BLOCKER.replace("__NAMES__", repr(set(names))) + textwrap.dedent(body)
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )


def test_the_blocker_actually_blocks():
    # Without this, every test below would pass by doing nothing.
    result = run_without(["tortoise"], "import tortoise")

    assert result.returncode != 0
    assert "No module named" in result.stderr


def test_importing_sillo_needs_no_optional_dependency():
    result = run_without(OPTIONAL, "import sillo; print(sillo.__version__)")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()


@pytest.mark.parametrize("missing", OPTIONAL)
def test_importing_sillo_survives_each_one_missing(missing):
    result = run_without([missing], "import sillo")

    assert result.returncode == 0, result.stderr


def test_the_application_can_be_built_without_the_orm():
    result = run_without(
        ["tortoise"],
        """
        from sillo import SilloApp

        app = SilloApp(title="Bare")

        @app.get("/")
        async def home(request, response):
            return json({"ok": True})

        print("built", len(app.router.routes))
        """,
    )

    assert result.returncode == 0, result.stderr
    assert "built" in result.stdout


def test_the_console_imports_without_the_orm():
    result = run_without(
        ["tortoise"],
        """
        from sillo.console import Command, Console

        console = Console(prog="sillo")
        print("console ok")
        """,
    )

    assert result.returncode == 0, result.stderr


def test_the_cli_runs_without_the_orm():
    result = run_without(
        OPTIONAL,
        """
        import sillo.__main__ as cli

        console, warning = cli.build_console()
        print(sorted(console.commands))
        """,
    )

    assert result.returncode == 0, result.stderr
    assert "version" in result.stdout


# -- what the deferred names must still do -----------------------------


def test_a_deferred_name_reports_the_missing_extra_when_used():
    # Deferring must not turn "you need the record extra" into something
    # inscrutable. The ORM's own ImportError is the clearest message available.
    result = run_without(
        ["tortoise"],
        """
        import sillo.users

        try:
            sillo.users.User
        except ImportError as error:
            print("ImportError:", error)
        """,
    )

    assert result.returncode == 0, result.stderr
    assert "tortoise" in result.stdout


def test_an_unknown_attribute_is_still_an_attribute_error():
    result = run_without(
        ["tortoise"],
        """
        import sillo.users

        try:
            sillo.users.NoSuchThing
        except AttributeError as error:
            print("AttributeError:", error)
        """,
    )

    assert result.returncode == 0, result.stderr
    assert "NoSuchThing" in result.stdout


# -- and with the extras present, nothing moved ------------------------


def test_the_deferred_names_are_the_objects_they_always_were():
    from sillo.security import RecordBackend
    from sillo.security.ratelimit import RecordBackend as viaratelimit
    from sillo.security.ratelimit.backends import RecordBackend as viabackends
    from sillo.security.ratelimit.backends.record import RecordBackend as direct

    assert RecordBackend is viaratelimit is viabackends is direct


def test_the_user_names_are_the_objects_they_always_were():
    from sillo.users import BaseUser, User, UserBaseModel, UserProtocol
    from sillo.users.base import User as direct_user
    from sillo.users.base import UserBaseModel as direct_model
    from sillo.users.protocol import BaseUser as direct_base
    from sillo.users.protocol import UserProtocol as direct_protocol

    assert User is direct_user
    assert UserBaseModel is direct_model
    assert BaseUser is direct_base
    assert UserProtocol is direct_protocol


def test_the_auth_names_are_the_objects_they_always_were():
    from sillo.auth import JWTAuthBackend, SessionAuthBackend, create_jwt
    from sillo.auth.jwt_auth import JWTAuthBackend as direct_jwt
    from sillo.auth.jwt_auth import create_jwt as direct_create
    from sillo.auth.session_auth import SessionAuthBackend as direct_session

    assert JWTAuthBackend is direct_jwt
    assert SessionAuthBackend is direct_session
    assert create_jwt is direct_create


def test_the_auth_submodules_are_still_reachable():
    from sillo.auth import apikey, jwt_auth, session_auth

    assert jwt_auth.__name__ == "sillo.auth.jwt_auth"
    assert session_auth.__name__ == "sillo.auth.session_auth"
    assert apikey.__name__ == "sillo.auth.apikey"
