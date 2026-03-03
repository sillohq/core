"""
Tests for advanced response features (pagination, custom responses, etc.)
"""

from typing import Any, Callable, Dict, List

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.http.response import (
    BaseResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
)
from nexios.testclient import TestClient

# ========== Custom Response Class Tests ==========


def test_custom_response_class(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test using custom response class with make_response"""
    app = NexiosApp()

    @app.get("/custom")
    async def custom_response(request: Request, response: Response):
        custom = PlainTextResponse(body="Custom class response", status_code=200)
        return response.make_response(custom)

    with test_client_factory(app) as client:
        resp = client.get("/custom")
        assert resp.status_code == 200
        assert resp.text == "Custom class response"


def test_custom_json_response_class(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test using JSONResponse class directly"""
    app = NexiosApp()

    @app.get("/custom-json")
    async def custom_json(request: Request, response: Response):
        custom = JSONResponse(content={"custom": True}, status_code=201)
        return response.make_response(custom)

    with test_client_factory(app) as client:
        resp = client.get("/custom-json")
        assert resp.status_code == 201
        assert resp.json()["custom"] is True


def test_custom_html_response_class(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test using HTMLResponse class directly"""
    app = NexiosApp()

    @app.get("/custom-html")
    async def custom_html(request: Request, response: Response):
        custom = HTMLResponse(content="<h1>Custom HTML</h1>", status_code=200)
        return response.make_response(custom)

    with test_client_factory(app) as client:
        resp = client.get("/custom-html")
        assert resp.status_code == 200
        assert "<h1>Custom HTML</h1>" in resp.text


# ========== Response with Different Data Types Tests ==========


def test_response_with_none(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test response with None values"""
    app = NexiosApp()

    @app.get("/with-none")
    async def with_none(request: Request, response: Response):
        return response.json({"value": None, "exists": True})

    with test_client_factory(app) as client:
        resp = client.get("/with-none")
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] is None
        assert data["exists"] is True


def test_response_with_boolean(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test response with boolean values"""
    app = NexiosApp()

    @app.get("/with-boolean")
    async def with_boolean(request: Request, response: Response):
        return response.json({"success": True, "failed": False})

    with test_client_factory(app) as client:
        resp = client.get("/with-boolean")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["failed"] is False


def test_response_with_numbers(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test response with various number types"""
    app = NexiosApp()

    @app.get("/with-numbers")
    async def with_numbers(request: Request, response: Response):
        return response.json(
            {"integer": 42, "float": 3.14159, "negative": -100, "zero": 0}
        )

    with test_client_factory(app) as client:
        resp = client.get("/with-numbers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["integer"] == 42
        assert data["float"] == 3.14159
        assert data["negative"] == -100
        assert data["zero"] == 0


def test_response_with_unicode(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test response with unicode characters"""
    app = NexiosApp()

    @app.get("/with-unicode")
    async def with_unicode(request: Request, response: Response):
        return response.json(
            {"emoji": "", "chinese": "你好", "arabic": "مرحبا", "special": "café"}
        )

    with test_client_factory(app) as client:
        resp = client.get("/with-unicode")
        assert resp.status_code == 200
        data = resp.json()
        assert data["emoji"] == ""
        assert data["chinese"] == "你好"


def test_response_with_empty_string(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test response with empty string"""
    app = NexiosApp()

    @app.get("/empty-string")
    async def empty_string(request: Request, response: Response):
        return response.json({"value": "", "name": "test"})

    with test_client_factory(app) as client:
        resp = client.get("/empty-string")
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == ""


# ========== Response Encoding Tests ==========


def test_response_ensure_ascii_false(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test JSON response with ensure_ascii=False"""
    app = NexiosApp()

    @app.get("/no-ascii")
    async def no_ascii(request: Request, response: Response):
        return response.json({"text": "café"}, ensure_ascii=False)

    with test_client_factory(app) as client:
        resp = client.get("/no-ascii")
        assert resp.status_code == 200


def test_response_ensure_ascii_true(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test JSON response with ensure_ascii=True"""
    app = NexiosApp()

    @app.get("/with-ascii")
    async def with_ascii(request: Request, response: Response):
        return response.json({"text": "café"}, ensure_ascii=True)

    with test_client_factory(app) as client:
        resp = client.get("/with-ascii")
        assert resp.status_code == 200


# ========== Response Size Tests ==========


def test_response_large_json(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test response with large JSON payload"""
    app = NexiosApp()

    @app.get("/large-json")
    async def large_json(request: Request, response: Response):
        # Create a large list
        items = [{"id": i, "data": f"value_{i}" * 10} for i in range(1000)]
        return response.json({"items": items})

    with test_client_factory(app) as client:
        resp = client.get("/large-json")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1000


def test_response_large_text(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test response with large text payload"""
    app = NexiosApp()

    @app.get("/large-text")
    async def large_text(request: Request, response: Response):
        # Create large text (1MB)
        text = "x" * (1024 * 1024)
        return response.text(text)

    with test_client_factory(app) as client:
        resp = client.get("/large-text")
        assert resp.status_code == 200
        assert len(resp.text) == 1024 * 1024


# ========== Response Conditional Tests ==========


def test_conditional_response_type(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test conditional response based on accept header"""
    app = NexiosApp()

    @app.get("/conditional")
    async def conditional_response(request: Request, response: Response):
        accept = request.headers.get("accept", "")

        data = {"message": "Hello", "status": "ok"}

        if "application/json" in accept:
            return response.json(data)
        elif "text/html" in accept:
            return response.html(f"<div>{data}</div>")
        else:
            return response.text(str(data))

    with test_client_factory(app) as client:
        # Request JSON
        resp_json = client.get("/conditional", headers={"accept": "application/json"})
        assert resp_json.status_code == 200
        assert "application/json" in resp_json.headers.get("content-type", "")

        # Request HTML
        resp_html = client.get("/conditional", headers={"accept": "text/html"})
        assert resp_html.status_code == 200
        assert "text/html" in resp_html.headers.get("content-type", "")


def test_response_based_on_method(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test different responses based on HTTP method"""
    app = NexiosApp()

    @app.route("/resource", methods=["GET", "POST", "PUT", "DELETE"])
    async def resource_handler(request: Request, response: Response):
        method = request.method

        if method == "GET":
            return response.json({"action": "read"})
        elif method == "POST":
            return response.status(201).json({"action": "created"})
        elif method == "PUT":
            return response.json({"action": "updated"})
        elif method == "DELETE":
            return response.status(204).empty()

    with test_client_factory(app) as client:
        get_resp = client.get("/resource")
        assert get_resp.json()["action"] == "read"

        post_resp = client.post("/resource")
        assert post_resp.status_code == 201

        put_resp = client.put("/resource")
        assert put_resp.json()["action"] == "updated"

        delete_resp = client.delete("/resource")
        assert delete_resp.status_code == 204
