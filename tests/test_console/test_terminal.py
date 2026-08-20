"""
Terminal capability detection.

All of it is decided from the environment and from whether a stream is a tty,
which makes it unusually testable — and unusually worth testing, because the
consequence of getting it wrong is escape sequences printed literally into
somebody's CI log.
"""

from __future__ import annotations

import io
import os
import sys

import pytest

from sillo.console import terminal


class Tty(io.StringIO):
    """A stream that claims to be a terminal."""

    def isatty(self) -> bool:
        return True

    def fileno(self) -> int:
        return 1


class Pipe(io.StringIO):
    """A stream that does not."""

    def isatty(self) -> bool:
        return False


@pytest.fixture
def clean(monkeypatch):
    """No terminal-related variables, so each test states its own world."""
    for name in (
        "TERM",
        "TERM_PROGRAM",
        "WT_SESSION",
        "VTE_VERSION",
        "COLORTERM",
        "NO_COLOR",
        "FORCE_COLOR",
        "CI",
        "SILLO_HYPERLINKS",
        "COLUMNS",
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


class TestIsTty:
    def test_a_terminal_is_one(self):
        assert terminal._is_tty(Tty()) is True

    def test_a_pipe_is_not(self):
        assert terminal._is_tty(Pipe()) is False

    def test_a_stream_that_cannot_say_is_not(self):
        class Mute:
            pass

        assert terminal._is_tty(Mute()) is False


class TestHyperlinks:
    def test_a_pipe_gets_no_hyperlinks(self, clean):
        assert terminal.supports_hyperlinks(Pipe()) is False

    def test_windows_terminal_gets_them(self, clean):
        clean.setenv("WT_SESSION", "1")
        assert terminal.supports_hyperlinks(Tty()) is True

    def test_kitty_gets_them(self, clean):
        clean.setenv("TERM", "xterm-kitty")
        assert terminal.supports_hyperlinks(Tty()) is True

    def test_a_recent_vte_gets_them(self, clean):
        clean.setenv("VTE_VERSION", "6003")
        assert terminal.supports_hyperlinks(Tty()) is True

    def test_an_old_vte_does_not(self, clean):
        clean.setenv("VTE_VERSION", "4000")
        assert terminal.supports_hyperlinks(Tty()) is False

    def test_a_nonsense_vte_version_does_not_raise(self, clean):
        clean.setenv("VTE_VERSION", "not-a-number")
        assert terminal.supports_hyperlinks(Tty()) is False

    def test_an_unknown_terminal_does_not(self, clean):
        clean.setenv("TERM", "dumb")
        assert terminal.supports_hyperlinks(Tty()) is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
    def test_it_can_be_forced_on(self, clean, value):
        clean.setenv("SILLO_HYPERLINKS", value)
        assert terminal.supports_hyperlinks(Pipe()) is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off"])
    def test_it_can_be_forced_off(self, clean, value):
        clean.setenv("SILLO_HYPERLINKS", value)
        clean.setenv("WT_SESSION", "1")
        assert terminal.supports_hyperlinks(Tty()) is False

    def test_wrapping_produces_an_osc_8_sequence(self, clean):
        clean.setenv("SILLO_HYPERLINKS", "1")
        wrapped = terminal.hyperlink("https://sillo.build", "sillo")

        assert wrapped.startswith("\x1b]8;;https://sillo.build\x1b\\")
        assert wrapped.endswith("\x1b]8;;\x1b\\")
        assert "sillo" in wrapped

    def test_wrapping_is_a_no_op_where_it_would_not_work(self, clean):
        clean.setenv("SILLO_HYPERLINKS", "0")
        assert terminal.hyperlink("https://sillo.build", "sillo") == "sillo"


class TestWindowsVirtualTerminal:
    def test_it_is_a_no_op_off_windows(self, monkeypatch):
        monkeypatch.setattr(os, "name", "posix")
        assert terminal._enable_windows_vt(sys.stdout) is True

    def test_a_console_that_will_not_cooperate_is_reported(self, monkeypatch):
        """Anything before Windows 10 1511. The caller falls back to plain
        output rather than printing escape sequences literally."""
        monkeypatch.setattr(os, "name", "nt")
        assert terminal._enable_windows_vt(sys.stdout) is False


class TestUnicode:
    def test_a_utf8_stream_can_take_unicode(self, clean):
        stream = Tty()
        assert isinstance(terminal.supports_unicode(stream), bool)

    def test_a_stream_with_no_encoding_is_handled(self, clean):
        class Odd(Tty):
            encoding = None

        assert isinstance(terminal.supports_unicode(Odd()), bool)


class TestInteractive:
    def test_two_terminals_are_interactive(self, clean):
        assert terminal.is_interactive(Tty(), Tty()) is True

    def test_a_piped_input_is_not(self, clean):
        assert terminal.is_interactive(Pipe(), Tty()) is False

    def test_a_piped_output_is_not(self, clean):
        assert terminal.is_interactive(Tty(), Pipe()) is False


class TestWidth:
    def test_the_environment_wins(self, clean):
        clean.setenv("COLUMNS", "120")
        assert terminal.terminal_width() == 120

    def test_a_nonsense_width_falls_back(self, clean):
        clean.setenv("COLUMNS", "wide")
        assert terminal.terminal_width(default=77) > 0

    def test_there_is_always_a_width(self, clean):
        assert terminal.terminal_width() > 0


class TestCursor:
    def test_moving_up_produces_a_sequence(self):
        assert terminal.cursor_up(3) == "\x1b[3A"

    def test_moving_up_nothing_is_nothing(self):
        assert terminal.cursor_up(0) == ""


class TestKeyClassification:
    @pytest.mark.parametrize(
        "char,name",
        [
            ("\r", terminal.Key.ENTER),
            ("\n", terminal.Key.ENTER),
            ("\x03", terminal.Key.INTERRUPT),
            ("\x04", terminal.Key.INTERRUPT),
            ("\x7f", terminal.Key.BACKSPACE),
            ("\b", terminal.Key.BACKSPACE),
            ("\t", terminal.Key.TAB),
            (" ", terminal.Key.SPACE),
        ],
    )
    def test_the_control_keys_are_named(self, char, name):
        assert terminal._classify(char) == name

    def test_end_of_input_reads_as_an_interrupt(self):
        """Ctrl-D on an empty line is the end of input, and a prompt should
        treat it the way it treats Ctrl-C rather than as a character."""
        assert terminal._classify("\x04") == terminal.Key.INTERRUPT

    def test_every_csi_tail_maps_to_a_key(self):
        assert set(terminal._CSI_KEYS.values()) <= {
            terminal.Key.UP,
            terminal.Key.DOWN,
            terminal.Key.LEFT,
            terminal.Key.RIGHT,
            terminal.Key.HOME,
            terminal.Key.END,
            terminal.Key.DELETE,
        }

    def test_home_and_end_are_mapped_in_both_spellings(self):
        """Terminals disagree, so mapping one spelling is being wrong on
        somebody's terminal."""
        assert terminal._CSI_KEYS["H"] == terminal._CSI_KEYS["1~"]
        assert terminal._CSI_KEYS["F"] == terminal._CSI_KEYS["4~"]

    def test_an_ordinary_character_is_itself(self):
        assert terminal._classify("a") == "a"


class TestWriting:
    def test_parts_are_joined(self):
        stream = io.StringIO()
        terminal.write(stream, "a", "b", "c")
        assert stream.getvalue() == "abc"

    def test_it_flushes(self):
        """Prompts redraw between keypresses, so an unflushed buffer shows the
        user a stale frame."""
        flushed = []

        class Watched(io.StringIO):
            def flush(self):
                flushed.append(True)

        terminal.write(Watched(), "x")
        assert flushed == [True]

    def test_a_closed_stream_propagates(self):
        """Documenting rather than endorsing: `write` does not guard, so a
        console piped into something that exits early — `sillo routes | head`
        — surfaces the broken pipe to the caller."""
        stream = io.StringIO()
        stream.close()

        with pytest.raises(ValueError):
            terminal.write(stream, "anything")

    def test_values_are_stringified(self):
        stream = io.StringIO()
        terminal.write(stream, 1, None, 2.5)
        assert stream.getvalue() == "1None2.5"
