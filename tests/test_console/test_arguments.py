"""Parsing a command line against declared parameters."""

from __future__ import annotations

import pytest

from sillo.console import Argument, Flag, Option, UsageError, parse


# -- positionals -------------------------------------------------------


def test_positional_arguments_fill_in_declaration_order():
    parameters = [Argument("email"), Argument("username")]

    parsed = parse(parameters, ["ada@example.com", "ada"])

    assert parsed.get("email") == "ada@example.com"
    assert parsed.get("username") == "ada"


def test_a_missing_required_argument_is_a_usage_error():
    with pytest.raises(UsageError, match="missing argument <EMAIL>"):
        parse([Argument("email")], [])


def test_an_argument_with_a_default_is_optional():
    parsed = parse([Argument("name", default="initial")], [])

    assert parsed.get("name") == "initial"


def test_a_surplus_positional_is_reported():
    with pytest.raises(UsageError, match="unexpected argument 'extra'"):
        parse([Argument("name")], ["one", "extra"])


def test_a_variadic_argument_collects_the_rest():
    parameters = [Argument("target"), Argument("files", variadic=True)]

    parsed = parse(parameters, ["build", "a.py", "b.py", "c.py"])

    assert parsed.get("target") == "build"
    assert parsed.get("files") == ["a.py", "b.py", "c.py"]


def test_a_variadic_argument_may_collect_nothing():
    parsed = parse([Argument("files", variadic=True)], [])

    assert parsed.get("files") == []


def test_a_variadic_argument_must_come_last():
    parameters = [Argument("files", variadic=True), Argument("target")]

    with pytest.raises(ValueError, match="must be the last argument"):
        parse(parameters, [])


# -- options -----------------------------------------------------------


def test_a_long_option_takes_the_next_token():
    parsed = parse([Option("limit", type=int)], ["--limit", "20"])

    assert parsed.get("limit") == 20


def test_a_long_option_accepts_an_inline_value():
    parsed = parse([Option("limit", type=int)], ["--limit=20"])

    assert parsed.get("limit") == 20


def test_a_short_option_takes_the_next_token():
    parsed = parse([Option("limit", type=int, short="l")], ["-l", "20"])

    assert parsed.get("limit") == 20


def test_a_short_option_accepts_an_attached_value():
    parsed = parse([Option("limit", type=int, short="l")], ["-l20"])

    assert parsed.get("limit") == 20


def test_an_option_falls_back_to_its_default():
    parsed = parse([Option("limit", type=int, default=50)], [])

    assert parsed.get("limit") == 50


def test_an_option_missing_its_value_is_reported():
    with pytest.raises(UsageError, match="--limit needs a value"):
        parse([Option("limit")], ["--limit"])


def test_a_repeatable_option_collects_every_value():
    parsed = parse(
        [Option("queue", multiple=True)],
        ["--queue", "mail", "--queue", "reports"],
    )

    assert parsed.get("queue") == ["mail", "reports"]


def test_a_repeatable_option_defaults_to_an_empty_list():
    parsed = parse([Option("queue", multiple=True)], [])

    assert parsed.get("queue") == []


def test_a_required_option_must_be_given():
    with pytest.raises(UsageError, match="missing required option --url"):
        parse([Option("url", required=True)], [])


def test_an_unknown_long_option_is_reported():
    with pytest.raises(UsageError, match="unknown option --nope"):
        parse([], ["--nope"])


def test_an_unknown_short_option_is_reported():
    with pytest.raises(UsageError, match="unknown option -z"):
        parse([], ["-z"])


# -- flags -------------------------------------------------------------


def test_a_flag_is_off_until_named():
    parsed = parse([Flag("staff")], [])

    assert parsed.get("staff") is False


def test_naming_a_flag_turns_it_on():
    parsed = parse([Flag("staff")], ["--staff"])

    assert parsed.get("staff") is True


def test_a_flag_that_defaults_on_is_turned_off_by_the_no_form():
    parsed = parse([Flag("color", default=True)], ["--no-color"])

    assert parsed.get("color") is False


def test_a_flag_that_defaults_on_stays_on_when_absent():
    parsed = parse([Flag("color", default=True)], [])

    assert parsed.get("color") is True


def test_a_flag_rejects_an_inline_value():
    with pytest.raises(UsageError, match="takes no value"):
        parse([Flag("staff")], ["--staff=yes"])


