"""
sillo.users.console — account management, as console commands.

``sillo.users.commands`` supplies the operations as plain functions. This binds
them to a user model and gives them names, arguments and output::

    from sillo.console import Console
    from sillo.users.console import user_commands

    console = Console(prog="python console.py")
    console.add_many(user_commands(context=database))

No model has to be named. ``sillo.users.commands`` already falls back to the
built-in :class:`sillo.users.base.User`, so a project that has not defined its
own still gets working commands; pass ``model=`` when it has.

Passwords are read from a hidden prompt, or from ``SILLO_PASSWORD`` when there
is no terminal — a CI job creating a seed account has nowhere to type.
"""

from __future__ import annotations

import os
from typing import Any, Callable, ClassVar, List, Optional, Type, Union

from sillo.console import Argument, Command, Flag, Option

__all__ = ["user_commands"]


ContextSource = Union[Any, Callable[[], Any], None]

#: Read instead of prompting when the terminal is not interactive.
PASSWORD_VARIABLE = "SILLO_PASSWORD"


class _Config:
    """What the user commands were bound to.

    Args:
        model: The user model, or None for sillo's own.
        context: An async context manager, or a callable returning one, opened
            around every command. The ORM has to be initialised before these
            operate on models, and that is the application's job.
    """

    def __init__(self, model: Any, context: ContextSource) -> None:
        self.model = model
        self.context = context

    def open(self) -> Any:
        """Return the context manager to wrap a command in.

        Returns:
            The context manager, or None when none was bound.
        """
        if self.context is None:
            return None
        return self.context() if callable(self.context) else self.context


class UserCommand(Command):
    """Base for the account commands.

    Attributes:
        config: Set by :func:`user_commands` on a subclass.
    """

    config: ClassVar[Optional[_Config]] = None

    def context(self) -> Any:
        """Open the database around the command, when one was bound.

        Returns:
            The bound context manager, or None.
        """
        return self.config.open() if self.config else None

    @property
    def model(self) -> Any:
        """The user model these commands act on.

        Returns:
            The bound model, or None to let sillo.users.commands choose.
        """
        return self.config.model if self.config else None

    def read_password(self, question: str = "Password", confirm: bool = True) -> str:
        """Get a password without echoing it.

        Args:
            question: What to ask.
            confirm: Ask twice and require a match.

        Returns:
            The password.

        Raises:
            CommandError: If there is no terminal and no environment variable,
                since the alternative is prompting into a pipe and hanging.
        """
        from_environment = os.environ.get(PASSWORD_VARIABLE)
        if from_environment:
            return from_environment

        if not self.prompt.interactive:
            self.fail(
                f"No terminal to read a password from. Set {PASSWORD_VARIABLE} instead."
            )

        return self.secret(question, confirm=confirm)

    def render(self, users: List[Any]) -> None:
        """Draw a table of *users*.

        Args:
            users: The rows to show.
        """
        if not users:
            self.muted("No users yet.")
            return

        self.table(
            ["id", "email", "username", "admin", "active"],
            [
                [
                    user.id,
                    user.email,
                    user.username,
                    "yes" if getattr(user, "is_staff", False) else "",
                    "yes" if getattr(user, "is_active", True) else "no",
                ]
                for user in users
            ],
            align=["right", "left", "left", "center", "center"],
        )


class Create(UserCommand):
    """Create an ordinary user account."""

    name = "user:create"
    help = "Create a user"

    arguments = [
        Argument("email", help="Email address. Must not already be registered"),
        Argument("username", help="Username. Must not already be taken"),
        Flag("admin", help="Give the account admin access"),
    ]

    async def handle(self) -> None:
        from .commands import create_admin, create_user

        password = self.read_password()
        create = create_admin if self.flag("admin") else create_user

        try:
            user = await create(
                self.argument("email"),
                self.argument("username"),
                password,
                model=self.model,
            )
        except ValueError as error:
            # The framework names the rule that failed — which address is taken,
            # or which part of the password policy. Its wording beats a guess.
            self.fail(str(error))

        self.success(f"Created {user.email}.")
        if self.flag("admin"):
            self.muted("  Sign in at /admin/")


class CreateAdmin(UserCommand):
    """Create an administrator account.

    The same as ``user:create --admin``, kept separate because it is the one
    people look for by name when setting a project up.
    """

    name = "user:admin"
    help = "Create an administrator"

    arguments = [
        Argument("email", help="Email address"),
        Argument("username", default=None, help="Username. Defaults to the mailbox"),
    ]

    async def handle(self) -> None:
        from .commands import create_admin

        email = self.argument("email")
        username = self.argument("username") or email.split("@", 1)[0]
        password = self.read_password()

        try:
            user = await create_admin(email, username, password, model=self.model)
        except ValueError as error:
            self.fail(str(error))

        self.success(f"Created {user.email}.")
        self.muted("  Sign in at /admin/")


