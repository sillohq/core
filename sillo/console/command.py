"""
sillo.console.command — the unit a console dispatches to.

A command is a class with a name, a list of parameters and a ``handle``
method::

    class CreateAdmin(Command):
        name = "user:admin"
        help = "Create an administrator"

        arguments = [
            Argument("email", help="Address to create the account under"),
            Argument("username"),
            Flag("force", help="Overwrite an existing account"),
        ]

        async def handle(self):
            password = self.secret("Password", confirm=True)
            user = await create_admin(
                self.argument("email"),
                self.argument("username"),
                password,
            )
            self.success(f"Created {user.email}")

``handle`` may be synchronous or a coroutine. Return an exit code from it, or
return nothing and let a clean run report success.

The parameter accessors are deliberately three methods rather than one. Reading
``self.option("force")`` when ``force`` was declared as a flag is a mistake worth
a message, not a silently wrong value.
"""

from __future__ import annotations

from typing import (
    Any,
    AsyncContextManager,
    Awaitable,
    ClassVar,
    List,
    NoReturn,
    Optional,
    Sequence,
    Union,
)

from .arguments import Parameter, ParsedInput
from .exceptions import CommandError
from .output import Output
from .prompt import Choice, Prompt, Validator
from .style import Style

__all__ = ["Command"]


