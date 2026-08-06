"""
sillo.console.exceptions — what goes wrong on the way into a command.

These separate the three failures a console has to tell apart. A
:class:`UsageError` is the user's typo and deserves the usage line. A
:class:`CommandError` is the command reporting that the work could not be done,
and deserves the message alone. An :class:`Abort` is the user pressing Ctrl-C,
which deserves neither.
"""

from __future__ import annotations

from typing import Optional

__all__ = ["Abort", "CommandError", "ConsoleError", "UsageError"]


class ConsoleError(Exception):
    """Base class for every error raised by the console."""


class UsageError(ConsoleError):
    """The command line could not be understood.

    Args:
        message: What was wrong with the input.
        command: The command being parsed, when one had been resolved. The
            runner uses it to print the usage line for that command rather
            than for the console as a whole.
    """

    exit_code = 2

    def __init__(self, message: str, command: Optional[str] = None) -> None:
        super().__init__(message)
        self.command = command


class CommandError(ConsoleError):
    """A command failed while doing its work.

    Raise this rather than printing and returning a code when the failure is
    worth a non-zero exit and a single line of explanation.

    Args:
        message: What failed.
        exit_code: The status to exit with.
    """

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class Abort(ConsoleError):
    """The user interrupted a prompt.

    Raised in place of ``KeyboardInterrupt`` so a command can catch an
    abandoned prompt without also catching a Ctrl-C aimed at its own work.
    """

    exit_code = 130
