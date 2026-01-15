"""
Tests for request cookies and authentication
"""

import base64
from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.testclient import TestClient

# ========== Cookies Tests ==========


def test_request_cookies(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test reading request cookies"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        session_id = request.cookies.get("session_id")
        user_id = request.cookies.get("user_id")
        return response.json({"session_id": session_id, "user_id": user_id})

    with test_client_factory(app) as client:
        client.cookies.set("session_id", "abc123")
        client.cookies.set("user_id", "user456")
        resp = client.get("/test")
        data = resp.json()
        assert data["session_id"] == "abc123"
        assert data["user_id"] == "user456"


def test_request_cookies_empty(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test request with no cookies"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json(
            {"has_cookies": bool(request.cookies), "count": len(request.cookies)}
        )

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["count"] == 0


def test_request_cookies_multiple(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test multiple cookies"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        cookies_dict = dict(request.cookies)
        return response.json(cookies_dict)

    with test_client_factory(app) as client:
        client.cookies.set("cookie1", "value1")
        client.cookies.set("cookie2", "value2")
        client.cookies.set("cookie3", "value3")
        resp = client.get("/test")
        data = resp.json()
        assert "cookie1" in data
        assert "cookie2" in data
        assert "cookie3" in data


def test_request_cookies_special_characters(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test cookies with special characters"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        token = request.cookies.get("token")
        return response.json({"token": token})

    with test_client_factory(app) as client:
        client.cookies.set("token", "abc-123_xyz")
        resp = client.get("/test")
        assert "abc" in resp.json()["token"]


def test_request_cookies_contains(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test checking if cookie exists"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        has_session = "session" in request.cookies
        has_missing = "missing" in request.cookies
        return response.json({"has_session": has_session, "has_missing": has_missing})

    with test_client_factory(app) as client:
        client.cookies.set("session", "xyz")
        resp = client.get("/test")
        data = resp.json()
        assert data["has_session"] is True
        assert data["has_missing"] is False


def test_request_cookies_iteration(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test iterating over cookies"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        cookie_names = list(request.cookies.keys())
        return response.json({"cookie_names": cookie_names})

    with test_client_factory(app) as client:
        client.cookies.set("a", "1")
        client.cookies.set("b", "2")
        resp = client.get("/test")
        names = resp.json()["cookie_names"]
        assert "a" in names
        assert "b" in names


# ========== Basic Authentication Tests ==========


def test_request_is_ajax(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test AJAX request detection"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json({"is_ajax": request.is_ajax})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.json()["is_ajax"] is True


def test_request_is_ajax_case_insensitive(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test AJAX detection is case insensitive"""
    app = NexiosApp()

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json({"is_ajax": request.is_ajax})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"X-Requested-With": "xmlhttprequest"})
        assert resp.json()["is_ajax"] is True


# ========== Combined Auth and Cookies Tests ==========
