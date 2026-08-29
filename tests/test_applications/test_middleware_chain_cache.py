"""The middleware chain is assembled outside the request path.

It used to be reassembled on every request — a stack of wrapper objects
identical to the previous request's, allocated and thrown away. It is now
built in ``__init__`` and rebuilt by everything that changes what it is made
of, so a request only ever reads it.

Building eagerly rather than on first use is the point: a lazy rebuild still
lands in whichever request arrives first. The awkward case is real rather than
hypothetical — `setup_record` and the admin panel both register middleware
while the application is being configured, and the admin registers its routes
from a startup hook, after the chain already exists.
"""

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.middleware.base import BaseMiddleware
from sillo.testclient import TestClient


class Tagging(BaseMiddleware):
    """Records that it ran, so ordering and presence are observable."""

    def __init__(self, tag):
        self.tag = tag

    async def dispatch(self, request, call_next):
        # On the way in, so the handler can see it: the handler is innermost
        # and has already serialized by the time the stack unwinds.
        request.scope.setdefault("tags", []).append(self.tag)
        return await call_next()


def _app():
    app = SilloApp()

    @app.get("/ping")
    async def ping(request: HttpContext):
        return json({"tags": request.scope.get("tags", [])})

    return app


class TestTheChainExistsBeforeAnyRequest:
    def test_it_is_built_during_construction(self):
        app = SilloApp()
        assert app._request_chain is not None

    def test_it_is_built_before_the_first_request_on_a_configured_app(self):
        app = _app()
        app.use(Tagging("x"))
        assert app._request_chain is not None

    def test_the_same_chain_object_serves_every_request(self):
        app = _app()

        with TestClient(app) as client:
            client.get("/ping")
            first = app._request_chain
            client.get("/ping")
            client.get("/ping")

        assert app._request_chain is first

    def test_a_request_never_rebuilds_it(self):
        app = _app()
        before = app._request_chain

        with TestClient(app) as client:
            client.get("/ping")
            client.get("/ping")

        assert app._request_chain is before


class TestItIsRebuiltWhenItMustBe:
    def test_use_rebuilds_immediately_rather_than_marking_it_stale(self):
        app = _app()
        before = app._request_chain

        app.use(Tagging("x"))

        assert app._request_chain is not before
        assert app._request_chain is not None

    def test_middleware_registered_after_a_request_still_runs(self):
        app = _app()

        with TestClient(app) as client:
            assert client.get("/ping").json()["tags"] == []

            app.use(Tagging("late"))

            assert client.get("/ping").json()["tags"] == ["late"]

    def test_registration_order_is_preserved_across_a_rebuild(self):
        app = _app()
        app.use(Tagging("first"))

        with TestClient(app) as client:
            assert client.get("/ping").json()["tags"] == ["first"]

            app.use(Tagging("second"))

            # `use` inserts at the front, so the most recently registered
            # middleware is the outermost and therefore runs first.
            assert client.get("/ping").json()["tags"] == ["second", "first"]

    def test_setting_debug_rebuilds(self):
        # ServerErrorMiddleware is constructed with the flag, so a chain built
        # once would otherwise keep the value debug had at construction.
        app = _app()
        before = app._request_chain

        app.debug = not app.debug

        assert app._request_chain is not before

    def test_debug_round_trips_through_the_property(self):
        app = SilloApp(debug=False)
        assert app.debug is False

        app.debug = True
        assert app.debug is True


class TestRoutesDoNotNeedARebuild:
    """Routes live on the router, which the chain holds by reference.

    The admin panel registers its routes from a startup hook, so this is the
    path that would break if the chain had captured a snapshot of them.
    """

    def test_a_route_added_after_the_first_request_is_reachable(self):
        app = _app()

        with TestClient(app) as client:
            assert client.get("/ping").status_code == 200
            chain = app._request_chain

            @app.get("/added-later")
            async def later(request: HttpContext):
                return json({"ok": True})

            assert client.get("/added-later").status_code == 200
            # No rebuild was needed to see it.
            assert app._request_chain is chain

    def test_a_route_registered_from_a_startup_hook_is_reachable(self):
        app = _app()

        async def register():
            @app.get("/from-startup")
            async def from_startup(request: HttpContext):
                return json({"ok": True})

        app.on_startup(register)

        with TestClient(app) as client:
            assert client.get("/from-startup").status_code == 200
