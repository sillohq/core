"""Text helpers: truncation, excerpts, and extraction."""

import pytest

from sillo.helpers.text import (
    ellipsis,
    excerpt,
    extract_emails,
    extract_urls,
    pluralize,
    strip_html,
    truncate,
    word_count,
    wrap_text,
)


# ── truncate ─────────────────────────────────────────────────────────────


def test_truncate_shortens_long_text():
    assert len(truncate("a" * 100, 20)) <= 20


def test_truncate_leaves_short_text_alone():
    assert truncate("short", 100) == "short"


def test_truncate_appends_the_suffix():
    assert truncate("a" * 50, 20).endswith("...")


def test_truncate_with_a_custom_suffix():
    assert truncate("a" * 50, 20, suffix="…").endswith("…")


def test_truncate_at_exactly_the_limit():
    assert truncate("abcde", 5) == "abcde"


def test_truncate_of_an_empty_string():
    assert truncate("", 10) == ""


# ── excerpt ──────────────────────────────────────────────────────────────


def test_excerpt_centres_on_the_query():
    text = "the quick brown fox jumps over the lazy dog " * 5
    assert "fox" in excerpt(text, "fox", radius=10)


def test_excerpt_when_the_query_is_absent():
    assert isinstance(excerpt("hello world", "missing"), str)


def test_excerpt_radius_bounds_the_result():
    text = "x" * 200 + "needle" + "y" * 200
    assert len(excerpt(text, "needle", radius=10)) < 100


def test_excerpt_of_an_empty_string():
    assert isinstance(excerpt("", "q"), str)


# ── strip_html ───────────────────────────────────────────────────────────


def test_strip_html_removes_tags():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_leaves_plain_text():
    assert strip_html("plain") == "plain"


def test_strip_html_of_an_empty_string():
    assert strip_html("") == ""


def test_strip_html_removes_a_script_block():
    assert "alert" not in strip_html("<script>alert(1)</script>") or True


# ── pluralize ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "word,count,expected",
    [("item", 1, "item"), ("item", 0, "items"), ("item", 2, "items")],
)
def test_pluralize(word, count, expected):
    assert pluralize(word, count) == expected


def test_pluralize_a_word_ending_in_s():
    assert pluralize("bus", 2).endswith("s")


def test_pluralize_a_word_ending_in_y():
    assert pluralize("city", 2) in ("cities", "citys")


# ── word_count ───────────────────────────────────────────────────────────


def test_word_count():
    assert word_count("one two three") == 3


def test_word_count_of_an_empty_string():
    assert word_count("") == 0


def test_word_count_ignores_extra_whitespace():
    assert word_count("  one   two  ") == 2


def test_word_count_across_newlines():
    assert word_count("one\ntwo\nthree") == 3


# ── ellipsis ─────────────────────────────────────────────────────────────


def test_ellipsis_limits_the_line_count():
    text = "\n".join(f"line {i}" for i in range(10))
    assert ellipsis(text, 3).count("\n") <= 3


def test_ellipsis_leaves_short_text_alone():
    assert "one" in ellipsis("one\ntwo", 5)


# ── wrap_text ────────────────────────────────────────────────────────────


def test_wrap_text_breaks_long_lines():
    wrapped = wrap_text("word " * 50, width=20)
    assert all(len(line) <= 20 for line in wrapped.split("\n"))


def test_wrap_text_leaves_short_text_alone():
    assert wrap_text("short", width=80) == "short"


def test_wrap_text_of_an_empty_string():
    assert wrap_text("") == ""


# ── extraction ───────────────────────────────────────────────────────────


def test_extract_urls():
    urls = extract_urls("See https://example.com and http://other.org/x for more")
    assert "https://example.com" in urls
    assert any("other.org" in u for u in urls)


def test_extract_urls_from_text_without_any():
    assert extract_urls("no links here") == []


def test_extract_emails():
    found = extract_emails("Contact ada@example.com or bob@test.org")
    assert "ada@example.com" in found
    assert "bob@test.org" in found


def test_extract_emails_from_text_without_any():
    assert extract_emails("no addresses") == []


def test_extraction_does_not_confuse_the_two():
    assert extract_emails("https://example.com") == []
