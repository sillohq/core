from __future__ import annotations

from sillo import silloApp
from sillo.core.http import Request
from sillo.security import RateLimit, RateLimitConfig, RateLimitMiddleware
from sillo.testclient import TestClient


def make_app(limit=3, window=60, key="client-a", **kw):
    app = silloApp()
    cfg = RateLimitConfig(
        limit=limit, window=window, key_func=lambda r: key, **kw
    )
    app.use(RateLimitMiddleware(config=cfg))

    @app.get("/")
    async def home(request, response):
        return {"ok": True}

    return app


def test_allows_up_to_limit():
    app = make_app(limit=3, window=60, key="a")
    client = TestClient(app)
    for _ in range(3):
        assert client.get("/").status_code == 200
    denied = client.get("/")
    assert denied.status_code == 429
    assert denied.json()["error"] == "rate_limit_exceeded"


def test_rate_limit_headers_present():
    app = make_app(limit=2, window=60, key="b")
    client = TestClient(app)
    r = client.get("/")
    assert r.headers["X-RateLimit-Limit"] == "2"
    assert r.headers["X-RateLimit-Remaining"] == "1"
    assert "X-RateLimit-Reset" in r.headers


def test_separate_keys_independent():
    app = make_app(limit=1, window=60, key="shared")
    client = TestClient(app)
    # Two different identities via different key_func by patching per request
    # is not possible here; instead verify same key shares the budget.
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 429
    # New app with different key resets budget
    app2 = make_app(limit=1, window=60, key="other")
    assert TestClient(app2).get("/").status_code == 200


def test_retry_after_header():
    app = make_app(limit=1, window=60, key="c")
    client = TestClient(app)
    client.get("/")
    denied = client.get("/")
    assert denied.headers["Retry-After"]
    assert int(denied.headers["Retry-After"]) >= 1


def test_skip_when_key_none():
    app = silloApp()
    cfg = RateLimitConfig(limit=1, window=60, key_func=lambda r: None)
    app.use(RateLimitMiddleware(config=cfg))

    @app.get("/")
    async def home(request, response):
        return {"ok": True}

    client = TestClient(app)
    # key is None -> never limited
    for _ in range(5):
        assert client.get("/").status_code == 200


def test_rate_limit_convenience_class():
    app = silloApp()
    app.use(RateLimit(limit=1, window=60, key_func=lambda r: "x"))

    @app.get("/")
    async def home(request, response):
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 429


def test_custom_on_exceed_callable():
    app = silloApp()
    cfg = RateLimitConfig(
        limit=1,
        window=60,
        key_func=lambda r: "z",
    )

    # on_exceed callable receives (request, response, result) and must
    # return a response built from the responder.
    def handler(request, response, result):
        return response.json({"custom": "blocked"}, status_code=429)

    cfg.on_exceed = handler
    app.use(RateLimitMiddleware(config=cfg))

    @app.get("/")
    async def home(request, response):
        return {"ok": True}

    client = TestClient(app)
    client.get("/")
    denied = client.get("/")
    assert denied.status_code == 429
    assert denied.json()["custom"] == "blocked"


def test_fail_open_allows_on_backend_error():
    from sillo.security.ratelimit.backends import RateLimitBackend

    class BoomBackend(RateLimitBackend):
        async def fetch_state(self, key):
            raise RuntimeError("backend down")

        async def save_state(self, key, state, ttl):
            raise RuntimeError("backend down")

        async def clear(self):
            pass

    app = silloApp()
    cfg = RateLimitConfig(
        limit=1, window=60, key_func=lambda r: "boom", backend=BoomBackend()
    )
    app.use(RateLimitMiddleware(config=cfg))

    @app.get("/")
    async def home(request, response):
        return {"ok": True}

    client = TestClient(app)
    # fail_open=True (default) -> requests pass despite backend errors
    for _ in range(3):
        assert client.get("/").status_code == 200


def test_fail_closed_raises_on_backend_error():
    from sillo.security.ratelimit.backends import RateLimitBackend

    class BoomBackend(RateLimitBackend):
        async def fetch_state(self, key):
            raise RuntimeError("backend down")

        async def save_state(self, key, state, ttl):
            raise RuntimeError("backend down")

        async def clear(self):
            pass

    app = silloApp()
    cfg = RateLimitConfig(
        limit=1,
        window=60,
        key_func=lambda r: "boom",
        backend=BoomBackend(),
        fail_open=False,
    )
    app.use(RateLimitMiddleware(config=cfg))

    @app.get("/")
    async def home(request, response):
        return {"ok": True}

    client = TestClient(app)
    # fail_closed -> backend error propagates and is reported as a 500
    # (the app error handler converts the raised RuntimeError into a response).
    assert client.get("/").status_code == 500
