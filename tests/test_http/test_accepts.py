"""
Content negotiation.

Pure functions over one header, which makes them cheap to test and worth
testing: getting a q-value comparison backwards means serving XML to a client
that asked for JSON, and nothing about that fails loudly.
"""

from __future__ import annotations

import pytest

from sillo.http.accepts import (
    create_vary_header,
    get_best_match,
    matches_media_type,
    negotiate_charset,
    negotiate_content_type,
    negotiate_encoding,
    negotiate_language,
    parse_accept_charset,
    parse_accept_encoding,
    parse_accept_header,
    parse_accept_language,
)


class TestParsing:
    def test_a_single_type(self):
        assert [item.value for item in parse_accept_header("text/html")] == [
            "text/html"
        ]

    def test_equally_weighted_types_are_reordered(self):
        """Documenting rather than endorsing. RFC 7231 breaks a quality tie on
        specificity, and leaves equally specific types in the order the client
        wrote them — so `Accept: text/html, application/json` should prefer
        HTML. This sorts it the other way."""
        parsed = parse_accept_header("text/html, application/json")
        assert [item.value for item in parsed] == ["application/json", "text/html"]

    def test_quality_decides_the_order(self):
        parsed = parse_accept_header("text/html;q=0.2, application/json;q=0.9")
        assert parsed[0].value == "application/json"

    def test_an_absent_quality_is_one(self):
        assert parse_accept_header("text/html")[0].quality == 1.0

    def test_a_quality_of_zero_is_kept_and_ranked_last(self):
        """A q=0 is a client saying "not this", which is information."""
        parsed = parse_accept_header("text/html;q=0, application/json")
        assert parsed[-1].value == "text/html"

    def test_whitespace_is_tolerated(self):
        parsed = parse_accept_header("  text/html ;  q=0.8  ,  application/json  ")
        assert len(parsed) == 2

    def test_an_empty_header_parses_to_nothing(self):
        assert parse_accept_header("") == []

    def test_a_malformed_quality_does_not_raise(self):
        assert parse_accept_header("text/html;q=banana") != []

    def test_parameters_beyond_quality_are_kept(self):
        parsed = parse_accept_header("text/html;level=1;q=0.5")
        assert parsed[0].quality == 0.5

    def test_languages_parse(self):
        parsed = parse_accept_language("en-GB, en;q=0.8, fr;q=0.5")
        assert [item.value for item in parsed] == ["en-GB", "en", "fr"]

    def test_charsets_parse(self):
        assert parse_accept_charset("utf-8, iso-8859-1;q=0.5")[0].value == "utf-8"

    def test_encodings_parse(self):
        assert parse_accept_encoding("gzip, br;q=0.9")[0].value == "gzip"


class TestMatching:
    @pytest.mark.parametrize(
        "pattern,media,expected",
        [
            ("text/html", "text/html", True),
            ("text/*", "text/html", True),
            ("*/*", "anything/at-all", True),
            ("text/html", "text/plain", False),
            ("text/*", "application/json", False),
            ("application/json", "application/json", True),
        ],
    )
    def test_patterns(self, pattern, media, expected):
        assert matches_media_type(pattern, media) is expected


class TestNegotiation:
    def test_the_client_gets_what_it_asked_for(self):
        assert (
            negotiate_content_type(
                "application/json", ["application/json", "text/html"]
            )
            == "application/json"
        )

    def test_quality_decides_between_two_it_can_have(self):
        chosen = negotiate_content_type(
            "text/html;q=0.3, application/json;q=0.9",
            ["text/html", "application/json"],
        )
        assert chosen == "application/json"

    def test_a_wildcard_takes_the_first_on_offer(self):
        assert (
            negotiate_content_type("*/*", ["text/html", "application/json"])
            == "text/html"
        )

    def test_a_subtype_wildcard_is_honoured(self):
        assert (
            negotiate_content_type("text/*", ["application/json", "text/csv"])
            == "text/csv"
        )

    def test_nothing_acceptable_is_none(self):
        assert negotiate_content_type("application/xml", ["application/json"]) is None

    def test_an_empty_header_takes_the_first_on_offer(self):
        """No preference stated is not the same as no preference satisfiable."""
        assert negotiate_content_type("", ["application/json"]) == "application/json"

    def test_a_language_is_negotiated(self):
        assert negotiate_language("fr;q=0.9, en;q=0.5", ["en", "fr"]) == "fr"

    def test_an_unavailable_language_falls_back(self):
        """Unlike content type, which returns None. A page in the wrong
        language is more use than no page."""
        assert negotiate_language("de", ["en", "fr"]) == "en"

    def test_a_charset_is_negotiated(self):
        assert negotiate_charset("utf-8", ["utf-8", "iso-8859-1"]) == "utf-8"

    def test_encoding_negotiation_returns_a_list(self):
        """The odd one out: every other negotiate_* returns `str | None` and
        this returns every acceptable encoding. Worth knowing before treating
        the result as a header value."""
        assert negotiate_encoding("gzip, deflate", ["deflate", "gzip"]) == [
            "deflate",
            "gzip",
        ]

    def test_the_best_match_helper_agrees_with_negotiation(self):
        assert (
            get_best_match("application/json", ["application/json"])
            == "application/json"
        )

    def test_the_best_match_falls_back_to_the_first_option(self):
        """Rather than None, so a caller always has something to serve."""
        assert (
            get_best_match("application/xml", ["application/json"])
            == "application/json"
        )


class TestVary:
    def test_a_field_is_added_where_there_was_none(self):
        assert create_vary_header(None, ["Accept"]) == "Accept"

    def test_a_field_is_appended(self):
        header = create_vary_header("Accept", ["Accept-Language"])
        assert "Accept" in header and "Accept-Language" in header

    def test_a_field_is_not_duplicated(self):
        """A Vary header listing Accept twice is a cache key nobody wants to
        reason about."""
        header = create_vary_header("Accept", ["Accept"])
        assert header.lower().count("accept") == 1

    def test_several_fields_at_once(self):
        header = create_vary_header(None, ["Accept", "Accept-Encoding"])
        assert "Accept" in header and "Accept-Encoding" in header

    def test_an_empty_addition_leaves_it_alone(self):
        assert create_vary_header("Accept", []) == "Accept"
