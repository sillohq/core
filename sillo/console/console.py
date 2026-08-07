"""
sillo.console.console — the registry, the argv walk and the help.

``Console`` is what the ``sillo`` command builds, and what a project builds for
tooling of its own::

    console = Console(prog="python tools.py")
    console.add(Migrate)
    console.add(CreateAdmin)

    if __name__ == "__main__":
        raise SystemExit(console.run())

It owns exactly three decisions: which command a set of tokens names, what the
help looks like, and which exit code a failure produces. The framework does not
supply the file, the command set or the names — those belong to the project, the
same way ``sillo.record.commands`` supplies migration operations without
supplying a migration CLI.

``run`` returns a status rather than calling ``sys.exit``, so a test can assert
on it and an embedding program can decide for itself what to do next.
"""

from __future__ import annotations

import asyncio
import difflib
import inspect
import sys
from typing import (
    IO,
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Sequence,
    Type,
    cast,
)

from .arguments import Argument, Flag, Option, Parameter, ParsedInput, parse
from .command import Command
from .exceptions import Abort, CommandError, ConsoleError, UsageError
from .output import Output
from .prompt import Prompt
from .style import HEADING, MUTED, PRIMARY, Palette

__all__ = ["Console"]


def _class_name_for(function: Callable) -> str:
    """Name the class generated for a function-form command.

    Args:
        function: The decorated function.

    Returns:
        A CamelCase class name. A callable is not required to carry
        ``__name__`` — a functools.partial does not — so the fallback keeps the
        decorator usable with anything callable.
    """
    name = getattr(function, "__name__", "generated")
    return name.title().replace("_", "") + "Command"


