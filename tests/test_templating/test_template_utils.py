"""Template helper functions exposed as Jinja globals."""

from datetime import datetime
from pathlib import Path

import pytest

from sillo.templating.utils import (
    create_template_dir,
    format_datetime,
    get_template_globals,
    merge_dicts,
    static_hash,
    truncate,
)


# ── static_hash ──────────────────────────────────────────────────────────


def test_static_hash_of_a_real_file(tmp_path):
    f = tmp_path / "style.css"
    f.write_text("body { color: red }")
    assert len(static_hash(str(f))) == 8


def test_static_hash_is_stable_for_unchanged_content(tmp_path):
    f = tmp_path / "style.css"
    f.write_text("body { color: red }")
    assert static_hash(str(f)) == static_hash(str(f))


def test_static_hash_changes_when_the_file_changes(tmp_path):
    """This is the whole point — the hash is a cache-busting query string."""
    f = tmp_path / "style.css"
    f.write_text("body { color: red }")
    before = static_hash(str(f))
    f.write_text("body { color: blue }")
    assert static_hash(str(f)) != before


def test_static_hash_of_a_missing_file_is_empty():
    assert static_hash("/nonexistent/path/style.css") == ""


def test_static_hash_of_an_empty_file(tmp_path):
    f = tmp_path / "empty.css"
    f.write_bytes(b"")
    assert len(static_hash(str(f))) == 8


def test_static_hash_reads_binary_content(tmp_path):
    f = tmp_path / "logo.png"
    f.write_bytes(bytes(range(256)))
    assert len(static_hash(str(f))) == 8


# ── format_datetime ──────────────────────────────────────────────────────


def test_format_datetime_uses_the_default_format():
    assert format_datetime(datetime(2024, 3, 1, 9, 30, 0)) == "2024-03-01 09:30:00"


def test_format_datetime_with_a_custom_format():
    assert format_datetime(datetime(2024, 3, 1), "%d/%m/%Y") == "01/03/2024"


def test_format_datetime_with_a_date_only_format():
    assert format_datetime(datetime(2024, 12, 25, 18, 0), "%Y-%m-%d") == "2024-12-25"


# ── truncate ─────────────────────────────────────────────────────────────


def test_truncate_leaves_short_text_alone():
    assert truncate("short text", length=100) == "short text"


def test_truncate_at_exactly_the_limit():
    assert truncate("abcde", length=5) == "abcde"


def test_truncate_appends_the_suffix():
    assert truncate("word " * 50, length=20).endswith("...")


def test_truncate_breaks_on_a_word_boundary():
    """A mid-word cut looks like a typo, so the trim walks back to a space."""
    result = truncate("the quick brown fox jumps", length=13)
    assert result == "the quick..."


def test_truncate_with_a_custom_suffix():
    assert truncate("word " * 50, length=20, suffix="…").endswith("…")


def test_truncate_of_an_empty_string():
    assert truncate("") == ""


# ── merge_dicts ──────────────────────────────────────────────────────────


def test_merge_two_dicts():
    assert merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_later_dicts_win():
    assert merge_dicts({"a": 1}, {"a": 2}) == {"a": 2}


def test_merge_leaves_the_inputs_untouched():
    first = {"a": 1}
    merge_dicts(first, {"b": 2})
    assert first == {"a": 1}


def test_merge_of_no_dicts():
    assert merge_dicts() == {}


def test_merge_of_several_dicts():
    assert merge_dicts({"a": 1}, {"b": 2}, {"c": 3}, {"a": 9}) == {
        "a": 9,
        "b": 2,
        "c": 3,
    }


def test_merge_with_an_empty_dict():
    assert merge_dicts({"a": 1}, {}) == {"a": 1}


# ── get_template_globals ─────────────────────────────────────────────────


def test_template_globals_expose_the_expected_names():
    assert set(get_template_globals()) == {
        "now",
        "static_hash",
        "format_datetime",
        "truncate",
    }


def test_template_globals_are_callable():
    assert all(callable(fn) for fn in get_template_globals().values())


def test_the_now_global_returns_a_datetime():
    assert isinstance(get_template_globals()["now"](), datetime)


def test_the_truncate_global_is_the_real_function():
    assert get_template_globals()["truncate"] is truncate


# ── create_template_dir ──────────────────────────────────────────────────


def test_create_template_dir_makes_the_directory(tmp_path):
    target = tmp_path / "templates"
    created = create_template_dir(target)
    assert created.is_dir()


def test_create_template_dir_returns_a_path(tmp_path):
    assert isinstance(create_template_dir(tmp_path / "templates"), Path)


def test_create_template_dir_creates_parents(tmp_path):
    created = create_template_dir(tmp_path / "a" / "b" / "templates")
    assert created.is_dir()


def test_create_template_dir_is_idempotent(tmp_path):
    target = tmp_path / "templates"
    create_template_dir(target)
    assert create_template_dir(target).is_dir()


def test_create_template_dir_accepts_a_string(tmp_path):
    created = create_template_dir(str(tmp_path / "templates"))
    assert created.is_dir()


def test_create_template_dir_defaults_to_templates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert create_template_dir().name == "templates"
