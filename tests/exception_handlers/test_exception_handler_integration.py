"""
Tests for exception handler integration with middleware and other components
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.exceptions import HTTPException
from nexios.http import Request, Response
from nexios.routing import Router
from nexios.testclient import TestClient

# ========== Exception Handler with Middleware Integration ==========


def test_exception_handler_with_middleware(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler working with middleware"""
    app = NexiosApp()

    execution_log = []

    class CustomError(Exception):
        pass

    async def logging_middleware(request: Request, response: Response, call_next):
        execution_log.append("middleware_before")
        try:
            await call_next()
        except CustomError:
            execution_log.append("middleware_caught")
            raise
        finally:
            execution_log.append("middleware_after")
        return response

    async def error_handler(request: Request, response: Response, exc: CustomError):
        execution_log.append("error_handler")
        return response.status(400).json({"error": str(exc)})

    app.add_middleware(logging_middleware)
    app.add_exception_handler(CustomError, error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        execution_log.append("handler")
        raise CustomError("Test error")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 400
        assert "middleware_before" in execution_log
        assert "handler" in execution_log
        assert "error_handler" in execution_log


def test_exception_handler_middleware_order(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler execution order with multiple middleware"""
    app = NexiosApp()

    execution_order = []

    class TestError(Exception):
        pass

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

    async def error_handler(request: Request, response: Response, exc: TestError):
        execution_order.append("error_handler")
        return response.status(500).json({"error": "handled"})

    app.add_middleware(middleware_1)
    app.add_middleware(middleware_2)
    app.add_exception_handler(TestError, error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        execution_order.append("handler")
        raise TestError()

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert "error_handler" in execution_order


def test_exception_handler_middleware_state_access(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler accessing state set by middleware"""
    app = NexiosApp()

    class AuthError(Exception):
        pass

    async def auth_middleware(request: Request, response: Response, call_next):
        request.state.user_id = "user-456"
        request.state.authenticated = True
        await call_next()
        return response

    async def auth_error_handler(request: Request, response: Response, exc: AuthError):
        user_id = getattr(request.state, "user_id", None)
        return response.status(403).json({"error": str(exc), "user_id": user_id})

    app.add_middleware(auth_middleware)
    app.add_exception_handler(AuthError, auth_error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise AuthError("Insufficient permissions")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.json()["user_id"] == "user-456"


# ========== Exception Handler with Router Integration ==========


def test_exception_handler_with_nested_routers(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler with nested routers"""
    app = NexiosApp()
    parent_router = Router(prefix="/api")
    child_router = Router(prefix="/child")

    class RouterError(Exception):
        pass

    async def router_error_handler(
        request: Request, response: Response, exc: RouterError
    ):
        return response.status(400).json({"error": "Router error"})

    app.add_exception_handler(RouterError, router_error_handler)

    @child_router.get("/test")
    async def handler(request: Request, response: Response):
        raise RouterError("Error in nested router")

    parent_router.mount_router(child_router)
    app.mount_router(parent_router)

    with test_client_factory(app) as client:
        resp = client.get("/api/child/test")
        assert resp.status_code == 400


def test_exception_handler_different_routers(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler applies across different routers"""
    app = NexiosApp()
    router1 = Router(prefix="/api1")
    router2 = Router(prefix="/api2")

    class SharedError(Exception):
        pass

    async def shared_error_handler(
        request: Request, response: Response, exc: SharedError
    ):
        return response.status(400).json({"error": "Shared error", "message": str(exc)})

    app.add_exception_handler(SharedError, shared_error_handler)

    @router1.get("/test")
    async def handler1(request: Request, response: Response):
        raise SharedError("Error in router 1")

    @router2.get("/test")
    async def handler2(request: Request, response: Response):
        raise SharedError("Error in router 2")

    app.mount_router(router1)
    app.mount_router(router2)

    with test_client_factory(app) as client:
        resp1 = client.get("/api1/test")
        assert resp1.status_code == 400
        assert "router 1" in resp1.json()["message"]

        resp2 = client.get("/api2/test")
        assert resp2.status_code == 400
        assert "router 2" in resp2.json()["message"]


# ========== Exception Handler with Different HTTP Methods ==========


def test_exception_handler_different_methods(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler works with different HTTP methods"""
    app = NexiosApp()

    class MethodError(Exception):
        pass

    async def method_error_handler(
        request: Request, response: Response, exc: MethodError
    ):
        return response.status(400).json({"error": str(exc), "method": request.method})

    app.add_exception_handler(MethodError, method_error_handler)

    @app.get("/test")
    async def get_handler(request: Request, response: Response):
        raise MethodError("GET error")

    @app.post("/test")
    async def post_handler(request: Request, response: Response):
        raise MethodError("POST error")

    @app.put("/test")
    async def put_handler(request: Request, response: Response):
        raise MethodError("PUT error")

    with test_client_factory(app) as client:
        resp_get = client.get("/test")
        assert resp_get.json()["method"] == "GET"

        resp_post = client.post("/test")
        assert resp_post.json()["method"] == "POST"

        resp_put = client.put("/test")
        assert resp_put.json()["method"] == "PUT"


# ========== Exception Handler with Query Parameters ==========


def test_exception_handler_with_query_params(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler accessing query parameters"""
    app = NexiosApp()

    class QueryError(Exception):
        pass

    async def query_error_handler(
        request: Request, response: Response, exc: QueryError
    ):
        page = request.query_params.get("page", "1")
        return response.status(400).json({"error": str(exc), "page": page})

    app.add_exception_handler(QueryError, query_error_handler)

    @app.get("/items")
    async def handler(request: Request, response: Response):
        raise QueryError("Invalid query")

    with test_client_factory(app) as client:
        resp = client.get("/items?page=5")
        assert resp.json()["page"] == "5"


# ========== Exception Handler with Path Parameters ==========


def test_exception_handler_with_path_params(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler accessing path parameters"""
    app = NexiosApp()

    class ItemNotFoundError(Exception):
        pass

    async def item_not_found_handler(
        request: Request, response: Response, exc: ItemNotFoundError
    ):
        item_id = request.path_params.get("item_id")
        return response.status(404).json(
            {"error": "Item not found", "item_id": item_id}
        )

    app.add_exception_handler(ItemNotFoundError, item_not_found_handler)

    @app.get("/items/{item_id}")
    async def handler(request: Request, response: Response):
        raise ItemNotFoundError()

    with test_client_factory(app) as client:
        resp = client.get("/items/123")
        assert resp.json()["item_id"] == "123"


# ========== Exception Handler with Request Body ==========


def test_exception_handler_with_request_body(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler that can access request body"""
    app = NexiosApp()

    class ValidationError(Exception):
        pass

    async def validation_error_handler(
        request: Request, response: Response, exc: ValidationError
    ):
        # Note: In real scenarios, body might already be consumed
        return response.status(422).json(
            {"error": "Validation failed", "message": str(exc), "path": request.path}
        )

    app.add_exception_handler(ValidationError, validation_error_handler)

    @app.post("/data")
    async def handler(request: Request, response: Response):
        raise ValidationError("Invalid data format")

    with test_client_factory(app) as client:
        resp = client.post("/data", json={"key": "value"})
        assert resp.status_code == 422
        assert "Invalid data format" in resp.json()["message"]


# ========== Exception Handler with Headers ==========


def test_exception_handler_with_request_headers(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler accessing request headers"""
    app = NexiosApp()

    class HeaderError(Exception):
        pass

    async def header_error_handler(
        request: Request, response: Response, exc: HeaderError
    ):
        api_key = request.headers.get("X-API-Key", "none")
        return response.status(400).json({"error": str(exc), "api_key": api_key})

    app.add_exception_handler(HeaderError, header_error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise HeaderError("Header validation failed")

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"X-API-Key": "test-key"})
        assert resp.json()["api_key"] == "test-key"


# ========== Exception Handler with Cookies ==========


def test_exception_handler_with_cookies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler accessing cookies"""
    app = NexiosApp()

    class SessionError(Exception):
        pass

    async def session_error_handler(
        request: Request, response: Response, exc: SessionError
    ):
        session_id = request.cookies.get("session_id", "none")
        return response.status(401).json({"error": str(exc), "session_id": session_id})

    app.add_exception_handler(SessionError, session_error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise SessionError("Invalid session")

    with test_client_factory(app) as client:
        client.cookies.set("session_id", "abc123")
        resp = client.get("/test")
        assert resp.json()["session_id"] == "abc123"


# ========== Exception Handler Priority Tests ==========


def test_exception_handler_priority_specific_over_general(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test that specific exception handlers take priority"""
    app = NexiosApp()

    class BaseError(Exception):
        pass

    class SpecificError(BaseError):
        pass

    async def base_handler(request: Request, response: Response, exc: BaseError):
        return response.status(400).json({"handler": "base"})

    async def specific_handler(
        request: Request, response: Response, exc: SpecificError
    ):
        return response.status(422).json({"handler": "specific"})

    app.add_exception_handler(BaseError, base_handler)
    app.add_exception_handler(SpecificError, specific_handler)

    @app.get("/specific")
    async def specific_route(request: Request, response: Response):
        raise SpecificError()

    @app.get("/base")
    async def base_route(request: Request, response: Response):
        raise BaseError()

    with test_client_factory(app) as client:
        resp_specific = client.get("/specific")
        assert resp_specific.json()["handler"] == "specific"

        resp_base = client.get("/base")
        assert resp_base.json()["handler"] == "base"


# ========== Exception Handler with Complex Scenarios ==========


def test_exception_handler_complex_scenario(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler in complex scenario with middleware and routers"""
    app = NexiosApp()
    router = Router(prefix="/api")

    execution_log = []

    class ComplexError(Exception):
        pass

    async def logging_middleware(request: Request, response: Response, call_next):
        execution_log.append("middleware")
        request.state.request_id = "req-123"
        await call_next()
        return response

    async def complex_error_handler(
        request: Request, response: Response, exc: ComplexError
    ):
        execution_log.append("error_handler")
        request_id = getattr(request.state, "request_id", None)
        return response.status(500).json({"error": str(exc), "request_id": request_id})

    app.add_middleware(logging_middleware)
    app.add_exception_handler(ComplexError, complex_error_handler)

    @router.get("/test")
    async def handler(request: Request, response: Response):
        execution_log.append("handler")
        raise ComplexError("Complex error occurred")

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/test")
        assert resp.status_code == 500
        data = resp.json()
        assert data["request_id"] == "req-123"
        assert "middleware" in execution_log
        assert "handler" in execution_log
        assert "error_handler" in execution_log


def test_exception_handler_no_handler_defined(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test behavior when no exception handler is defined for an error"""
    app = NexiosApp()

    class UnhandledError(Exception):
        pass

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise UnhandledError("This error has no handler")

    with test_client_factory(app) as client:
        request = client.get("/test")
        assert request.status_code != 200


def test_exception_handler_with_successful_request(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test that exception handler doesn't interfere with successful requests"""
    app = NexiosApp()

    class TestError(Exception):
        pass

    async def test_error_handler(request: Request, response: Response, exc: TestError):
        return response.status(400).json({"error": "handled"})

    app.add_exception_handler(TestError, test_error_handler)

    @app.get("/success")
    async def success_handler(request: Request, response: Response):
        return response.json({"status": "ok"})

    @app.get("/error")
    async def error_handler(request: Request, response: Response):
        raise TestError()

    with test_client_factory(app) as client:
        # Successful request should work normally
        resp_success = client.get("/success")
        assert resp_success.status_code == 200
        assert resp_success.json()["status"] == "ok"

        # Error request should be handled
        resp_error = client.get("/error")
        assert resp_error.status_code == 400
