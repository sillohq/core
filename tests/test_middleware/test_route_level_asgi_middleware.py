"""Route- and router-level middleware accepts everything app.use() accepts (#463)."""

import pytest

from sillo import SilloApp, json
from sillo.core.http import HttpContext
from sillo.core.routing import Route, Router
from sillo.middleware.base import BaseMiddleware
from sillo.middleware.define import DefineMiddleware
from sillo.security import RateLimit
from sillo.testclient import TestClient


class Stamp:
    """Raw ASGI factory: adds a response header and records that it ran."""

    calls: list[str] = []

    def __init__(self, app, name="stamp", value="1"):
        self.app = app
        self.name = name
        self.value = value

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        Stamp.calls.append(self.name)

        async def send_stamped(message):
            if message["type"] == "http.response.start":
                message["headers"].append(
                    (f"x-{self.name}".encode(), self.value.encode())
                )
            await send(message)

        await self.app(scope, receive, send_stamped)


class StampInstance:
    """A configured raw ASGI instance, in the shape RateLimit(...) has."""

    def __init__(self, name="inst"):
        self.app = None
        self.name = name

    async def __call__(self, scope, receive, send):
        async def send_stamped(message):
            if message["type"] == "http.response.start":
                message["headers"].append((f"x-{self.name}".encode(), b"1"))
            await send(message)

        await self.app(scope, receive, send_stamped)


class DispatchStamp(BaseMiddleware):
    async def dispatch(self, ctx, call_next):
        Stamp.calls.append("dispatch")
        response = await call_next()
        response.headers["x-dispatch"] = "1"
        return response


@pytest.fixture(autouse=True)
def _reset_calls():
    Stamp.calls.clear()


async def ok(ctx: HttpContext):
    return json({"ok": True})


def client_for(app) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------- route level


def test_route_accepts_a_raw_asgi_class():
    app = SilloApp()
    app.router.add_route(Route("/a", ok, middleware=[Stamp]))
    app.router.add_route(Route("/b", ok))
    c = client_for(app)

    assert c.get("/a").headers["x-stamp"] == "1"
    assert "x-stamp" not in c.get("/b").headers


def test_route_accepts_a_factory_tuple_with_arguments():
    app = SilloApp()
    app.router.add_route(
        Route("/a", ok, middleware=[(Stamp, (), {"name": "named", "value": "v"})])
    )
    assert client_for(app).get("/a").headers["x-named"] == "v"


def test_route_accepts_a_define_middleware():
    app = SilloApp()
    app.router.add_route(
        Route("/a", ok, middleware=[DefineMiddleware(Stamp, name="defined")])
    )
    assert "x-defined" in client_for(app).get("/a").headers


def test_route_accepts_a_built_raw_instance():
    app = SilloApp()
    app.router.add_route(Route("/a", ok, middleware=[StampInstance("built")]))
    assert "x-built" in client_for(app).get("/a").headers


def test_route_accepts_a_base_middleware_instance():
    app = SilloApp()
    app.router.add_route(Route("/a", ok, middleware=[DispatchStamp()]))
    assert "x-dispatch" in client_for(app).get("/a").headers


def test_mixed_forms_run_in_list_order_first_is_outermost():
    app = SilloApp()
    order = []

    async def first(ctx, call_next):
        order.append("first-in")
        response = await call_next()
        order.append("first-out")
        return response

    class Second:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            order.append("second-in")
            await self.app(scope, receive, send)
            order.append("second-out")

    async def handler(ctx):
        order.append("handler")
        return json({})

    app.router.add_route(Route("/a", handler, middleware=[first, Second]))
    client_for(app).get("/a")
    # Entry order is the contract: the first listed is outermost. (How far the
    # dispatch bridge has unwound by the time the raw layer finishes is the
    # bridge's own behaviour, not something this feature changes.)
    assert order[:3] == ["first-in", "second-in", "handler"]
    assert sorted(order[3:]) == ["first-out", "second-out"]


def test_one_instance_can_guard_several_routes():
    shared = StampInstance("shared")
    app = SilloApp()
    app.router.add_route(Route("/a", ok, middleware=[shared]))
    app.router.add_route(Route("/b", ok, middleware=[shared]))
    c = client_for(app)

    # Each route must reach its own handler; a shared .app would send one of
    # them to the other's chain.
    assert "x-shared" in c.get("/a").headers
    assert "x-shared" in c.get("/b").headers
    assert shared.app is None


