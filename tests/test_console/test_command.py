"""The command instance: reading parameters, writing output, describing itself."""

from __future__ import annotations

import io

import pytest

from sillo.console import (
    Argument,
    Command,
    CommandError,
    Flag,
    Option,
    Output,
    Palette,
    Prompt,
    parse,
    strip_ansi,
)


class Sample(Command):
    """Do the sample thing.

    A second paragraph that only the long help shows.
    """

    name = "db:migrate"
    help = "Apply pending migrations"
    arguments = [
        Argument("target", default="latest"),
        Option("limit", type=int, default=5),
        Flag("fake"),
    ]

    async def handle(self):
        return None


def instantiate(command=Sample, argv=()) -> tuple:
    """Build *command* as if it had been invoked with *argv*."""
    stream = io.StringIO()
    output = Output(stream, Palette(enabled=False), unicode=False)
    prompt = Prompt(output, io.StringIO(), interactive=False)
    parsed = parse(command.arguments, list(argv), command=command.name)
    return command(parsed, output, prompt), stream


# -- reading parameters ------------------------------------------------


def test_each_accessor_reads_its_own_kind():
    command, _ = instantiate(argv=["0001", "--limit", "9", "--fake"])

    assert command.argument("target") == "0001"
    assert command.option("limit") == 9
    assert command.flag("fake") is True


def test_defaults_come_through_when_nothing_was_passed():
    command, _ = instantiate()

    assert command.argument("target") == "latest"
    assert command.option("limit") == 5
    assert command.flag("fake") is False


def test_reading_an_option_as_an_argument_is_refused():
    command, _ = instantiate()

    with pytest.raises(KeyError, match="declared as option, not argument"):
        command.argument("limit")


def test_reading_a_flag_as_an_option_is_refused():
    command, _ = instantiate()

    with pytest.raises(KeyError, match="declared as flag, not option"):
        command.option("fake")


def test_the_error_names_the_accessor_that_would_work():
    command, _ = instantiate()

    with pytest.raises(KeyError, match=r"read it with \.flag\('fake'\)"):
        command.option("fake")


def test_reading_something_undeclared_is_refused():
    command, _ = instantiate()

    with pytest.raises(KeyError, match="no parameter named 'nope'"):
        command.option("nope")


def test_tokens_after_a_double_dash_are_available_as_extra():
    command, _ = instantiate(argv=["--", "--verbose", "path"])

    assert command.extra == ["--verbose", "path"]


def test_extra_is_empty_without_a_double_dash():
    command, _ = instantiate()

    assert command.extra == []


# -- output ------------------------------------------------------------


@pytest.mark.parametrize(
    "method,expected",
    [
        ("line", "plain"),
        ("info", "plain"),
        ("muted", "plain"),
        ("success", "v plain"),
        ("warn", "! plain"),
        ("error", "x plain"),
    ],
)
def test_the_output_helpers_write_through(method, expected):
    command, stream = instantiate()

    getattr(command, method)("plain")

    assert stream.getvalue() == f"{expected}\n"


def test_blank_writes_newlines():
    command, stream = instantiate()

    command.blank(2)

    assert stream.getvalue() == "\n\n"


def test_a_table_is_drawn_through_the_command():
    command, stream = instantiate()

    command.table(["id"], [["1"]])

    assert "id" in stream.getvalue()


def test_a_panel_is_drawn_through_the_command():
    command, stream = instantiate()

    command.panel("body", title="Title")

    assert "Title" in stream.getvalue()


def test_a_rule_is_drawn_through_the_command():
    command, stream = instantiate()

    command.rule("Section")

    assert "Section" in stream.getvalue()


def test_a_progress_bar_is_available_on_the_command():
    command, stream = instantiate()

    with command.progress(total=2, label="Work") as bar:
        bar.advance(2)

    assert "100%" in stream.getvalue()


def test_a_spinner_is_available_on_the_command():
    command, stream = instantiate()

    with command.spinner("Working"):
        pass

    assert "Working" in stream.getvalue()


# -- questions ---------------------------------------------------------


def test_the_prompts_are_reachable_from_the_command():
    command, _ = instantiate()

    assert command.ask("Name", default="ada") == "ada"
    assert command.confirm("Sure", default=True) is True
    assert command.choice("Pick", ["a", "b"], default="b") == "b"
    assert command.multichoice("Pick", ["a", "b"], defaults=["a"]) == ["a"]


# -- failing -----------------------------------------------------------


def test_fail_raises_a_command_error():
    command, _ = instantiate()

    with pytest.raises(CommandError, match="broken") as caught:
        command.fail("broken")

    assert caught.value.exit_code == 1


def test_fail_carries_the_exit_code():
    command, _ = instantiate()

    with pytest.raises(CommandError) as caught:
        command.fail("broken", exit_code=7)

    assert caught.value.exit_code == 7


# -- describing itself -------------------------------------------------


def test_the_group_is_the_part_before_the_colon():
    assert Sample.group() == "db"


def test_a_name_without_a_colon_has_no_group():
    class Loose(Command):
        name = "serve"

    assert Loose.group() == ""


def test_the_summary_prefers_the_help_attribute():
    assert Sample.summary() == "Apply pending migrations"


def test_the_summary_falls_back_to_the_first_docstring_line():
    class Documented(Command):
        """Only a docstring.

        With more below it.
        """

        name = "documented"

    assert Documented.summary() == "Only a docstring."


def test_a_command_with_neither_has_an_empty_summary():
    class Bare(Command):
        name = "bare"

    assert Bare.summary() == ""


def test_the_details_fall_back_to_the_whole_docstring():
    assert "A second paragraph" in Sample.details()


def test_the_details_prefer_an_explicit_description():
    class Described(Command):
        """Ignored."""

        name = "described"
        description = "Used instead."

    assert Described.details() == "Used instead."


def test_the_context_hook_defaults_to_nothing():
    command, _ = instantiate()

    assert command.context() is None


def test_the_console_is_reachable_from_the_command():
    stream = io.StringIO()
    output = Output(stream, Palette(enabled=False), unicode=False)
    prompt = Prompt(output, io.StringIO(), interactive=False)
    parsed = parse([], [])
    sentinel = object()

    command = Command(parsed, output, prompt, console=sentinel)

    assert command.console is sentinel


def test_styling_is_reachable_for_a_command_that_wants_it():
    from sillo.console import PRIMARY

    stream = io.StringIO()
    output = Output(stream, Palette(enabled=True), unicode=True)
    prompt = Prompt(output, io.StringIO(), interactive=False)
    command = Command(parse([], []), output, prompt)

    command.line("emphasis", PRIMARY)

    assert strip_ansi(stream.getvalue()) == "emphasis\n"
    assert "\x1b[" in stream.getvalue()
