"""
sillo.console.prompt — asking the user something.

Six prompts: free text, a hidden secret, yes or no, one choice from a list,
several choices from a list, and a value constrained by a validator. The list
prompts take over the terminal and redraw as the arrow keys move, which is why
they live behind the interactivity check in
:func:`sillo.console.terminal.is_interactive`.

A prompt that cannot be shown falls back to its default. A prompt that cannot be
shown *and* has no default raises, because guessing on the user's behalf is how
a scripted invocation ends up creating the wrong account. Pass ``default=`` to
every prompt a command might hit in CI, and the same command works in both.
"""

from __future__ import annotations

import sys
from typing import (
    IO,
    Any,
    Callable,
    List,
    Optional,
    Sequence,
    TextIO,
    Tuple,
    Union,
    cast,
)

from .exceptions import Abort, UsageError
from .output import Output, _clear_lines
from .style import DANGER, MUTED, PRIMARY, SUCCESS, Style
from .terminal import (
    Key,
    cursor_hide,
    cursor_show,
    is_interactive,
    raw_mode,
    read_key,
)

__all__ = ["Prompt"]


Choice = Union[str, Tuple[Any, str]]
Validator = Callable[[str], Any]


def _split(option: Choice) -> Tuple[Any, str]:
    """Split a choice into its value and its label.

    Args:
        option: Either a string used as both, or a ``(value, label)`` pair.

    Returns:
        The value and the label.
    """
    if isinstance(option, tuple):
        return option[0], str(option[1])
    return option, str(option)


