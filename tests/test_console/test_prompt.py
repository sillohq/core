"""Asking questions, and what happens when there is nobody to ask."""

from __future__ import annotations

import io

import pytest

from sillo.console import Abort, Output, Palette, Prompt, UsageError, strip_ansi

DOWN = "\x1b[B"
UP = "\x1b[A"
ENTER = "\n"
SPACE = " "
CTRL_C = "\x03"
ESCAPE = "\x1b\x1b"


def build(keys: str = "", interactive: bool = True) -> tuple:
    """A prompt driven by *keys*, writing into a buffer."""
    stream = io.StringIO()
    output = Output(stream, Palette(enabled=False), unicode=False)
    return Prompt(output, io.StringIO(keys), interactive=interactive), stream


# -- non-interactive fallbacks -----------------------------------------


def test_ask_takes_its_default_without_a_terminal():
    prompt, _ = build(interactive=False)

    assert prompt.ask("Name", default="ada") == "ada"


def test_ask_without_a_default_refuses_to_guess():
    prompt, _ = build(interactive=False)

    with pytest.raises(UsageError, match="not\ninteractive|not interactive"):
        prompt.ask("Name")


def test_confirm_takes_its_default_without_a_terminal():
    prompt, _ = build(interactive=False)

    assert prompt.confirm("Continue", default=True) is True
    assert prompt.confirm("Continue", default=False) is False


def test_choice_takes_its_default_without_a_terminal():
    prompt, _ = build(interactive=False)

    assert prompt.choice("Pick", ["a", "b"], default="b") == "b"


def test_multichoice_takes_its_defaults_without_a_terminal():
    prompt, _ = build(interactive=False)

    assert prompt.multichoice("Pick", ["a", "b", "c"], defaults=["a", "c"]) == ["a", "c"]


def test_a_secret_is_never_read_from_a_pipe():
    prompt, _ = build(interactive=False)

    with pytest.raises(UsageError, match="non-interactive"):
        prompt.secret("Password")


# -- text --------------------------------------------------------------


def test_ask_returns_what_was_typed():
    prompt, _ = build("ada\n")

    assert prompt.ask("Name") == "ada"


def test_ask_returns_the_default_on_an_empty_line():
    prompt, _ = build("\n")

    assert prompt.ask("Name", default="ada") == "ada"


def test_ask_shows_the_default_in_the_question():
    prompt, stream = build("\n")

    prompt.ask("Name", default="ada")

    assert "(ada)" in stream.getvalue()


def test_ask_repeats_until_something_is_typed():
    prompt, stream = build("\nada\n")

    assert prompt.ask("Name") == "ada"
    assert "An answer is required." in stream.getvalue()


def test_a_validator_may_reject_with_a_message():
    prompt, stream = build("x\nada@example.com\n")

    def validate(value):
        return None if "@" in value else "That is not an email address."

    assert prompt.ask("Email", validate=validate) == "ada@example.com"
    assert "That is not an email address." in stream.getvalue()


def test_a_validator_checks_rather_than_transforms():
    # A validator that returns a string is rejecting with that message, so a
    # normaliser like str.lower cannot double as one. The answer comes back
    # exactly as it was typed.
    prompt, _ = build("  ADA \n")

    assert prompt.ask("Name", validate=lambda value: True) == "ADA"


def test_a_validator_may_reject_by_returning_false():
    prompt, stream = build("x\nok\n")

    assert prompt.ask("Name", validate=lambda value: value != "x") == "ok"
    assert "not a valid answer" in stream.getvalue()


def test_a_validator_may_raise():
    prompt, stream = build("x\nok\n")

    def validate(value):
        if value == "x":
            raise ValueError("no")

    assert prompt.ask("Name", validate=validate) == "ok"
    assert "no" in stream.getvalue()


def test_input_that_runs_out_aborts():
    prompt, _ = build("")

    with pytest.raises(Abort):
        prompt.ask("Name")


# -- confirm -----------------------------------------------------------


@pytest.mark.parametrize("typed,expected", [("y", True), ("yes", True), ("Y", True)])
def test_confirm_accepts_yes(typed, expected):
    prompt, _ = build(f"{typed}\n")

    assert prompt.confirm("Continue") is expected


@pytest.mark.parametrize("typed", ["n", "no", "N"])
def test_confirm_accepts_no(typed):
    prompt, _ = build(f"{typed}\n")

    assert prompt.confirm("Continue", default=True) is False


def test_confirm_returns_the_default_on_enter():
    prompt, _ = build("\n")

    assert prompt.confirm("Continue", default=True) is True


def test_confirm_shows_which_way_enter_goes():
    prompt, stream = build("\n")

    prompt.confirm("Continue", default=True)

    assert "[Y/n]" in stream.getvalue()


def test_confirm_repeats_on_anything_else():
    prompt, stream = build("maybe\ny\n")

    assert prompt.confirm("Continue") is True
    assert "Answer y or n." in stream.getvalue()


# -- choice ------------------------------------------------------------


def test_choice_returns_the_highlighted_option():
    prompt, _ = build(ENTER)

    assert prompt.choice("Pick", ["a", "b", "c"]) == "a"


def test_the_arrow_keys_move_the_highlight():
    prompt, _ = build(DOWN + DOWN + ENTER)

    assert prompt.choice("Pick", ["a", "b", "c"]) == "c"


def test_the_highlight_wraps_at_the_top():
    prompt, _ = build(UP + ENTER)

    assert prompt.choice("Pick", ["a", "b", "c"]) == "c"


