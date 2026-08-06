"""
sillo.console.output — drawing to the terminal.

Everything here degrades. A table drawn into a pipe loses its borders but keeps
its columns, a progress bar that cannot redraw prints its milestones on separate
lines, and a spinner that cannot animate prints its label once. Commands are
written the same way in both cases; the decision happens here.

Widths are measured with escape sequences stripped, so a styled cell lines up
with an unstyled one.
"""

from __future__ import annotations

import itertools
import threading
import time
from contextlib import contextmanager
from typing import IO, Any, Iterator, Optional, Sequence

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
    cursor_hide,
    cursor_show,
    cursor_up,
    erase_line,
    supports_unicode,
    terminal_width,
)

__all__ = ["Output", "ProgressBar", "Spinner"]


_BORDERS = {
    True: {
        "horizontal": "─",
        "vertical": "│",
        "top_left": "╭",
        "top_right": "╮",
        "bottom_left": "╰",
        "bottom_right": "╯",
        "bullet": "•",
        "tick": "✓",
        "cross": "✗",
        "bar_full": "█",
        "bar_empty": "░",
        "frames": "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏",
    },
    False: {
        "horizontal": "-",
        "vertical": "|",
        "top_left": "+",
        "top_right": "+",
        "bottom_left": "+",
        "bottom_right": "+",
        "bullet": "*",
        "tick": "v",
        "cross": "x",
        "bar_full": "#",
        "bar_empty": ".",
        "frames": "|/-\\",
    },
}


def _pad(text: str, width: int, align: str = "left") -> str:
    """Pad *text* to *width*, measuring its printable length.

    Args:
        text: Possibly styled text.
        width: The column width to fill.
        align: One of ``left``, ``right`` or ``center``.

    Returns:
        The padded text.
    """
    padding = max(0, width - len(strip_ansi(text)))
    if align == "right":
        return " " * padding + text
    if align == "center":
        left = padding // 2
        return " " * left + text + " " * (padding - left)
    return text + " " * padding


def _truncate(text: str, width: int) -> str:
    """Shorten *text* to *width*, appending an ellipsis when it does not fit.

    Styled text is returned unchanged: cutting it would leave a dangling escape
    sequence that bleeds colour into the rest of the line.

    Args:
        text: The text to shorten.
        width: The maximum printable length.

    Returns:
        The text, shortened if it was too long.
    """
    if len(strip_ansi(text)) <= width or len(text) != len(strip_ansi(text)):
        return text
    return text[: max(1, width - 1)] + "…" if width > 1 else text[:width]


