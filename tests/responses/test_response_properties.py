"""
Tests for response properties and methods
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.testclient import TestClient

# ========== Response Body Tests ==========


def test_response_body_property(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test accessing response body property"""
    app = NexiosApp()

    @app.get("/body")
    async def get_body(request: Request, response: Response):
        response.text("Test body content")
        body = response.body
        # Body should be bytes
        assert isinstance(body, (bytes, memoryview))
        return response

    with test_client_factory(app) as client:
        resp = client.get("/body")
        assert resp.status_code == 200


def test_set_body_method(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting response body directly"""
    app = NexiosApp()

    @app.get("/set-body")
    async def set_body(request: Request, response: Response):
        response.set_body(b"Custom body content")
        return response.text("This will be overridden")

    with test_client_factory(app) as client:
        resp = client.get("/set-body")
        assert resp.status_code == 200


# ========== Response Status Tests ==========




def test_response_status_codes(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test various HTTP status codes"""
    app = NexiosApp()

    status_codes = [200, 201, 204, 400, 401, 403, 404, 500, 502, 503]

    for code in status_codes:

        @app.get(f"/status-{code}")
        async def handler(request: Request, response: Response, status_code=code):
            return response.text(f"Status {status_code}").status(status_code)

    with test_client_factory(app) as client:
        for code in status_codes:
            resp = client.get(f"/status-{code}")
            assert resp.status_code == code


# ========== Response Content Type Tests ==========


def test_response_content_type_property(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test accessing response content type property"""
    app = NexiosApp()

    @app.get("/content-type-check")
    async def check_content_type(request: Request, response: Response):
        response.json({"test": "data"})
        content_type = response.content_type
        return response

    with test_client_factory(app) as client:
        resp = client.get("/content-type-check")
        assert resp.status_code == 200


def test_response_content_length_property(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test accessing response content length property"""
    app = NexiosApp()

    @app.get("/content-length-check")
    async def check_content_length(request: Request, response: Response):
        response.text("Test content")
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
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test chaining multiple response methods"""
    app = NexiosApp()

    @app.get("/chain-all")
    async def chain_all(request: Request, response: Response):
        return (
            response
            .json({"chained": True})
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
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test that method chaining works regardless of order"""
    app = NexiosApp()

    @app.get("/chain-order-1")
    async def chain_order_1(request: Request, response: Response):
        return response.json({"test": 1}).status(201).set_header("X-Test", "1")

    @app.get("/chain-order-2")
    async def chain_order_2(request: Request, response: Response):
        return response.json({"test": 2}).set_header("X-Test", "2").status(201)

    with test_client_factory(app) as client:
        resp1 = client.get("/chain-order-1")
        assert resp1.status_code == 201
        assert resp1.json()["test"] == 1

        resp2 = client.get("/chain-order-2")
        assert resp2.status_code == 201
        assert resp2.json()["test"] == 2


# ========== Response Type Switching Tests ==========


def test_response_type_switching(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test switching between different response types"""
    app = NexiosApp()

    @app.get("/switch-type")
    async def switch_type(request: Request, response: Response):
        format_param = request.query_params.get("format", "json")

        data = {"message": "Hello", "value": 42}

        if format_param == "json":
            return response.json(data)
        elif format_param == "text":
            return response.text(str(data))
        elif format_param == "html":
            return response.html(f"<pre>{data}</pre>")
        else:
            return response.empty(status_code=400)

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







def test_response_resp_method(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test using the base resp() method"""
    app = NexiosApp()

    @app.get("/base-resp")
    async def base_resp(request: Request, response: Response):
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
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test getting the underlying response object"""
    app = NexiosApp()

    @app.get("/get-response")
    async def get_response_obj(request: Request, response: Response):
        response.json({"test": "data"})
        base_response = response.get_response()
        # Should return a BaseResponse object
        assert base_response is not None
        return response

    with test_client_factory(app) as client:
        resp = client.get("/get-response")
        assert resp.status_code == 200


# ========== Response Error Handling Tests ==========


def test_response_with_error_status(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test response with error status codes"""
    app = NexiosApp()

    @app.get("/bad-request")
    async def bad_request(request: Request, response: Response):
        response = response.json({"error": "Bad request"})
        return response.status(400)

    @app.get("/unauthorized")
    async def unauthorized(request: Request, response: Response):
        response = response.json({"error": "Unauthorized"})
        return response.status(401)

    @app.get("/not-found")
    async def not_found(request: Request, response: Response):
        response = response.json({"error": "Not found"})
        return response.status(404)

    @app.get("/server-error")
    async def server_error(request: Request, response: Response):
        response = response.json({"error": "Internal server error"})
        return response.status(500)

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


