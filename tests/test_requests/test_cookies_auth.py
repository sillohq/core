"""
Tests for request cookies and authentication
"""

import base64
from typing import Callable

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.testclient import TestClient

# ========== Cookies Tests ==========


def test_request_cookies(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test reading request cookies"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        session_id = ctx.cookies.get("session_id")
        user_id = ctx.cookies.get("user_id")
        return json({"session_id": session_id, "user_id": user_id})

    with test_client_factory(app) as client:
        client.cookies.set("session_id", "abc123")
        client.cookies.set("user_id", "user456")
        resp = client.get("/test")
        data = resp.json()
        assert data["session_id"] == "abc123"
        assert data["user_id"] == "user456"


def test_request_cookies_empty(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test request with no cookies"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json(
            {"has_cookies": bool(ctx.cookies), "count": len(ctx.cookies)}
        )

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["count"] == 0


def test_request_cookies_multiple(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test multiple cookies"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        cookies_dict = dict(ctx.cookies)
        return json(cookies_dict)

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test cookies with special characters"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        token = ctx.cookies.get("token")
        return json({"token": token})

    with test_client_factory(app) as client:
        client.cookies.set("token", "abc-123_xyz")
        resp = client.get("/test")
        assert "abc" in resp.json()["token"]


def test_request_cookies_contains(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test checking if cookie exists"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        has_session = "session" in ctx.cookies
        has_missing = "missing" in ctx.cookies
        return json({"has_session": has_session, "has_missing": has_missing})

    with test_client_factory(app) as client:
        client.cookies.set("session", "xyz")
        resp = client.get("/test")
        data = resp.json()
        assert data["has_session"] is True
        assert data["has_missing"] is False


def test_request_cookies_iteration(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test iterating over cookies"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        cookie_names = list(ctx.cookies.keys())
        return json({"cookie_names": cookie_names})

    with test_client_factory(app) as client:
        client.cookies.set("a", "1")
        client.cookies.set("b", "2")
        resp = client.get("/test")
        names = resp.json()["cookie_names"]
        assert "a" in names
        assert "b" in names


# ========== Basic Authentication Tests ==========


def test_request_is_ajax(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test AJAX request detection"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"is_ajax": ctx.is_ajax})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.json()["is_ajax"] is True


def test_request_is_ajax_case_insensitive(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test AJAX detection is case insensitive"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"is_ajax": ctx.is_ajax})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"X-Requested-With": "xmlhttprequest"})
        assert resp.json()["is_ajax"] is True


# ========== Combined Auth and Cookies Tests ==========
