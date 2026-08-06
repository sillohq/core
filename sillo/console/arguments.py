"""
sillo.console.arguments — what a command accepts, declared and then parsed.

A command lists its parameters explicitly::

    arguments = [
        Argument("email", help="Address to create the account under"),
        Option("limit", type=int, default=50, help="How many to show"),
        Flag("staff", help="Only administrators"),
    ]

The three kinds map onto the three shapes a command line has. An
:class:`Argument` is positional. An :class:`Option` takes a value. A
:class:`Flag` is on or off and never consumes the token after it.

Parsing is done here rather than by ``argparse`` because the console owns its
own help rendering and error wording, and because ``argparse`` calls
``sys.exit`` on a bad argument, which a test cannot catch cleanly and an
embedding application should not have happen underneath it.
"""

from __future__ import annotations

from typing import Any, Callable, ClassVar, Dict, List, Optional, Sequence, Tuple

from .exceptions import UsageError

__all__ = ["Argument", "Flag", "Option", "Parameter", "ParsedInput", "parse"]


class _Unset:
    """The absence of a default.

    ``None`` cannot mean "no default was given", because ``None`` is a
    perfectly good default for an optional argument. Distinguishing the two is
    what makes ``Argument("name")`` required and ``Argument("name",
    default=None)`` optional.
    """

    def __repr__(self) -> str:
        return "<unset>"


UNSET = _Unset()


def _normalise(name: str) -> str:
    """Return the lookup key for *name*.

    ``--dry-run`` and ``dry_run`` name the same parameter. Lookups go through
    this so a command can use whichever spelling reads better at the call site.

    Args:
        name: The parameter name in either spelling.

    Returns:
        The name with dashes replaced by underscores.
    """
    return name.replace("-", "_")


class Parameter:
    """Base class for the three parameter kinds.

    Attributes:
        kind: What an accessor has to ask for to read this parameter. Carried
            on the class rather than derived from ``type(parameter)`` so that a
            subclass of ``Option`` still reads as an option.

    Args:
        name: The parameter name. Dashes are permitted and are what appears on
            the command line; lookups accept either spelling.
        help: One line describing it, shown in the command's help.
        default: The value when the parameter is absent.
        type: A callable converting the raw string. Anything that raises
            ``ValueError`` or ``TypeError`` on bad input works, which includes
            ``int``, ``float`` and ``pathlib.Path``.
        choices: The permitted values, checked after conversion.
        metavar: What to call the value in the help output.
    """

    takes_value: ClassVar[bool] = True
    kind: ClassVar[str] = "parameter"

    def __init__(
        self,
        name: str,
        help: str = "",
        default: Any = UNSET,
        type: Optional[Callable[[str], Any]] = None,
        choices: Optional[Sequence[Any]] = None,
        metavar: Optional[str] = None,
    ) -> None:
        if not name:
            raise ValueError("a parameter needs a name")

        self.name = name
        self.key = _normalise(name)
        self.help = help
        self.has_default = default is not UNSET
        self.default = None if default is UNSET else default
        self.type = type
        self.choices = list(choices) if choices is not None else None
        self.metavar = metavar or name.upper().replace("-", "_")

    def convert(self, raw: str) -> Any:
        """Convert and validate one raw value.

        Args:
            raw: The token as it arrived from the command line.

        Returns:
            The converted value.

        Raises:
            UsageError: If conversion fails or the value is not a valid choice.
        """
        value: Any = raw
        if self.type is not None:
            try:
                value = self.type(raw)
            except (ValueError, TypeError):
                expected = getattr(self.type, "__name__", str(self.type))
                raise UsageError(f"{self.name}: {raw!r} is not a valid {expected}")

        if self.choices is not None and value not in self.choices:
            allowed = ", ".join(str(choice) for choice in self.choices)
            raise UsageError(f"{self.name}: {raw!r} is not one of {allowed}")

        return value

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"


class Argument(Parameter):
    """A positional parameter.

    An argument is required unless it is given a default. A variadic argument
    collects every remaining positional token into a list and must be declared
    last.

    Args:
        name: The parameter name.
        help: One line describing it.
        default: The value when it is absent. Supplying one makes the argument
            optional.
        type: A callable converting each raw string.
        choices: The permitted values.
        metavar: What to call the value in the help output.
        variadic: Collect all remaining positionals into a list.
    """

    kind: ClassVar[str] = "argument"

    def __init__(
        self,
        name: str,
        help: str = "",
        default: Any = UNSET,
        type: Optional[Callable[[str], Any]] = None,
        choices: Optional[Sequence[Any]] = None,
        metavar: Optional[str] = None,
        variadic: bool = False,
    ) -> None:
        super().__init__(name, help, default, type, choices, metavar)
        self.variadic = variadic

    @property
    def required(self) -> bool:
        """Whether the argument has to be supplied.

        Returns:
            True when no default was given. A variadic argument is never
            required; absent, it is an empty list.
        """
        return not self.has_default and not self.variadic

    def usage(self) -> str:
        """Return how this argument appears in a usage line.

        Returns:
            The placeholder, bracketed when optional and suffixed when variadic.
        """
        body = f"{self.metavar}..." if self.variadic else self.metavar
        return f"<{body}>" if self.required else f"[{body}]"