class ListUsers(UserCommand):
    """List accounts, newest first."""

    name = "user:list"
    help = "List users, newest first"

    arguments = [
        Option("limit", type=int, default=50, short="l", help="Maximum rows"),
        Option("offset", type=int, default=0, help="Rows to skip"),
        Flag("staff", help="Only accounts with admin access"),
    ]

    async def handle(self) -> None:
        from .commands import list_users

        users = await list_users(
            model=self.model,
            limit=self.option("limit"),
            offset=self.option("offset"),
            staff_only=self.flag("staff"),
        )
        self.render(users)
        if users:
            self.blank()
            self.muted(f"  {len(users)} shown")


class Show(UserCommand):
    """Show one account."""

    name = "user:show"
    help = "Show one account"

    arguments = [Argument("identifier", help="Email address or username")]

    async def handle(self) -> None:
        from .commands import find_user

        user = await find_user(self.argument("identifier"), model=self.model)
        if user is None:
            self.fail(f"No user matches {self.argument('identifier')!r}.")

        self.pairs(
            [
                ("id", user.id),
                ("email", user.email),
                ("username", user.username),
                ("admin", "yes" if getattr(user, "is_staff", False) else "no"),
                ("active", "yes" if getattr(user, "is_active", True) else "no"),
            ]
        )


class SetPassword(UserCommand):
    """Change an account's password."""

    name = "user:password"
    help = "Change a password"

    arguments = [Argument("identifier", help="Email address or username")]

    async def handle(self) -> None:
        from .commands import set_password

        password = self.read_password("New password")

        try:
            await set_password(self.argument("identifier"), password, model=self.model)
        except (LookupError, ValueError) as error:
            self.fail(str(error))

        self.success("Password changed.")


class SetActive(UserCommand):
    """Activate or deactivate an account.

    A deactivated account keeps its rows and its history; it just cannot sign
    in. That is almost always what "delete this user" should mean.
    """

    name = "user:active"
    help = "Activate or deactivate an account"

    arguments = [
        Argument("identifier", help="Email address or username"),
        Flag("off", help="Deactivate instead of activating"),
    ]

    async def handle(self) -> None:
        from .commands import set_active

        active = not self.flag("off")
        try:
            user = await set_active(
                self.argument("identifier"), active, model=self.model
            )
        except LookupError as error:
            self.fail(str(error))

        self.success(f"{user.email} is now {'active' if active else 'deactivated'}.")


class SetStaff(UserCommand):
    """Grant or revoke admin access."""

    name = "user:staff"
    help = "Grant or revoke admin access"

    arguments = [
        Argument("identifier", help="Email address or username"),
        Flag("revoke", help="Take the access away instead"),
    ]

    async def handle(self) -> None:
        from .commands import set_staff

        staff = not self.flag("revoke")
        try:
            user = await set_staff(self.argument("identifier"), staff, model=self.model)
        except LookupError as error:
            self.fail(str(error))

        self.success(f"{user.email} {'now has' if staff else 'no longer has'} access.")


#: Every command this module defines, in the order they are listed.
COMMANDS: List[Type[UserCommand]] = [
    Create,
    CreateAdmin,
    ListUsers,
    Show,
    SetPassword,
    SetActive,
    SetStaff,
]


def user_commands(
    *,
    model: Any = None,
    context: ContextSource = None,
    only: Optional[List[str]] = None,
) -> List[Type[Command]]:
    """Return the account commands.

    Args:
        model: The user model. Omit it to use sillo's built-in one.
        context: An async context manager, or a callable returning one, opened
            around every command. These operate on models, so the ORM has to be
            initialised first; pass the project's database here.
        only: Names to include, such as ``["user:admin", "user:list"]``. Omit it
            for all of them.

    Returns:
        Command classes ready to pass to :meth:`~sillo.console.Console.add_many`.

    Raises:
        ValueError: If *only* names a command this module does not define.
    """
    config = _Config(model, context)
    chosen = COMMANDS

    if only is not None:
        available = {command.name: command for command in COMMANDS}
        unknown = [name for name in only if name not in available]
        if unknown:
            raise ValueError(
                f"user_commands has no {unknown[0]!r}. "
                f"It defines: {', '.join(sorted(available))}"
            )
        chosen = [available[name] for name in only]

    return [
        type(command.__name__, (command,), {"config": config}) for command in chosen
    ]