class Command:
    """Base class for console commands.

    Attributes:
        name: How the command is invoked. A colon groups related commands in
            the help output, so ``db:migrate`` and ``db:make`` are listed
            together under ``db``.
        help: One line, shown in the command list.
        description: A longer explanation, shown in the command's own help.
            Falls back to the class docstring.
        arguments: The parameters the command accepts.
        aliases: Other names that dispatch here.
        hidden: Keep the command out of the listing. It still runs.
    """

    name: ClassVar[str] = ""
    help: ClassVar[str] = ""
    description: ClassVar[str] = ""
    arguments: ClassVar[Sequence[Parameter]] = []
    aliases: ClassVar[Sequence[str]] = []
    hidden: ClassVar[bool] = False

    def __init__(
        self,
        input: ParsedInput,
        output: Output,
        prompt: Prompt,
        console: Any = None,
    ) -> None:
        """Bind one invocation.

        Args:
            input: The parsed parameters.
            output: Where to write.
            prompt: How to ask questions.
            console: The console that dispatched here, for commands that need
                to list or call their siblings.
        """
        self.input = input
        self.output = output
        self.prompt = prompt
        self.console = console

    # -- to override ---------------------------------------------------

    def handle(  # pragma: no cover - overridden
        self,
    ) -> Union[Optional[int], Awaitable[Optional[int]]]:
        """Do the work.

        Declared synchronously and returning either a value or an awaitable,
        because both spellings are supported: most commands are ``async def``,
        but one that hands the event loop to something else — ``uvicorn.run``
        — has to be a plain ``def``. Declaring this ``async`` would make that
        override an incompatible one.

        Returns:
            An exit code, or None for success. May be awaitable.
        """
        raise NotImplementedError(f"{type(self).__name__} does not define handle()")

    def context(self) -> Optional[AsyncContextManager]:
        """Return a context manager to wrap :meth:`handle`.

        Override it when every command in a family needs the same thing opened
        and closed around it — a database connection being the usual one::

            class DatabaseCommand(Command):
                def context(self):
                    return database()

        Returns:
            An async context manager, or None to run handle() directly.
        """
        return None

    # -- parameters ----------------------------------------------------

    def argument(self, name: str) -> Any:
        """Return a positional argument's value.

        Args:
            name: The parameter name.

        Returns:
            The value.

        Raises:
            KeyError: If no such argument was declared.
        """
        return self.input.get(name, "argument")

    def option(self, name: str) -> Any:
        """Return an option's value.

        Args:
            name: The parameter name.

        Returns:
            The value.

        Raises:
            KeyError: If no such option was declared.
        """
        return self.input.get(name, "option")

    def flag(self, name: str) -> bool:
        """Return whether a flag is set.

        Args:
            name: The parameter name.

        Returns:
            The value.

        Raises:
            KeyError: If no such flag was declared.
        """
        return bool(self.input.get(name, "flag"))

    @property
    def extra(self) -> List[str]:
        """Positional tokens that followed ``--``.

        Returns:
            The tokens, in order, for a command that forwards them to another
            process.
        """
        return self.input.extra

    # -- output --------------------------------------------------------

    def line(self, text: str = "", style: Optional[Style] = None) -> None:
        """Write one line.

        Args:
            text: The text.
            style: The style to apply.
        """
        self.output.line(text, style)

    def blank(self, count: int = 1) -> None:
        """Write empty lines.

        Args:
            count: How many.
        """
        self.output.blank(count)

    def info(self, text: str) -> None:
        """Write an informational line.

        Args:
            text: The message.
        """
        self.output.info(text)

    def success(self, text: str) -> None:
        """Write a line marking something as done.

        Args:
            text: The message.
        """
        self.output.success(text)

    def warn(self, text: str) -> None:
        """Write a warning.

        Args:
            text: The message.
        """
        self.output.warn(text)

    def error(self, text: str) -> None:
        """Write an error.

        Args:
            text: The message.
        """
        self.output.error(text)

    def muted(self, text: str) -> None:
        """Write a line of secondary detail.

        Args:
            text: The message.
        """
        self.output.muted(text)

    def bullet(self, text: str, indent: int = 2) -> None:
        """Write a bulleted line.

        Args:
            text: The item.
            indent: Leading spaces.
        """
        self.output.bullet(text, indent)

    def pairs(self, items: Sequence[Sequence[Any]], indent: int = 2) -> None:
        """Write aligned label/value pairs.

        Args:
            items: Two-element sequences of label and value.
            indent: Leading spaces.
        """
        self.output.pairs(items, indent)

    def table(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        align: Optional[Sequence[str]] = None,
    ) -> None:
        """Draw a table.

        Args:
            headers: The column headings.
            rows: The body.
            align: Per-column alignment.
        """
        self.output.table(headers, rows, align)

    def panel(self, body: str, title: str = "") -> None:
        """Draw a bordered box.

        Args:
            body: The contents.
            title: Text set into the top border.
        """
        self.output.panel(body, title)

    def rule(self, label: str = "") -> None:
        """Draw a horizontal rule.

        Args:
            label: Text to set into it.
        """
        self.output.rule(label)

    def progress(self, total: int, label: str = ""):
        """Show a progress bar for the duration of the block.

        Args:
            total: The number of steps that count as complete.
            label: Text shown before the bar.

        Returns:
            A context manager yielding the bar.
        """
        return self.output.progress(total, label)

    def spinner(self, label: str = "Working"):
        """Show a spinner for the duration of the block.

        Args:
            label: Text shown beside it.

        Returns:
            A context manager yielding the spinner.
        """
        return self.output.spinner(label)

    # -- questions -----------------------------------------------------

    def ask(
        self,
        question: str,
        default: Optional[str] = None,
        validate: Optional[Validator] = None,
    ) -> Any:
        """Ask for a line of text.

        Args:
            question: What to ask.
            default: Used when the answer is empty, and when the terminal is
                not interactive.
            validate: Called with the answer.

        Returns:
            The answer.
        """
        return self.prompt.ask(question, default, validate)

    def secret(self, question: str = "Password", confirm: bool = False) -> str:
        """Ask for a value without echoing it.

        Args:
            question: What to ask.
            confirm: Ask twice and require a match.

        Returns:
            The answer.
        """
        return self.prompt.secret(question, confirm)

    def confirm(self, question: str, default: bool = False) -> bool:
        """Ask a yes or no question.

        Args:
            question: What to ask.
            default: The answer on Enter, and when not interactive.

        Returns:
            The answer.
        """
        return self.prompt.confirm(question, default)

    def choice(
        self,
        question: str,
        options: Sequence[Choice],
        default: Any = None,
    ) -> Any:
        """Ask the user to pick one option.

        Args:
            question: What to ask.
            options: The options.
            default: Preselected value, and the answer when not interactive.

        Returns:
            The chosen value.
        """
        return self.prompt.choice(question, options, default)

    def multichoice(
        self,
        question: str,
        options: Sequence[Choice],
        defaults: Optional[Sequence[Any]] = None,
        minimum: int = 0,
    ) -> List[Any]:
        """Ask the user to pick any number of options.

        Args:
            question: What to ask.
            options: The options.
            defaults: Preselected values.
            minimum: Reject a smaller selection.

        Returns:
            The chosen values.
        """
        return self.prompt.multichoice(question, options, defaults, minimum)

    # -- failing -------------------------------------------------------

    def fail(self, message: str, exit_code: int = 1) -> NoReturn:
        """Abandon the command with a message.

        Annotated ``NoReturn`` because it always raises. That is what lets a
        caller write ``if user is None: self.fail(...)`` and have everything
        after it treat ``user`` as found, rather than needing a ``return`` the
        reader would wonder about.

        Args:
            message: What went wrong.
            exit_code: The status to exit with.

        Raises:
            CommandError: Always.
        """
        raise CommandError(message, exit_code)

    # -- introspection -------------------------------------------------

    @classmethod
    def group(cls) -> str:
        """The part of the name before the colon.

        Returns:
            The group, or an empty string for an ungrouped command.
        """
        return cls.name.split(":", 1)[0] if ":" in cls.name else ""

    @classmethod
    def summary(cls) -> str:
        """One line describing the command.

        Returns:
            The ``help`` attribute, falling back to the first line of the
            docstring.
        """
        if cls.help:
            return cls.help
        doc = (cls.__doc__ or "").strip()
        return doc.split("\n", 1)[0] if doc else ""

    @classmethod
    def details(cls) -> str:
        """The longer explanation shown in the command's own help.

        Returns:
            The ``description`` attribute, falling back to the docstring.
        """
        if cls.description:
            return cls.description.strip()
        return (cls.__doc__ or "").strip()
