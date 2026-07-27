"""
``Cookie`` header parsing.

The parser is deliberately browser-lenient rather than RFC-strict, so the
malformed inputs below are specified behaviour, not accidents: a single bad
cookie must never cost the request the rest of its cookies.
"""

import pytest

from sillo.core.http.cookies import parse_cookies


# ── the ordinary case ────────────────────────────────────────────────────


def test_a_single_cookie():
    assert parse_cookies("session=abc123") == {"session": "abc123"}


def test_several_cookies():
    assert parse_cookies("a=1; b=2; c=3") == {"a": "1", "b": "2", "c": "3"}


def test_surrounding_whitespace_is_trimmed():
    assert parse_cookies("  a = 1  ;  b = 2  ") == {"a": "1", "b": "2"}


def test_cookies_without_spaces_after_the_separator():
    assert parse_cookies("a=1;b=2") == {"a": "1", "b": "2"}


def test_a_later_duplicate_wins():
    assert parse_cookies("a=1; a=2") == {"a": "2"}


# ── empty and absent input ───────────────────────────────────────────────


def test_a_missing_header_gives_an_empty_mapping():
    assert parse_cookies(None) == {}


def test_an_empty_header_gives_an_empty_mapping():
    assert parse_cookies("") == {}


def test_a_header_of_only_separators():
    assert parse_cookies(";;;") == {}


def test_whitespace_only():
    assert parse_cookies("   ") == {}


# ── values ───────────────────────────────────────────────────────────────


def test_values_are_url_decoded():
    assert parse_cookies("name=John%20Doe") == {"name": "John Doe"}


def test_encoded_punctuation_is_decoded():
    assert parse_cookies("path=%2Fhome%2Fuser") == {"path": "/home/user"}


def test_a_value_may_contain_an_equals_sign():
    """Only the first ``=`` separates name from value, so base64 padding and
    signed values survive intact."""
    assert parse_cookies("token=abc=def=") == {"token": "abc=def="}


def test_an_empty_value_becomes_none():
    assert parse_cookies("a=") == {"a": None}


def test_a_bare_token_is_stored_under_the_empty_key():
    assert parse_cookies("justavalue") == {"": "justavalue"}


def test_a_quoted_value_keeps_its_quotes():
    assert parse_cookies('a="quoted"') == {"a": '"quoted"'}


def test_a_json_like_value_survives():
    assert parse_cookies("data=%7B%22k%22%3A1%7D") == {"data": '{"k":1}'}


# ── leniency ─────────────────────────────────────────────────────────────


def test_a_malformed_entry_does_not_lose_the_others():
    """One broken cookie in the header must not discard the valid ones."""
    assert parse_cookies("good=1; ; bad; other=2") == {
        "good": "1",
        "": "bad",
        "other": "2",
    }


def test_an_empty_name_with_a_value():
    assert parse_cookies("=orphan") == {"": "orphan"}


def test_a_percent_sign_that_is_not_an_escape_is_left_alone():
    assert parse_cookies("a=100%") == {"a": "100%"}


def test_the_result_is_a_plain_dict():
    assert type(parse_cookies("a=1")) is dict


def test_unicode_values_round_trip():
    assert parse_cookies("name=caf%C3%A9") == {"name": "café"}
