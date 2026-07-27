"""
String helpers: case conversion, slugs, masking, and secure randomness.

The masking helpers are used on secrets in logs and UIs, so the short-input
cases — where a naive implementation leaks the whole value — are covered
explicitly.
"""

import pytest

from sillo.helpers.strings import (
    camel_to_snake,
    is_camel_case,
    is_snake_case,
    kebab_case,
    mask_email,
    mask_string,
    pascal_case,
    random_digits,
    random_string,
    random_token,
    slugify,
    snake_to_camel,
    strip_accents,
)


# ── slugify ──────────────────────────────────────────────────────────────


def test_slugify_lowercases_and_joins_words():
    assert slugify("Hello, World!") == "hello-world"


def test_slugify_folds_accents_to_ascii():
    assert slugify("Héllo Wörld") == "hello-world"


def test_slugify_with_a_custom_separator():
    assert slugify("Hello World", separator="_") == "hello_world"


def test_slugify_collapses_runs_of_whitespace():
    assert slugify("too    many   spaces") == "too-many-spaces"


def test_slugify_drops_punctuation():
    assert slugify("What?! Really...") == "what-really"


def test_slugify_of_an_empty_string():
    assert slugify("") == ""


def test_slugify_of_whitespace_only():
    assert slugify("   ") == ""


def test_slugify_does_not_leave_edge_separators():
    result = slugify("  -- leading and trailing -- ")
    assert not result.startswith("-")
    assert not result.endswith("-")


def test_slugify_keeps_digits():
    assert slugify("Top 10 Tips") == "top-10-tips"


# ── camel_to_snake ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "given,expected",
    [
        ("myVariable", "my_variable"),
        ("MyVariable", "my_variable"),
        ("HTTPServer", "http_server"),
        ("parseHTTPResponse", "parse_http_response"),
        ("already_snake", "already_snake"),
        ("lower", "lower"),
        ("", ""),
    ],
)
def test_camel_to_snake(given, expected):
    assert camel_to_snake(given) == expected


def test_camel_to_snake_handles_trailing_digits():
    assert camel_to_snake("value2Name") == "value2_name"


# ── snake_to_camel and pascal_case ───────────────────────────────────────


def test_snake_to_camel():
    assert snake_to_camel("my_variable") == "myVariable"


def test_snake_to_camel_leaves_a_bare_word_alone():
    assert snake_to_camel("variable") == "variable"


def test_snake_to_camel_can_capitalize_the_first_letter():
    assert snake_to_camel("my_variable", capitalize_first=True) == "MyVariable"


def test_snake_to_camel_of_an_empty_string():
    """The capitalize branch must not index into an empty result."""
    assert snake_to_camel("", capitalize_first=True) == ""


def test_pascal_case():
    assert pascal_case("user_profile") == "UserProfile"


def test_pascal_case_of_a_single_word():
    assert pascal_case("user") == "User"


def test_snake_to_camel_handles_digits_after_underscores():
    assert snake_to_camel("field_1_name") == "field1Name"


# ── kebab_case ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "given,expected",
    [
        ("myVariable", "my-variable"),
        ("HTTPServer", "http-server"),
        ("lower", "lower"),
    ],
)
def test_kebab_case(given, expected):
    assert kebab_case(given) == expected


def test_case_conversions_round_trip():
    assert camel_to_snake(pascal_case("user_profile")) == "user_profile"


# ── mask_string ──────────────────────────────────────────────────────────


def test_mask_string_keeps_the_ends_visible():
    assert mask_string("1234567890123456") == "1234********3456"


def test_mask_string_preserves_the_length():
    value = "1234567890123456"
    assert len(mask_string(value)) == len(value)


def test_a_short_value_is_masked_entirely():
    """Anything at or below the visible budget must not leak — showing the
    first four and last four of a six-character secret would reveal all of it."""
    assert mask_string("abcdef") == "******"


def test_a_value_exactly_at_the_visible_budget_is_fully_masked():
    assert mask_string("12345678") == "********"


