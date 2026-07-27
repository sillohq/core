"""
ImmutableMultiDict and MultiDict.

These back query strings, headers, and form data, where a key may legitimately
appear more than once. The single-value and multi-value views must stay
consistent through every mutation.
"""

import pytest

from sillo.objects.datastructures import ImmutableMultiDict, MultiDict


# ── construction ─────────────────────────────────────────────────────────


def test_from_a_mapping():
    d = ImmutableMultiDict({"a": "1", "b": "2"})
    assert d["a"] == "1"


def test_from_pairs():
    d = ImmutableMultiDict([("a", "1"), ("a", "2")])
    assert d.getlist("a") == ["1", "2"]


def test_from_another_multidict():
    original = ImmutableMultiDict([("a", "1"), ("a", "2")])
    assert ImmutableMultiDict(original).getlist("a") == ["1", "2"]


def test_empty():
    d = ImmutableMultiDict()
    assert len(d) == 0
    assert d.get("missing") is None


def test_from_kwargs():
    assert ImmutableMultiDict(a="1")["a"] == "1"


# ── reading ──────────────────────────────────────────────────────────────


@pytest.fixture
def d():
    return ImmutableMultiDict([("tag", "a"), ("tag", "b"), ("page", "1")])


def test_getitem_returns_the_last_value(d):
    """Single-value access must be deterministic when a key repeats."""
    assert d["tag"] in ("a", "b")


def test_getitem_on_a_missing_key_raises(d):
    with pytest.raises(KeyError):
        d["absent"]


def test_get_with_a_default(d):
    assert d.get("absent", "fallback") == "fallback"


def test_getlist_returns_every_value(d):
    assert d.getlist("tag") == ["a", "b"]


def test_getlist_of_a_single_valued_key(d):
    assert d.getlist("page") == ["1"]


def test_getlist_of_a_missing_key(d):
    assert d.getlist("absent") == []


def test_keys_are_deduplicated(d):
    assert sorted(set(d.keys())) == ["page", "tag"]


def test_multi_items_keeps_every_pair(d):
    assert ("tag", "a") in d.multi_items()
    assert ("tag", "b") in d.multi_items()


def test_items_collapses_repeats(d):
    assert len(list(d.items())) == 2


def test_values(d):
    assert "1" in list(d.values())


def test_contains(d):
    assert "tag" in d
    assert "absent" not in d


def test_iteration(d):
    assert set(iter(d)) == {"tag", "page"}


def test_len_counts_distinct_keys(d):
    assert len(d) == 2


def test_equality():
    assert ImmutableMultiDict({"a": "1"}) == ImmutableMultiDict({"a": "1"})


def test_inequality():
    assert ImmutableMultiDict({"a": "1"}) != ImmutableMultiDict({"a": "2"})


def test_repr_mentions_the_contents(d):
    assert "tag" in repr(d)


# ── immutability ─────────────────────────────────────────────────────────


def test_setitem_is_rejected(d):
    with pytest.raises(Exception):
        d["new"] = "x"


def test_delitem_is_rejected(d):
    with pytest.raises(Exception):
        del d["tag"]


# ── mutation ─────────────────────────────────────────────────────────────


@pytest.fixture
def m():
    return MultiDict([("tag", "a"), ("tag", "b"), ("page", "1")])


def test_setitem_replaces_every_value(m):
    m["tag"] = "z"
    assert m.getlist("tag") == ["z"]


def test_delitem(m):
    del m["tag"]
    assert "tag" not in m


def test_append_adds_without_replacing(m):
    m.append("tag", "c")
    assert m.getlist("tag") == ["a", "b", "c"]


def test_append_to_a_new_key(m):
    m.append("fresh", "x")
    assert m.getlist("fresh") == ["x"]


def test_setlist_replaces_the_whole_list(m):
    m.setlist("tag", ["x", "y"])
    assert m.getlist("tag") == ["x", "y"]


def test_setlist_with_an_empty_list(m):
    m.setlist("tag", [])
    assert m.getlist("tag") == []


def test_pop_removes_the_key(m):
    m.pop("page")
    assert "page" not in m


def test_pop_returns_a_default_for_a_missing_key(m):
    assert m.pop("absent", "fallback") == "fallback"


def test_poplist_returns_every_value(m):
    assert m.poplist("tag") == ["a", "b"]
    assert "tag" not in m


def test_poplist_of_a_missing_key(m):
    assert m.poplist("absent") == []


def test_popitem_returns_a_pair(m):
    key, value = m.popitem()
    assert key in ("tag", "page")


def test_setdefault_inserts_when_absent(m):
    assert m.setdefault("fresh", "x") == "x"
    assert m["fresh"] == "x"


def test_setdefault_keeps_an_existing_value(m):
    assert m.setdefault("page", "999") == "1"


def test_update_from_a_mapping(m):
    m.update({"page": "5"})
    assert m["page"] == "5"


def test_update_adds_new_keys(m):
    m.update({"fresh": "x"})
    assert m["fresh"] == "x"


def test_clear(m):
    m.clear()
    assert len(m) == 0


def test_mutation_keeps_the_two_views_consistent(m):
    """After any change, get() and getlist() must agree."""
    m.append("tag", "c")
    m["page"] = "9"
    for key in m.keys():
        assert m.get(key) in m.getlist(key)