class Option(Parameter):
    """A named parameter that takes a value.

    Args:
        name: The parameter name, used as ``--name``.
        help: One line describing it.
        default: The value when it is absent.
        type: A callable converting each raw string.
        choices: The permitted values.
        metavar: What to call the value in the help output.
        short: A single-character alias, used as ``-n``.
        multiple: Allow repetition, collecting the values into a list.
        required: Fail when the option is absent.
    """

    kind: ClassVar[str] = "option"

    def __init__(
        self,
        name: str,
        help: str = "",
        default: Any = UNSET,
        type: Optional[Callable[[str], Any]] = None,
        choices: Optional[Sequence[Any]] = None,
        metavar: Optional[str] = None,
        short: Optional[str] = None,
        multiple: bool = False,
        required: bool = False,
    ) -> None:
        super().__init__(name, help, default, type, choices, metavar)
        if short is not None and len(short) != 1:
            raise ValueError(f"short name for {name!r} must be one character")
        self.short = short
        self.multiple = multiple
        self.required = required
        if multiple and not self.has_default:
            self.default = []

    def usage(self) -> str:
        """Return how this option appears in a usage line.

        Returns:
            The flag and its placeholder.
        """
        return f"--{self.name} <{self.metavar}>"


class Flag(Parameter):
    """A named parameter that is either on or off.

    A flag defaults to off and is turned on by ``--name``. Give it
    ``default=True`` and it is turned off by ``--no-name`` instead.

    Args:
        name: The parameter name, used as ``--name``.
        help: One line describing it.
        default: Whether it starts on.
        short: A single-character alias, used as ``-n``.
    """

    takes_value: ClassVar[bool] = False
    kind: ClassVar[str] = "flag"

    def __init__(
        self,
        name: str,
        help: str = "",
        default: bool = False,
        short: Optional[str] = None,
    ) -> None:
        super().__init__(name, help, bool(default))
        if short is not None and len(short) != 1:
            raise ValueError(f"short name for {name!r} must be one character")
        self.short = short

    @property
    def negative(self) -> str:
        """The spelling that turns the flag off.

        Returns:
            The ``--no-`` form of the name.
        """
        return f"no-{self.name}"

    def usage(self) -> str:
        """Return how this flag appears in a usage line.

        Returns:
            The flag, in whichever direction changes the default.
        """
        return f"--{self.negative}" if self.default else f"--{self.name}"


class ParsedInput:
    """The values a command was invoked with.

    Args:
        values: Every parameter's resolved value, keyed by normalised name.
        kinds: The parameter kind each name was declared as, so an accessor can
            reject a lookup that names the wrong one.
        extra: Positional tokens after ``--``.
    """

    def __init__(
        self,
        values: Dict[str, Any],
        kinds: Dict[str, str],
        extra: Optional[List[str]] = None,
    ) -> None:
        self.values = values
        self.kinds = kinds
        self.extra = extra or []

    def get(self, name: str, expected: Optional[str] = None) -> Any:
        """Return the value of *name*.

        Args:
            name: The parameter name, in either spelling.
            expected: The kind the caller expects. When given and the parameter
                was declared as something else, the mismatch is reported rather
                than silently returning a value of the wrong shape.

        Returns:
            The resolved value.

        Raises:
            KeyError: If no such parameter was declared, or it was declared as
                a different kind than *expected*.
        """
        key = _normalise(name)
        if key not in self.values:
            raise KeyError(f"no parameter named {name!r} was declared")

        if expected is not None and self.kinds[key] != expected:
            raise KeyError(
                f"{name!r} is declared as {self.kinds[key]}, not {expected}; "
                f"read it with .{self.kinds[key]}({name!r})"
            )

        return self.values[key]

    def __contains__(self, name: str) -> bool:
        return _normalise(name) in self.values

    def __repr__(self) -> str:
        return f"ParsedInput({self.values!r})"


def _index(
    parameters: Sequence[Parameter],
) -> Tuple[List[Argument], Dict[str, Parameter], Dict[str, Parameter]]:
    """Split declared parameters into the lookups the parser needs.

    Args:
        parameters: The command's declared parameters.

    Returns:
        The positionals in order, the long-name lookup, and the short-name
        lookup.

    Raises:
        ValueError: If a name or short alias is used twice, or a variadic
            argument is not last.
    """
    positionals: List[Argument] = []
    long_names: Dict[str, Parameter] = {}
    short_names: Dict[str, Parameter] = {}

    for parameter in parameters:
        if isinstance(parameter, Argument):
            if positionals and positionals[-1].variadic:
                raise ValueError(
                    f"{positionals[-1].name!r} is variadic, so it must be the "
                    f"last argument; {parameter.name!r} follows it"
                )
            positionals.append(parameter)
            continue

        if parameter.name in long_names:
            raise ValueError(f"{parameter.name!r} is declared twice")
        long_names[parameter.name] = parameter

        if isinstance(parameter, Flag):
            long_names[parameter.negative] = parameter

        short = getattr(parameter, "short", None)
        if short:
            if short in short_names:
                raise ValueError(f"-{short} is declared twice")
            short_names[short] = parameter

    return positionals, long_names, short_names