class Output:
    """Writes to one stream, in colour when the stream can take it.

    Args:
        stream: Where to write.
        palette: How to render styles. One is built for the stream when omitted.
        unicode: Force the box-drawing character set on or off. When None the
            stream's encoding is inspected.
    """

    def __init__(
        self,
        stream: IO[str],
        palette: Optional[Palette] = None,
        unicode: Optional[bool] = None,
    ) -> None:
        self.stream = stream
        self.palette = palette if palette is not None else Palette(stream)
        self.unicode = supports_unicode(stream) if unicode is None else unicode
        self.glyphs = _BORDERS[self.unicode]

    # -- primitives ----------------------------------------------------

    def paint(self, text: str, style: Optional[Style] = None) -> str:
        """Style *text* without writing it.

        Args:
            text: The text to style.
            style: The style to apply.

        Returns:
            The styled text.
        """
        return self.palette.render(text, style)

    def write(self, *parts: Any) -> None:
        """Write *parts* with no trailing newline.

        Args:
            *parts: Values to concatenate, stringified.
        """
        self.stream.write("".join(str(part) for part in parts))
        self.stream.flush()

    def line(self, text: str = "", style: Optional[Style] = None) -> None:
        """Write one line.

        Args:
            text: The text to write.
            style: The style to apply.
        """
        self.write(self.paint(text, style), "\n")

    def blank(self, count: int = 1) -> None:
        """Write *count* empty lines.

        Args:
            count: How many.
        """
        self.write("\n" * count)

    # -- levels --------------------------------------------------------

    def info(self, text: str) -> None:
        """Write an informational line.

        Args:
            text: The message.
        """
        self.line(text, INFO)

    def success(self, text: str) -> None:
        """Write a line marking something as done.

        Args:
            text: The message.
        """
        self.line(f"{self.glyphs['tick']} {text}", SUCCESS)

    def warn(self, text: str) -> None:
        """Write a warning.

        Args:
            text: The message.
        """
        self.line(f"! {text}", WARNING)

    def error(self, text: str) -> None:
        """Write an error.

        Args:
            text: The message.
        """
        self.line(f"{self.glyphs['cross']} {text}", DANGER)

    def muted(self, text: str) -> None:
        """Write a line of secondary detail.

        Args:
            text: The message.
        """
        self.line(text, MUTED)

    def heading(self, text: str) -> None:
        """Write a section heading, preceded by a blank line.

        Args:
            text: The heading.
        """
        self.blank()
        self.line(text, HEADING)

    # -- structures ----------------------------------------------------

    def rule(self, label: str = "") -> None:
        """Draw a horizontal rule, optionally labelled.

        Args:
            label: Text to set into the rule.
        """
        width = terminal_width()
        horizontal = self.glyphs["horizontal"]

        if not label:
            self.line(self.paint(horizontal * width, MUTED))
            return

        left = 3
        right = max(0, width - left - len(strip_ansi(label)) - 2)
        self.write(
            self.paint(horizontal * left, MUTED),
            " ",
            self.paint(label, PRIMARY),
            " ",
            self.paint(horizontal * right, MUTED),
            "\n",
        )

    def bullet(self, text: str, indent: int = 2) -> None:
        """Write a bulleted line.

        Args:
            text: The item.
            indent: Leading spaces.
        """
        marker = self.paint(self.glyphs["bullet"], PRIMARY)
        self.line(f"{' ' * indent}{marker} {text}")

    def pairs(self, items: Sequence[Sequence[Any]], indent: int = 2) -> None:
        """Write aligned label/value pairs.

        Args:
            items: Two-element sequences of label and value.
            indent: Leading spaces.
        """
        rows = [(str(label), str(value)) for label, value in items]
        if not rows:
            return
        width = max(len(strip_ansi(label)) for label, _ in rows)
        for label, value in rows:
            self.write(
                " " * indent,
                self.paint(_pad(label, width), MUTED),
                "  ",
                value,
                "\n",
            )

    def table(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        align: Optional[Sequence[str]] = None,
        indent: int = 1,
    ) -> None:
        """Draw a table.

        Columns are sized to their widest cell and then shrunk proportionally
        if the total would overflow the terminal.

        Args:
            headers: The column headings.
            rows: The body, one sequence per row.
            align: Per-column alignment, each ``left``, ``right`` or ``center``.
            indent: Leading spaces.

        Raises:
            ValueError: If a row has a different length than *headers*.
        """
        body = [[str(cell) for cell in row] for row in rows]
        for number, row in enumerate(body):
            if len(row) != len(headers):
                raise ValueError(
                    f"row {number} has {len(row)} cells but there are "
                    f"{len(headers)} columns"
                )

        alignment = list(align) if align else ["left"] * len(headers)
        widths = [len(strip_ansi(header)) for header in headers]
        for row in body:
            for column, cell in enumerate(row):
                widths[column] = max(widths[column], len(strip_ansi(cell)))

        # Three characters of separator per gap, plus the indent.
        available = terminal_width() - indent - 3 * (len(headers) - 1)
        if sum(widths) > available and widths:
            scale = available / sum(widths)
            widths = [max(3, int(width * scale)) for width in widths]

        horizontal = self.glyphs["horizontal"]
        pad = " " * indent

        self.write(
            pad,
            "   ".join(
                self.paint(_pad(header, width), HEADING)
                for header, width in zip(headers, widths)
            ).rstrip(),
            "\n",
        )
        self.write(
            pad,
            self.paint(
                "   ".join(horizontal * width for width in widths),
                MUTED,
            ),
            "\n",
        )

        for row in body:
            cells = [
                _pad(_truncate(cell, width), width, how)
                for cell, width, how in zip(row, widths, alignment)
            ]
            self.write(pad, "   ".join(cells).rstrip(), "\n")

    def panel(self, body: str, title: str = "", style: Optional[Style] = None) -> None:
        """Draw a bordered box around *body*.

        Args:
            body: The contents. Newlines separate lines.
            title: Text set into the top border.
            style: Style for the border.
        """
        style = style if style is not None else MUTED
        glyphs = self.glyphs
        lines = body.split("\n")
        inner = max(
            [len(strip_ansi(line)) for line in lines] + [len(strip_ansi(title)) + 2]
        )
        inner = min(inner, terminal_width() - 4)

        if title:
            heading = f"{glyphs['horizontal']} {title} "
            filler = glyphs["horizontal"] * max(0, inner + 2 - len(strip_ansi(heading)))
            top = f"{glyphs['top_left']}{heading}{filler}{glyphs['top_right']}"
        else:
            top = (
                f"{glyphs['top_left']}{glyphs['horizontal'] * (inner + 2)}"
                f"{glyphs['top_right']}"
            )

        bottom = (
            f"{glyphs['bottom_left']}{glyphs['horizontal'] * (inner + 2)}"
            f"{glyphs['bottom_right']}"
        )
        vertical = self.paint(glyphs["vertical"], style)

        self.line(self.paint(top, style))
        for line in lines:
            self.write(vertical, " ", _pad(_truncate(line, inner), inner), " ")
            self.write(vertical, "\n")
        self.line(self.paint(bottom, style))

    # -- activity ------------------------------------------------------

    @contextmanager
    def progress(
        self,
        total: int,
        label: str = "",
        width: int = 30,
    ) -> Iterator["ProgressBar"]:
        """Show a progress bar for the duration of the block.

        Args:
            total: The number of steps that count as complete.
            label: Text shown before the bar.
            width: The bar's width in characters.

        Yields:
            The bar, to advance as work completes.
        """
        bar = ProgressBar(self, total=total, label=label, width=width)
        try:
            bar.start()
            yield bar
        finally:
            bar.finish()

    @contextmanager
    def spinner(self, label: str = "Working") -> Iterator["Spinner"]:
        """Show a spinner for the duration of the block.

        Args:
            label: Text shown beside the spinner.

        Yields:
            The spinner, whose label can be changed as work proceeds.
        """
        spinner = Spinner(self, label=label)
        try:
            spinner.start()
            yield spinner
        finally:
            spinner.stop()


