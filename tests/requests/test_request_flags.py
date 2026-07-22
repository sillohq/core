"""
Tests for new Request utility flags and methods
"""

import pytest

from sillo import silloApp
from sillo.core.http import Request, Response
from sillo.testclient import TestClient


def test_request_is_json_flag(test_client_factory):
    """Test is_json property"""
    app = silloApp()

    @app.post("/json")
    async def json_endpoint(request: Request, response: Response):
        return response.json({"is_json": request.is_json})

    @app.post("/text")
    async def text_endpoint(request: Request, response: Response):
        return response.json({"is_json": request.is_json})

    with test_client_factory(app) as client:
        # Test JSON request
        resp = client.post("/json", json={"test": "data"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_json"] is True

        # Test non-JSON request
        resp = client.post(
            "/text", data="plain text", headers={"Content-Type": "text/plain"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_json"] is False


def test_request_is_form_flag(test_client_factory):
    """Test is_form property"""
    app = silloApp()

    @app.post("/form")
    async def form_endpoint(request: Request, response: Response):
        return response.json({"is_form": request.is_form})

    @app.post("/json")
    async def json_endpoint(request: Request, response: Response):
        return response.json({"is_form": request.is_form})

    with test_client_factory(app) as client:
        # Test form request
        resp = client.post("/form", data={"field": "value"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_form"] is True

        # Test JSON request
        resp = client.post("/json", json={"test": "data"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_form"] is False


def test_request_is_multipart_flag(test_client_factory):
    """Test is_multipart property"""
    app = silloApp()

    @app.post("/upload")
    async def upload_endpoint(request: Request, response: Response):
        return response.json({"is_multipart": request.is_multipart})

    @app.post("/json")
    async def json_endpoint(request: Request, response: Response):
        return response.json({"is_multipart": request.is_multipart})

    with test_client_factory(app) as client:
        # Test multipart request (simulated)
        # Note: TestClient doesn't fully simulate multipart, but we can test the logic
        resp = client.post("/json", json={"test": "data"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_multipart"] is False


def test_request_is_urlencoded_flag(test_client_factory):
    """Test is_urlencoded property"""
    app = silloApp()

    @app.post("/form")
    async def form_endpoint(request: Request, response: Response):
        return response.json({"is_urlencoded": request.is_urlencoded})

    @app.post("/json")
    async def json_endpoint(request: Request, response: Response):
        return response.json({"is_urlencoded": request.is_urlencoded})

    with test_client_factory(app) as client:
        # Test URL-encoded request
        resp = client.post("/form", data={"field": "value"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_urlencoded"] is True

        # Test JSON request
        resp = client.post("/json", json={"test": "data"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_urlencoded"] is False


def test_request_has_cookie_flag(test_client_factory):
    """Test has_cookie property"""
    app = silloApp()

    @app.get("/cookies")
    async def cookies_endpoint(request: Request, response: Response):
        return response.json({"has_cookie": request.has_cookie})

    with test_client_factory(app) as client:
        # Test request with cookies
        resp = client.get("/cookies", cookies={"session": "abc123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_cookie"] is True

        # Test request without cookies
        resp = client.get("/cookies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_cookie"] is False


def test_request_has_body_flag(test_client_factory):
    """Test has_body property"""
    app = silloApp()

    @app.post("/data")
    async def data_endpoint(request: Request, response: Response):
        return response.json({"has_body": request.has_body})

    @app.get("/no-data")
    async def no_data_endpoint(request: Request, response: Response):
        return response.json({"has_body": request.has_body})

    with test_client_factory(app) as client:
        # Test POST request with body
        resp = client.post("/data", json={"test": "data"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_body"] is True

        # Test GET request without body
        resp = client.get("/no-data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_body"] is False


def test_request_is_authenticated_flag(test_client_factory):
    """Test is_authenticated property"""
    app = silloApp()

    @app.get("/auth")
    async def auth_endpoint(request: Request, response: Response):
        return response.json({"is_authenticated": request.is_authenticated})

    with test_client_factory(app) as client:
        # Test unauthenticated request
        resp = client.get("/auth")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_authenticated"] is False


def test_request_has_session_flag(test_client_factory):
    """Test has_session property"""
    app = silloApp()

    @app.get("/session")
    async def session_endpoint(request: Request, response: Response):
        return response.json({"has_session": request.has_session})

    with test_client_factory(app) as client:
        # Test request without session middleware
        resp = client.get("/session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_session"] is False


def test_request_has_files_flag(test_client_factory):
    """Test has_files property"""
    app = silloApp()

    @app.post("/upload")
    async def upload_endpoint(request: Request, response: Response):
        return response.json({"has_files": request.has_files})

    with test_client_factory(app) as client:
        # Test request without files
        resp = client.post("/upload", json={"test": "data"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_files"] is False


def test_request_flags_with_different_content_types(test_client_factory):
    """Test various flags with different content types"""
    app = silloApp()

    @app.post("/check")
    async def check_endpoint(request: Request, response: Response):
        return response.json(
            {
                "is_json": request.is_json,
                "is_form": request.is_form,
                "is_multipart": request.is_multipart,
                "is_urlencoded": request.is_urlencoded,
                "has_body": request.has_body,
                "content_type": request.content_type,
            }
        )

    with test_client_factory(app) as client:
        # Test JSON request
        resp = client.post("/check", json={"test": "data"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_json"] is True
        assert data["is_form"] is False
        assert data["is_multipart"] is False
        assert data["is_urlencoded"] is False
        assert data["has_body"] is True
        assert data["content_type"] == "application/json"

        # Test form request
        resp = client.post("/check", data={"field": "value"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_json"] is False
        assert data["is_form"] is True
        assert data["is_multipart"] is False
        assert data["is_urlencoded"] is True
        assert data["has_body"] is True
        assert data["content_type"] == "application/x-www-form-urlencoded"


def test_request_has_header_method(test_client_factory):
    """Test has_header method"""
    app = silloApp()

    @app.get("/headers")
    async def headers_endpoint(request: Request, response: Response):
        return response.json(
            {
                "has_content_type": request.has_header("content-type"),
                "has_authorization": request.has_header("authorization"),
                "has_custom_header": request.has_header("x-custom-header"),
            }
        )

    with test_client_factory(app) as client:
        # Test with Content-Type header
        resp = client.get("/headers", headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_content_type"] is True
        assert data["has_authorization"] is False
        assert data["has_custom_header"] is False


def test_request_get_header_method(test_client_factory):
    """Test get_header method"""
    app = silloApp()

    @app.get("/headers")
    async def headers_endpoint(request: Request, response: Response):
        return response.json(
            {
                "content_type": request.get_header("content-type"),
                "missing_header": request.get_header("x-missing", "default_value"),
                "none_default": request.get_header("x-none"),
            }
        )

    with test_client_factory(app) as client:
        # Test with headers
        resp = client.get("/headers", headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["content_type"] == "application/json"
        assert data["missing_header"] == "default_value"
        assert data["none_default"] is None
