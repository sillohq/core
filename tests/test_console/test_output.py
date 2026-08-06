"""Drawing to a stream, with and without a terminal to draw on."""

from __future__ import annotations

import io

import pytest

from sillo.console import Output, Palette, strip_ansi


def plain() -> tuple:
    """An output that writes uncoloured ASCII into a buffer."""
    stream = io.StringIO()
    return Output(stream, Palette(enabled=False), unicode=False), stream


def fancy() -> tuple:
    """An output that writes coloured unicode into a buffer."""
    stream = io.StringIO()
    return Output(stream, Palette(enabled=True), unicode=True), stream


# -- lines -------------------------------------------------------------


def test_a_line_ends_with_a_newline():
    output, stream = plain()

    output.line("hello")

    assert stream.getvalue() == "hello\n"


def test_writing_does_not_add_a_newline():
    output, stream = plain()

    output.write("a", "b", 1)

    assert stream.getvalue() == "ab1"


def test_blank_writes_the_requested_newlines():
    output, stream = plain()

    output.blank(3)

    assert stream.getvalue() == "\n\n\n"


@pytest.mark.parametrize(
    "method,marker",
    [("success", "v"), ("error", "x"), ("warn", "!")],
)
def test_the_levels_carry_an_ascii_marker_without_unicode(method, marker):
    output, stream = plain()

    getattr(output, method)("something happened")

    assert stream.getvalue() == f"{marker} something happened\n"


def test_the_levels_carry_a_unicode_marker_with_it():
    output, stream = fancy()

    output.success("done")

    assert "✓ done" in strip_ansi(stream.getvalue())


def test_a_heading_is_preceded_by_a_blank_line():
    output, stream = plain()

    output.heading("Users")

    assert stream.getvalue() == "\nUsers\n"


# -- structures --------------------------------------------------------


def test_a_table_lines_its_columns_up():
    output, stream = plain()

    output.table(["id", "email"], [["1", "ada@example.com"], ["22", "b@x.io"]])
    lines = stream.getvalue().split("\n")

    # Every body row starts its second column at the same offset.
    assert lines[2].index("ada@example.com") == lines[3].index("b@x.io")


def test_a_table_sizes_columns_to_the_widest_cell():
    output, stream = plain()

    output.table(["id"], [["a-very-long-value"]])

    assert "a-very-long-value" in stream.getvalue()


def test_a_table_aligns_right_when_asked():
    output, stream = plain()

    output.table(["n"], [["1"], ["100"]], align=["right"])
    lines = [line for line in stream.getvalue().split("\n") if line.strip()]

    assert lines[-2].rstrip().endswith("1")
    assert lines[-1].rstrip().endswith("100")


def test_a_table_row_of_the_wrong_length_is_rejected():
    output, _ = plain()

    with pytest.raises(ValueError, match="row 0 has 1 cells but there are 2"):
        output.table(["a", "b"], [["only-one"]])


def test_a_table_measures_styled_cells_by_their_printable_width():
    output, stream = fancy()
    cell = output.paint("ada", None)

    output.table(["name"], [[cell]])

    assert "ada" in strip_ansi(stream.getvalue())


def test_a_panel_draws_a_border_around_the_body():
    output, stream = plain()

    output.panel("inside")
    lines = stream.getvalue().rstrip("\n").split("\n")

    assert lines[0].startswith("+") and lines[0].endswith("+")
    assert lines[-1].startswith("+") and lines[-1].endswith("+")
    assert "inside" in lines[1]


def test_a_panel_sets_its_title_into_the_top_border():
    output, stream = plain()

    output.panel("body", title="Summary")

    assert "Summary" in stream.getvalue().split("\n")[0]


def test_a_panel_keeps_its_right_edge_with_uneven_lines():
    output, stream = plain()

    output.panel("short\na much longer line")
    lines = stream.getvalue().rstrip("\n").split("\n")

    assert len({len(line) for line in lines}) == 1


def test_a_rule_fills_the_width():
    output, stream = plain()

    output.rule()

    assert set(stream.getvalue().strip()) == {"-"}


def test_a_labelled_rule_contains_its_label():
    output, stream = plain()

    output.rule("Migrations")

    assert "Migrations" in stream.getvalue()


def test_pairs_align_their_values():
    output, stream = plain()

    output.pairs([("id", 1), ("email", "ada@example.com")])
    lines = stream.getvalue().rstrip("\n").split("\n")

    assert lines[0].index("1") == lines[1].index("ada@example.com")


def test_pairs_of_nothing_writes_nothing():
    output, stream = plain()

    output.pairs([])

    assert stream.getvalue() == ""


def test_a_bullet_is_indented():
    output, stream = plain()

    output.bullet("item")

    assert stream.getvalue() == "  * item\n"


# -- activity ----------------------------------------------------------


def test_a_progress_bar_without_a_terminal_reports_milestones_on_lines():
    output, stream = plain()

    with output.progress(total=10, label="Importing") as bar:
        for _ in range(10):
            bar.advance()

    lines = [line for line in stream.getvalue().split("\n") if line]

    # One line per ten per cent, not one per step, and no redraw sequences.
    assert "\r" not in stream.getvalue()
    assert lines[0] == "Importing 0%"
    assert lines[-1] == "Importing 100%"


def test_a_progress_bar_with_a_terminal_redraws_in_place():
    output, stream = fancy()

    with output.progress(total=4, label="Work") as bar:
        bar.advance(2)

    written = stream.getvalue()

    assert "\r" in written
    assert "50%" in strip_ansi(written)


def test_a_progress_bar_can_be_set_absolutely():
    output, stream = plain()

    with output.progress(total=100) as bar:
        bar.set(50)

    assert "50%" in stream.getvalue()


def test_a_progress_bar_does_not_run_past_its_total():
    output, stream = plain()

    with output.progress(total=2) as bar:
        bar.advance(99)

    assert bar.current == 2


def test_a_progress_bar_of_zero_does_not_divide_by_zero():
    output, _ = plain()

    with output.progress(total=0) as bar:
        bar.advance()

    assert bar.current == 1


def test_a_spinner_without_a_terminal_prints_its_label_once():
    output, stream = plain()

    with output.spinner("Connecting"):
        pass

    assert stream.getvalue() == "Connecting...\n"
    assert "\r" not in stream.getvalue()


def test_a_spinner_with_a_terminal_clears_the_line_when_it_stops():
    output, stream = fancy()

    with output.spinner("Working"):
        pass

    assert "\x1b[?25h" in stream.getvalue()


def test_a_spinner_can_report_a_result_when_it_stops():
    output, stream = fancy()

    spinner = output.spinner("Working").__enter__()
    spinner.stop("Connected")

    assert "Connected" in strip_ansi(stream.getvalue())