class ProgressBar:
    """A single-line progress bar.

    When the stream cannot be redrawn the bar prints a line at each ten per
    cent instead, so a CI log records the progress without 400 frames of it.

    Args:
        output: Where to draw.
        total: The number of steps that count as complete.
        label: Text shown before the bar.
        width: The bar's width in characters.
    """

    def __init__(
        self,
        output: Output,
        total: int,
        label: str = "",
        width: int = 30,
    ) -> None:
        self.output = output
        self.total = max(1, total)
        self.label = label
        self.width = width
        self.current = 0
        self._live = output.palette.enabled
        self._last_milestone = -1

    def start(self) -> None:
        """Draw the bar in its initial state."""
        if self._live:
            self.output.write(cursor_hide)
        self.render()

    def advance(self, step: int = 1) -> None:
        """Move the bar forward.

        Args:
            step: How many units of work completed.
        """
        self.current = min(self.total, self.current + step)
        self.render()

    def set(self, current: int) -> None:
        """Move the bar to an absolute position.

        Args:
            current: The number of units completed so far.
        """
        self.current = max(0, min(self.total, current))
        self.render()

    def render(self) -> None:
        """Draw the bar at its current position."""
        fraction = self.current / self.total
        percent = int(fraction * 100)

        if not self._live:
            milestone = percent // 10
            if milestone > self._last_milestone:
                self._last_milestone = milestone
                label = f"{self.label} " if self.label else ""
                self.output.line(f"{label}{percent}%")
            return

        filled = int(fraction * self.width)
        bar = self.output.glyphs["bar_full"] * filled + self.output.glyphs[
            "bar_empty"
        ] * (self.width - filled)

        self.output.write(
            "\r",
            erase_line,
            f"{self.label} " if self.label else "",
            self.output.paint(bar, PRIMARY),
            self.output.paint(f" {percent:>3}%", MUTED),
        )

    def finish(self) -> None:
        """Complete the bar and restore the cursor."""
        if self._live:
            self.set(self.total)
            self.output.write(cursor_show, "\n")


class Spinner:
    """An animated activity indicator.

    Animation runs on a daemon thread so the caller's work is not interrupted
    by redraws. Where the stream cannot be redrawn the label is printed once and
    no thread is started.

    Args:
        output: Where to draw.
        label: Text shown beside the spinner.
        interval: Seconds between frames.
    """

    def __init__(self, output: Output, label: str = "Working", interval: float = 0.08):
        self.output = output
        self.label = label
        self.interval = interval
        self._live = output.palette.enabled
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _spin(self) -> None:
        """Redraw the spinner until stopped."""
        for frame in itertools.cycle(self.output.glyphs["frames"]):
            if self._stop.is_set():
                return
            self.output.write(
                "\r",
                erase_line,
                self.output.paint(frame, PRIMARY),
                f" {self.label}",
            )
            time.sleep(self.interval)

    def start(self) -> None:
        """Begin animating."""
        if not self._live:
            self.output.muted(f"{self.label}...")
            return
        self.output.write(cursor_hide)
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, text: str = "") -> None:
        """Stop animating and clear the line.

        Args:
            text: A final line to write in place of the spinner.
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

        if self._live:
            self.output.write("\r", erase_line, cursor_show)

        if text:
            self.output.success(text)

    def __enter__(self) -> "Spinner":
        return self

    def __exit__(self, *exception: object) -> None:
        self.stop()


def _clear_lines(output: Output, count: int) -> None:
    """Move up and erase *count* previously drawn lines.

    Used by prompts that redraw a multi-line menu in place.

    Args:
        output: Where the lines were drawn.
        count: How many lines to erase.
    """
    if count <= 0:
        return
    output.write("\r", erase_line)
    for _ in range(count - 1):
        output.write(cursor_up(1), erase_line)