def test_verb_decorator_takes_raw_middleware():
    app = SilloApp()

    @app.get("/a", middleware=[Stamp])
    async def a(ctx):
        return json({})

    assert "x-stamp" in client_for(app).get("/a").headers


def test_bad_middleware_tuple_fails_at_registration():
    with pytest.raises(TypeError, match="middleware tuple"):
        Route("/a", ok, middleware=[(1, 2)])


# --------------------------------------------------------------- router level


def test_router_constructor_accepts_raw_and_built_middleware():
    router = Router(prefix="/api", middleware=[Stamp, StampInstance("ctor")])

    @router.get("/x")
    async def x(ctx):
        return json({})

    app = SilloApp()
    app.mount_router(router)
    headers = client_for(app).get("/api/x").headers
    assert "x-stamp" in headers and "x-ctor" in headers


def test_router_verbs_take_route_middleware():
    router = Router(prefix="/api")

    @router.get("/guarded", middleware=[Stamp])
    async def guarded(ctx):
        return json({})

    @router.get("/open")
    async def open_(ctx):
        return json({})

    app = SilloApp()
    app.mount_router(router)
    c = client_for(app)
    assert "x-stamp" in c.get("/api/guarded").headers
    assert "x-stamp" not in c.get("/api/open").headers


def test_router_use_accepts_a_built_instance_shared_between_routers():
    shared = StampInstance("both")
    app = SilloApp()
    for prefix in ("/one", "/two"):
        router = Router(prefix=prefix)
        router.use(shared)

        @router.get("/x")
        async def x(ctx):
            return json({"prefix": prefix})

        app.mount_router(router)
    c = client_for(app)
    assert "x-both" in c.get("/one/x").headers
    assert "x-both" in c.get("/two/x").headers


def test_router_use_still_refuses_arguments_for_dispatch_middleware():
    router = Router()
    with pytest.raises(TypeError, match="dispatch form"):
        router.use(DispatchStamp(), name="x")


# ---------------------------------------------------- the case from the issue


def _limited(limit=2):
    return RateLimit(limit=limit, window=60, key_func=lambda ctx: "client")


def test_rate_limit_attaches_to_a_single_route():
    app = SilloApp()

    @app.get("/login", middleware=[_limited(2)])
    async def login(ctx):
        return json({"ok": True})

    @app.get("/other")
    async def other(ctx):
        return json({"ok": True})

    c = client_for(app)
    assert [c.get("/login").status_code for _ in range(3)] == [200, 200, 429]
    assert [c.get("/other").status_code for _ in range(5)] == [200] * 5


def test_rate_limit_denial_has_the_standard_body_and_headers():
    app = SilloApp()

    @app.get("/login", middleware=[_limited(1)])
    async def login(ctx):
        return json({"ok": True})

    c = client_for(app)
    ok_response = c.get("/login")
    assert ok_response.headers["x-ratelimit-limit"] == "1"
    assert ok_response.headers["x-ratelimit-remaining"] == "0"

    denied = c.get("/login")
    assert denied.status_code == 429
    assert denied.json()["error"] == "rate_limit_exceeded"
    assert int(denied.headers["retry-after"]) >= 1


def test_separate_instances_keep_separate_limits():
    app = SilloApp()

    @app.get("/a", middleware=[_limited(1)])
    async def a(ctx):
        return json({})

    @app.get("/b", middleware=[_limited(1)])
    async def b(ctx):
        return json({})

    c = client_for(app)
    assert c.get("/a").status_code == 200
    assert c.get("/b").status_code == 200
    assert c.get("/a").status_code == 429


def test_one_rate_limit_instance_counts_across_the_routes_it_guards():
    shared = _limited(2)
    app = SilloApp()

    @app.get("/a", middleware=[shared])
    async def a(ctx):
        return json({})

    @app.get("/b", middleware=[shared])
    async def b(ctx):
        return json({})

    c = client_for(app)
    assert c.get("/a").status_code == 200
    assert c.get("/b").status_code == 200
    assert c.get("/a").status_code == 429


def test_rate_limit_on_a_router():
    router = Router(prefix="/api", middleware=[_limited(1)])

    @router.get("/x")
    async def x(ctx):
        return json({})

    app = SilloApp()
    app.mount_router(router)
    c = client_for(app)
    assert [c.get("/api/x").status_code for _ in range(2)] == [200, 429]
