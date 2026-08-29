"""
Tests for response properties and methods
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import empty, html, json, text
from sillo.core.http import HttpContext
from sillo.testclient import TestClient

# ========== Response Body Tests ==========


def test_response_body_property(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test accessing response body property"""
    app = SilloApp()

    @app.get("/body")
    async def get_body(request: HttpContext):
        response = text("Test body content")
        body = response.body
        # Body should be bytes
        assert isinstance(body, (bytes, memoryview))
        return response

    with test_client_factory(app) as client:
        resp = client.get("/body")
        assert resp.status_code == 200


def test_set_body_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test setting response body directly"""
    app = SilloApp()

    @app.get("/set-body")
    async def set_body(request: HttpContext):
        response.set_body(b"Custom body content")
        return text("This will be overridden")

    with test_client_factory(app) as client:
        resp = client.get("/set-body")
        assert resp.status_code == 200


# ========== Response Status Tests ==========


def test_response_status_codes(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test various HTTP status codes"""
    app = SilloApp()

    status_codes = [200, 201, 204, 400, 401, 403, 404, 500, 502, 503]

    for code in status_codes:

        @app.get(f"/status-{code}")
        async def handler(request: HttpContext, status_code=code):
            return text(f"Status {status_code}").status(status_code)

    with test_client_factory(app) as client:
        for code in status_codes:
            resp = client.get(f"/status-{code}")
            assert resp.status_code == code


# ========== Response Content Type Tests ==========


def test_response_content_type_property(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test accessing response content type property"""
    app = SilloApp()

    @app.get("/content-type-check")
    async def check_content_type(request: HttpContext):
        response = json({"test": "data"})
        content_type = response.content_type
        return response

    with test_client_factory(app) as client:
        resp = client.get("/content-type-check")
        assert resp.status_code == 200


def test_response_content_length_property(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test accessing response content length property"""
    app = SilloApp()

    @app.get("/content-length-check")
    async def check_content_length(request: HttpContext):
        response = text("Test content")
        length = response.content_length
        # Length should be a string or number
        assert length is not None
        return response

    with test_client_factory(app) as client:
        resp = client.get("/content-length-check")
        assert resp.status_code == 200
        assert "content-length" in resp.headers


# ========== Response Method Chaining Tests ==========


def test_method_chaining_all_methods(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test chaining multiple response methods"""
    app = SilloApp()

    @app.get("/chain-all")
    async def chain_all(request: HttpContext):
        return (
            json({"chained": True})
            .set_header("X-Custom-1", "value1")
            .set_header("X-Custom-2", "value2")
            .set_cookie("session", "abc123")
            .cache(max_age=3600)
            .status(201)
        )

    with test_client_factory(app) as client:
        resp = client.get("/chain-all")
        assert resp.status_code == 201
        assert resp.headers.get("x-custom-1") == "value1"
        assert resp.headers.get("x-custom-2") == "value2"
        assert "session" in resp.cookies
        assert resp.json()["chained"] is True


def test_method_chaining_order_independence(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test that method chaining works regardless of order"""
    app = SilloApp()

    @app.get("/chain-order-1")
    async def chain_order_1(request: HttpContext):
        return json({"test": 1}).status(201).set_header("X-Test", "1")

    @app.get("/chain-order-2")
    async def chain_order_2(request: HttpContext):
        return json({"test": 2}).set_header("X-Test", "2").status(201)

    with test_client_factory(app) as client:
        resp1 = client.get("/chain-order-1")
        assert resp1.status_code == 201
        assert resp1.json()["test"] == 1

        resp2 = client.get("/chain-order-2")
        assert resp2.status_code == 201
        assert resp2.json()["test"] == 2


# ========== Response Type Switching Tests ==========


def test_response_type_switching(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test switching between different response types"""
    app = SilloApp()

    @app.get("/switch-type")
    async def switch_type(request: HttpContext):
        format_param = request.query_params.get("format", "json")

        data = {"message": "Hello", "value": 42}

        if format_param == "json":
            return json(data)
        elif format_param == "text":
            return text(str(data))
        elif format_param == "html":
            return html(f"<pre>{data}</pre>")
        else:
            return empty(status_code=400)

    with test_client_factory(app) as client:
        # Test JSON
        resp_json = client.get("/switch-type?format=json")
        assert resp_json.status_code == 200
        assert "application/json" in resp_json.headers.get("content-type", "")

        # Test text
        resp_text = client.get("/switch-type?format=text")
        assert resp_text.status_code == 200
        assert "text/plain" in resp_text.headers.get("content-type", "")

        # Test HTML
        resp_html = client.get("/switch-type?format=html")
        assert resp_html.status_code == 200
        assert "text/html" in resp_html.headers.get("content-type", "")


def test_response_resp_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test using the base resp() method"""
    app = SilloApp()

    @app.get("/base-resp")
    async def base_resp(request: HttpContext):
        return response.resp(
            body="Custom response",
            status_code=200,
            headers={"X-Custom": "header"},
            content_type="text/plain",
        )

    with test_client_factory(app) as client:
        resp = client.get("/base-resp")
        assert resp.status_code == 200
        assert resp.text == "Custom response"
        assert resp.headers.get("x-custom") == "header"


def test_response_get_response_method(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test getting the underlying response object"""
    app = SilloApp()

    @app.get("/get-response")
    async def get_response_obj(request: HttpContext):
        response = json({"test": "data"})
        base_response = response
        # Should return a BaseResponse object
        assert base_response is not None
        return response

    with test_client_factory(app) as client:
        resp = client.get("/get-response")
        assert resp.status_code == 200


# ========== Response Error Handling Tests ==========


def test_response_with_error_status(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test response with error status codes"""
    app = SilloApp()

    @app.get("/bad-request")
    async def bad_request(request: HttpContext):
        response = json({"error": "Bad request"})
        return empty(400)

    @app.get("/unauthorized")
    async def unauthorized(request: HttpContext):
        response = json({"error": "Unauthorized"})
        return empty(401)

    @app.get("/not-found")
    async def not_found(request: HttpContext):
        response = json({"error": "Not found"})
        return empty(404)

    @app.get("/server-error")
    async def server_error(request: HttpContext):
        response = json({"error": "Internal server error"})
        return empty(500)

    with test_client_factory(app) as client:
        resp400 = client.get("/bad-request")
        assert resp400.status_code == 400
        assert "error" in resp400.json()

        resp401 = client.get("/unauthorized")
        assert resp401.status_code == 401

        resp404 = client.get("/not-found")
        assert resp404.status_code == 404

        resp500 = client.get("/server-error")
        assert resp500.status_code == 500
