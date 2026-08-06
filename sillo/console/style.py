"""
sillo.console.style — colour and text attributes, resolved once per stream.

A :class:`Style` is a description, not an escape sequence. It only becomes one
when a :class:`Palette` renders it, and a palette that has decided the stream
cannot take colour renders every style as the text itself. That split is what
lets output code be written once and stay correct in a pipe, a CI log and a
terminal.

Colours may be named (``"red"``), a 256-colour index (``"38"``) or a hex triple
(``"#fc0345"``). Hex is emitted as true colour where the terminal advertises it
and downsampled to the 256-colour cube otherwise, so the brand red survives on a
terminal that has never heard of ``COLORTERM``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from typing import IO, Dict, Optional

from .terminal import supports_color

__all__ = ["Palette", "Style", "strip_ansi"]


_RESET = "\x1b[0m"
_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

# The eight base colours and their bright variants, as SGR foreground offsets.
_NAMED: Dict[str, int] = {
    "black": 0,
    "red": 1,
    "green": 2,
    "yellow": 3,
    "blue": 4,
    "magenta": 5,
    "cyan": 6,
    "white": 7,
    "bright_black": 8,
    "bright_red": 9,
    "bright_green": 10,
    "bright_yellow": 11,
    "bright_blue": 12,
    "bright_magenta": 13,
    "bright_cyan": 14,
    "bright_white": 15,
}

# "grey" is the colour every console writer reaches for and no ANSI palette
# defines. Bright black is what they mean.
_NAMED["grey"] = _NAMED["gray"] = _NAMED["bright_black"]


def strip_ansi(text: str) -> str:
    """Remove escape sequences from *text*.

    Used wherever a printable width matters — table columns, panel borders,
    truncation — because a styled string is longer than it looks.

    Args:
        text: Possibly styled text.

    Returns:
        The text with every escape sequence removed.
    """
    return _ANSI.sub("", text)


@dataclass(frozen=True)
class Style:
    """A description of how text should look.

    Attributes:
        fg: Foreground colour, as a name, a 256-colour index or a hex triple.
        bg: Background colour, in the same forms as *fg*.
        bold: Render at increased weight.
        dim: Render at reduced intensity.
        italic: Render italic, where the terminal supports it.
        underline: Underline the text.
        strike: Strike the text through.
    """

    fg: Optional[str] = None
    bg: Optional[str] = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False

    def __or__(self, other: "Style") -> "Style":
        """Merge two styles, with *other* winning on any attribute it sets.

        Args:
            other: The style layered on top.

        Returns:
            The combined style.
        """
        return Style(
            fg=other.fg if other.fg is not None else self.fg,
            bg=other.bg if other.bg is not None else self.bg,
            bold=self.bold or other.bold,
            dim=self.dim or other.dim,
            italic=self.italic or other.italic,
            underline=self.underline or other.underline,
            strike=self.strike or other.strike,
        )

    def with_(self, **changes: object) -> "Style":
        """Return a copy with *changes* applied.

        Args:
            **changes: Attributes to override.

        Returns:
            The modified copy.
        """
        return replace(self, **changes)  # type: ignore[arg-type]


def _hex_to_rgb(value: str) -> tuple:
    """Split a hex triple into its channels.

    Args:
        value: A hex colour, with or without the leading hash.

    Returns:
        The red, green and blue channels as integers.
    """
    match = _HEX.match(value)
    if match is None:
        raise ValueError(f"{value!r} is not a hex colour")
    digits = match.group(1)
    return tuple(int(digits[index : index + 2], 16) for index in (0, 2, 4))


def _rgb_to_cube(red: int, green: int, blue: int) -> int:
    """Map an RGB triple onto the xterm 256-colour palette.

    Greys are matched against the 24-step ramp rather than the colour cube,
    because the cube's grey diagonal is coarse enough that ``#111112`` would
    land on pure black.

    Args:
        red: Red channel.
        green: Green channel.
        blue: Blue channel.

    Returns:
        The palette index.
    """
    if abs(red - green) < 12 and abs(green - blue) < 12:
        if red < 8:
            return 16
        if red > 248:
            return 231
        return 232 + round((red - 8) / 247 * 23)

    return (
        16
        + 36 * round(red / 255 * 5)
        + 6 * round(green / 255 * 5)
        + round(blue / 255 * 5)
    )


class Palette:
    """Renders styles for one output stream.

    A palette decides once whether the stream takes colour, then applies that
    decision to every style it is asked to render. Construct one per stream and
    keep it; the capability checks read the environment and call ``isatty``.

    Args:
        stream: The stream that will receive the output.
        enabled: Force colour on or off. When None the stream is inspected.
        truecolor: Force 24-bit colour on or off. When None the environment is
            inspected.
    """

    def __init__(
        self,
        stream: Optional[IO[str]] = None,
        enabled: Optional[bool] = None,
        truecolor: Optional[bool] = None,
    ) -> None:
        self.enabled = supports_color(stream) if enabled is None else enabled
        if truecolor is None:
            truecolor = os.environ.get("COLORTERM", "") in ("truecolor", "24bit")
        self.truecolor = truecolor

    def _colour_codes(self, value: str, background: bool) -> str:
        """Build the SGR parameters for one colour.

        Args:
            value: A name, a 256-colour index or a hex triple.
            background: Whether this is a background colour.

        Returns:
            The parameters, without the surrounding escape sequence.
        """
        base = 48 if background else 38
        offset = 40 if background else 30

        if value in _NAMED:
            index = _NAMED[value]
            # The low eight have single-parameter codes; the bright eight use
            # the 90/100 range. Both are far more widely supported than 38;5.
            if index < 8:
                return str(offset + index)
            return str(offset + 60 + index - 8)

        if _HEX.match(value):
            red, green, blue = _hex_to_rgb(value)
            if self.truecolor:
                return f"{base};2;{red};{green};{blue}"
            return f"{base};5;{_rgb_to_cube(red, green, blue)}"

        if value.isdigit():
            return f"{base};5;{int(value)}"

        raise ValueError(f"{value!r} is not a colour")

    def render(self, text: str, style: Optional[Style] = None) -> str:
        """Apply *style* to *text*.

        Args:
            text: The text to style.
            style: The style to apply. None returns the text unchanged.

        Returns:
            The styled text, or the text itself when colour is disabled.
        """
        if style is None or not self.enabled or not text:
            return text

        codes = []
        if style.bold:
            codes.append("1")
        if style.dim:
            codes.append("2")
        if style.italic:
            codes.append("3")
        if style.underline:
            codes.append("4")
        if style.strike:
            codes.append("9")
        if style.fg:
            codes.append(self._colour_codes(style.fg, background=False))
        if style.bg:
            codes.append(self._colour_codes(style.bg, background=True))

        if not codes:
            return text

        return f"\x1b[{';'.join(codes)}m{text}{_RESET}"


# -- the semantic palette ----------------------------------------------
#
# Commands name intent, not colour, so that one change here restyles every
# console in every project rather than every call site needing an edit.

PRIMARY = Style(fg="#fc0345")
SUCCESS = Style(fg="green")
WARNING = Style(fg="yellow")
DANGER = Style(fg="red")
INFO = Style(fg="cyan")
MUTED = Style(fg="grey")
HEADING = Style(bold=True)
INVERSE = Style(bold=True, fg="black", bg="#fc0345")
