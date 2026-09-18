"""Coverage for ``Group`` behavior nothing else exercises: middleware
wrapping, typed path parameters in the group's own prefix, the leading-
slash normalisation on the residual path, NotFoundException propagation
restoring the original scope, ``url_path_for``, ``__call__`` and
``__repr__``.
"""

from __future__ import annotations

import pytest

from sillo import SilloApp, json
from sillo.core.http import HttpContext
from sillo.core.routing import Group, Route, Router
from sillo.core.routing._utils import MatchStatus
from sillo.exceptions import NotFoundException
from sillo.middleware.define import DefineMiddleware
from sillo.testclient import TestClient


class _TagMiddleware:
    """A raw-ASGI middleware that tags a response header, so ordering is
    observable from the outside."""

    def __init__(self, app, tag: str):
        self.app = app
        self.tag = tag

    async def __call__(self, scope, receive, send):
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"x-tag", self.tag.encode()))
            await send(message)

        await self.app(scope, receive, send_wrapper)


class TestMiddlewareWrapping:
    def test_group_middleware_wraps_the_mounted_app(self):
        router = Router()

        @router.get("/ping")
        async def ping(ctx: HttpContext):
            return json({"ok": True})

        group = Group(
            path="/api",
            app=router,
            middleware=[DefineMiddleware(_TagMiddleware, tag="outer")],
        )
        app = SilloApp()
        app.add_route(group)

        with TestClient(app) as client:
            response = client.get("/api/ping")

        assert response.headers["x-tag"] == "outer"

    def test_middleware_order_is_first_listed_outermost(self):
        router = Router()

        @router.get("/ping")
        async def ping(ctx: HttpContext):
            return json({"ok": True})

        group = Group(
            path="/api",
            app=router,
            middleware=[
                DefineMiddleware(_TagMiddleware, tag="outer"),
                DefineMiddleware(_TagMiddleware, tag="inner"),
            ],
        )
        app = SilloApp()
        app.add_route(group)

        with TestClient(app) as client:
            response = client.get("/api/ping")

        # Both wrap the response; the last one applied (innermost) runs its
        # send_wrapper first, so its header lands first in the list -- the
        # point of the test is just that both ran, in a deterministic order.
        assert response.headers.get_list("x-tag") == ["inner", "outer"]


class TestTypedPrefixParameters:
    def test_match_converts_a_typed_parameter_in_the_groups_own_prefix(self):
        group = Group(path="/tenants/{tenant_id:int}", app=Router())

        status, params = group.match(
            {"type": "http", "path": "/tenants/42/profile", "root_path": ""}
        )

        assert status is MatchStatus.FULL
        assert params == {"tenant_id": 42}

    def test_a_request_under_a_typed_prefix_still_reaches_the_mounted_app(self):
        """Regression: `handle()` used to strip the *literal template text*
        (e.g. the string `/tenants/{tenant_id:int}`) off the front of the
        real request path, which never matches a concrete URL -- so every
        request to a group with a parameter in its own prefix fell straight
        through to the mounted app with its original, unstripped path and
        404'd there instead."""
        router = Router()

        @router.get("/profile")
        async def profile(ctx: HttpContext):
            return json({"ok": True})

        group = Group(path="/tenants/{tenant_id:int}", app=router)
        app = SilloApp()
        app.add_route(group)

        with TestClient(app) as client:
            response = client.get("/tenants/42/profile")

        assert response.status_code == 200


class TestResidualPathNormalisation:
    def test_a_remainder_with_no_leading_slash_is_still_matched(self):
        group = Group(path="/api", app=Router())

        status, params = group.match({"type": "http", "path": "/apiv2", "root_path": ""})

        assert status is MatchStatus.FULL


class TestHandleWithNoPatternMatch:
    async def test_a_path_the_pattern_no_longer_matches_passes_through_untouched(self):
        """Defensive branch: `handle()` is only ever called by a router
        after `match()` already confirmed this exact scope matches, so this
        should not occur in practice -- but if the scope were mutated
        between the two calls, the request must still reach the mounted app
        rather than crash, with the scope left exactly as it arrived."""
        seen = {}

        async def app(scope, receive, send):
            seen["path"] = scope["path"]
            seen["root_path"] = scope.get("root_path")

        group = Group(path="/api", app=app)
        scope = {"type": "http", "path": "/does-not-match", "root_path": ""}

        await group.handle(scope, None, None)

        assert seen["path"] == "/does-not-match"
        assert seen["root_path"] == ""
        assert scope["path"] == "/does-not-match"
        assert scope["root_path"] == ""


class TestHandleNotFoundPropagation:
    async def test_the_original_scope_path_is_restored_on_not_found(self):
        async def always_missing(scope, receive, send):
            raise NotFoundException()

        group = Group(path="/api", app=always_missing)
        scope = {"type": "http", "path": "/api/missing", "root_path": ""}

        with pytest.raises(NotFoundException):
            await group.handle(scope, None, None)

        assert scope["path"] == "/api/missing"
        assert scope["root_path"] == ""


class TestUrlPathFor:
    def test_substitutes_named_parameters(self):
        group = Group(path="/tenants/{tenant_id}", app=Router(), name="tenant")

        url = group.url_path_for("tenant", tenant_id="42")

        assert str(url) == "/tenants/42"

    def test_a_path_kwarg_is_appended_rather_than_substituted(self):
        group = Group(path="/files", app=Router(), name="files")

        url = group.url_path_for("files", path="/a/b.txt")

        assert str(url) == "/files/a/b.txt"

    def test_a_mismatched_name_is_refused(self):
        group = Group(path="/api", app=Router(), name="api")

        with pytest.raises(ValueError, match="does not match"):
            group.url_path_for("not-api")


class TestCallAndRepr:
    async def test_call_delegates_to_handle(self):
        seen = {}

        async def app(scope, receive, send):
            seen["path"] = scope["path"]

        group = Group(path="/api", app=app)
        scope = {"type": "http", "path": "/api/x", "root_path": ""}

        await group(scope, None, None)

        assert seen["path"] == "/x"

    def test_repr_includes_path_and_name(self):
        group = Group(path="/api", app=Router(), name="api")

        assert repr(group) == f"Group(path='/api', name='api', app={group.app!r})"

    def test_repr_with_no_name_is_still_readable(self):
        group = Group(path="/api", app=Router())

        assert "Group(path='/api', name=''" in repr(group)
