"""
Tests for application-level middleware
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.middleware.base import BaseMiddleware
from sillo.testclient import TestClient

# ========== Basic App-Level Middleware Tests ==========


def test_app_level_middleware_basic(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test basic app-level middleware"""
    app = SilloApp()

    executed = []

    async def logging_middleware(ctx: HttpContext, call_next):
        executed.append("before")
        response = await call_next()
        executed.append("after")
        return response

    app.use(logging_middleware)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        executed.append("handler")
        return json({"message": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert executed == ["before", "handler", "after"]


def test_app_level_middleware_modifies_request(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test middleware that modifies request"""
    app = SilloApp()

    async def add_custom_header_middleware(
        ctx: HttpContext, call_next
    ):
        ctx.scope["custom_data"] = "middleware_value"
        response = await call_next()
        return response

    app.use(add_custom_header_middleware)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        custom_data = ctx.scope.get("custom_data")
        return json({"custom_data": custom_data})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.json()["custom_data"] == "middleware_value"


def test_app_level_middleware_modifies_response(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test middleware that modifies response"""
    app = SilloApp()

    async def add_response_header_middleware(
        ctx: HttpContext, call_next
    ):
        response = await call_next()
        response.set_header("X-Custom-Header", "middleware-added")
        return response

    app.use(add_response_header_middleware)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.headers.get("x-custom-header") == "middleware-added"


def test_app_level_middleware_multiple(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test multiple app-level middleware execution order"""
    app = SilloApp()

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

    async def middleware_3(ctx: HttpContext, call_next):
        execution_order.append("m3_before")
        response = await call_next()
        execution_order.append("m3_after")
        return response

    app.use(middleware_1)
    app.use(middleware_2)
    app.use(middleware_3)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        execution_order.append("handler")
        return json({"message": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        # Middleware added first executes last (LIFO order)
        assert execution_order == [
            "m3_before",
            "m2_before",
            "m1_before",
            "handler",
            "m1_after",
            "m2_after",
            "m3_after",
        ]


def test_app_level_middleware_early_return(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test middleware that returns early without calling next"""
    app = SilloApp()

    async def auth_middleware(ctx: HttpContext, call_next):
        token = ctx.headers.get("Authorization")
        if not token:
            return json({"error": "Unauthorized"}).status(401)
        response = await call_next()
        return response

    app.use(auth_middleware)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "authenticated"})

    with test_client_factory(app) as client:
        # Without token
        resp1 = client.get("/test")
        assert resp1.status_code == 401
        assert resp1.json()["error"] == "Unauthorized"

        # With token
        resp2 = client.get("/test", headers={"Authorization": "Bearer token"})
        assert resp2.status_code == 200
        assert resp2.json()["message"] == "authenticated"


def test_app_level_middleware_exception_handling(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test middleware handling exceptions"""
    app = SilloApp()

    async def error_handler_middleware(ctx: HttpContext, call_next):
        try:
            response = await call_next()
        except ValueError as e:
            return json({"error": str(e)}).status(400)
        return response

    app.use(error_handler_middleware)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        raise ValueError("Something went wrong")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 400
        assert "Something went wrong" in resp.json()["error"]


def test_app_level_middleware_applies_to_all_routes(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test that app-level middleware applies to all routes"""
    app = SilloApp()

    request_count = {"count": 0}

    async def counter_middleware(ctx: HttpContext, call_next):
        request_count["count"] += 1
        response = await call_next()
        return response

    app.use(counter_middleware)

    @app.get("/route1")
    async def handler1(ctx: HttpContext):
        return json({"route": "1"})

    @app.get("/route2")
    async def handler2(ctx: HttpContext):
        return json({"route": "2"})

    @app.post("/route3")
    async def handler3(ctx: HttpContext):
        return json({"route": "3"})

    with test_client_factory(app) as client:
        client.get("/route1")
        client.get("/route2")
        client.post("/route3")
        assert request_count["count"] == 3


# ========== BaseMiddleware Class Tests ==========


def test_base_middleware_class(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test using BaseMiddleware class"""
    app = SilloApp()

    class CustomMiddleware(BaseMiddleware):
        async def dispatch(self, ctx: HttpContext, call_next):
            ctx.scope["processed"] = True
            response = await call_next()
            response.set_header("X-Processed", "true")
            return response

    middleware_instance = CustomMiddleware()
    app.use(middleware_instance)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        processed = ctx.scope.get("processed", False)
        return json({"processed": processed})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.json()["processed"] is True
        assert resp.headers.get("x-processed") == "true"


def test_base_middleware_with_config(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test BaseMiddleware with configuration"""
    app = SilloApp()

    class ConfigurableMiddleware(BaseMiddleware):
        def __init__(self, prefix: str = "X-", **kwargs):
            super().__init__(**kwargs)
            self.prefix = prefix

        async def dispatch(self, ctx: HttpContext, call_next):
            response = await call_next()
            response.set_header(f"{self.prefix}Custom", "value")
            return response

    middleware_instance = ConfigurableMiddleware(prefix="Custom-")
    app.use(middleware_instance)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.headers.get("custom-custom") == "value"


# ========== Middleware State Management Tests ==========


def test_middleware_request_state(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test middleware using request state"""
    app = SilloApp()

    async def state_middleware(ctx: HttpContext, call_next):
        ctx.state.user_id = "12345"
        ctx.state.role = "admin"
        response = await call_next()
        return response

    app.use(state_middleware)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json(
            {"user_id": ctx.state.user_id, "role": ctx.state.role}
        )

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["user_id"] == "12345"
        assert data["role"] == "admin"


def test_middleware_timing(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test middleware for request timing"""
    app = SilloApp()

    import time

    async def timing_middleware(ctx: HttpContext, call_next):
        start_time = time.time()
        response = await call_next()
        process_time = time.time() - start_time
        response.set_header("X-Process-Time", str(process_time))
        return response

    app.use(timing_middleware)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert "x-process-time" in resp.headers
        process_time = float(resp.headers["x-process-time"])
        assert process_time >= 0


def test_middleware_request_id(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test middleware adding request ID"""
    app = SilloApp()

    import uuid

    async def request_id_middleware(ctx: HttpContext, call_next):
        request_id = str(uuid.uuid4())
        ctx.scope["request_id"] = request_id
        response = await call_next()
        response.set_header("X-Request-ID", request_id)
        return response

    app.use(request_id_middleware)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        request_id = ctx.scope.get("request_id")
        return json({"request_id": request_id})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        request_id_header = resp.headers.get("x-request-id")
        request_id_body = resp.json()["request_id"]
        assert request_id_header == request_id_body
        assert len(request_id_header) == 36  # UUID length
