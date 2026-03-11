"""
Tests for basic exception handlers
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.exceptions import HTTPException, NotFoundException
from nexios.http import Request, Response
from nexios.testclient import TestClient

# ========== Basic Exception Handler Tests ==========


def test_exception_handler_custom_exception(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test handling custom exception"""
    app = NexiosApp()

    class CustomError(Exception):
        pass

    async def custom_error_handler(
        request: Request, response: Response, exc: CustomError
    ):
        return response.json({"error": "CustomError", "message": str(exc)}).status(400)

    app.add_exception_handler(CustomError, custom_error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise CustomError("Something went wrong")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "CustomError"
        assert "Something went wrong" in data["message"]


def test_exception_handler_http_exception(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test handling HTTPException"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise HTTPException(status_code=403, detail="Forbidden resource")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 403


def test_exception_handler_not_found_exception(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test handling NotFoundException"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise NotFoundException("Resource not found")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 404


def test_exception_handler_value_error(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test handling ValueError"""
    app = NexiosApp()

    async def value_error_handler(
        request: Request, response: Response, exc: ValueError
    ):
        return response.json({"error": "ValueError", "message": str(exc)}).status(400)

    app.add_exception_handler(ValueError, value_error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise ValueError("Invalid value provided")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 400
        assert "Invalid value provided" in resp.json()["message"]


def test_exception_handler_type_error(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test handling TypeError"""
    app = NexiosApp()

    async def type_error_handler(request: Request, response: Response, exc: TypeError):
        return response.json(
            {"error": "TypeError", "message": "Type mismatch"}
        ).status(400)

    app.add_exception_handler(TypeError, type_error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise TypeError("Expected string, got int")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 400
        assert resp.json()["error"] == "TypeError"


def test_exception_handler_multiple_exceptions(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test handling multiple exception types"""
    app = NexiosApp()

    class ErrorA(Exception):
        pass

    class ErrorB(Exception):
        pass

    async def error_a_handler(request: Request, response: Response, exc: ErrorA):
        return response.json({"error": "ErrorA"}).status(400)

    async def error_b_handler(request: Request, response: Response, exc: ErrorB):
        return response.json({"error": "ErrorB"}).status(500)

    app.add_exception_handler(ErrorA, error_a_handler)
    app.add_exception_handler(ErrorB, error_b_handler)

    @app.get("/error-a")
    async def handler_a(request: Request, response: Response):
        raise ErrorA()

    @app.get("/error-b")
    async def handler_b(request: Request, response: Response):
        raise ErrorB()

    with test_client_factory(app) as client:
        resp_a = client.get("/error-a")
        assert resp_a.status_code == 400
        assert resp_a.json()["error"] == "ErrorA"

        resp_b = client.get("/error-b")
        assert resp_b.status_code == 500
        assert resp_b.json()["error"] == "ErrorB"


def test_exception_handler_decorator_style(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler using decorator style"""
    app = NexiosApp()

    class CustomException(Exception):
        pass

    @app.add_exception_handler(CustomException)
    async def handle_custom_exception(
        request: Request, response: Response, exc: CustomException
    ):
        return response.json({"error": "I'm a teapot", "message": str(exc)}).status(418)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise CustomException("Teapot error")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 418
        assert resp.json()["error"] == "I'm a teapot"


# ========== Status Code Handler Tests ==========


def test_exception_handler_status_code_404(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test handling 404 status code"""
    app = NexiosApp()

    async def custom_404_handler(
        request: Request, response: Response, exc: HTTPException
    ):
        return response.json(
            {"error": "Not Found", "path": request.path, "custom": True}
        ).status(404)

    app.add_exception_handler(404, custom_404_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise HTTPException(status_code=404, detail="Page not found")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 404
        data = resp.json()
        assert data["custom"] is True
        assert data["path"] == "/test"


def test_exception_handler_status_code_500(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test handling 500 status code"""
    app = NexiosApp()

    async def custom_500_handler(
        request: Request, response: Response, exc: HTTPException
    ):
        return response.json(
            {
                "error": "Internal Server Error",
                "message": "Something went wrong on our end",
            }
        ).status(500)

    app.add_exception_handler(500, custom_500_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise HTTPException(status_code=500, detail="Server error")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 500
        assert "Something went wrong" in resp.json()["message"]


def test_exception_handler_status_code_401(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test handling 401 status code"""
    app = NexiosApp()

    async def custom_401_handler(
        request: Request, response: Response, exc: HTTPException
    ):
        return response.json(
            {"error": "Unauthorized", "login_url": "/login"}
        ).status(401)

    app.add_exception_handler(401, custom_401_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise HTTPException(status_code=401, detail="Not authenticated")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 401
        assert resp.json()["login_url"] == "/login"


# ========== Exception Handler with Headers Tests ==========


def test_exception_handler_with_custom_headers(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler adding custom headers"""
    app = NexiosApp()

    class RateLimitError(Exception):
        pass

    async def rate_limit_handler(
        request: Request, response: Response, exc: RateLimitError
    ):
        return (
            response
            .json({"error": "Rate limit exceeded", "retry_after": 60})
            .set_header("Retry-After", "60")
            .status(429)
        )

    app.add_exception_handler(RateLimitError, rate_limit_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise RateLimitError()

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 429
        assert resp.headers.get("retry-after") == "60"


def test_exception_handler_http_exception_with_headers(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test HTTPException with custom headers"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise HTTPException(
            status_code=403,
            detail="Forbidden",
            headers={"X-Custom-Header": "custom-value"},
        )

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 403
        assert resp.headers.get("x-custom-header") == "custom-value"


# ========== Exception Inheritance Tests ==========


def test_exception_handler_inheritance(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler with inheritance"""
    app = NexiosApp()

    class BaseError(Exception):
        pass

    class SpecificError(BaseError):
        pass

    async def base_error_handler(request: Request, response: Response, exc: BaseError):
        return response.json({"error": "BaseError"}).status(400)

    app.add_exception_handler(BaseError, base_error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise SpecificError("Specific error")

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 400
        assert resp.json()["error"] == "BaseError"


def test_exception_handler_specific_over_base(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test that specific exception handler takes precedence over base"""
    app = NexiosApp()

    class BaseError(Exception):
        pass

    class SpecificError(BaseError):
        pass

    async def base_error_handler(request: Request, response: Response, exc: BaseError):
        return response.status(400).json({"error": "BaseError"})

    async def specific_error_handler(
        request: Request, response: Response, exc: SpecificError
    ):
        return response.json({"error": "SpecificError"}).status(422)

    app.add_exception_handler(BaseError, base_error_handler)
    app.add_exception_handler(SpecificError, specific_error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise SpecificError()

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 422
        assert resp.json()["error"] == "SpecificError"


# ========== Exception Handler Context Tests ==========


def test_exception_handler_access_request_data(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler accessing request data"""
    app = NexiosApp()

    class ValidationError(Exception):
        pass

    async def validation_error_handler(
        request: Request, response: Response, exc: ValidationError
    ):
        return (
            response.json(
                {
                    "error": "Validation failed",
                    "path": request.path,
                    "method": request.method,
                    "message": str(exc),
                }
            )
            .status(400)
        )

    app.add_exception_handler(ValidationError, validation_error_handler)

    @app.post("/test")
    async def handler(request: Request, response: Response):
        raise ValidationError("Invalid input")

    with test_client_factory(app) as client:
        resp = client.post("/test")
        data = resp.json()
        assert data["path"] == "/test"
        assert data["method"] == "POST"
        assert "Invalid input" in data["message"]


def test_exception_handler_with_exception_details(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test exception handler with detailed exception info"""
    app = NexiosApp()

    class DetailedError(Exception):
        def __init__(self, message: str, code: int):
            super().__init__(message)
            self.code = code

    async def detailed_error_handler(
        request: Request, response: Response, exc: DetailedError
    ):
        return response.json(
            {"error": "DetailedError", "message": str(exc), "code": exc.code}
        ).status(400)

    app.add_exception_handler(DetailedError, detailed_error_handler)

    @app.get("/test")
    async def handler(request: Request, response: Response):
        raise DetailedError("Custom error", code=1001)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["code"] == 1001
        assert "Custom error" in data["message"]