def test_choice_opens_on_its_default():
    prompt, _ = build(ENTER)

    assert prompt.choice("Pick", ["a", "b", "c"], default="b") == "b"


def test_choice_returns_the_value_of_a_labelled_pair():
    prompt, _ = build(DOWN + ENTER)
    options = [(1, "First"), (2, "Second")]

    assert prompt.choice("Pick", options) == 2


def test_choice_echoes_the_chosen_label():
    prompt, stream = build(DOWN + ENTER)

    prompt.choice("Pick", [(1, "First"), (2, "Second")])

    assert "Second" in strip_ansi(stream.getvalue())


def test_ctrl_c_aborts_a_choice():
    prompt, _ = build(CTRL_C)

    with pytest.raises(Abort):
        prompt.choice("Pick", ["a", "b"])


def test_escape_aborts_a_choice():
    prompt, _ = build(ESCAPE)

    with pytest.raises(Abort):
        prompt.choice("Pick", ["a", "b"])


def test_choice_needs_options():
    prompt, _ = build(ENTER)

    with pytest.raises(ValueError, match="at least one option"):
        prompt.choice("Pick", [])


def test_typing_filters_a_searchable_list():
    # 'c' narrows the list to cherry, which then becomes the highlight.
    prompt, _ = build("c" + ENTER)
    options = ["apple", "banana", "cherry"]

    assert prompt.choice("Pick", options, search=True) == "cherry"


def test_backspace_widens_the_filter_but_keeps_the_highlight():
    # Widening the list should not yank the highlight back to the top; the
    # user is still looking at what they filtered down to.
    prompt, _ = build("c\x7f" + ENTER)
    options = ["apple", "banana", "cherry"]

    assert prompt.choice("Pick", options, search=True) == "cherry"


def test_backspace_brings_the_filtered_out_options_back():
    # Filtered to cherry, then unfiltered: moving up must now be able to reach
    # an option the filter had excluded.
    prompt, _ = build("c\x7f" + UP + ENTER)
    options = ["apple", "banana", "cherry"]

    assert prompt.choice("Pick", options, search=True) == "banana"


def test_a_long_list_only_draws_a_window():
    prompt, stream = build(ENTER)
    options = [f"option-{number}" for number in range(30)]

    prompt.choice("Pick", options, search=False)

    assert "more" in stream.getvalue()


# -- multichoice -------------------------------------------------------


def test_space_toggles_and_enter_accepts():
    prompt, _ = build(SPACE + ENTER)

    assert prompt.multichoice("Pick", ["a", "b", "c"]) == ["a"]


def test_several_options_can_be_ticked():
    prompt, _ = build(SPACE + DOWN + DOWN + SPACE + ENTER)

    assert prompt.multichoice("Pick", ["a", "b", "c"]) == ["a", "c"]


def test_space_twice_unticks():
    prompt, _ = build(SPACE + SPACE + ENTER)

    assert prompt.multichoice("Pick", ["a", "b"]) == []


def test_multichoice_opens_with_its_defaults_ticked():
    prompt, _ = build(ENTER)

    assert prompt.multichoice("Pick", ["a", "b"], defaults=["b"]) == ["b"]


def test_multichoice_returns_values_in_declaration_order():
    prompt, _ = build(DOWN + DOWN + SPACE + UP + UP + SPACE + ENTER)

    assert prompt.multichoice("Pick", ["a", "b", "c"]) == ["a", "c"]


def test_a_minimum_is_enforced():
    prompt, stream = build(ENTER + SPACE + ENTER)

    assert prompt.multichoice("Pick", ["a", "b"], minimum=1) == ["a"]
    assert "Choose at least 1." in stream.getvalue()


def test_multichoice_needs_options():
    prompt, _ = build(ENTER)

    with pytest.raises(ValueError, match="at least one option"):
        prompt.multichoice("Pick", [])


# -- destructive confirmation ------------------------------------------


def test_a_destructive_action_needs_the_phrase_typed_back():
    prompt, _ = build("production\n")

    assert prompt.confirm_destructive("This drops the database.", "production") is True


def test_the_wrong_phrase_does_not_confirm():
    prompt, _ = build("yes\n")

    assert prompt.confirm_destructive("This drops the database.", "production") is False


def test_a_destructive_action_never_confirms_without_a_terminal():
    prompt, _ = build(interactive=False)

    assert prompt.confirm_destructive("This drops it.", "production") is False


# -- secrets -----------------------------------------------------------


def test_a_secret_is_read_without_echoing(monkeypatch):
    prompt, _ = build()
    monkeypatch.setattr("getpass.getpass", lambda *a, **k: "hunter2")

    assert prompt.secret("Password") == "hunter2"


def test_a_confirmed_secret_must_match(monkeypatch):
    prompt, stream = build()
    answers = iter(["first", "second", "same", "same"])
    monkeypatch.setattr("getpass.getpass", lambda *a, **k: next(answers))

    assert prompt.secret("Password", confirm=True) == "same"
    assert "They do not match." in stream.getvalue()


def test_an_empty_secret_is_rejected(monkeypatch):
    prompt, stream = build()
    answers = iter(["", "hunter2"])
    monkeypatch.setattr("getpass.getpass", lambda *a, **k: next(answers))

    assert prompt.secret("Password") == "hunter2"
    assert "An answer is required." in stream.getvalue()


def test_interrupting_a_secret_aborts(monkeypatch):
    prompt, _ = build()

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("getpass.getpass", interrupt)

    with pytest.raises(Abort):
        prompt.secret("Password")
