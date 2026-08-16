"""``RedisBackend`` for rate limiting, driven against ``fakeredis``.

This module was 0% covered. It is not obscure: it is exported in ``__all__``,
reached by the documented ``RateLimit(backend="redis")``, described in its own
docstring as "recommended for multi-instance deployments", and referenced from
three pages of documentation. It is the production path for the feature, and
nothing had ever executed it -- including the Lua script that makes the
save atomic, which is the whole reason this backend exists rather than a
plain SET.

``fakeredis[lua]`` is a dev dependency and answers EVAL, so the script runs
for real here rather than being stubbed.
"""

from __future__ import annotations

import json

import pytest

fakeredis = pytest.importorskip(
    "fakeredis", reason="fakeredis provides the in-process Redis these tests need"
)
import fakeredis.aioredis  # noqa: E402

from sillo.security.ratelimit.backends import get_backend  # noqa: E402
from sillo.security.ratelimit.backends.redis import RedisBackend  # noqa: E402


@pytest.fixture
def backend():
    """A backend whose client is an in-process fake.

    The client and the script are both rebound, because ``register_script``
    is bound to the client it was created from -- leaving the original script
    would send EVAL to the real connection the constructor opened.
    """
    instance = RedisBackend(prefix="test:rl:")
    instance._client = fakeredis.aioredis.FakeRedis(decode_responses=False)
    instance._script = instance._client.register_script(
        "redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[1])\nreturn ARGV[2]"
    )
    return instance


class TestKeyNamespacing:
    def test_keys_carry_the_prefix(self, backend):
        assert backend._key("abc") == "test:rl:abc"

    def test_the_default_prefix_is_namespaced_to_sillo(self):
        """Two applications sharing a Redis must not share rate-limit state,
        and the default has to be specific enough that they do not."""
        assert RedisBackend.__init__.__defaults__[1] == "sillo:ratelimit:"


class TestFetchAndSave:
    async def test_an_unknown_key_has_no_state(self, backend):
        assert await backend.fetch_state("nothing-here") is None

    async def test_state_survives_a_round_trip(self, backend):
        await backend.save_state("k", {"count": 3, "reset_at": 1234.5}, ttl=60)

        assert await backend.fetch_state("k") == {"count": 3, "reset_at": 1234.5}

    async def test_numbers_keep_their_types(self, backend):
        """State is JSON, and a counter that came back as a string would
        compare wrongly against an int limit without ever raising."""
        await backend.save_state("k", {"count": 3, "reset_at": 1234.5}, ttl=60)
        state = await backend.fetch_state("k")

        assert isinstance(state["count"], int)
        assert isinstance(state["reset_at"], float)

    async def test_saving_again_replaces_the_state(self, backend):
        await backend.save_state("k", {"count": 1}, ttl=60)
        await backend.save_state("k", {"count": 2}, ttl=60)

        assert await backend.fetch_state("k") == {"count": 2}

    async def test_the_ttl_is_applied(self, backend):
        """Without an expiry the key outlives its window and a client stays
        limited forever."""
        await backend.save_state("k", {"count": 1}, ttl=42)

        ttl = await backend._client.ttl("test:rl:k")
        assert 0 < ttl <= 42

    async def test_two_keys_do_not_share_state(self, backend):
        await backend.save_state("a", {"count": 1}, ttl=60)
        await backend.save_state("b", {"count": 9}, ttl=60)

        assert await backend.fetch_state("a") == {"count": 1}
        assert await backend.fetch_state("b") == {"count": 9}


class TestCorruptState:
    async def test_unparseable_json_reads_as_absent(self, backend):
        """Something else wrote to the key, or a half-written value survived.

        Answering ``None`` restarts the window, which lets one request through
        that maybe should not have been. Raising would fail *every* request
        for that key until the key expired, which is worse.
        """
        await backend._client.set("test:rl:k", b"{not json")

        assert await backend.fetch_state("k") is None

    async def test_a_json_scalar_still_reads_back(self, backend):
        """`json.loads` succeeds here and returns a non-dict. The caller
        treats it as state, so this documents what actually happens rather
        than asserting a guard that does not exist."""
        await backend._client.set("test:rl:k", b"12")

        assert await backend.fetch_state("k") == 12


class TestClear:
    async def test_clear_removes_this_backend_s_keys(self, backend):
        await backend.save_state("a", {"count": 1}, ttl=60)
        await backend.save_state("b", {"count": 2}, ttl=60)

        await backend.clear()

        assert await backend.fetch_state("a") is None
        assert await backend.fetch_state("b") is None

    async def test_clear_leaves_other_namespaces_alone(self, backend):
        """``clear`` scans by prefix. A scan that dropped the match would
        empty the whole database, which in a shared Redis is somebody else's
        outage."""
        await backend.save_state("mine", {"count": 1}, ttl=60)
        await backend._client.set("someone-else:key", b"keep me")

        await backend.clear()

        assert await backend._client.get("someone-else:key") == b"keep me"

    async def test_clear_on_an_empty_store_is_fine(self, backend):
        await backend.clear()

        assert await backend.fetch_state("anything") is None


class TestTheDocumentedEntryPoint:
    def test_the_string_spec_resolves_to_this_backend(self):
        """``RateLimit(backend="redis")`` goes through ``get_backend``, and
        that string is what the package docstring and the docs both show."""
        resolved = get_backend("redis")

        assert isinstance(resolved, RedisBackend)

    def test_an_instance_is_passed_through(self, backend):
        assert get_backend(backend) is backend


class TestTheSaveIsAtomic:
    async def test_the_script_returns_what_it_stored(self, backend):
        """The Lua does the set and returns the payload, so a caller can tell
        a successful write from a silent no-op. Running it through fakeredis'
        EVAL is what makes this a test of the script rather than of a mock.
        """
        payload = json.dumps({"count": 7})
        returned = await backend._script(keys=["test:rl:direct"], args=[60, payload])

        assert json.loads(returned) == {"count": 7}
        assert await backend._client.get("test:rl:direct") == payload.encode()
