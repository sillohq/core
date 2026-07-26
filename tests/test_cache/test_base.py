"""Tests for sillo.cache.base key building, serialization, and stats."""

import pytest

from sillo.cache.base import (
    CacheStats,
    build_key,
    deserialize,
    serialize,
    tag_key,
)


def test_build_key_deterministic():
    a = build_key("f", 1, 2, namespace="ns", version="v1")
    b = build_key("f", 1, 2, namespace="ns", version="v1")
    assert a == b


def test_build_key_differs_on_args():
    a = build_key("f", 1, namespace="ns")
    b = build_key("f", 2, namespace="ns")
    assert a != b


def test_build_key_namespace_and_version_isolate():
    base = build_key("f", 1)
    ns = build_key("f", 1, namespace="ns")
    ver = build_key("f", 1, namespace="ns", version="v2")
    assert base != ns != ver


def test_build_key_kwargs_order_independent():
    a = build_key("f", {"b": 2, "a": 1})
    b = build_key("f", {"a": 1, "b": 2})
    assert a == b


def test_tag_key_format():
    assert tag_key("ns", "t1") == "tag:ns:t1"
    assert tag_key(None, "t1") == "tag:_:t1"


def test_serialize_deserialize_json():
    payload = serialize({"x": 1, "y": [1, 2, 3]}, use_pickle=False)
    assert deserialize(payload) == {"x": 1, "y": [1, 2, 3]}


def test_serialize_deserialize_pickle():
    obj = {"set": {1, 2, 3}, "n": 5}
    payload = serialize(obj, use_pickle=True)
    assert deserialize(payload) == obj


def test_serialize_pickle_rejects_lambda():
    # JSON falls back to str() so it rarely fails; pickle refuses functions.
    payload = serialize(lambda: 1, use_pickle=False)
    assert payload.startswith(b"j:")
    with pytest.raises(Exception):
        serialize(lambda: 1, use_pickle=True)


def test_cache_stats_hit_rate():
    s = CacheStats()
    s.hits = 3
    s.misses = 1
    assert s.total == 4
    assert s.hit_rate == 0.75
    assert s.as_dict()["hit_rate"] == 0.75


def test_cache_stats_zero_total():
    assert CacheStats().hit_rate == 0.0
