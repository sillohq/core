"""
sillo.console.terminal — what the attached terminal can actually do.

Everything above this module assumes it may draw in colour, move the cursor and
read a keypress without waiting for Enter. None of that is true of a log file, a
CI runner or a pipe into ``less``, so the decisions live here and are made once.

The rules are the conventional ones. ``NO_COLOR`` set to anything disables
colour, ``FORCE_COLOR`` overrides the check for build systems that pipe output
but still want it, and a stream that is not a TTY gets plain text. Windows
consoles have virtual-terminal processing switched on if they support it, which
every build since Windows 10 1511 does.

Nothing here imports anything that is not in the standard library.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO, Any

__all__ = [
    "Key",
    "cursor_hide",
    "cursor_show",
    "cursor_up",
    "erase_line",
    "is_interactive",
    "raw_mode",
    "read_key",
    "supports_color",
    "supports_unicode",
    "terminal_width",
]


# -- capability detection ----------------------------------------------


def _is_tty(stream: IO[str]) -> bool:
    """Return whether *stream* is attached to a terminal.

    A stream is free to raise from ``isatty`` — ``io.IOBase`` promises the
    method exists, not that it works on a closed or detached file — and a
    replacement stream in a test may not define it at all.

    Args:
        stream: The stream to inspect.

    Returns:
        True when the stream reports that it is a terminal.
    """
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def _enable_windows_vt(stream: IO[str]) -> bool:
    """Turn on virtual-terminal processing for a Windows console.

    Without this the console prints escape sequences literally. The flag is
    supported from Windows 10 1511 onward; on anything older the call fails and
    the caller falls back to plain output.

    Args:
        stream: The stream whose console handle should be reconfigured.

    Returns:
        True when the console will now interpret escape sequences.
    """
    if os.name != "nt":
        return True

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # ty: ignore[unresolved-attribute]
        handle = kernel32.GetStdHandle(-12 if stream is sys.stderr else -11)
        mode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        enable_virtual_terminal_processing = 0x0004
        return bool(
            kernel32.SetConsoleMode(
                handle, mode.value | enable_virtual_terminal_processing
            )
        )
    except Exception:
        return False


def supports_color(stream: IO[str] | None = None) -> bool:
    """Return whether *stream* should be written to in colour.

    Checked in order: ``NO_COLOR`` wins over everything, then ``FORCE_COLOR``,
    then ``TERM=dumb``, then whether the stream is a terminal.

    Args:
        stream: The stream to check. Defaults to stdout.

    Returns:
        True when colour escape sequences are safe to emit.
    """
    stream = stream if stream is not None else sys.stdout

    # NO_COLOR is a presence check by specification, not a value check: an
    # empty string still means no colour.
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR") is not None:
        return True
    if os.environ.get("TERM") == "dumb":
        return False
    if not _is_tty(stream):
        return False

    return _enable_windows_vt(stream)


def supports_unicode(stream: IO[str] | None = None) -> bool:
    """Return whether *stream* can encode the box-drawing and marker glyphs.

    Args:
        stream: The stream to check. Defaults to stdout.

    Returns:
        True when the stream's encoding round-trips the characters used for
        borders, spinners and selection markers.
    """
    stream = stream if stream is not None else sys.stdout
    encoding = getattr(stream, "encoding", None) or "ascii"
    try:
        "─│┌╭●✓✗▏".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def is_interactive(
    input_stream: IO[str] | None = None,
    output_stream: IO[str] | None = None,
) -> bool:
    """Return whether a prompt may take over the terminal.

    Both ends have to be a terminal. Reading keys from a pipe would block
    forever, and drawing a menu into a log file leaves redraw sequences in it.

    Args:
        input_stream: Where keys would be read from. Defaults to stdin.
        output_stream: Where the prompt would draw. Defaults to stdout.

    Returns:
        True when interactive prompting is safe.
    """
    return _is_tty(input_stream if input_stream is not None else sys.stdin) and _is_tty(
        output_stream if output_stream is not None else sys.stdout
    )


def terminal_width(default: int = 80) -> int:
    """Return the usable width of the terminal in columns.

    Args:
        default: Width to assume when the size cannot be determined.

    Returns:
        The column count, never below 20 — narrower than that and tables and
        panels produce nonsense rather than a cramped but readable layout.
    """
    try:
        import shutil

        width = shutil.get_terminal_size((default, 24)).columns
    except Exception:
        width = default
    return max(20, width)


# -- cursor control ----------------------------------------------------

cursor_hide = "\x1b[?25l"
cursor_show = "\x1b[?25h"
erase_line = "\x1b[2K"


def cursor_up(lines: int = 1) -> str:
    """Return the sequence moving the cursor up *lines* rows.

    Args:
        lines: How many rows to move. Zero produces an empty string rather
            than ``\\x1b[0A``, which some terminals read as a one-row move.

    Returns:
        The escape sequence, or an empty string for a zero-row move.
    """
    return f"\x1b[{lines}A" if lines > 0 else ""


# -- keyboard ----------------------------------------------------------


class Key:
    """The keys a prompt reacts to.

    Printable characters are returned as themselves, so a caller compares
    against these constants first and treats anything else as text.
    """

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    HOME = "home"
    END = "end"
    ENTER = "enter"
    SPACE = "space"
    TAB = "tab"
    ESCAPE = "escape"
    BACKSPACE = "backspace"
    DELETE = "delete"
    INTERRUPT = "interrupt"


# Escape sequence tails, keyed by what follows the leading CSI. Terminals
# disagree on whether Home and End arrive as \x1b[H or \x1b[1~, so both spellings
# are mapped rather than picking one and being wrong on somebody's terminal.
_CSI_KEYS = {
    "A": Key.UP,
    "B": Key.DOWN,
    "C": Key.RIGHT,
    "D": Key.LEFT,
    "H": Key.HOME,
    "F": Key.END,
    "1~": Key.HOME,
    "3~": Key.DELETE,
    "4~": Key.END,
    "7~": Key.HOME,
    "8~": Key.END,
}


@contextmanager
def raw_mode(stream: IO[str] | None = None) -> Iterator[None]:
    """Put the terminal into cbreak mode for the duration of the block.

    Keys arrive unbuffered and unechoed, which is what makes a menu feel like a
    menu. The previous settings are always restored, including when the body
    raises, because leaving a shell in cbreak mode makes it unusable.

    On Windows this does nothing: ``msvcrt`` reads keys directly and there is no
    line discipline to change.

    Args:
        stream: The terminal to reconfigure. Defaults to stdin.

    Yields:
        None.
    """
    stream = stream if stream is not None else sys.stdin

    if os.name == "nt" or not _is_tty(stream):
        yield
        return

    try:
        import termios
        import tty
    except ImportError:  # pragma: no cover - POSIX only
        yield
        return

    descriptor = stream.fileno()
    saved = termios.tcgetattr(descriptor)
    try:
        tty.setcbreak(descriptor)
        yield
    finally:
        # TCSADRAIN waits for pending output to be written first, so a restore
        # racing with a final redraw does not truncate it.
        termios.tcsetattr(descriptor, termios.TCSADRAIN, saved)


def _read_key_windows() -> str:
    """Read one keypress from a Windows console.

    Returns:
        A Key constant or the printable character that was typed.
    """
    import msvcrt  # ty: ignore[unresolved-import]

    char = msvcrt.getwch()  # ty: ignore[unresolved-attribute]

    if char in ("\x00", "\xe0"):
        # Special keys arrive as a two-character sequence led by a null or E0.
        second = msvcrt.getwch()  # ty: ignore[unresolved-attribute]
        return {
            "H": Key.UP,
            "P": Key.DOWN,
            "K": Key.LEFT,
            "M": Key.RIGHT,
            "G": Key.HOME,
            "O": Key.END,
            "S": Key.DELETE,
        }.get(second, "")

    return _classify(char)


def _classify(char: str) -> str:
    """Map a single control character onto a Key constant.

    Args:
        char: The character that was read.

    Returns:
        A Key constant, or *char* unchanged when it is printable.
    """
    if char in ("\r", "\n"):
        return Key.ENTER
    if char == " ":
        return Key.SPACE
    if char == "\t":
        return Key.TAB
    if char in ("\x7f", "\b"):
        return Key.BACKSPACE
    if char == "\x03":
        return Key.INTERRUPT
    if char == "\x04":
        # Ctrl-D on an empty line is end-of-input, which a prompt should treat
        # the same way as Ctrl-C rather than as a printable character.
        return Key.INTERRUPT
    return char


def read_key(stream: IO[str] | None = None) -> str:
    """Read a single keypress, resolving escape sequences to Key constants.

    Must be called inside :func:`raw_mode`, otherwise the read blocks until the
    user presses Enter.

    Args:
        stream: Where to read from. Defaults to stdin.

    Returns:
        A Key constant, or the printable character that was typed. An empty
        string means the input ended or the sequence was not recognised.
    """
    if os.name == "nt":  # pragma: no cover - Windows only
        return _read_key_windows()

    stream = stream if stream is not None else sys.stdin
    char = stream.read(1)

    if not char:
        return ""
    if char != "\x1b":
        return _classify(char)

    # An escape sequence, or a bare Escape key. Peek at the next character: if
    # it is not '[' or 'O' the user pressed Escape on its own.
    following = stream.read(1)
    if following not in ("[", "O"):
        return Key.ESCAPE

    sequence = ""
    while True:
        char = stream.read(1)
        if not char:
            break
        sequence += char
        # Parameter bytes are digits and semicolons; anything else ends it.
        if not char.isdigit() and char != ";":
            break

    return _CSI_KEYS.get(sequence, "")


def write(stream: IO[str], *parts: Any) -> None:
    """Write *parts* to *stream* and flush.

    Prompts redraw between keypresses, so an unflushed buffer shows the user a
    stale frame.

    Args:
        stream: Where to write.
        *parts: Values to concatenate, stringified.
    """
    stream.write("".join(str(part) for part in parts))
    stream.flush()