def test_mask_string_with_a_custom_character():
    assert mask_string("1234567890123456", mask_char="#") == "1234########3456"


def test_mask_string_with_custom_visible_widths():
    assert mask_string("1234567890", visible_start=2, visible_end=2) == "12******90"


def test_mask_string_of_an_empty_string():
    assert mask_string("") == ""


def test_mask_string_with_nothing_visible():
    """``value[-0:]`` is the whole string; asking for no visible suffix must
    not append the secret after the mask."""
    assert mask_string("secret-value", visible_start=0, visible_end=0) == "*" * 12


def test_mask_string_with_a_visible_prefix_but_no_suffix():
    assert mask_string("abcdefghij", visible_start=4, visible_end=0) == "abcd******"


def test_mask_string_with_a_visible_suffix_but_no_prefix():
    assert mask_string("abcdefghij", visible_start=0, visible_end=4) == "******ghij"


# ── mask_email ───────────────────────────────────────────────────────────


def test_mask_email_keeps_the_domain():
    assert mask_email("ada@example.com").endswith("@example.com")


def test_mask_email_keeps_the_first_and_last_local_characters():
    assert mask_email("adalovelace@example.com") == "a*********e@example.com"


def test_mask_email_of_a_two_character_local_part():
    assert mask_email("ab@x.com") == "a*@x.com"


def test_mask_email_of_a_one_character_local_part():
    assert mask_email("a@x.com") == "a*@x.com"


def test_mask_email_hides_the_middle():
    assert "dalovelac" not in mask_email("adalovelace@example.com")


# ── randomness ───────────────────────────────────────────────────────────


def test_random_string_has_the_requested_length():
    assert len(random_string(16)) == 16


def test_random_string_defaults_to_32_characters():
    assert len(random_string()) == 32


def test_random_strings_are_unique():
    assert len({random_string(16) for _ in range(100)}) == 100


def test_random_string_uses_only_the_given_alphabet():
    assert set(random_string(50, chars="ab")) <= {"a", "b"}


def test_random_string_of_zero_length():
    assert random_string(0) == ""


def test_random_digits_are_digits():
    assert random_digits(20).isdigit()


def test_random_digits_has_the_requested_length():
    assert len(random_digits(4)) == 4


def test_random_digits_defaults_to_six():
    assert len(random_digits()) == 6


def test_random_tokens_are_url_safe():
    token = random_token(32)
    assert set(token) <= set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )


def test_random_tokens_are_unique():
    assert len({random_token(16) for _ in range(50)}) == 50


def test_random_token_length_is_a_byte_count():
    """The argument is bytes of entropy, so the string comes out longer."""
    assert len(random_token(32)) >= 32


# ── strip_accents ────────────────────────────────────────────────────────


def test_strip_accents():
    assert strip_accents("café") == "cafe"


def test_strip_accents_across_a_phrase():
    assert strip_accents("Àéîõü") == "Aeiou"


def test_strip_accents_leaves_plain_ascii_alone():
    assert strip_accents("plain") == "plain"


def test_strip_accents_of_an_empty_string():
    assert strip_accents("") == ""


# ── format predicates ────────────────────────────────────────────────────


@pytest.mark.parametrize("text", ["myVariable", "MyVariable", "parseHTTP"])
def test_camel_case_is_recognised(text):
    assert is_camel_case(text) is True


@pytest.mark.parametrize("text", ["lowercase", "UPPERCASE", "my_Variable", ""])
def test_non_camel_case_is_rejected(text):
    assert is_camel_case(text) is False


@pytest.mark.parametrize("text", ["my_variable", "a_b_c"])
def test_snake_case_is_recognised(text):
    assert is_snake_case(text) is True


@pytest.mark.parametrize("text", ["myVariable", "nounderscore", "_private", ""])
def test_non_snake_case_is_rejected(text):
    assert is_snake_case(text) is False


def test_the_two_predicates_are_mutually_exclusive():
    for text in ("my_variable", "myVariable", "plain"):
        assert not (is_camel_case(text) and is_snake_case(text))