class Console:
    """A registry of commands and the entry point that dispatches to them.

    Args:
        prog: How the program is invoked, shown in usage lines.
        description: One line shown at the top of the help.
        version: Reported by ``--version``. Omit it and the flag is not offered.
        output: Where normal output goes. Defaults to stdout.
        error: Where errors go. Defaults to stderr.
        input: Where answers are read. Defaults to stdin.
        color: Force colour on or off. When None the streams are inspected.
        interactive: Force prompting on or off. When None the streams are
            inspected.
    """

    def __init__(
        self,
        prog: str = "console.py",
        description: str = "",
        version: Optional[str] = None,
        output: Optional[IO[str]] = None,
        error: Optional[IO[str]] = None,
        input: Optional[IO[str]] = None,
        color: Optional[bool] = None,
        interactive: Optional[bool] = None,
    ) -> None:
        self.prog = prog
        self.description = description
        self.version = version

        out_stream = output if output is not None else sys.stdout
        err_stream = error if error is not None else sys.stderr

        self.output = Output(out_stream, Palette(out_stream, enabled=color))
        self.error_output = Output(err_stream, Palette(err_stream, enabled=color))
        self.prompt = Prompt(self.output, input, interactive=interactive)

        self._commands: Dict[str, Type[Command]] = {}
        self._aliases: Dict[str, str] = {}

    # -- registration --------------------------------------------------

    def add(self, command: Type[Command], override: bool = False) -> Type[Command]:
        """Register *command*.

        Args:
            command: The command class.
            override: Replace an existing registration of the same name instead
                of refusing. For a console that merges a command set it does
                not own — ``sillo`` carrying a project's — where the incoming
                name is meant to win.

        Returns:
            The class, so this can be used as a decorator.

        Raises:
            ValueError: If the command has no name, or a name or alias is
                already taken and *override* is False.
        """
        if not getattr(command, "name", ""):
            raise ValueError(f"{command.__name__} needs a name")

        if command.name in self._commands and not override:
            existing = self._commands[command.name].__name__
            raise ValueError(f"{command.name!r} is already registered to {existing}")

        if override:
            self._forget(command.name)

        self._commands[command.name] = command
        for alias in command.aliases:
            if alias in self._aliases or alias in self._commands:
                if not override:
                    raise ValueError(f"{alias!r} is already registered")
                self._forget(self._aliases.get(alias, alias))
            self._aliases[alias] = command.name

        return command

    def _forget(self, name: str) -> None:
        """Remove a registration and every alias pointing at it.

        Args:
            name: The command name to drop.
        """
        self._commands.pop(name, None)
        for alias, target in list(self._aliases.items()):
            if target == name or alias == name:
                self._aliases.pop(alias, None)

    def add_many(self, commands: Sequence[Type[Command]]) -> None:
        """Register several commands.

        Args:
            commands: The command classes.
        """
        for command in commands:
            self.add(command)

    def command(
        self,
        name: str,
        help: str = "",
        arguments: Optional[Sequence[Parameter]] = None,
        aliases: Sequence[str] = (),
        hidden: bool = False,
    ) -> Callable[[Callable], Type[Command]]:
        """Register a plain function as a command.

        The class form is the primary one and is what a command with any real
        body should use. This exists for the one-liners, where a class is more
        ceremony than the command is worth::

            @console.command("cache:clear", help="Drop every cached entry")
            async def clear(command):
                await cache.flush()
                command.success("Cache cleared.")

        The function receives the command instance, so the same accessors and
        output helpers are available.

        Args:
            name: How the command is invoked.
            help: One line for the listing.
            arguments: The parameters it accepts.
            aliases: Other names that dispatch here.
            hidden: Keep it out of the listing.

        Returns:
            A decorator returning the generated command class.
        """

        def decorate(function: Callable) -> Type[Command]:
            async def handle(self: Command) -> Optional[int]:
                result = function(self)
                if inspect.isawaitable(result):
                    result = await result
                return result

            generated = type(
                _class_name_for(function),
                (Command,),
                {
                    "name": name,
                    "help": help or (function.__doc__ or "").strip().split("\n")[0],
                    "arguments": list(arguments or []),
                    "aliases": list(aliases),
                    "hidden": hidden,
                    "handle": handle,
                    "__doc__": function.__doc__,
                },
            )
            return self.add(generated)

        return decorate

    @property
    def commands(self) -> Dict[str, Type[Command]]:
        """Every registered command, keyed by name.

        Returns:
            A copy, so callers cannot mutate the registry by accident.
        """
        return dict(self._commands)

    def resolve(self, name: str) -> Optional[Type[Command]]:
        """Find the command *name* refers to.

        Args:
            name: A command name or alias.

        Returns:
            The command class, or None when nothing matches.
        """
        if name in self._commands:
            return self._commands[name]
        if name in self._aliases:
            return self._commands[self._aliases[name]]
        return None

    # -- help ----------------------------------------------------------

    def _usage_for(self, command: Type[Command]) -> str:
        """Build the usage line for *command*.

        Args:
            command: The command class.

        Returns:
            The usage line, without the leading label.
        """
        parts = [self.prog, command.name]
        parts.extend(
            parameter.usage()
            for parameter in command.arguments
            if isinstance(parameter, Argument)
        )
        if any(not isinstance(p, Argument) for p in command.arguments):
            parts.append("[options]")
        return " ".join(parts)

    def print_help(self) -> None:
        """Write the command listing."""
        out = self.output
        out.blank()
        out.write("  ", out.paint(self.prog, HEADING))
        if self.version:
            out.write(out.paint(f"  {self.version}", MUTED))
        out.blank()
        if self.description:
            out.line(f"  {out.paint(self.description, MUTED)}")

        out.blank()
        out.line(f"  {out.paint('USAGE', HEADING)}")
        out.line(f"    {self.prog} {out.paint('<command>', PRIMARY)} [options]")

        visible = [command for command in self._commands.values() if not command.hidden]
        groups: Dict[str, List[Type[Command]]] = {}
        for command in sorted(visible, key=lambda item: item.name):
            groups.setdefault(command.group(), []).append(command)

        options = [("-h, --help", "Show this help")]
        if self.version:
            options.append(("-V, --version", "Show the version"))

        # One column across both sections, so the descriptions line up whether
        # they belong to a command or to a global flag.
        width = max(
            [len(command.name) for command in visible]
            + [len(flag) for flag, _ in options]
            + [12]
        )

        for group in sorted(groups, key=lambda name: (name == "", name)):
            out.blank()
            out.line(f"  {out.paint(group.upper() or 'COMMANDS', HEADING)}")
            for command in groups[group]:
                out.write(
                    "    ",
                    out.paint(command.name.ljust(width), PRIMARY),
                    "  ",
                    command.summary(),
                    "\n",
                )

        out.blank()
        out.line(f"  {out.paint('OPTIONS', HEADING)}")
        for flag, text in options:
            out.write("    ", out.paint(flag.ljust(width), PRIMARY), "  ", text, "\n")
        out.blank()

    def print_command_help(self, command: Type[Command]) -> None:
        """Write the help for one command.

        Args:
            command: The command class.
        """
        out = self.output
        out.blank()
        out.write("  ", out.paint(command.name, HEADING))
        if command.summary():
            out.write(out.paint(f"  {command.summary()}", MUTED))
        out.blank()

        details = command.details()
        if details and details != command.summary():
            out.blank()
            for line in details.split("\n"):
                # A blank line in a docstring is a paragraph break, not two
                # spaces of trailing whitespace.
                out.blank() if not line.strip() else out.line(f"  {line.strip()}")

        out.blank()
        out.line(f"  {out.paint('USAGE', HEADING)}")
        out.line(f"    {self._usage_for(command)}")

        positionals = [p for p in command.arguments if isinstance(p, Argument)]
        named = [p for p in command.arguments if not isinstance(p, Argument)]
        width = max(
            [len(p.metavar) for p in positionals]
            + [len(self._spelling(p)) for p in named]
            + [12]
        )

        if positionals:
            out.blank()
            out.line(f"  {out.paint('ARGUMENTS', HEADING)}")
            for parameter in positionals:
                out.write(
                    "    ",
                    out.paint(parameter.metavar.ljust(width), PRIMARY),
                    "  ",
                    parameter.help,
                    "\n",
                )

        out.blank()
        out.line(f"  {out.paint('OPTIONS', HEADING)}")
        for parameter in named:
            suffix = ""
            if (
                isinstance(parameter, Option)
                and parameter.has_default
                and parameter.default not in (None, [])
            ):
                suffix = out.paint(f"  [{parameter.default}]", MUTED)
            out.write(
                "    ",
                out.paint(self._spelling(parameter).ljust(width), PRIMARY),
                "  ",
                parameter.help,
                suffix,
                "\n",
            )
        out.write("    ", out.paint("-h, --help".ljust(width), PRIMARY), "  ")
        out.write("Show this help\n")
        out.blank()

    @staticmethod
    def _spelling(parameter: Parameter) -> str:
        """How a named parameter is written on the command line.

        Args:
            parameter: An option or a flag.

        Returns:
            The short and long spellings, comma separated.
        """
        short = getattr(parameter, "short", None)
        name = parameter.name
        if isinstance(parameter, Flag) and parameter.default:
            name = parameter.negative
        return f"-{short}, --{name}" if short else f"--{name}"

    def _suggest(self, name: str) -> Optional[str]:
        """Find the registered name closest to *name*.

        Args:
            name: What the user typed.

        Returns:
            The nearest command name, or None when nothing is close.
        """
        candidates = list(self._commands) + list(self._aliases)
        matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
        return matches[0] if matches else None

    # -- running -------------------------------------------------------

    @staticmethod
    def _owns_loop(command: Type[Command]) -> bool:
        """Whether the command runs synchronously, owning any loop it makes.

        A plain ``def handle`` opts out of the console's loop: it hands the
        loop to something else — ``uvicorn.run`` — and wrapping it in
        ``asyncio.run`` would nest two. An ``async def handle``, including
        every function-form command, runs on the console's loop instead.

        Args:
            command: The resolved command class.

        Returns:
            True for a synchronous handle, False for a coroutine one.
        """
        return not inspect.iscoroutinefunction(command.handle)

    async def _dispatch(self, command: Type[Command], parsed: ParsedInput) -> int:
        """Instantiate and run *command*.

        Args:
            command: The command class.
            parsed: Its parameters.

        Returns:
            The exit code.
        """
        instance = command(parsed, self.output, self.prompt, console=self)

        async def call() -> Any:
            # handle() may be a plain def, so its return is a value or an
            # awaitable. Awaiting unconditionally would fail on the None a
            # synchronous command hands back. The result is narrowed to an exit
            # code below, which is why this is annotated loosely.
            result = instance.handle()
            if inspect.isawaitable(result):
                result = await result
            return result

        manager = instance.context()
        if manager is None:
            result = await call()
        else:
            async with manager:
                result = await call()

        return int(result) if isinstance(result, int) else 0

    def _dispatch_sync(self, command: Type[Command], parsed: ParsedInput) -> int:
        """Run a synchronous command without creating an event loop.

        Mirrors :meth:`_dispatch` for the commands :meth:`_owns_loop` picks
        out. A context hook that turns out to be async, or a handle that
        returns an awaitable anyway, falls back to ``asyncio.run`` — the
        command asked to run without the console's loop, but correctness
        beats the hint.

        Args:
            command: The command class.
            parsed: Its parameters.

        Returns:
            The exit code.
        """
        instance = command(parsed, self.output, self.prompt, console=self)

        manager = instance.context()
        if manager is not None and hasattr(manager, "__aenter__"):
            return asyncio.run(self._dispatch(command, parsed))

        if manager is None:
            result = instance.handle()
        else:
            with manager:
                result = instance.handle()

        if inspect.isawaitable(result):
            # isawaitable narrows to Awaitable, which asyncio.run does not
            # accept; a handle() that returns one returns a coroutine.
            result = asyncio.run(cast(Coroutine[Any, Any, Any], result))

        return int(result) if isinstance(result, int) else 0

    def _guard(self, command: Type[Command], body: Callable[[], int]) -> int:
        """Map a dispatch failure to its exit code, whichever path raised it.

        Args:
            command: The command being run, for the usage line.
            body: The dispatch, sync or ``asyncio.run``-wrapped.

        Returns:
            The exit code.
        """
        try:
            return body()
        except UsageError as error:
            return self._report_usage(error, command)
        except Abort:
            self.error_output.blank()
            self.error_output.muted("Cancelled.")
            return Abort.exit_code
        except KeyboardInterrupt:
            self.error_output.blank()
            self.error_output.muted("Cancelled.")
            return Abort.exit_code
        except CommandError as error:
            self.error_output.error(str(error))
            return error.exit_code
        except ConsoleError as error:
            self.error_output.error(str(error))
            return 1

    def _prepare(
        self, argv: Optional[Sequence[str]]
    ) -> int | tuple[Type[Command], ParsedInput]:
        """Walk the tokens to a command and its parsed input.

        Shared by :meth:`run` and :meth:`run_async`: help, version, resolving
        the name and parsing the parameters, none of which need a loop.

        Args:
            argv: The tokens after the program name. Defaults to
                ``sys.argv[1:]``.

        Returns:
            An exit code when the walk ends without dispatching, otherwise the
            command class and its parsed input.
        """
        tokens = list(sys.argv[1:] if argv is None else argv)

        if not tokens or tokens[0] in ("-h", "--help", "help"):
            self.print_help()
            return 0

        if self.version and tokens[0] in ("-V", "--version"):
            self.output.line(self.version)
            return 0

        name, rest = tokens[0], tokens[1:]
        command = self.resolve(name)

        if command is None:
            self.error_output.error(f"Unknown command {name!r}.")
            suggestion = self._suggest(name)
            if suggestion:
                self.error_output.muted(f"  Did you mean {suggestion}?")
            self.error_output.muted(f"  Run {self.prog} --help for the list.")
            return 2

        if any(token in ("-h", "--help") for token in rest):
            self.print_command_help(command)
            return 0

        try:
            parsed = parse(command.arguments, rest, command=command.name)
        except UsageError as error:
            return self._report_usage(error, command)

        return command, parsed

    def run(self, argv: Optional[Sequence[str]] = None) -> int:
        """Parse *argv* and run the command it names.

        This is the synchronous entry point, for a console run from a shell. Call :meth:`run_async` instead from inside a running event loop —
        a test, or an application that dispatches a command of its own.

        Only commands that ask for one get a loop: an ``async def handle``
        runs inside ``asyncio.run``, while a plain ``def handle`` — one that
        hands the loop to something else, like ``uvicorn.run`` — runs with no
        loop in this thread at all.

        Args:
            argv: The tokens after the program name. Defaults to
                ``sys.argv[1:]``.

        Returns:
            The exit code. Zero for success, 2 for a usage error, 130 for a
            cancelled prompt, and whatever a failing command asked for.

        Raises:
            RuntimeError: If an event loop is already running in this thread.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "Console.run() cannot be called while an event loop is running. "
                "Use `await console.run_async(argv)` instead."
            )

        prepared = self._prepare(argv)
        if isinstance(prepared, int):
            return prepared
        command, parsed = prepared

        if self._owns_loop(command):
            return self._guard(command, lambda: self._dispatch_sync(command, parsed))
        return self._guard(
            command, lambda: asyncio.run(self._dispatch(command, parsed))
        )

    async def run_async(self, argv: Optional[Sequence[str]] = None) -> int:
        """Parse *argv* and run the command it names, on the current loop.

        Args:
            argv: The tokens after the program name. Defaults to
                ``sys.argv[1:]``.

        Returns:
            The exit code.
        """
        prepared = self._prepare(argv)
        if isinstance(prepared, int):
            return prepared
        command, parsed = prepared

        try:
            return await self._dispatch(command, parsed)
        except UsageError as error:
            return self._report_usage(error, command)
        except Abort:
            self.error_output.blank()
            self.error_output.muted("Cancelled.")
            return Abort.exit_code
        except KeyboardInterrupt:
            self.error_output.blank()
            self.error_output.muted("Cancelled.")
            return Abort.exit_code
        except CommandError as error:
            self.error_output.error(str(error))
            return error.exit_code
        except ConsoleError as error:
            self.error_output.error(str(error))
            return 1

    def _report_usage(self, error: UsageError, command: Type[Command]) -> int:
        """Write a usage error and the line that would have been correct.

        Args:
            error: What went wrong.
            command: The command being invoked.

        Returns:
            The exit code.
        """
        self.error_output.error(str(error))
        self.error_output.muted(f"  Usage: {self._usage_for(command)}")
        self.error_output.muted(f"  Run {self.prog} {command.name} --help")
        return error.exit_code

    def main(self, argv: Optional[Sequence[str]] = None) -> None:
        """Run and exit.

        Args:
            argv: The tokens after the program name.

        Raises:
            SystemExit: Always, with the command's exit code.
        """
        raise SystemExit(self.run(argv))
