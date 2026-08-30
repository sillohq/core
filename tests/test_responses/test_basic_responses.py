"""
Tests for basic response types (text, json, html, empty)
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import empty, html, json, text
from sillo.core.http import HttpContext
from sillo.testclient import TestClient

# ========== Text Response Tests ==========


def test_text_response(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test basic text response"""
    app = SilloApp()

    @app.get("/text")
    async def text_handler(ctx: HttpContext):
        return text("Hello, World!")

    with test_client_factory(app) as client:
        resp = client.get("/text")
        assert resp.status_code == 200
        assert resp.text == "Hello, World!"
        assert "text/plain" in resp.headers.get("content-type", "")


def test_text_response_with_status_code(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test text response with custom status code"""
    app = SilloApp()

    @app.get("/text-created")
    async def text_created(ctx: HttpContext):
        return text("Resource created", status_code=201)

    with test_client_factory(app) as client:
        resp = client.get("/text-created")
        assert resp.status_code == 201
        assert resp.text == "Resource created"


def test_text_response_with_headers(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test text response with custom headers"""
    app = SilloApp()

    @app.get("/text-headers")
    async def text_headers(ctx: HttpContext):
        return text("Custom headers", headers={"X-Custom": "value"})

    with test_client_factory(app) as client:
        resp = client.get("/text-headers")
        assert resp.status_code == 200
        assert resp.headers.get("x-custom") == "value"


# ========== JSON Response Tests ==========


def test_json_response(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test basic JSON response"""
    app = SilloApp()

    @app.get("/json")
    async def json_handler(ctx: HttpContext):
        return json({"message": "Hello", "status": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/json")
        assert resp.status_code == 200
        assert resp.json() == {"message": "Hello", "status": "ok"}
        assert "application/json" in resp.headers.get("content-type", "")


def test_json_response_with_list(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test JSON response with list data"""
    app = SilloApp()

    @app.get("/items")
    async def get_items(ctx: HttpContext):
        return json([{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}])

    with test_client_factory(app) as client:
        resp = client.get("/items")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == 1


def test_json_response_with_status_code(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test JSON response with custom status code"""
    app = SilloApp()

    @app.post("/create")
    async def create_resource(ctx: HttpContext):
        return json({"id": 123, "created": True}, status_code=201)

    with test_client_factory(app) as client:
        resp = client.post("/create")
        assert resp.status_code == 201
        assert resp.json()["created"] is True


def test_json_response_with_indent(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test JSON response with indentation"""
    app = SilloApp()

    @app.get("/pretty")
    async def pretty_json(ctx: HttpContext):
        return json({"key": "value"}, indent=2)

    with test_client_factory(app) as client:
        resp = client.get("/pretty")
        assert resp.status_code == 200
        # Check that response is indented
        assert "\n" in resp.text


def test_json_response_with_nested_data(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test JSON response with nested data structures"""
    app = SilloApp()

    @app.get("/nested")
    async def nested_json(ctx: HttpContext):
        data = {
            "user": {"id": 1, "name": "Alice", "profile": {"age": 30, "city": "NYC"}}
        }
        return json(data)

    with test_client_factory(app) as client:
        resp = client.get("/nested")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["profile"]["city"] == "NYC"


# ========== HTML Response Tests ==========


def test_html_response(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test basic HTML response"""
    app = SilloApp()

    @app.get("/html")
    async def html_handler(ctx: HttpContext):
        return html("<h1>Hello World</h1>")

    with test_client_factory(app) as client:
        resp = client.get("/html")
        assert resp.status_code == 200
        assert "<h1>Hello World</h1>" in resp.text
        assert "text/html" in resp.headers.get("content-type", "")


def test_html_response_with_full_page(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test HTML response with full HTML page"""
    app = SilloApp()

    @app.get("/page")
    async def html_page(ctx: HttpContext):
        page = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Page</title></head>
        <body><h1>Welcome</h1></body>
        </html>
        """
        return html(page)

    with test_client_factory(app) as client:
        resp = client.get("/page")
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text
        assert "<title>Test Page</title>" in resp.text


def test_html_response_with_status_code(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test HTML response with custom status code"""
    app = SilloApp()

    @app.get("/error")
    async def html_error(ctx: HttpContext):
        return html("<h1>Not Found</h1>", status_code=404)

    with test_client_factory(app) as client:
        resp = client.get("/error")
        assert resp.status_code == 404
        assert "<h1>Not Found</h1>" in resp.text


# ========== Empty Response Tests ==========


def test_empty_response(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test empty response"""
    app = SilloApp()

    @app.get("/empty")
    async def empty_handler(ctx: HttpContext):
        return empty()

    with test_client_factory(app) as client:
        resp = client.get("/empty")
        assert resp.status_code == 204
        assert resp.text == ""


def test_empty_response_with_status_code(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test empty response with custom status code"""
    app = SilloApp()

    @app.delete("/resource/{id}")
    async def delete_resource(ctx: HttpContext, id: str):
        return empty(status_code=204)

    with test_client_factory(app) as client:
        resp = client.delete("/resource/123")
        assert resp.status_code == 204
        assert resp.text == ""


# ========== Status Code Tests ==========


def test_response_status_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test setting status code using status() method"""
    app = SilloApp()

    @app.get("/custom-status")
    async def custom_status(ctx: HttpContext):
        return text("I'm a teapot").status(418)

    with test_client_factory(app) as client:
        resp = client.get("/custom-status")
        assert resp.status_code == 418
        assert resp.text == "I'm a teapot"


def test_response_chaining(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test method chaining on response"""
    app = SilloApp()

    @app.get("/chain")
    async def chain_methods(ctx: HttpContext):
        return json({"created": True}).status(201)

    with test_client_factory(app) as client:
        resp = client.get("/chain")
        assert resp.status_code == 201
        assert resp.json()["created"] is True


# ========== Content Type Tests ==========


def test_response_content_type_text(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test content-type header for text response"""
    app = SilloApp()

    @app.get("/text")
    async def text_response(ctx: HttpContext):
        return text("Plain text")

    with test_client_factory(app) as client:
        resp = client.get("/text")
        content_type = resp.headers.get("content-type", "")
        assert "text/plain" in content_type


def test_response_content_type_json(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test content-type header for JSON response"""
    app = SilloApp()

    @app.get("/json")
    async def json_response(ctx: HttpContext):
        return json({"test": "data"})

    with test_client_factory(app) as client:
        resp = client.get("/json")
        content_type = resp.headers.get("content-type", "")
        assert "application/json" in content_type


def test_response_content_type_html(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test content-type header for HTML response"""
    app = SilloApp()

    @app.get("/html")
    async def html_response(ctx: HttpContext):
        return html("<p>HTML content</p>")

    with test_client_factory(app) as client:
        resp = client.get("/html")
        content_type = resp.headers.get("content-type", "")
        assert "text/html" in content_type