def test_short_flags_bundle():
    parameters = [Flag("all", short="a"), Flag("verbose", short="v")]

    parsed = parse(parameters, ["-av"])

    assert parsed.get("all") is True
    assert parsed.get("verbose") is True


def test_a_bundle_may_end_in_an_option_value():
    parameters = [Flag("all", short="a"), Option("limit", type=int, short="l")]

    parsed = parse(parameters, ["-al5"])

    assert parsed.get("all") is True
    assert parsed.get("limit") == 5


# -- conversion and validation -----------------------------------------


def test_a_value_that_will_not_convert_is_reported():
    with pytest.raises(UsageError, match="'x' is not a valid int"):
        parse([Option("limit", type=int)], ["--limit", "x"])


def test_a_value_outside_the_choices_is_reported():
    parameters = [Option("role", choices=["admin", "owner"])]

    with pytest.raises(UsageError, match="not one of admin, owner"):
        parse(parameters, ["--role", "guest"])


def test_a_value_inside_the_choices_is_accepted():
    parameters = [Option("role", choices=["admin", "owner"])]

    assert parse(parameters, ["--role", "owner"]).get("role") == "owner"


def test_choices_are_checked_after_conversion():
    parameters = [Option("port", type=int, choices=[80, 443])]

    assert parse(parameters, ["--port", "443"]).get("port") == 443


# -- structure ---------------------------------------------------------


def test_a_double_dash_stops_option_parsing():
    parsed = parse([Flag("staff")], ["--", "--staff", "raw"])

    assert parsed.get("staff") is False
    assert parsed.extra == ["--staff", "raw"]


def test_dashes_and_underscores_name_the_same_parameter():
    parsed = parse([Flag("dry-run")], ["--dry-run"])

    assert parsed.get("dry_run") is True
    assert parsed.get("dry-run") is True


def test_a_duplicate_name_is_rejected():
    with pytest.raises(ValueError, match="declared twice"):
        parse([Option("limit"), Option("limit")], [])


def test_a_duplicate_short_name_is_rejected():
    parameters = [Option("limit", short="l"), Option("level", short="l")]

    with pytest.raises(ValueError, match="-l is declared twice"):
        parse(parameters, [])


def test_a_short_name_must_be_one_character():
    with pytest.raises(ValueError, match="must be one character"):
        Option("limit", short="li")


def test_a_parameter_needs_a_name():
    with pytest.raises(ValueError, match="needs a name"):
        Argument("")


# -- reading values back -----------------------------------------------


def test_reading_an_undeclared_parameter_says_so():
    parsed = parse([Flag("staff")], [])

    with pytest.raises(KeyError, match="no parameter named 'nope'"):
        parsed.get("nope")


def test_reading_a_flag_as_an_option_reports_the_mismatch():
    parsed = parse([Flag("staff")], [])

    with pytest.raises(KeyError, match=r"declared as flag, not option"):
        parsed.get("staff", "option")


def test_membership_uses_either_spelling():
    parsed = parse([Flag("dry-run")], [])

    assert "dry_run" in parsed
    assert "dry-run" in parsed
    assert "nope" not in parsed


def test_the_usage_fragment_marks_optional_arguments():
    assert Argument("name").usage() == "<NAME>"
    assert Argument("name", default="x").usage() == "[NAME]"
    assert Argument("files", variadic=True).usage() == "[FILES...]"


# -- the difference between no default and a default of None -----------


def test_an_argument_with_no_default_is_required():
    with pytest.raises(UsageError, match="missing argument <NAME>"):
        parse([Argument("name")], [])


def test_an_argument_defaulting_to_none_is_optional():
    # None is a perfectly good default, so it cannot also mean "no default was
    # given". Without the distinction this argument stays required and the
    # command it belongs to can never be called without it.
    parsed = parse([Argument("name", default=None)], [])

    assert parsed.get("name") is None


def test_an_argument_defaulting_to_none_still_accepts_a_value():
    parsed = parse([Argument("name", default=None)], ["given"])

    assert parsed.get("name") == "given"


def test_an_option_defaulting_to_none_is_reported_as_having_one():
    assert Option("limit", default=None).has_default is True
    assert Option("limit").has_default is False


def test_a_repeatable_option_with_an_explicit_default_keeps_it():
    parsed = parse([Option("queue", multiple=True, default=["mail"])], [])

    assert parsed.get("queue") == ["mail"]