def _seed(parameters: Sequence[Parameter]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Build the starting values and the kind lookup.

    Args:
        parameters: The command's declared parameters.

    Returns:
        Defaults keyed by normalised name, and each name's kind.
    """
    values: Dict[str, Any] = {}
    kinds: Dict[str, str] = {}

    for parameter in parameters:
        kinds[parameter.key] = parameter.kind
        collects = (isinstance(parameter, Argument) and parameter.variadic) or (
            isinstance(parameter, Option) and parameter.multiple
        )
        if collects:
            # A fresh list per parse, so a default never accumulates values
            # across two invocations of the same declaration.
            values[parameter.key] = list(parameter.default or [])
        else:
            values[parameter.key] = parameter.default

    return values, kinds


def _store(values: Dict[str, Any], parameter: Parameter, value: Any) -> None:
    """Record one parsed value, appending when the parameter repeats.

    Args:
        values: The value map being built.
        parameter: The parameter the value belongs to.
        value: The converted value.
    """
    if isinstance(parameter, Option) and parameter.multiple:
        values[parameter.key].append(value)
    else:
        values[parameter.key] = value


def parse(
    parameters: Sequence[Parameter],
    argv: Sequence[str],
    command: Optional[str] = None,
) -> ParsedInput:
    """Parse *argv* against the declared *parameters*.

    Recognises ``--name value``, ``--name=value``, ``-n value``, ``-nvalue``,
    bundled short flags such as ``-abc``, and ``--`` to stop option parsing.

    Args:
        parameters: What the command accepts.
        argv: The tokens after the command name.
        command: The command name, used in error messages.

    Returns:
        The resolved values.

    Raises:
        UsageError: If a token is unrecognised, a value is missing or invalid,
            or a required parameter was not supplied.
    """
    positionals, long_names, short_names = _index(parameters)
    values, kinds = _seed(parameters)

    seen: set = set()
    waiting: List[str] = []
    extra: List[str] = []
    tokens = list(argv)
    index = 0

    def fail(message: str) -> UsageError:
        return UsageError(message, command=command)

    def consume_value(parameter: Parameter, inline: Optional[str], token: str) -> None:
        """Take a value for *parameter*, from *inline* or the next token."""
        nonlocal index
        if inline is not None:
            raw = inline
        else:
            if index >= len(tokens):
                raise fail(f"{token} needs a value")
            raw = tokens[index]
            index += 1
        _store(values, parameter, parameter.convert(raw))
        seen.add(parameter.key)

    while index < len(tokens):
        token = tokens[index]
        index += 1

        if token == "--":
            extra.extend(tokens[index:])
            break

        if token.startswith("--") and len(token) > 2:
            body = token[2:]
            inline: Optional[str] = None
            if "=" in body:
                body, inline = body.split("=", 1)

            parameter = long_names.get(body)
            if parameter is None:
                raise fail(f"unknown option --{body}")

            if isinstance(parameter, Flag):
                if inline is not None:
                    raise fail(f"--{body} is a flag and takes no value")
                values[parameter.key] = body != parameter.negative
                seen.add(parameter.key)
            else:
                consume_value(parameter, inline, f"--{body}")
            continue

        if token.startswith("-") and len(token) > 1 and token != "-":
            letters = token[1:]
            position = 0
            while position < len(letters):
                letter = letters[position]
                parameter = short_names.get(letter)
                if parameter is None:
                    raise fail(f"unknown option -{letter}")

                if isinstance(parameter, Flag):
                    values[parameter.key] = True
                    seen.add(parameter.key)
                    position += 1
                    continue

                # Everything left in the cluster is this option's value, which
                # is what makes -n5 work; an empty remainder falls through to
                # the next token.
                remainder = letters[position + 1 :]
                consume_value(parameter, remainder or None, f"-{letter}")
                break
            continue

        waiting.append(token)

    # Positionals, in declaration order, with the variadic one taking the rest.
    for offset, argument in enumerate(positionals):
        if argument.variadic:
            values[argument.key] = [
                argument.convert(token) for token in waiting[offset:]
            ]
            waiting = waiting[:offset]
            break

        if offset < len(waiting):
            values[argument.key] = argument.convert(waiting[offset])
            seen.add(argument.key)
        elif argument.required:
            raise fail(f"missing argument <{argument.metavar}>")
    else:
        surplus = waiting[len(positionals) :]
        if surplus:
            raise fail(f"unexpected argument {surplus[0]!r}")

    for parameter in parameters:
        # A required Argument has already been reported by the positional loop
        # above, so only options are left to check here.
        if isinstance(parameter, Option) and parameter.required:
            if parameter.key not in seen:
                raise fail(f"missing required option --{parameter.name}")

    return ParsedInput(values, kinds, extra)