class Prompt:
    """Asks questions on one pair of streams.

    Args:
        output: Where questions are drawn.
        input_stream: Where answers are read. Defaults to stdin.
        interactive: Force interactivity on or off. When None the streams are
            inspected. Setting it False makes every prompt take its default,
            which is what a test wants.
    """

    def __init__(
        self,
        output: Output,
        input_stream: Optional[IO[str]] = None,
        interactive: Optional[bool] = None,
    ) -> None:
        self.output = output
        self.input_stream = input_stream if input_stream is not None else sys.stdin
        if interactive is None:
            interactive = is_interactive(self.input_stream, output.stream)
        self.interactive = interactive

    # -- helpers -------------------------------------------------------

    def _marker(self) -> str:
        """Return the styled question marker.

        Returns:
            The glyph that opens every question.
        """
        return self.output.paint("?", PRIMARY)

    def _fallback(self, question: str, default: Any) -> Any:
        """Return *default* for a prompt that cannot be shown.

        Args:
            question: The question, for the error message.
            default: The value to use.

        Returns:
            The default.

        Raises:
            UsageError: If there is no default to fall back to.
        """
        if default is None:
            raise UsageError(
                f"{question!r} needs an answer, but the terminal is not "
                f"interactive. Supply it as an argument, or give the prompt a "
                f"default."
            )
        return default

    def _read_line(self, prompt: str) -> str:
        """Read one line of input.

        Uses ``input`` on a real stdin so the user gets line editing and
        history from readline, and a plain read otherwise so tests can drive it
        from a StringIO.

        Args:
            prompt: The text shown before the cursor.

        Returns:
            The line, without its newline.

        Raises:
            Abort: If the user interrupted or the input ended.
        """
        try:
            if self.input_stream is sys.stdin:
                return input(prompt)
            self.output.write(prompt)
            line = self.input_stream.readline()
            if not line:
                raise EOFError
            return line.rstrip("\n")
        except (KeyboardInterrupt, EOFError):
            self.output.blank()
            raise Abort("cancelled")

    def _validate(self, value: str, validate: Optional[Validator]) -> Any:
        """Run *validate* over *value*.

        A validator checks; it does not transform. Return None or True to
        accept, return a string or False to reject, or raise ``ValueError``.

        Returning the value itself would be the obvious way to express a
        replacement, and it is deliberately not supported: a validator like
        ``lambda value: value.lower()`` returns a string, and a string is how a
        rejection carries its message. One of the two meanings has to win, and
        silently treating a normalised answer as an error message is the worse
        failure. Normalise the answer after :meth:`ask` returns it.

        Args:
            value: The raw input.
            validate: The validator, if any.

        Returns:
            The value, unchanged.

        Raises:
            ValueError: If the validator rejected the input.
        """
        if validate is None:
            return value

        result = validate(value)
        if isinstance(result, str):
            raise ValueError(result)
        if result is False:
            raise ValueError("that is not a valid answer")
        return value

    # -- text ----------------------------------------------------------

    def ask(
        self,
        question: str,
        default: Optional[str] = None,
        validate: Optional[Validator] = None,
    ) -> Any:
        """Ask for a line of text.

        Args:
            question: What to ask.
            default: Returned when the user presses Enter on an empty line.
            validate: Called with the answer. Return a string or False to
                reject it, or raise ``ValueError``. It checks rather than
                transforms; see :meth:`_validate`.

        Returns:
            The answer.

        Raises:
            Abort: If the user cancelled.
            UsageError: If the terminal is not interactive and there is no
                default.
        """
        if not self.interactive:
            return self._fallback(question, default)

        hint = self.output.paint(f" ({default})", MUTED) if default else ""
        prompt = f"{self._marker()} {question}{hint} {self.output.paint('›', PRIMARY)} "

        while True:
            answer = self._read_line(prompt).strip()
            if not answer:
                if default is not None:
                    return default
                self.output.error("An answer is required.")
                continue
            try:
                return self._validate(answer, validate)
            except ValueError as error:
                self.output.error(str(error))

    def secret(
        self,
        question: str = "Password",
        confirm: bool = False,
        validate: Optional[Validator] = None,
    ) -> str:
        """Ask for a value without echoing it.

        Args:
            question: What to ask.
            confirm: Ask a second time and require the two to match.
            validate: Called with the answer.

        Returns:
            The answer.

        Raises:
            Abort: If the user cancelled.
            UsageError: If the terminal is not interactive.
        """
        if not self.interactive:
            raise UsageError(
                f"{question!r} cannot be read from a non-interactive terminal. "
                f"Supply it through the environment instead."
            )

        import getpass

        prompt = f"{self._marker()} {question} {self.output.paint('›', PRIMARY)} "

        while True:
            try:
                answer = getpass.getpass(
                    prompt, stream=cast(TextIO, self.output.stream)
                )
            except (KeyboardInterrupt, EOFError):
                self.output.blank()
                raise Abort("cancelled")

            if not answer:
                self.output.error("An answer is required.")
                continue

            try:
                answer = self._validate(answer, validate)
            except ValueError as error:
                self.output.error(str(error))
                continue

            if not confirm:
                return answer

            try:
                again = getpass.getpass(
                    f"{self._marker()} Confirm {self.output.paint('›', PRIMARY)} ",
                    stream=cast(TextIO, self.output.stream),
                )
            except (KeyboardInterrupt, EOFError):
                self.output.blank()
                raise Abort("cancelled")

            if again == answer:
                return answer
            self.output.error("They do not match.")

    def confirm(self, question: str, default: bool = False) -> bool:
        """Ask a yes or no question.

        Args:
            question: What to ask.
            default: The answer when the user presses Enter.

        Returns:
            The answer.

        Raises:
            Abort: If the user cancelled.
        """
        if not self.interactive:
            return default

        hint = "Y/n" if default else "y/N"
        prompt = (
            f"{self._marker()} {question} {self.output.paint(f'[{hint}]', MUTED)} "
            f"{self.output.paint('›', PRIMARY)} "
        )

        while True:
            answer = self._read_line(prompt).strip().lower()
            if not answer:
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            self.output.error("Answer y or n.")

    # -- lists ---------------------------------------------------------

    def _render_choices(
        self,
        question: str,
        options: Sequence[Tuple[Any, str]],
        cursor: int,
        selected: Optional[set] = None,
        filter_text: str = "",
        window: int = 10,
    ) -> int:
        """Draw the menu and return how many lines were written.

        Only *window* options are drawn at once, scrolled to keep the cursor
        visible, so a hundred-item list does not clear the scrollback.

        Args:
            question: The question, drawn above the list.
            options: The value/label pairs to show.
            cursor: Index of the highlighted option.
            selected: Indices that are ticked, for a multiple-choice prompt.
            filter_text: The current search text.
            window: How many options to show at once.

        Returns:
            The number of lines drawn.
        """
        glyphs = self.output.glyphs
        suffix = self.output.paint(f" {filter_text}", PRIMARY) if filter_text else ""
        self.output.write(self._marker(), " ", question, suffix, "\n")
        lines = 1

        start = 0
        if len(options) > window:
            start = max(0, min(cursor - window // 2, len(options) - window))
        visible = list(enumerate(options))[start : start + window]

        for index, (_, label) in visible:
            active = index == cursor
            if selected is None:
                marker = glyphs["bullet"] if active else " "
            else:
                marker = glyphs["tick"] if index in selected else " "

            style: Optional[Style] = None
            if active:
                style = PRIMARY
            elif selected is not None and index in selected:
                style = SUCCESS

            pointer = self.output.paint("›" if active else " ", PRIMARY)
            body = self.output.paint(f"{marker} {label}", style)
            self.output.write(f"{pointer} {body}\n")
            lines += 1

        if start + window < len(options):
            remaining = len(options) - start - window
            self.output.line(f"  … {remaining} more", MUTED)
            lines += 1

        return lines

    def _drive(
        self,
        question: str,
        options: Sequence[Tuple[Any, str]],
        cursor: int,
        selected: Optional[set],
        searchable: bool,
    ) -> Tuple[int, Optional[set]]:
        """Run the key loop for a list prompt.

        Args:
            question: The question, redrawn on each frame.
            options: The value/label pairs.
            cursor: Where the highlight starts.
            selected: Ticked indices for a multiple-choice prompt, or None for
                a single-choice one.
            searchable: Whether typing filters the list.

        Returns:
            The final cursor position and selection.

        Raises:
            Abort: If the user cancelled.
        """
        filter_text = ""
        matches = list(range(len(options)))
        drawn = 0

        # The menu redraws on every keypress, and a visible cursor parked at
        # the end of the last drawn row flickers through all of it. Restored in
        # the finally so an abort does not leave the terminal without one.
        self.output.write(cursor_hide)
        try:
            return self._loop(question, options, cursor, selected, searchable)
        finally:
            self.output.write(cursor_show)

    def _loop(
        self,
        question: str,
        options: Sequence[Tuple[Any, str]],
        cursor: int,
        selected: Optional[set],
        searchable: bool,
    ) -> Tuple[int, Optional[set]]:
        """Read keys and redraw until the user accepts or cancels.

        Args:
            question: The question, redrawn on each frame.
            options: The value/label pairs.
            cursor: Where the highlight starts.
            selected: Ticked indices, or None for a single-choice prompt.
            searchable: Whether typing filters the list.

        Returns:
            The final cursor position and selection.

        Raises:
            Abort: If the user cancelled.
        """
        filter_text = ""
        matches = list(range(len(options)))
        drawn = 0

        with raw_mode(self.input_stream):
            while True:
                shown = [options[index] for index in matches]
                position = matches.index(cursor) if cursor in matches else 0
                marks = (
                    {matches.index(i) for i in selected if i in matches}
                    if selected is not None
                    else None
                )

                _clear_lines(self.output, drawn)
                drawn = self._render_choices(
                    question, shown, position, marks, filter_text
                )

                key = read_key(self.input_stream)

                if key == Key.INTERRUPT or key == Key.ESCAPE:
                    _clear_lines(self.output, drawn)
                    raise Abort("cancelled")

                if key == Key.ENTER:
                    _clear_lines(self.output, drawn)
                    return cursor, selected

                if key == Key.UP and shown:
                    position = (position - 1) % len(shown)
                    cursor = matches[position]
                elif key == Key.DOWN and shown:
                    position = (position + 1) % len(shown)
                    cursor = matches[position]
                elif key == Key.SPACE and selected is not None:
                    selected.symmetric_difference_update({cursor})
                elif searchable and key == Key.BACKSPACE:
                    filter_text = filter_text[:-1]
                elif searchable and len(key) == 1 and key.isprintable():
                    filter_text += key

                if searchable:
                    needle = filter_text.lower()
                    matches = [
                        index
                        for index, (_, label) in enumerate(options)
                        if needle in label.lower()
                    ]
                    if cursor not in matches and matches:
                        cursor = matches[0]

    def choice(
        self,
        question: str,
        options: Sequence[Choice],
        default: Any = None,
        search: Optional[bool] = None,
    ) -> Any:
        """Ask the user to pick one option.

        Args:
            question: What to ask.
            options: The options, each a string or a ``(value, label)`` pair.
            default: The value selected when the prompt opens, and the answer
                when the terminal is not interactive.
            search: Whether typing filters the list. Defaults to on once there
                are more than eight options.

        Returns:
            The chosen value.

        Raises:
            Abort: If the user cancelled.
            ValueError: If *options* is empty.
            UsageError: If the terminal is not interactive and there is no
                default.
        """
        if not options:
            raise ValueError("choice() needs at least one option")

        pairs = [_split(option) for option in options]
        values = [value for value, _ in pairs]

        if not self.interactive:
            return self._fallback(question, default)

        cursor = values.index(default) if default in values else 0
        searchable = len(pairs) > 8 if search is None else search

        cursor, _ = self._drive(question, pairs, cursor, None, searchable)
        value, label = pairs[cursor]
        self.output.write(
            self.output.paint(self.output.glyphs["tick"], SUCCESS),
            f" {question} ",
            self.output.paint(label, MUTED),
            "\n",
        )
        return value

    def multichoice(
        self,
        question: str,
        options: Sequence[Choice],
        defaults: Optional[Sequence[Any]] = None,
        minimum: int = 0,
    ) -> List[Any]:
        """Ask the user to pick any number of options.

        Space toggles the highlighted option, Enter accepts the selection.

        Args:
            question: What to ask.
            options: The options, each a string or a ``(value, label)`` pair.
            defaults: Values ticked when the prompt opens, and the answer when
                the terminal is not interactive.
            minimum: Reject an answer with fewer than this many selections.

        Returns:
            The chosen values, in declaration order.

        Raises:
            Abort: If the user cancelled.
            ValueError: If *options* is empty.
        """
        if not options:
            raise ValueError("multichoice() needs at least one option")

        pairs = [_split(option) for option in options]
        values = [value for value, _ in pairs]
        chosen = {values.index(value) for value in (defaults or []) if value in values}

        if not self.interactive:
            return [values[index] for index in sorted(chosen)]

        while True:
            _, selected = self._drive(question, pairs, 0, set(chosen), False)
            chosen = selected or set()
            if len(chosen) >= minimum:
                break
            self.output.error(f"Choose at least {minimum}.")

        picked = [values[index] for index in sorted(chosen)]
        labels = ", ".join(pairs[index][1] for index in sorted(chosen)) or "nothing"
        self.output.write(
            self.output.paint(self.output.glyphs["tick"], SUCCESS),
            f" {question} ",
            self.output.paint(labels, MUTED),
            "\n",
        )
        return picked

    def confirm_destructive(self, question: str, phrase: str) -> bool:
        """Require the user to type *phrase* before continuing.

        For the operations where a mistyped ``y`` is expensive — dropping a
        database, rolling back to zero — so that muscle memory cannot approve
        them.

        Args:
            question: What is about to happen.
            phrase: What the user has to type back.

        Returns:
            True when the phrase matched.

        Raises:
            Abort: If the user cancelled.
        """
        if not self.interactive:
            return False

        self.output.line(question, DANGER)
        typed = self.ask(f"Type {phrase!r} to continue", default="")
        return typed == phrase
