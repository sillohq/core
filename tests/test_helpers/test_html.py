"""
HTML escaping and sanitization.

These guard against XSS, so the malicious-input cases are the point rather
than an afterthought.
"""

import pytest

from sillo.helpers.html import (
    escape_html,
    generate_safe_id,
    linkify,
    safe_attrs,
    sanitize_html,
    strip_tags,
    unescape_html,
)


# ── escaping ─────────────────────────────────────────────────────────────


def test_escape_angle_brackets():
    assert "<" not in escape_html("<script>")


def test_escape_ampersand():
    assert escape_html("a & b") == "a &amp; b"


def test_escape_quotes():
    escaped = escape_html('say "hi"')
    assert '"' not in escaped or "&quot;" in escaped


def test_escape_leaves_plain_text_alone():
    assert escape_html("plain text") == "plain text"


def test_escape_of_an_empty_string():
    assert escape_html("") == ""


def test_escaping_a_script_tag_neutralizes_it():
    assert "<script>" not in escape_html("<script>alert(1)</script>")


def test_unescape_round_trips():
    original = '<a href="x">&</a>'
    assert unescape_html(escape_html(original)) == original


def test_unescape_named_entities():
    assert unescape_html("&lt;b&gt;") == "<b>"


# ── strip_tags ───────────────────────────────────────────────────────────


def test_strip_tags_keeps_the_text():
    assert strip_tags("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_tags_on_plain_text():
    assert strip_tags("plain") == "plain"


def test_strip_tags_of_an_empty_string():
    assert strip_tags("") == ""


def test_strip_tags_handles_unclosed_tags():
    assert isinstance(strip_tags("<p>unclosed"), str)


# ── sanitize_html ────────────────────────────────────────────────────────


def test_sanitize_removes_a_script_tag():
    assert "script" not in sanitize_html("<p>ok</p><script>alert(1)</script>").lower()


def test_sanitize_keeps_allowed_tags():
    assert "<p>" in sanitize_html("<p>hello</p>", allowed_tags={"p"})


def test_sanitize_drops_disallowed_tags():
    assert "<b>" not in sanitize_html("<b>bold</b>", allowed_tags={"p"})


def test_sanitize_strips_an_onerror_handler():
    """Inline event handlers are the classic XSS vector."""
    result = sanitize_html('<img src="x" onerror="alert(1)">')
    assert "onerror" not in result.lower()


def test_sanitize_strips_a_javascript_url():
    result = sanitize_html('<a href="javascript:alert(1)">click</a>')
    assert "javascript:" not in result.lower()


def test_sanitize_of_an_empty_string():
    assert sanitize_html("") == ""


def test_sanitize_with_explicit_allowed_attrs():
    result = sanitize_html(
        '<a href="/x" title="t">link</a>',
        allowed_tags={"a"},
        allowed_attrs={"href"},
    )
    assert "href" in result


# ── safe_attrs ───────────────────────────────────────────────────────────


def test_safe_attrs_renders_pairs():
    out = safe_attrs({"class": "btn", "id": "x"})
    assert 'class="btn"' in out
    assert 'id="x"' in out


def test_safe_attrs_escapes_the_values():
    assert '"' not in safe_attrs({"title": 'a"b'}).split("=", 1)[1][1:-1]


def test_safe_attrs_of_an_empty_mapping():
    assert safe_attrs({}) == ""


def test_safe_attrs_neutralizes_an_injected_attribute():
    out = safe_attrs({"title": '" onload="alert(1)'})
    assert "onload=\"alert(1)\"" not in out


# ── generate_safe_id ─────────────────────────────────────────────────────


def test_safe_id_from_a_phrase():
    assert " " not in generate_safe_id("Hello World")


def test_safe_id_is_deterministic():
    assert generate_safe_id("Same Input") == generate_safe_id("Same Input")


def test_safe_id_strips_punctuation():
    result = generate_safe_id("Hello, World! #1")
    assert "," not in result and "!" not in result


def test_safe_id_of_an_empty_string():
    assert isinstance(generate_safe_id(""), str)


def test_safe_id_is_usable_as_an_html_id():
    result = generate_safe_id("123 starts with a digit")
    assert result and not result[0].isspace()


# ── linkify ──────────────────────────────────────────────────────────────


def test_linkify_wraps_a_url_in_an_anchor():
    assert "<a" in linkify("visit https://example.com now")


def test_linkify_leaves_text_without_urls_alone():
    assert "<a" not in linkify("no links here")


def test_linkify_of_an_empty_string():
    assert linkify("") == ""


def test_linkify_handles_several_urls():
    out = linkify("https://a.com and https://b.com")
    assert out.count("<a") == 2
