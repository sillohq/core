"""
``use_for_route``: scope a middleware to a path pattern.

The decorator picks a wrapper based on the function name — ``__call__`` gets
the ``self``-taking form — so both the function and class shapes are covered,
as is the pass-through branch where the pattern does not match.
"""

from typing import Callable

from sillo import SilloApp
from sillo.core.http import Request, Response
from sillo.middleware.base import BaseMiddleware
from sillo.middleware.utils import use_for_route
from sillo.testclient import TestClient


def _app_with(middleware) -> SilloApp:
    app = SilloApp()
    app.use(middleware)

    @app.get("/api/users")
    async def users(request: Request, response: Response):
        return response.json({"path": "users"})

    @app.get("/api/posts/recent")
    async def recent(request: Request, response: Response):
        return response.json({"path": "recent"})

    @app.get("/public")
    async def public(request: Request, response: Response):
        return response.json({"path": "public"})

    return app


# ── exact paths ──────────────────────────────────────────────────────────


def test_the_middleware_runs_on_the_matching_path(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    seen = []

    @use_for_route("/api/users")
    async def guard(request: Request, response: Response, call_next):
        seen.append(request.url.path)
        return await call_next()

    with test_client_factory(_app_with(guard)) as client:
        assert client.get("/api/users").status_code == 200
    assert seen == ["/api/users"]


def test_the_middleware_is_skipped_elsewhere(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    seen = []

    @use_for_route("/api/users")
    async def guard(request: Request, response: Response, call_next):
        seen.append(request.url.path)
        return await call_next()

    with test_client_factory(_app_with(guard)) as client:
        assert client.get("/public").status_code == 200
    assert seen == []


def test_an_exact_pattern_does_not_match_a_longer_path(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """``/api`` is anchored at both ends, so it must not catch ``/api/users``."""
    seen = []

    @use_for_route("/api")
    async def guard(request: Request, response: Response, call_next):
        seen.append(request.url.path)
        return await call_next()

    with test_client_factory(_app_with(guard)) as client:
        client.get("/api/users")
    assert seen == []


def test_a_skipped_middleware_still_reaches_the_handler(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    @use_for_route("/nothing-here")
    async def guard(request: Request, response: Response, call_next):
        return await call_next()

    with test_client_factory(_app_with(guard)) as client:
        assert client.get("/public").json() == {"path": "public"}


# ── wildcard patterns ────────────────────────────────────────────────────


def test_a_wildcard_matches_a_child_path(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    seen = []

    @use_for_route("/api/*")
    async def guard(request: Request, response: Response, call_next):
        seen.append(request.url.path)
        return await call_next()

    with test_client_factory(_app_with(guard)) as client:
        client.get("/api/users")
        client.get("/api/posts/recent")
    assert seen == ["/api/users", "/api/posts/recent"]


def test_a_wildcard_does_not_leak_to_a_sibling_prefix(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    seen = []

    @use_for_route("/api/*")
    async def guard(request: Request, response: Response, call_next):
        seen.append(request.url.path)
        return await call_next()

    with test_client_factory(_app_with(guard)) as client:
        client.get("/public")
    assert seen == []


def test_a_scoped_middleware_can_short_circuit_the_request(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    @use_for_route("/api/*")
    async def guard(request: Request, response: Response, call_next):
        return response.json({"blocked": True}, status_code=403)

    with test_client_factory(_app_with(guard)) as client:
        blocked = client.get("/api/users")
        allowed = client.get("/public")

    assert blocked.status_code == 403
    assert allowed.status_code == 200


def test_a_scoped_middleware_can_set_a_header(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    @use_for_route("/api/*")
    async def tag(request: Request, response: Response, call_next):
        await call_next()
        response.set_header("X-Scope", "api")
        return response

    with test_client_factory(_app_with(tag)) as client:
        assert client.get("/api/users").headers.get("X-Scope") == "api"
        assert client.get("/public").headers.get("X-Scope") is None


# ── class-based middleware ───────────────────────────────────────────────


def test_a_scoped_class_middleware_runs_on_a_match(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """A ``__call__`` method needs the wrapper that passes ``self`` through."""
    seen = []

    class Scoped(BaseMiddleware):
        @use_for_route("/api/*")
        async def __call__(self, request: Request, response: Response, call_next):
            seen.append(request.url.path)
            return await call_next()

    with test_client_factory(_app_with(Scoped())) as client:
        assert client.get("/api/users").status_code == 200
    assert seen == ["/api/users"]


def test_a_scoped_class_middleware_is_skipped_elsewhere(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    seen = []

    class Scoped(BaseMiddleware):
        @use_for_route("/api/*")
        async def __call__(self, request: Request, response: Response, call_next):
            seen.append(request.url.path)
            return await call_next()

    with test_client_factory(_app_with(Scoped())) as client:
        assert client.get("/public").status_code == 200
    assert seen == []


def test_a_scoped_class_middleware_keeps_access_to_instance_state(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    class Counting(BaseMiddleware):
        def __init__(self):
            self.hits = 0

        @use_for_route("/api/*")
        async def __call__(self, request: Request, response: Response, call_next):
            self.hits += 1
            return await call_next()

    middleware = Counting()
    with test_client_factory(_app_with(middleware)) as client:
        client.get("/api/users")
        client.get("/public")
        client.get("/api/posts/recent")

    assert middleware.hits == 2


# ── decorator mechanics ──────────────────────────────────────────────────


def test_the_decorator_preserves_the_function_name():
    @use_for_route("/api/*")
    async def guard(request, response, call_next):
        return await call_next()

    assert guard.__name__ == "guard"
