"""
Content negotiation: parsing Accept-* headers and picking the best match.

These are pure functions over header strings, so they are tested directly.
Quality-value ordering and wildcard handling are the parts most likely to
regress, so they are covered explicitly.
"""

import pytest

from sillo.http.accepts import (
    AcceptItem,
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


# ── parsing ──────────────────────────────────────────────────────────────


def test_parse_single_type():
    items = parse_accept_header("text/html")
    assert items[0].value == "text/html"
    assert items[0].quality == 1.0


def test_parse_sorts_by_descending_quality():
    items = parse_accept_header("text/plain;q=0.3, text/html;q=0.9, application/json")
    assert [i.value for i in items] == ["application/json", "text/html", "text/plain"]


def test_parse_captures_extra_parameters():
    items = parse_accept_header("text/html;level=1;q=0.5")
    assert items[0].params.get("level") == "1"
    assert items[0].quality == 0.5


def test_parse_empty_header():
    assert parse_accept_header("") == []


def test_parse_ignores_blank_segments():
    assert len(parse_accept_header("text/html, ,application/json")) == 2


def test_parse_malformed_quality_is_treated_as_unacceptable():
    """An unparseable q collapses to 0.0 rather than being assumed acceptable."""
    items = parse_accept_header("text/html;q=notanumber")
    assert items[0].quality == 0.0


def test_parse_language():
    items = parse_accept_language("en-GB, en;q=0.8, fr;q=0.5")
    assert [i.value for i in items] == ["en-GB", "en", "fr"]


def test_parse_charset():
    items = parse_accept_charset("utf-8, iso-8859-1;q=0.5")
    assert [i.value for i in items] == ["utf-8", "iso-8859-1"]


def test_parse_encoding():
    items = parse_accept_encoding("gzip, deflate;q=0.5, br;q=0.9")
    assert [i.value for i in items] == ["gzip", "br", "deflate"]


# ── media type matching ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "pattern,media_type,expected",
    [
        ("text/html", "text/html", True),
        ("text/html", "text/plain", False),
        ("text/*", "text/html", True),
        ("text/*", "application/json", False),
        ("*/*", "anything/at-all", True),
    ],
)
def test_matches_media_type(pattern, media_type, expected):
    assert matches_media_type(pattern, media_type) is expected


# ── content type negotiation ─────────────────────────────────────────────


def test_negotiate_picks_the_highest_quality_available():
    chosen = negotiate_content_type(
        "text/plain;q=0.3, application/json;q=0.9",
        ["text/plain", "application/json"],
    )
    assert chosen == "application/json"


def test_negotiate_honours_a_wildcard():
    assert negotiate_content_type("*/*", ["application/json"]) == "application/json"


def test_negotiate_honours_a_subtype_wildcard():
    assert negotiate_content_type("text/*", ["text/csv"]) == "text/csv"


def test_negotiate_returns_none_when_nothing_matches():
    assert negotiate_content_type("text/html", ["application/json"]) is None


def test_negotiate_skips_zero_quality():
    """q=0 means 'explicitly not acceptable'."""
    assert negotiate_content_type("application/json;q=0", ["application/json"]) is None


def test_negotiate_with_an_empty_header_takes_the_first_option():
    assert negotiate_content_type("", ["application/json", "text/html"]) is not None


# ── language, charset, encoding ──────────────────────────────────────────


def test_negotiate_language():
    assert negotiate_language("fr;q=0.9, en;q=0.5", ["en", "fr"]) == "fr"


def test_negotiate_language_falls_back_to_the_first_available():
    """A response must carry some language, so no match yields the default."""
    assert negotiate_language("de", ["en", "fr"]) == "en"


def test_negotiate_charset():
    assert negotiate_charset("utf-8, iso-8859-1;q=0.5", ["utf-8"]) == "utf-8"


def test_negotiate_charset_falls_back_to_the_first_available():
    assert negotiate_charset("iso-8859-1", ["utf-8"]) == "utf-8"


def test_negotiate_encoding_returns_every_acceptable_option():
    result = negotiate_encoding("gzip, br", ["gzip", "br", "deflate"])
    assert "gzip" in result and "br" in result


def test_negotiate_encoding_no_match():
    assert negotiate_encoding("compress", ["gzip"]) == []


# ── helpers ──────────────────────────────────────────────────────────────


def test_get_best_match():
    assert get_best_match("text/html, application/json;q=0.9", ["application/json"]) == (
        "application/json"
    )


def test_get_best_match_without_options():
    assert get_best_match("text/html", []) is None


def test_create_vary_header_from_nothing():
    assert create_vary_header(None, ["Accept"]) == "Accept"


def test_create_vary_header_appends():
    result = create_vary_header("Accept", ["Accept-Language"])
    assert "Accept" in result and "Accept-Language" in result


def test_create_vary_header_does_not_duplicate():
    assert create_vary_header("Accept", ["Accept"]).count("Accept") == 1


# ── AcceptItem ───────────────────────────────────────────────────────────


def test_accept_item_defaults():
    item = AcceptItem("text/html")
    assert item.quality == 1.0
    assert item.params == {}


def test_accept_item_repr_is_informative():
    assert "text/html" in repr(AcceptItem("text/html", 0.5))
