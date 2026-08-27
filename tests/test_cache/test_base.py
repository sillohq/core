"""Tests for sillo.cache.base key building, serialization, and stats."""

import pytest

from sillo.cache.base import (
    BaseCache,
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


def test_deserialize_rejects_a_corrupt_payload():
    from sillo.cache.base import SerializationError

    with pytest.raises(SerializationError):
        deserialize(b"j:{not-valid-json")


def test_deserialize_legacy_payload_without_a_prefix():
    """Payloads written before the format-prefix scheme was added are still
    readable, treated as plain JSON."""
    import json as json_module

    payload = json_module.dumps({"legacy": True}).encode("utf-8")
    assert deserialize(payload) == {"legacy": True}


def test_cache_stats_hit_rate():
    s = CacheStats()
    s.hits = 3
    s.misses = 1
    assert s.total == 4
    assert s.hit_rate == 0.75
    assert s.as_dict()["hit_rate"] == 0.75


def test_cache_stats_zero_total():
    assert CacheStats().hit_rate == 0.0


# ── _stable_repr, via build_key (it is not exported) ─────────────────────


def test_build_key_stable_for_bytes():
    a = build_key(b"raw bytes")
    b = build_key(b"raw bytes")
    c = build_key(b"different")
    assert a == b != c


def test_build_key_set_is_order_independent():
    a = build_key({1, 2, 3})
    b = build_key({3, 2, 1})
    assert a == b


def test_build_key_list_and_nested_dict():
    a = build_key([1, {"a": 2}, (3, 4)])
    b = build_key([1, {"a": 2}, (3, 4)])
    assert a == b


def test_build_key_falls_back_to_repr_for_arbitrary_objects():
    class Thing:
        def __repr__(self):
            return "Thing<fixed>"

    a = build_key(Thing())
    b = build_key(Thing())
    assert a == b  # same repr -> same key


# ── _json_default, via serialize() ────────────────────────────────────────


def test_serialize_json_converts_sets_to_sorted_lists():
    payload = serialize({3, 1, 2}, use_pickle=False)
    assert deserialize(payload) == [1, 2, 3]


def test_serialize_json_uses_dunder_dict_for_plain_objects():
    class Point:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    payload = serialize(Point(1, 2), use_pickle=False)
    assert deserialize(payload) == {"x": 1, "y": 2}


def test_serialize_json_falls_back_to_str_for_dictless_objects():
    payload = serialize(1 + 2j, use_pickle=False)  # complex has no __dict__
    assert deserialize(payload) == str(1 + 2j)


# ── BaseCache ──────────────────────────────────────────────────────────────


class _ConcreteCache(BaseCache):
    name = "concrete"

    async def get(self, key):
        return None

    async def set(self, key, value, ttl=None, *, tags=None, sliding=False):
        pass

    async def delete(self, key):
        return False

    async def exists(self, key):
        return False

    async def touch(self, key, ttl=None):
        return False

    async def invalidate_tags(self, *tags):
        return 0

    async def clear(self):
        pass

    async def close(self):
        pass


def test_base_cache_rejects_an_unknown_serializer():
    with pytest.raises(ValueError, match="serializer must be"):
        _ConcreteCache(serializer="yaml")


def test_base_cache_stats_and_reset():
    cache = _ConcreteCache()
    stats = cache.stats()
    stats.hits = 5
    assert cache.stats().hits == 5

    cache.reset_stats()
    assert cache.stats().hits == 0


def test_base_cache_make_key_uses_backends_namespace():
    cache = _ConcreteCache(namespace="ns")
    assert cache.make_key("a") == build_key("a", namespace="ns")


def test_base_cache_resolve_ttl():
    cache = _ConcreteCache(default_ttl=60)
    assert cache._resolve_ttl(None) == 60
    assert cache._resolve_ttl(30) == 30


async def test_base_cache_as_async_context_manager():
    closed = []

    class TrackingCache(_ConcreteCache):
        async def close(self):
            closed.append(1)

    async with TrackingCache() as cache:
        assert isinstance(cache, TrackingCache)

    assert closed == [1]
