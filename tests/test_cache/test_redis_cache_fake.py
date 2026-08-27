"""``RedisCache`` driven against ``fakeredis`` instead of skipping.

The backend accepts an externally-managed client, so the fake goes in through
the documented ``client=`` parameter and every method under test is the real
one. Without this the class was unreachable on any machine without a Redis
server — which is how the TTL and sliding-expiry bugs fixed in 0.0.1a15
reached a release in the first place.

Two contract details these tests depend on: a miss returns the ``_MISSING``
sentinel rather than ``None`` (``None`` is a storable value), and ``get``/
``set`` use the key exactly as given — namespacing is something the caller
applies with ``make_key``.
"""

import pytest

from sillo.cache.base import _MISSING
from sillo.cache.backends import RedisCache

fakeredis = pytest.importorskip(
    "fakeredis", reason="fakeredis provides the in-process Redis these tests need"
)
import fakeredis.aioredis  # noqa: E402


@pytest.fixture
def cache():
    return RedisCache(client=fakeredis.aioredis.FakeRedis(decode_responses=False))


class TestGetAndSet:
    async def test_a_value_round_trips(self, cache):
        await cache.set("k", {"a": 1})
        assert await cache.get("k") == {"a": 1}

    async def test_a_missing_key_returns_the_sentinel(self, cache):
        assert await cache.get("absent") is _MISSING

    async def test_a_stored_none_is_distinguishable_from_a_miss(self, cache):
        await cache.set("k", None)

        assert await cache.get("k") is None
        assert await cache.get("other") is _MISSING

    async def test_a_value_can_be_overwritten(self, cache):
        await cache.set("k", "first")
        await cache.set("k", "second")
        assert await cache.get("k") == "second"

    @pytest.mark.parametrize(
        "value", [1, 1.5, True, "text", [1, 2], {"nested": {"deep": 1}}]
    )
    async def test_json_serialisable_values_survive(self, cache, value):
        await cache.set("k", value)
        assert await cache.get("k") == value


class TestExpiry:
    async def test_an_expired_entry_reads_as_a_miss(self, cache):
        await cache.set("k", "v", ttl=50)
        assert await cache.get("k") == "v"

        await cache._client.delete("k")

        assert await cache.get("k") is _MISSING

    async def test_a_ttl_is_applied(self, cache):
        await cache.set("k", "v", ttl=50)
        assert 0 < await cache._client.ttl("k") <= 50

    async def test_reading_does_not_extend_a_fixed_ttl(self, cache):
        # A read used to refresh the TTL unconditionally, and a None ttl
        # resolves to default_ttl — so an entry written with ttl=1 had its
        # expiry pushed out to the backend default the moment anything read
        # it. An entry given one second lived sixty.
        await cache.set("k", "v", ttl=50)
        before = await cache._client.ttl("k")

        await cache.get("k")

        assert await cache._client.ttl("k") <= before

    async def test_a_sliding_entry_is_refreshed_on_read(self, cache):
        await cache.set("k", "v", ttl=50, sliding=True)
        await cache._client.expire("k", 5)

        await cache.get("k")

        assert await cache._client.ttl("k") > 5

    async def test_a_sliding_value_reads_back_as_itself(self, cache):
        # It used to come back as its internal wrapper:
        # {"_value": ..., "_sliding": True, ...}
        await cache.set("k", {"real": "value"}, ttl=50, sliding=True)
        assert await cache.get("k") == {"real": "value"}

    async def test_touch_extends_an_entry(self, cache):
        await cache.set("k", "v", ttl=5)

        assert await cache.touch("k", ttl=100) is True
        assert await cache._client.ttl("k") > 5

    async def test_touching_a_missing_key_reports_false(self, cache):
        assert await cache.touch("absent", ttl=10) is False

    async def test_touch_without_a_resolvable_ttl_reports_false(self, cache):
        await cache.set("k", "v")
        # No explicit ttl and no default_ttl configured, so nothing to apply.
        assert await cache.touch("k") is False


class TestDeletionAndExistence:
    async def test_delete_removes_an_entry(self, cache):
        await cache.set("k", "v")

        assert await cache.delete("k") is True
        assert await cache.get("k") is _MISSING

    async def test_deleting_a_missing_key_reports_false(self, cache):
        assert await cache.delete("absent") is False

    async def test_exists_reflects_presence(self, cache):
        assert await cache.exists("k") is False
        await cache.set("k", "v")
        assert await cache.exists("k") is True

    async def test_clear_empties_the_store(self, cache):
        await cache.set("a", 1)
        await cache.set("b", 2)

        await cache.clear()

        assert await cache.get("a") is _MISSING
        assert await cache.get("b") is _MISSING

    async def test_clear_with_a_namespace_only_scans_that_namespace(self):
        ns_cache = RedisCache(
            client=fakeredis.aioredis.FakeRedis(decode_responses=False),
            namespace="ns",
        )
        other_cache = RedisCache(client=ns_cache._client)  # shares the store

        await ns_cache.set(ns_cache.make_key("a"), 1)
        await other_cache.set("outside", 2)

        await ns_cache.clear()

        assert await ns_cache.get(ns_cache.make_key("a")) is _MISSING
        assert await other_cache.get("outside") == 2


