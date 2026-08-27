"""Coverage for sillo.storage.paths.segments/parent/join: pure helpers with
no prior tests (only normalise() and contain() were exercised elsewhere)."""

from __future__ import annotations

from sillo.storage.paths import join, parent, segments


def test_segments_splits_a_key_into_parts():
    assert segments("a/b/c.txt") == ("a", "b", "c.txt")


def test_segments_ignores_empty_parts():
    assert segments("a//b/") == ("a", "b")


def test_segments_of_a_top_level_key():
    assert segments("file.txt") == ("file.txt",)


def test_parent_of_a_nested_key():
    assert parent("a/b/c.txt") == "a/b/"


def test_parent_of_a_top_level_key_is_empty():
    assert parent("file.txt") == ""


def test_join_normalises_the_result():
    assert join("a/", "/b/", "c.txt") == "a/b/c.txt"


def test_join_ignores_empty_fragments():
    assert join("a", "", "b") == "a/b"
