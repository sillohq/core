"""
Tests for Cookie parameter extractor.
"""

import pytest
from nexios import NexiosApp, Cookie
from nexios.http import Request, Response
from nexios.testclient import TestClient


@pytest.fixture
def app():
    return NexiosApp()


@pytest.fixture
def client(app):
    return TestClient(app)


def test_cookie_with_value(app, client):
    """Test Cookie extractor returns provided value."""

    @app.get("/test")
    async def handler(request: Request, response: Response, user_id: str = Cookie()):
        return {"user_id": user_id}

    response = client.get("/test", cookies={"user_id": "user123"})
    assert response.status_code == 200
    assert response.json()["user_id"] == "user123"


def test_cookie_with_default(app, client):
    """Test Cookie extractor returns default when no cookie provided."""

    @app.get("/test")
    async def handler(
        request: Request, response: Response, theme: str = Cookie("light")
    ):
        return {"theme": theme}

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["theme"] == "light"


def test_cookie_no_default(app, client):
    """Test Cookie with no default returns None."""

    @app.get("/test")
    async def handler(request: Request, response: Response, session: str = Cookie()):
        return {"session": session}

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["session"] is None


def test_cookie_override_default(app, client):
    """Test Cookie overrides default when provided."""

    @app.get("/test")
    async def handler(
        request: Request, response: Response, theme: str = Cookie("light")
    ):
        return {"theme": theme}

    response = client.get("/test", cookies={"theme": "dark"})
    assert response.status_code == 200
    assert response.json()["theme"] == "dark"


def test_cookie_multiple(app, client):
    """Test multiple Cookie extractors."""

    @app.get("/test")
    async def handler(
        request: Request,
        response: Response,
        user_id: str = Cookie(),
        theme: str = Cookie("light"),
        lang: str = Cookie("en"),
    ):
        return {"user_id": user_id, "theme": theme, "lang": lang}

    response = client.get("/test", cookies={"user_id": "u123", "theme": "dark"})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "u123"
    assert data["theme"] == "dark"
    assert data["lang"] == "en"


def test_cookie_alias(app, client):
    """Test Cookie with alias."""

    @app.get("/test")
    async def handler(
        request: Request,
        response: Response,
        session_id: str = Cookie(alias="session_id"),
    ):
        return {"session": session_id}

    response = client.get("/test", cookies={"session_id": "abc123"})
    assert response.status_code == 200
    assert response.json()["session"] == "abc123"
