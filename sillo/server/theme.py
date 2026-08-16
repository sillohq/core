"""The visual vocabulary of the Sillo server.

Everything the server prints — the banner, the log lines, the shutdown card —
draws its colours and glyphs from here, so restyling the server is one file
rather than a search across the package.

Two capabilities decide what is emitted, both detected once at import against
stderr: whether the stream takes colour, and whether it takes Unicode. A log
piped into a file, a CI job, or a Windows console that never learned UTF-8 all
end up with plain ASCII and no escape sequences, and the alignment still holds
because the ASCII glyphs are the same width as the ones they replace.
"""

from __future__ import annotations

import sys

from sillo.console.style import Palette, Style
from sillo.console.terminal import supports_unicode

#: The brand red, shared with the rest of the console layer.
BRAND = Style(fg="#fc0345")

#: Rendered once against stderr, which is where the server logs.
PALETTE = Palette(sys.stderr)
UNICODE = supports_unicode(sys.stderr)

# -- text styles -------------------------------------------------------

DIM = Style(fg="grey")
LABEL = Style(fg="grey")
VALUE = Style(bold=True)
TIMESTAMP = Style(fg="grey")

LEVELS: dict[str, Style] = {
    "ready": Style(fg="green", bold=True),
    "info": Style(fg="cyan"),
    "warn": Style(fg="yellow", bold=True),
    "error": Style(fg="red", bold=True),
    "debug": Style(fg="grey"),
    "reload": BRAND,
    "stop": Style(fg="grey", bold=True),
}

# -- glyphs ------------------------------------------------------------

#: Same printable width in both sets, so columns line up either way.
GLYPHS: dict[str, str] = (
    {"mark": "●", "rail": "│", "arrow": "→", "dot": "·", "bar": "─"}
    if UNICODE
    else {"mark": "*", "rail": "|", "arrow": "->", "dot": "-", "bar": "-"}
)


def paint(text: str, style: Style | None = None) -> str:
    """Style *text* for the server's stream.

    Args:
        text: The text to style.
        style: The style to apply, or ``None`` to leave it bare.

    Returns:
        The text, with escape sequences only if the stream takes them.
    """
    if style is None:
        return text
    return PALETTE.render(text, style)


def status_style(status: int) -> Style:
    """Return the style for an HTTP status code.

    Colour carries the class of the response so a wall of access lines can be
    scanned without reading the numbers: anything not green is worth a look.

    Args:
        status: The HTTP status code.

    Returns:
        The style for that status class.
    """
    if status >= 500:
        return Style(fg="red", bold=True)
    if status >= 400:
        return Style(fg="yellow", bold=True)
    if status >= 300:
        return Style(fg="cyan")
    return Style(fg="green")


def duration_style(milliseconds: float) -> Style:
    """Return the style for a request duration.

    Thresholds are deliberately generous. The point is to make an outlier
    findable in a scrolling log, not to characterise performance — a handler
    doing real work is legitimately slow and should not be painted as a fault.

    Args:
        milliseconds: How long the request took.

    Returns:
        Muted below 100ms, yellow to a second, red beyond it.
    """
    if milliseconds >= 1000:
        return Style(fg="red")
    if milliseconds >= 100:
        return Style(fg="yellow")
    return DIM


def format_duration(milliseconds: float) -> str:
    """Render a duration at a readable precision.

    Args:
        milliseconds: The measured duration.

    Returns:
        Microseconds under a millisecond, milliseconds under a minute, and
        seconds beyond — always three significant figures or fewer, so the
        column stays narrow.
    """
    if milliseconds < 1:
        return f"{milliseconds * 1000:.0f}us"
    if milliseconds < 1000:
        return f"{milliseconds:.1f}ms"
    return f"{milliseconds / 1000:.2f}s"
