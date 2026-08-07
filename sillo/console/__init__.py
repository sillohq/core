"""
sillo.console — building blocks for a project's command-line tooling.

sillo ships a `sillo` command, and this is the toolkit
for the one a project writes: a command class, explicit parameter declaration, a
dispatcher, and the output and prompt primitives that make a console readable.
The file, the command set and the names stay the project's, in the same way that
``sillo.record.commands`` supplies migration operations without supplying a
migration CLI.

A console in full::

    from sillo.console import Argument, Command, Console, Flag, Option


    class CreateAdmin(Command):
        name = "user:admin"
        help = "Create an administrator"

        arguments = [
            Argument("email", help="Address to create the account under"),
            Argument("username"),
            Option("role", default="admin", choices=["admin", "owner"]),
            Flag("force", short="f", help="Overwrite an existing account"),
        ]

        async def handle(self):
            if self.flag("force") and not self.confirm("Overwrite?"):
                return 1

            password = self.secret("Password", confirm=True)
            user = await create_admin(
                self.argument("email"),
                self.argument("username"),
                password,
                role=self.option("role"),
            )
            self.success(f"Created {user.email}")


    console = Console(prog="python tools.py")
    console.add(CreateAdmin)

    if __name__ == "__main__":
        console.main()

Nothing in this package imports anything outside the standard library.
"""

from __future__ import annotations

from .arguments import Argument, Flag, Option, Parameter, ParsedInput, parse
from .command import Command
from .console import Console
from .exceptions import Abort, CommandError, ConsoleError, UsageError
from .output import Output, ProgressBar, Spinner
from .prompt import Prompt
from .style import (
    DANGER,
    HEADING,
    INFO,
    MUTED,
    PRIMARY,
    SUCCESS,
    WARNING,
    Palette,
    Style,
    strip_ansi,
)
from .terminal import (
    Key,
    is_interactive,
    supports_color,
    supports_unicode,
    terminal_width,
)

__all__ = [
    "DANGER",
    "HEADING",
    "INFO",
    "MUTED",
    "PRIMARY",
    "SUCCESS",
    "WARNING",
    "Abort",
    "Argument",
    "Command",
    "CommandError",
    "Console",
    "ConsoleError",
    "Flag",
    "Key",
    "Option",
    "Output",
    "Palette",
    "Parameter",
    "ParsedInput",
    "ProgressBar",
    "Prompt",
    "Spinner",
    "Style",
    "UsageError",
    "is_interactive",
    "parse",
    "strip_ansi",
    "supports_color",
    "supports_unicode",
    "terminal_width",
]
