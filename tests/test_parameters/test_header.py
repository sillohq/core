"""
Tests for Header parameter extractor.
"""

import pytest
from nexios import NexiosApp, Header
from nexios.http import Request, Response
from nexios.testclient import TestClient


@pytest.fixture
def app():
    return NexiosApp()


@pytest.fixture
def client(app):
    return TestClient(app)


def test_header_auto_conversion(app, client):
    """Test Header auto-converts param_name to canonical header name."""

    @app.get("/test")
    async def handler(
        request: Request, response: Response, authorization: str = Header()
    ):
        return {"auth": authorization}

    response = client.get("/test", headers={"Authorization": "Bearer token123"})
    assert response.status_code == 200
    assert response.json()["auth"] == "Bearer token123"


def test_header_underscore_to_camel(app, client):
    """Test Header converts underscores to proper case."""

    @app.get("/test")
    async def handler(
        request: Request, response: Response, x_request_id: str = Header()
    ):
        return {"request_id": x_request_id}

    response = client.get("/test", headers={"X-Request-Id": "req-456"})
    assert response.status_code == 200
    assert response.json()["request_id"] == "req-456"


def test_header_no_default(app, client):
    """Test Header with no default returns None."""

    @app.get("/test")
    async def handler(request: Request, response: Response, auth: str = Header()):
        return {"auth": auth}

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["auth"] is None


def test_header_with_alias(app, client):
    """Test Header with explicit alias."""

    @app.get("/test")
    async def handler(
        request: Request, response: Response, token: str = Header(alias="X-API-Token")
    ):
        return {"token": token}

    response = client.get("/test", headers={"X-API-Token": "secret123"})
    assert response.status_code == 200
    assert response.json()["token"] == "secret123"


def test_header_multiple(app, client):
    """Test multiple Header extractors."""

    @app.get("/test")
    async def handler(
        request: Request,
        response: Response,
        authorization: str = Header(),
        content_type: str = Header(),
    ):
        return {"auth": authorization, "content_type": content_type}

    response = client.get(
        "/test",
        headers={"Authorization": "Bearer abc", "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["auth"] == "Bearer abc"
    assert data["content_type"] == "application/json"


def test_header_mixed_with_alias(app, client):
    """Test Header with mix of auto-converted and aliased."""

    @app.get("/test")
    async def handler(
        request: Request,
        response: Response,
        authorization: str = Header(),
        api_key: str = Header(alias="X-API-Key"),
    ):
        return {"auth": authorization, "api_key": api_key}

    response = client.get(
        "/test",
        headers={"Authorization": "Bearer secret", "X-API-Key": "key123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["auth"] == "Bearer secret"
    assert data["api_key"] == "key123"


def test_header_with_custom_alias(app, client):
    """Test Header with custom alias."""

    @app.get("/test")
    async def handler(
        request: Request,
        response: Response,
        token: str = Header(alias="x-custom-token"),
    ):
        return {"token": token}

    response = client.get("/test", headers={"x-custom-token": "custom123"})
    assert response.status_code == 200
    assert response.json()["token"] == "custom123"
