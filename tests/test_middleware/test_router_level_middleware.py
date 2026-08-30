"""
Tests for router-level middleware
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.middleware.base import BaseMiddleware
from sillo.core.routing import Router
from sillo.testclient import TestClient

# ========== Basic Router-Level Middleware Tests ==========


def test_router_level_middleware_basic(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test basic router-level middleware"""
    app = SilloApp()
    router = Router(prefix="/api")

    executed = []

    async def router_middleware(ctx: HttpContext, call_next):
        executed.append("router_middleware")
        response = await call_next()
        return response

    router.use(router_middleware)

    @router.get("/test")
    async def handler(ctx: HttpContext):
        executed.append("handler")
        return json({"message": "ok"})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert "router_middleware" in executed
        assert "handler" in executed


def test_router_level_middleware_isolated(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test that router middleware only applies to that router"""
    app = SilloApp()
    router1 = Router(prefix="/api1")
    router2 = Router(prefix="/api2")

    executed = []

    async def router1_middleware(ctx: HttpContext, call_next):
        executed.append("router1_middleware")
        response = await call_next()
        return response

    router1.use(router1_middleware)

    @router1.get("/route1")
    async def handler1(ctx: HttpContext):
        return json({"router": "1"})

    @router2.get("/route2")
    async def handler2(ctx: HttpContext):
        return json({"router": "2"})

    app.mount_router(router1)
    app.mount_router(router2)

    with test_client_factory(app) as client:
        # Router1 route should trigger middleware
        executed.clear()
        resp1 = client.get("/api1/route1")
        assert resp1.status_code == 200
        assert "router1_middleware" in executed

        # Router2 route should NOT trigger router1 middleware
        executed.clear()
        resp2 = client.get("/api2/route2")
        assert resp2.status_code == 200
        assert "router1_middleware" not in executed


def test_router_level_middleware_multiple(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test multiple router-level middleware"""
    app = SilloApp()
    router = Router(prefix="/api")

    execution_order = []

    async def middleware_1(ctx: HttpContext, call_next):
        execution_order.append("m1_before")
        response = await call_next()
        execution_order.append("m1_after")
        return response

    async def middleware_2(ctx: HttpContext, call_next):
        execution_order.append("m2_before")
        response = await call_next()
        execution_order.append("m2_after")
        return response

    router.use(middleware_1)
    router.use(middleware_2)

    @router.get("/test")
    async def handler(ctx: HttpContext):
        execution_order.append("handler")
        return json({"message": "ok"})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/test")
        assert resp.status_code == 200
        # Verify execution order
        assert "m1_before" in execution_order
        assert "m2_before" in execution_order
        assert "handler" in execution_order
        assert "m1_after" in execution_order
        assert "m2_after" in execution_order


def test_router_level_middleware_with_prefix(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test router middleware with path prefix"""
    app = SilloApp()
    router = Router(prefix="/api")

    async def add_prefix_header(ctx: HttpContext, call_next):
        response = await call_next()
        response.set_header("X-Router-Prefix", "api")
        return response

    router.use(add_prefix_header)

    @router.get("/users")
    async def get_users(ctx: HttpContext):
        return json({"users": []})

    @router.get("/posts")
    async def get_posts(ctx: HttpContext):
        return json({"posts": []})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp1 = client.get("/api/users")
        assert resp1.headers.get("x-router-prefix") == "api"

        resp2 = client.get("/api/posts")
        assert resp2.headers.get("x-router-prefix") == "api"


def test_router_level_middleware_auth(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test router-level authentication middleware"""
    app = SilloApp()
    protected_router = Router(prefix="/api")
    public_router = Router(prefix="/public")

    async def auth_middleware(ctx: HttpContext, call_next):
        token = ctx.headers.get("Authorization")
        if not token or not token.startswith("Bearer "):
            return json({"error": "Unauthorized"}).status(401)
        response = await call_next()
        return response

    protected_router.use(auth_middleware)

    @protected_router.get("/protected")
    async def protected_handler(ctx: HttpContext):
        return json({"message": "Protected resource"})

    @public_router.get("/test")
    async def public_handler(ctx: HttpContext):
        return json({"message": "Public resource"})

    app.mount_router(protected_router)
    app.mount_router(public_router)

    with test_client_factory(app) as client:
        # Protected route without auth
        resp1 = client.get("/api/protected")
        assert resp1.status_code == 401

        # Protected route with auth
        resp2 = client.get("/api/protected", headers={"Authorization": "Bearer token"})
        assert resp2.status_code == 200

        # Public route without auth
        resp3 = client.get("/public/test")
        assert resp3.status_code == 200


def test_router_level_middleware_modifies_response(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test router middleware modifying response"""
    app = SilloApp()
    router = Router(prefix="/api")

    async def json_wrapper_middleware(ctx: HttpContext, call_next):
        response = await call_next()
        # Wrap response in a standard format
        response.set_header("X-Wrapped", "true")
        return response

    router.use(json_wrapper_middleware)

    @router.get("/data")
    async def get_data(ctx: HttpContext):
        return json({"value": 42})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/data")
        assert resp.headers.get("x-wrapped") == "true"
        assert resp.json()["value"] == 42


# ========== Router Middleware with App Middleware Tests ==========


def test_router_and_app_middleware_combined(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test router middleware combined with app middleware"""
    app = SilloApp()
    router = Router(prefix="/api")

    execution_order = []

    async def app_middleware(ctx: HttpContext, call_next):
        execution_order.append("app_before")
        response = await call_next()
        execution_order.append("app_after")
        return response

    async def router_middleware(ctx: HttpContext, call_next):
        execution_order.append("router_before")
        response = await call_next()
        execution_order.append("router_after")
        return response

    app.use(app_middleware)
    router.use(router_middleware)

    @router.get("/test")
    async def handler(ctx: HttpContext):
        execution_order.append("handler")
        return json({"message": "ok"})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/test")
        assert resp.status_code == 200
        # App middleware should execute before router middleware
        assert execution_order.index("app_before") < execution_order.index(
            "router_before"
        )
        assert execution_order.index("router_after") < execution_order.index(
            "app_after"
        )


def test_multiple_routers_different_middleware(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test multiple routers with different middleware"""
    app = SilloApp()
    router1 = Router(prefix="/api1")
    router2 = Router(prefix="/api2")

    async def router1_middleware(ctx: HttpContext, call_next):
        response = await call_next()
        response.set_header("X-Router", "1")
        return response

    async def router2_middleware(ctx: HttpContext, call_next):
        response = await call_next()
        response.set_header("X-Router", "2")
        return response

    router1.use(router1_middleware)
    router2.use(router2_middleware)

    @router1.get("/route")
    async def handler1(ctx: HttpContext):
        return json({"router": "1"})

    @router2.get("/route")
    async def handler2(ctx: HttpContext):
        return json({"router": "2"})

    app.mount_router(router1)
    app.mount_router(router2)

    with test_client_factory(app) as client:
        resp1 = client.get("/api1/route")
        assert resp1.headers.get("x-router") == "1"

        resp2 = client.get("/api2/route")
        assert resp2.headers.get("x-router") == "2"


# ========== Router Middleware State Tests ==========


def test_router_middleware_state_isolation(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test that router middleware state is isolated"""
    app = SilloApp()
    router1 = Router(prefix="/api1")
    router2 = Router(prefix="/api2")

    async def router1_state_middleware(ctx: HttpContext, call_next):
        ctx.state.router_name = "router1"
        response = await call_next()
        return response

    async def router2_state_middleware(ctx: HttpContext, call_next):
        ctx.state.router_name = "router2"
        response = await call_next()
        return response

    router1.use(router1_state_middleware)
    router2.use(router2_state_middleware)

    @router1.get("/test")
    async def handler1(ctx: HttpContext):
        return json({"router": ctx.state.router_name})

    @router2.get("/test")
    async def handler2(ctx: HttpContext):
        return json({"router": ctx.state.router_name})

    app.mount_router(router1)
    app.mount_router(router2)

    with test_client_factory(app) as client:
        resp1 = client.get("/api1/test")
        assert resp1.json()["router"] == "router1"

        resp2 = client.get("/api2/test")
        assert resp2.json()["router"] == "router2"


def test_router_middleware_error_handling(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test router middleware handling errors"""
    app = SilloApp()
    router = Router(prefix="/api")

    async def error_handler_middleware(ctx: HttpContext, call_next):
        try:
            response = await call_next()
        except ValueError as e:
            return json({"error": str(e), "router": "api"}).status(400)
        return response

    router.use(error_handler_middleware)

    @router.get("/error")
    async def error_handler(ctx: HttpContext):
        raise ValueError("Router error")

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/error")
        assert resp.status_code == 400
        data = resp.json()
        assert "Router error" in data["error"]
        assert data["router"] == "api"


def test_router_middleware_with_nested_routers(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test middleware with nested routers"""
    app = SilloApp()
    parent_router = Router(prefix="/api")
    child_router = Router(prefix="/child")

    async def parent_middleware(ctx: HttpContext, call_next):
        ctx.scope["parent"] = True
        response = await call_next()
        return response

    async def child_middleware(ctx: HttpContext, call_next):
        ctx.scope["child"] = True
        response = await call_next()
        return response

    parent_router.use(parent_middleware)
    child_router.use(child_middleware)

    @child_router.get("/test")
    async def handler(ctx: HttpContext):
        return json(
            {
                "parent": ctx.scope.get("parent", False),
                "child": ctx.scope.get("child", False),
            }
        )

    parent_router.mount_router(child_router)
    app.mount_router(parent_router)

    with test_client_factory(app) as client:
        resp = client.get("/api/child/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parent"] is True
        assert data["child"] is True
