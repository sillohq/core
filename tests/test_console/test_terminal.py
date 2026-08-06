"""Terminal capability detection and key decoding."""

from __future__ import annotations

import io

import pytest

from sillo.console import supports_color, supports_unicode, terminal_width
from sillo.console.terminal import Key, is_interactive, read_key


class FakeTTY(io.StringIO):
    """A StringIO that claims to be a terminal.

    ``encoding`` is a read-only descriptor on the C base class, so it is
    shadowed with a property rather than assigned in ``__init__``.
    """

    def __init__(self, contents: str = "", encoding: str = "utf-8") -> None:
        super().__init__(contents)
        self._encoding = encoding

    @property
    def encoding(self) -> str:
        return self._encoding

    def isatty(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _clear_colour_environment(monkeypatch):
    """Start each test from an environment with no colour opinion."""
    for name in ("NO_COLOR", "FORCE_COLOR", "TERM", "COLORTERM"):
        monkeypatch.delenv(name, raising=False)


# -- colour ------------------------------------------------------------


def test_a_terminal_takes_colour():
    assert supports_color(FakeTTY()) is True


def test_a_pipe_does_not():
    assert supports_color(io.StringIO()) is False


def test_no_color_wins_over_everything(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")

    assert supports_color(FakeTTY()) is False


def test_no_color_is_a_presence_check_not_a_value_check(monkeypatch):
    # The specification says any value, including an empty one, disables it.
    monkeypatch.setenv("NO_COLOR", "")

    assert supports_color(FakeTTY()) is False


def test_force_color_overrides_a_pipe(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")

    assert supports_color(io.StringIO()) is True


def test_a_dumb_terminal_gets_none(monkeypatch):
    monkeypatch.setenv("TERM", "dumb")

    assert supports_color(FakeTTY()) is False


def test_a_stream_that_raises_from_isatty_is_treated_as_a_pipe():
    class Hostile(io.StringIO):
        def isatty(self):
            raise OSError("detached")

    assert supports_color(Hostile()) is False


# -- unicode -----------------------------------------------------------


def test_a_utf8_stream_takes_box_drawing():
    assert supports_unicode(FakeTTY(encoding="utf-8")) is True


def test_an_ascii_stream_does_not():
    assert supports_unicode(FakeTTY(encoding="ascii")) is False


def test_a_stream_with_no_encoding_is_assumed_ascii():
    assert supports_unicode(io.StringIO()) is False


# -- interactivity -----------------------------------------------------


def test_both_ends_must_be_a_terminal():
    assert is_interactive(FakeTTY(), FakeTTY()) is True
    assert is_interactive(io.StringIO(), FakeTTY()) is False
    assert is_interactive(FakeTTY(), io.StringIO()) is False


def test_the_width_never_collapses_below_twenty():
    assert terminal_width() >= 20


# -- keys --------------------------------------------------------------


@pytest.mark.parametrize(
    "sequence,expected",
    [
        ("\x1b[A", Key.UP),
        ("\x1b[B", Key.DOWN),
        ("\x1b[C", Key.RIGHT),
        ("\x1b[D", Key.LEFT),
        ("\x1b[H", Key.HOME),
        ("\x1b[F", Key.END),
        ("\x1b[3~", Key.DELETE),
        ("\x1b[1~", Key.HOME),
        ("\x1b[4~", Key.END),
    ],
)
def test_escape_sequences_decode_to_keys(sequence, expected):
    assert read_key(io.StringIO(sequence)) == expected


@pytest.mark.parametrize(
    "character,expected",
    [
        ("\r", Key.ENTER),
        ("\n", Key.ENTER),
        (" ", Key.SPACE),
        ("\t", Key.TAB),
        ("\x7f", Key.BACKSPACE),
        ("\b", Key.BACKSPACE),
        ("\x03", Key.INTERRUPT),
        ("\x04", Key.INTERRUPT),
    ],
)
def test_control_characters_decode_to_keys(character, expected):
    assert read_key(io.StringIO(character)) == expected


def test_a_printable_character_comes_back_as_itself():
    assert read_key(io.StringIO("q")) == "q"


def test_a_bare_escape_is_the_escape_key():
    # No '[' follows, so the user pressed Escape rather than starting a
    # sequence.
    assert read_key(io.StringIO("\x1bx")) == Key.ESCAPE


def test_exhausted_input_reads_as_nothing():
    assert read_key(io.StringIO("")) == ""


def test_an_unrecognised_sequence_reads_as_nothing():
    assert read_key(io.StringIO("\x1b[99Z")) == ""
