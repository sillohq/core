import functools
import os

import pytest

from sillo.testclient import TestClient


@pytest.fixture
def test_client_factory():
    return functools.partial(
        TestClient,
    )


# ── optional service availability ────────────────────────────────────────

REDIS_URL = os.environ.get("SILLO_TEST_REDIS_URL", "redis://localhost:6379/15")


@functools.lru_cache(maxsize=1)
def redis_available() -> bool:
    """Whether a live Redis is reachable for integration tests.

    Probed once per session. Tests needing Redis are skipped rather than
    failed when it is absent, so the suite stays runnable on a bare checkout
    while still exercising the real client when one is present.

    Set ``SILLO_TEST_REDIS_URL`` to point at a different instance. Database 15
    is used by default and is flushed around each test, so do not point this at
    anything you care about.
    """
    try:
        import redis
    except ImportError:
        return False
    try:
        client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=0.5)
        client.ping()
        client.close()
        return True
    except Exception:
        return False


#: Decorator for tests that need a live Redis server.
requires_redis = pytest.mark.skipif(
    not redis_available(),
    reason=f"no Redis reachable at {REDIS_URL} (set SILLO_TEST_REDIS_URL to override)",
)


@pytest.fixture
def redis_url():
    """The Redis URL under test, with the database flushed before and after."""
    import redis

    client = redis.Redis.from_url(REDIS_URL)
    client.flushdb()
    try:
        yield REDIS_URL
    finally:
        client.flushdb()
        client.close()
