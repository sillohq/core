"""
Tests for application-level middleware
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.middleware.base import BaseMiddleware
from nexios.testclient import TestClient

# ========== Basic App-Level Middleware Tests ==========


def test_app_level_middleware_basic(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test basic app-level middleware"""
    app = NexiosApp()

    executed = []

    async def logging_middleware(request: Request, response: Response, call_next):
        executed.append("before")
        await call_next()
        executed.append("after")
        return response

    app.add_middleware(logging_middleware)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        executed.append("handler")
        return response.json({"message": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert executed == ["before", "handler", "after"]


def test_app_level_middleware_modifies_request(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test middleware that modifies request"""
    app = NexiosApp()

    async def add_custom_header_middleware(
        request: Request, response: Response, call_next
    ):
        request.scope["custom_data"] = "middleware_value"
        await call_next()
        return response

    app.add_middleware(add_custom_header_middleware)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        custom_data = request.scope.get("custom_data")
        return response.json({"custom_data": custom_data})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.json()["custom_data"] == "middleware_value"


def test_app_level_middleware_modifies_response(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test middleware that modifies response"""
    app = NexiosApp()

    async def add_response_header_middleware(
        request: Request, response: Response, call_next
    ):
        await call_next()
        response.set_header("X-Custom-Header", "middleware-added")
        return response

    app.add_middleware(add_response_header_middleware)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json({"message": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.headers.get("x-custom-header") == "middleware-added"


def test_app_level_middleware_multiple(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test multiple app-level middleware execution order"""
    app = NexiosApp()

    execution_order = []

    async def middleware_1(request: Request, response: Response, call_next):
        execution_order.append("m1_before")
        await call_next()
        execution_order.append("m1_after")
        return response

    async def middleware_2(request: Request, response: Response, call_next):
        execution_order.append("m2_before")
        await call_next()
        execution_order.append("m2_after")
        return response

    async def middleware_3(request: Request, response: Response, call_next):
        execution_order.append("m3_before")
        await call_next()
        execution_order.append("m3_after")
        return response

    app.add_middleware(middleware_1)
    app.add_middleware(middleware_2)
    app.add_middleware(middleware_3)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        execution_order.append("handler")
        return response.json({"message": "ok"})

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
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test middleware that returns early without calling next"""
    app = NexiosApp()

    async def auth_middleware(request: Request, response: Response, call_next):
        token = request.headers.get("Authorization")
        if not token:
            return response.json({"error": "Unauthorized"}).status(401)
        await call_next()
        return response

    app.add_middleware(auth_middleware)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json({"message": "authenticated"})

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
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test middleware handling exceptions"""
    app = NexiosApp()

    async def error_handler_middleware(request: Request, response: Response, call_next):
        try:
            await call_next()
        except ValueError as e:
            return response.json({"error": str(e)}).status(400)
        return response

    app.add_middleware(error_handler_middleware)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise ValueError("Something went wrong")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 400
        assert "Something went wrong" in resp.json()["error"]


def test_app_level_middleware_applies_to_all_routes(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test that app-level middleware applies to all routes"""
    app = NexiosApp()

    request_count = {"count": 0}

    async def counter_middleware(request: Request, response: Response, call_next):
        request_count["count"] += 1
        await call_next()
        return response

    app.add_middleware(counter_middleware)

    @app.get("/route1")
    async def handler1(request: Request, response: Response):
        return response.json({"route": "1"})

    @app.get("/route2")
    async def handler2(request: Request, response: Response):
        return response.json({"route": "2"})

    @app.post("/route3")
    async def handler3(request: Request, response: Response):
        return response.json({"route": "3"})

    with test_client_factory(app) as client:
        client.get("/route1")
        client.get("/route2")
        client.post("/route3")
        assert request_count["count"] == 3


# ========== BaseMiddleware Class Tests ==========


def test_base_middleware_class(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test using BaseMiddleware class"""
    app = NexiosApp()

    class CustomMiddleware(BaseMiddleware):
        async def process_request(
            self, request: Request, response: Response, call_next
        ):
            request.scope["processed"] = True
            return await call_next()

        async def process_response(self, request: Request, response: Response):
            response.set_header("X-Processed", "true")
            return response

    middleware_instance = CustomMiddleware()
    app.add_middleware(middleware_instance)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        processed = request.scope.get("processed", False)
        return response.json({"processed": processed})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.json()["processed"] is True
        assert resp.headers.get("x-processed") == "true"


def test_base_middleware_with_config(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test BaseMiddleware with configuration"""
    app = NexiosApp()

    class ConfigurableMiddleware(BaseMiddleware):
        def __init__(self, prefix: str = "X-", **kwargs):
            super().__init__(**kwargs)
            self.prefix = prefix

        async def process_request(
            self, request: Request, response: Response, call_next
        ):
            return await call_next()

        async def process_response(self, request: Request, response: Response):
            response.set_header(f"{self.prefix}Custom", "value")
            return response

    middleware_instance = ConfigurableMiddleware(prefix="Custom-")
    app.add_middleware(middleware_instance)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json({"message": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.headers.get("custom-custom") == "value"


# ========== Middleware State Management Tests ==========


def test_middleware_request_state(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test middleware using request state"""
    app = NexiosApp()

    async def state_middleware(request: Request, response: Response, call_next):
        request.state.user_id = "12345"
        request.state.role = "admin"
        await call_next()
        return response

    app.add_middleware(state_middleware)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json(
            {"user_id": request.state.user_id, "role": request.state.role}
        )

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["user_id"] == "12345"
        assert data["role"] == "admin"


def test_middleware_timing(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test middleware for request timing"""
    app = NexiosApp()

    import time

    async def timing_middleware(request: Request, response: Response, call_next):
        start_time = time.time()
        await call_next()
        process_time = time.time() - start_time
        response.set_header("X-Process-Time", str(process_time))
        return response

    app.add_middleware(timing_middleware)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json({"message": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert "x-process-time" in resp.headers
        process_time = float(resp.headers["x-process-time"])
        assert process_time >= 0


def test_middleware_request_id(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test middleware adding request ID"""
    app = NexiosApp()

    import uuid

    async def request_id_middleware(request: Request, response: Response, call_next):
        request_id = str(uuid.uuid4())
        request.scope["request_id"] = request_id
        await call_next()
        response.set_header("X-Request-ID", request_id)
        return response

    app.add_middleware(request_id_middleware)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        request_id = request.scope.get("request_id")
        return response.json({"request_id": request_id})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        request_id_header = resp.headers.get("x-request-id")
        request_id_body = resp.json()["request_id"]
        assert request_id_header == request_id_body
        assert len(request_id_header) == 36  # UUID length
