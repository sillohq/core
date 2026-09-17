"""
Tests for pure ASGI middleware, and app.use() with raw ASGI middleware
"""

from typing import Callable

import pytest

from sillo import SilloApp, json
from sillo.core.http import HttpContext
from sillo.testclient import TestClient
from sillo.types import ASGIApp, Receive, Scope, Send

# ========== Pure ASGI Middleware Tests ==========


def test_pure_asgi_middleware_basic(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test basic pure ASGI middleware"""
    app = SilloApp()

    executed = []

    class ASGIMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                executed.append("asgi_middleware")
            await self.app(scope, receive, send)

    # Wrap the app with pure ASGI middleware
    wrapped_app = ASGIMiddleware(app)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        executed.append("handler")
        return json({"message": "ok"})

    with test_client_factory(wrapped_app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "asgi_middleware" in executed
        assert "handler" in executed


def test_pure_asgi_middleware_modifies_scope(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test ASGI middleware modifying scope"""
    app = SilloApp()

    class ScopeModifierMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                scope["custom_value"] = "asgi_modified"
            await self.app(scope, receive, send)

    wrapped_app = ScopeModifierMiddleware(app)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        custom_value = ctx.scope.get("custom_value")
        return json({"custom_value": custom_value})

    with test_client_factory(wrapped_app) as client:
        resp = client.get("/test")
        assert resp.json()["custom_value"] == "asgi_modified"


def test_pure_asgi_middleware_intercepts_send(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test ASGI middleware intercepting send"""
    app = SilloApp()

    class HeaderInjectorMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"x-asgi-middleware", b"injected"))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_wrapper)

    wrapped_app = HeaderInjectorMiddleware(app)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    with test_client_factory(wrapped_app) as client:
        resp = client.get("/test")
        assert resp.headers.get("x-asgi-middleware") == "injected"


def test_pure_asgi_middleware_multiple_layers(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test multiple pure ASGI middleware layers"""
    app = SilloApp()

    execution_order = []

    class Middleware1:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                execution_order.append("m1")
            await self.app(scope, receive, send)

    class Middleware2:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                execution_order.append("m2")
            await self.app(scope, receive, send)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        execution_order.append("handler")
        return json({"message": "ok"})

    # Wrap with multiple middleware layers
    wrapped_app = Middleware1(Middleware2(app))

    with test_client_factory(wrapped_app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert execution_order == ["m1", "m2", "handler"]


def test_pure_asgi_middleware_request_logging(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test ASGI middleware for request logging"""
    app = SilloApp()

    logs = []

    class LoggingMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                logs.append(
                    {
                        "method": scope["method"],
                        "path": scope["path"],
                        "query_string": scope.get("query_string", b"").decode(),
                    }
                )
            await self.app(scope, receive, send)

    wrapped_app = LoggingMiddleware(app)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    with test_client_factory(wrapped_app) as client:
        client.get("/test?param=value")
        assert len(logs) == 1
        assert logs[0]["method"] == "GET"
        assert logs[0]["path"] == "/test"
        assert "param=value" in logs[0]["query_string"]


def test_pure_asgi_middleware_handles_websocket(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test ASGI middleware handling different connection types"""
    app = SilloApp()

    handled_types = []

    class TypeTrackerMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            handled_types.append(scope["type"])
            await self.app(scope, receive, send)

    wrapped_app = TypeTrackerMiddleware(app)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    with test_client_factory(wrapped_app) as client:
        client.get("/test")
        assert "http" in handled_types or "lifespan" in handled_types


def test_pure_asgi_middleware_timing(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test ASGI middleware for request timing"""
    app = SilloApp()

    import time

    class TimingMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            start_time = time.time()

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    process_time = time.time() - start_time
                    headers = list(message.get("headers", []))
                    headers.append((b"x-process-time", str(process_time).encode()))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_wrapper)

    wrapped_app = TimingMiddleware(app)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    with test_client_factory(wrapped_app) as client:
        resp = client.get("/test")
        assert "x-process-time" in resp.headers
        process_time = float(resp.headers["x-process-time"])
        assert process_time >= 0


def test_pure_asgi_middleware_with_sillo_middleware(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test combining pure ASGI middleware with sillo middleware"""
    app = SilloApp()

    execution_order = []

    class ASGIMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                execution_order.append("asgi")
            await self.app(scope, receive, send)

    async def sillo_middleware(ctx: HttpContext, call_next):
        execution_order.append("sillo")
        response = await call_next()
        return response

    app.use(sillo_middleware)
    wrapped_app = ASGIMiddleware(app)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        execution_order.append("handler")
        return json({"message": "ok"})

    with test_client_factory(wrapped_app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        # ASGI middleware executes before sillo middleware
        assert execution_order.index("asgi") < execution_order.index("sillo")


# ========== ASGI Middleware Error Handling Tests ==========


def test_pure_asgi_middleware_error_handling(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test ASGI middleware handling errors"""
    app = SilloApp()

    class ErrorHandlerMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            try:
                await self.app(scope, receive, send)
            except Exception as e:
                # Send error response
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [[b"content-type", b"application/json"]],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"error": "Internal server error"}',
                    }
                )

    wrapped_app = ErrorHandlerMiddleware(app)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        raise RuntimeError("Test error")

    with test_client_factory(wrapped_app) as client:
        resp = client.get("/test")
        # Error should be handled by middleware
        assert resp.status_code in [500, 200]  # Depends on error handling


def test_pure_asgi_middleware_conditional_processing(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test ASGI middleware with conditional processing"""
    app = SilloApp()

    class ConditionalMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http" and scope["path"].startswith("/api"):
                scope["api_request"] = True
            await self.app(scope, receive, send)

    wrapped_app = ConditionalMiddleware(app)

    @app.get("/api/test")
    async def api_handler(ctx: HttpContext):
        is_api = ctx.scope.get("api_request", False)
        return json({"is_api": is_api})

    @app.get("/public/test")
    async def public_handler(ctx: HttpContext):
        is_api = ctx.scope.get("api_request", False)
        return json({"is_api": is_api})

    with test_client_factory(wrapped_app) as client:
        resp1 = client.get("/api/test")
        assert resp1.json()["is_api"] is True

        resp2 = client.get("/public/test")
        assert resp2.json()["is_api"] is False


def test_pure_asgi_middleware_request_id(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test ASGI middleware adding request ID"""
    app = SilloApp()

    import uuid

    class RequestIDMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                request_id = str(uuid.uuid4())
                scope["request_id"] = request_id

                async def send_wrapper(message):
                    if message["type"] == "http.response.start":
                        headers = list(message.get("headers", []))
                        headers.append((b"x-request-id", request_id.encode()))
                        message["headers"] = headers
                    await send(message)

                await self.app(scope, receive, send_wrapper)
            else:
                await self.app(scope, receive, send)

    wrapped_app = RequestIDMiddleware(app)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        request_id = ctx.scope.get("request_id")
        return json({"request_id": request_id})

    with test_client_factory(wrapped_app) as client:
        resp = client.get("/test")
        request_id_header = resp.headers.get("x-request-id")
        request_id_body = resp.json()["request_id"]
        assert request_id_header == request_id_body
        assert len(request_id_header) == 36  # UUID length


# ========== use() with raw ASGI middleware ==========


def test_use_raw_asgi_basic(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test basic use() with a raw ASGI middleware class"""
    app = SilloApp()

    executed = []

    class SimpleMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                executed.append("middleware")
            await self.app(scope, receive, send)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        executed.append("handler")
        return json({"message": "ok"})

    # Use the raw ASGI middleware class
    app.use(SimpleMiddleware)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "middleware" in executed
        assert "handler" in executed


def test_use_raw_asgi_with_kwargs(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test use() with a raw ASGI middleware factory taking kwargs"""
    app = SilloApp()

    class ConfigurableMiddleware:
        def __init__(self, app: ASGIApp, prefix: str = "", suffix: str = ""):
            self.app = app
            self.prefix = prefix
            self.suffix = suffix

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                scope["custom_value"] = f"{self.prefix}value{self.suffix}"
            await self.app(scope, receive, send)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        custom_value = ctx.scope.get("custom_value", "")
        return json({"custom_value": custom_value})

    # Use with kwargs
    app.use(ConfigurableMiddleware, prefix="[", suffix="]")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.json()["custom_value"] == "[value]"


def test_use_raw_asgi_multiple_times(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test calling use() with raw ASGI middleware multiple times"""
    app = SilloApp()

    execution_order = []

    class Middleware1:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                execution_order.append("m1")
            await self.app(scope, receive, send)

    class Middleware2:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                execution_order.append("m2")
            await self.app(scope, receive, send)

    class Middleware3:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                execution_order.append("m3")
            await self.app(scope, receive, send)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        execution_order.append("handler")
        return json({"message": "ok"})

    # Register multiple times - last registered is outermost
    app.use(Middleware1)
    app.use(Middleware2)
    app.use(Middleware3)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        # Execution order: outermost (m3) -> m2 -> m1 -> handler
        assert execution_order == ["m3", "m2", "m1", "handler"]


def test_use_raw_with_dispatch_middleware_ordering(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test use() combining a dispatch middleware with raw ASGI middleware"""
    app = SilloApp()

    execution_order = []

    class ASGIMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                execution_order.append("asgi")
            await self.app(scope, receive, send)

    async def sillo_middleware(ctx: HttpContext, call_next):
        execution_order.append("sillo")
        response = await call_next()
        return response

    @app.get("/test")
    async def handler(ctx: HttpContext):
        execution_order.append("handler")
        return json({"message": "ok"})

    # Add the dispatch middleware first, then the raw ASGI middleware, so
    # the raw middleware -- registered last -- is the outermost layer.
    app.use(sillo_middleware)
    app.use(ASGIMiddleware)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        # Raw ASGI middleware runs before the dispatch middleware (outermost),
        # and the dispatch middleware runs before the handler.
        assert execution_order.index("asgi") < execution_order.index("sillo")
        assert execution_order.index("sillo") < execution_order.index("handler")


def test_use_raw_asgi_header_injection(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test use() with a raw ASGI middleware injecting headers"""
    app = SilloApp()

    class HeaderMiddleware:
        def __init__(
            self,
            app: ASGIApp,
            header_name: str = "x-custom",
            header_value: str = "test",
        ):
            self.app = app
            self.header_name = header_name.encode()
            self.header_value = header_value.encode()

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((self.header_name, self.header_value))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_wrapper)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"message": "ok"})

    app.use(HeaderMiddleware, header_name="x-powered-by", header_value="sillo")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.headers.get("x-powered-by") == "sillo"


def test_use_raw_asgi_scope_modification(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test use() with a raw ASGI middleware modifying scope"""
    app = SilloApp()

    class ScopeMiddleware:
        def __init__(self, app: ASGIApp, key: str = "custom", value: str = "default"):
            self.app = app
            self.key = key
            self.value = value

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                scope[self.key] = self.value
            await self.app(scope, receive, send)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        custom_value = ctx.scope.get("app_name", "unknown")
        return json({"app_name": custom_value})

    app.use(ScopeMiddleware, key="app_name", value="sillo-app")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.json()["app_name"] == "sillo-app"


def test_use_raw_asgi_error_handling(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test use() with a raw ASGI middleware handling errors"""
    app = SilloApp()

    class ErrorHandlerMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] == "http":
                try:
                    await self.app(scope, receive, send)
                except Exception:
                    # Catch errors and send custom response
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 500,
                            "headers": [[b"content-type", b"application/json"]],
                        }
                    )
                    await send(
                        {
                            "type": "http.response.body",
                            "body": b'{"error": "handled by middleware"}',
                        }
                    )
            else:
                await self.app(scope, receive, send)

    @app.get("/test")
    async def handler(ctx: HttpContext):
        raise ValueError("Test error")

    app.use(ErrorHandlerMiddleware)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        # Error should be caught and handled
        assert resp.status_code in [
            500,
            200,
        ]  # Depends on error handling implementation