class TestTags:
    async def test_invalidating_a_tag_drops_the_tagged_entries(self, cache):
        await cache.set("a", 1, tags=["group"])
        await cache.set("b", 2, tags=["group"])
        await cache.set("c", 3)

        removed = await cache.invalidate_tags("group")

        assert removed >= 2
        assert await cache.get("a") is _MISSING
        assert await cache.get("b") is _MISSING
        assert await cache.get("c") == 3

    async def test_invalidating_with_no_tags_removes_nothing(self, cache):
        await cache.set("a", 1)

        assert await cache.invalidate_tags() == 0
        assert await cache.get("a") == 1

    async def test_invalidating_an_unused_tag_removes_nothing(self, cache):
        await cache.set("a", 1)

        assert await cache.invalidate_tags("never-used") == 0
        assert await cache.get("a") == 1

    async def test_one_key_can_carry_several_tags(self, cache):
        await cache.set("a", 1, tags=["x", "y"])

        assert await cache.invalidate_tags("y") >= 1
        assert await cache.get("a") is _MISSING


class TestKeyBuilding:
    def test_the_namespace_scopes_a_built_key(self):
        cache = RedisCache(client=object(), namespace="app")
        assert cache.make_key("thing").startswith("app:")

    def test_backends_with_different_namespaces_build_different_keys(self):
        one = RedisCache(client=object(), namespace="one")
        two = RedisCache(client=object(), namespace="two")

        assert one.make_key("shared") != two.make_key("shared")

    def test_the_namespace_can_be_overridden_per_call(self):
        cache = RedisCache(client=object(), namespace="app")
        assert cache.make_key("thing", namespace="other").startswith("other:")


class TestStats:
    async def test_hits_and_misses_are_counted(self, cache):
        await cache.set("k", "v")

        await cache.get("k")
        await cache.get("absent")

        assert cache._stats.hits >= 1
        assert cache._stats.misses >= 1


class TestConstruction:
    async def test_close_is_safe_to_call(self, cache):
        await cache.set("k", "v")
        await cache.close()

    def test_a_url_is_accepted_without_connecting(self):
        # Construction must not touch the network; the client is lazy.
        assert RedisCache(url="redis://localhost:6379/0") is not None

    def test_host_and_port_are_accepted(self):
        assert RedisCache(host="localhost", port=6379, db=1) is not None

    def test_a_password_is_accepted(self):
        assert RedisCache(host="localhost", password="secret") is not None

    async def test_redis_raises_cache_error_without_the_redis_package(
        self, monkeypatch
    ):
        import sillo.cache.backends as backends_module
        from sillo.cache.base import CacheError

        monkeypatch.setattr(backends_module, "aioredis", None)
        cache = RedisCache(url="redis://localhost:6379/0")

        with pytest.raises(CacheError, match="redis.*package is required"):
            await cache._redis()

    async def test_redis_connects_lazily_via_url(self, monkeypatch):
        import sillo.cache.backends as backends_module

        fake_server = fakeredis.aioredis.FakeRedis(decode_responses=False)

        class FakeAioredisModule:
            @staticmethod
            def from_url(url, db=0, password=None, decode_responses=False):
                return fake_server

        monkeypatch.setattr(backends_module, "aioredis", FakeAioredisModule)
        cache = RedisCache(url="redis://localhost:6379/0")

        client = await cache._redis()
        assert client is fake_server
        assert await cache._redis() is fake_server  # cached

    async def test_redis_connects_lazily_via_host_and_port(self, monkeypatch):
        import sillo.cache.backends as backends_module

        fake_server = fakeredis.aioredis.FakeRedis(decode_responses=False)
        captured = {}

        class FakeAioredisModule:
            @staticmethod
            def Redis(host, port, db, password, decode_responses):
                captured.update(host=host, port=port, db=db, password=password)
                return fake_server

        monkeypatch.setattr(backends_module, "aioredis", FakeAioredisModule)
        cache = RedisCache(host="cache.example.com", port=6380, db=2)

        client = await cache._redis()
        assert client is fake_server
        assert captured == {
            "host": "cache.example.com",
            "port": 6380,
            "db": 2,
            "password": None,
        }

    async def test_close_actually_closes_a_client_the_backend_owns(
        self, monkeypatch
    ):
        import sillo.cache.backends as backends_module

        closed = []

        class FakeClient:
            async def aclose(self):
                closed.append(1)

        fake_client = FakeClient()

        class FakeAioredisModule:
            @staticmethod
            def from_url(url, db=0, password=None, decode_responses=False):
                return fake_client

        monkeypatch.setattr(backends_module, "aioredis", FakeAioredisModule)
        cache = RedisCache(url="redis://localhost:6379/0")
        await cache._redis()  # establishes the owned client

        await cache.close()
        assert closed == [1]

    async def test_close_swallows_errors(self, monkeypatch):
        import sillo.cache.backends as backends_module

        class BrokenClient:
            async def aclose(self):
                raise RuntimeError("already gone")

        class FakeAioredisModule:
            @staticmethod
            def from_url(url, db=0, password=None, decode_responses=False):
                return BrokenClient()

        monkeypatch.setattr(backends_module, "aioredis", FakeAioredisModule)
        cache = RedisCache(url="redis://localhost:6379/0")
        await cache._redis()

        await cache.close()  # must not raise
