"""
Tests for response headers and cookies
"""

from datetime import datetime, timedelta, timezone
from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.testclient import TestClient

# ========== Header Tests ==========


def test_set_header(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting custom headers"""
    app = NexiosApp()

    @app.get("/headers")
    async def with_headers(request: Request, response: Response):
        return response.set_header("X-Custom-Header", "custom-value").text("ok")

    with test_client_factory(app) as client:
        resp = client.get("/headers")
        assert resp.status_code == 200
        assert resp.headers.get("x-custom-header") == "custom-value"


def test_set_multiple_headers(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting multiple headers"""
    app = NexiosApp()

    @app.get("/multi-headers")
    async def multi_headers(request: Request, response: Response):
        return (
            response.set_header("X-Header-1", "value1")
            .set_header("X-Header-2", "value2")
            .set_header("X-Header-3", "value3")
            .json({"status": "ok"})
        )

    with test_client_factory(app) as client:
        resp = client.get("/multi-headers")
        assert resp.headers.get("x-header-1") == "value1"
        assert resp.headers.get("x-header-2") == "value2"
        assert resp.headers.get("x-header-3") == "value3"


def test_set_headers_method(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting headers using set_headers method"""
    app = NexiosApp()

    @app.get("/batch-headers")
    async def batch_headers(request: Request, response: Response):
        headers = {
            "X-API-Version": "1.0",
            "X-Request-ID": "abc123",
            "X-Rate-Limit": "100",
        }
        return response.set_headers(headers).json({"status": "ok"})

    with test_client_factory(app) as client:
        resp = client.get("/batch-headers")
        assert resp.headers.get("x-api-version") == "1.0"
        assert resp.headers.get("x-request-id") == "abc123"
        assert resp.headers.get("x-rate-limit") == "100"


def test_override_header(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test overriding existing header"""
    app = NexiosApp()

    @app.get("/override")
    async def override_header(request: Request, response: Response):
        return (
            response.set_header("X-Value", "first", overide=True)
            .set_header("X-Value", "second", overide=True)
            .text("ok")
        )

    with test_client_factory(app) as client:
        resp = client.get("/override")
        assert resp.headers.get("x-value") == "second"


def test_has_header(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test checking if header exists"""
    app = NexiosApp()

    @app.get("/check-header")
    async def check_header(request: Request, response: Response):
        response.set_header("X-Test", "value")
        has_test = response.has_header("X-Test")
        has_missing = response.has_header("X-Missing")
        return response.json({"has_test": has_test, "has_missing": has_missing})

    with test_client_factory(app) as client:
        resp = client.get("/check-header")
        data = resp.json()
        assert data["has_test"] is True
        assert data["has_missing"] is False


def test_remove_header(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test removing a header"""
    app = NexiosApp()

    @app.get("/remove-header")
    async def remove_header(request: Request, response: Response):
        response.set_header("X-Temporary", "value")
        response.remove_header("X-Temporary")
        return response.text("ok")

    with test_client_factory(app) as client:
        resp = client.get("/remove-header")
        assert "x-temporary" not in resp.headers


# ========== Cookie Tests ==========


def test_set_cookie(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting a basic cookie"""
    app = NexiosApp()

    @app.get("/set-cookie")
    async def set_cookie(request: Request, response: Response):
        return response.set_cookie("session_id", "abc123").text("Cookie set")

    with test_client_factory(app) as client:
        resp = client.get("/set-cookie")
        assert resp.status_code == 200
        cookies = resp.cookies
        assert "session_id" in cookies
        assert cookies["session_id"] == "abc123"


def test_set_cookie_with_max_age(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test setting cookie with max_age"""
    app = NexiosApp()

    @app.get("/cookie-max-age")
    async def cookie_max_age(request: Request, response: Response):
        return response.set_cookie("token", "xyz789", max_age=3600).text("ok")

    with test_client_factory(app) as client:
        resp = client.get("/cookie-max-age")
        assert "token" in resp.cookies


def test_set_cookie_with_path(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting cookie with path"""
    app = NexiosApp()

    @app.get("/cookie-path")
    async def cookie_path(request: Request, response: Response):
        return response.set_cookie("user", "alice", path="/api").text("ok")

    with test_client_factory(app) as client:
        resp = client.get("/cookie-path")
        assert "user" in resp.cookies


def test_set_cookie_with_domain(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting cookie with domain"""
    app = NexiosApp()

    @app.get("/cookie-domain")
    async def cookie_domain(request: Request, response: Response):
        return response.set_cookie("tracking", "123", domain="example.com").text("ok")

    with test_client_factory(app, base_url="http://example.com") as client:
        resp = client.get("/cookie-domain")
        assert "tracking" in resp.cookies


def test_set_cookie_secure(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting secure cookie"""
    app = NexiosApp()

    @app.get("/cookie-secure")
    async def cookie_secure(request: Request, response: Response):
        return response.set_cookie("secure_token", "secret", secure=True).text("ok")

    with test_client_factory(app) as client:
        resp = client.get("/cookie-secure")
        assert "secure_token" in resp.cookies


def test_set_cookie_httponly(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting httponly cookie"""
    app = NexiosApp()

    @app.get("/cookie-httponly")
    async def cookie_httponly(request: Request, response: Response):
        return response.set_cookie("session", "data", httponly=True).text("ok")

    with test_client_factory(app) as client:
        resp = client.get("/cookie-httponly")
        assert "session" in resp.cookies


def test_set_cookie_samesite(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting cookie with samesite attribute"""
    app = NexiosApp()

    @app.get("/cookie-samesite")
    async def cookie_samesite(request: Request, response: Response):
        return response.set_cookie("csrf", "token", samesite="strict").text("ok")

    with test_client_factory(app) as client:
        resp = client.get("/cookie-samesite")
        assert "csrf" in resp.cookies


def test_set_multiple_cookies(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting multiple cookies"""
    app = NexiosApp()

    @app.get("/multi-cookies")
    async def multi_cookies(request: Request, response: Response):
        return (
            response.set_cookie("cookie1", "value1")
            .set_cookie("cookie2", "value2")
            .set_cookie("cookie3", "value3")
            .text("ok")
        )

    with test_client_factory(app) as client:
        resp = client.get("/multi-cookies")
        cookies = resp.cookies
        assert "cookie1" in cookies
        assert "cookie2" in cookies
        assert "cookie3" in cookies


def test_set_cookies_batch(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting cookies in batch"""
    app = NexiosApp()

    @app.get("/batch-cookies")
    async def batch_cookies(request: Request, response: Response):
        cookies = [
            {"key": "user_id", "value": "123"},
            {"key": "session", "value": "abc"},
            {"key": "preferences", "value": "dark_mode"},
        ]
        return response.set_cookies(cookies).text("ok")

    with test_client_factory(app) as client:
        resp = client.get("/batch-cookies")
        cookies = resp.cookies
        assert "user_id" in cookies
        assert "session" in cookies
        assert "preferences" in cookies


def test_delete_cookie(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test deleting a cookie"""
    app = NexiosApp()

    @app.get("/delete-cookie")
    async def delete_cookie(request: Request, response: Response):
        return response.delete_cookie("old_session").text("Cookie deleted")

    with test_client_factory(app) as client:
        resp = client.get("/delete-cookie")
        assert resp.status_code == 200


def test_set_permanent_cookie(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test setting a permanent cookie"""
    app = NexiosApp()

    @app.get("/permanent-cookie")
    async def permanent_cookie(request: Request, response: Response):
        return response.set_permanent_cookie("remember_me", "true").text("ok")

    with test_client_factory(app) as client:
        resp = client.get("/permanent-cookie")
        assert "remember_me" in resp.cookies


# ========== Cache Control Tests ==========


def test_enable_caching(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test enabling response caching"""
    app = NexiosApp()

    @app.get("/cached")
    async def cached_response(request: Request, response: Response):
        return response.cache(max_age=3600).json({"data": "cached"})

    with test_client_factory(app) as client:
        resp = client.get("/cached")
        assert "cache-control" in resp.headers
        assert "max-age=3600" in resp.headers.get("cache-control", "")


def test_enable_caching_private(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test enabling private caching"""
    app = NexiosApp()

    @app.get("/private-cache")
    async def private_cache(request: Request, response: Response):
        return response.cache(max_age=1800, private=True).json({"data": "private"})

    with test_client_factory(app) as client:
        resp = client.get("/private-cache")
        cache_control = resp.headers.get("cache-control", "")
        assert "private" in cache_control
        assert "max-age=1800" in cache_control


def test_disable_caching(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test disabling response caching"""
    app = NexiosApp()

    @app.get("/no-cache")
    async def no_cache_response(request: Request, response: Response):
        return response.no_cache().json({"data": "fresh"})

    with test_client_factory(app) as client:
        resp = client.get("/no-cache")
        cache_control = resp.headers.get("cache-control", "")
        assert "no-store" in cache_control or "no-cache" in cache_control


# ========== CSP Header Tests ==========


def test_add_csp_header(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test adding Content Security Policy header"""
    app = NexiosApp()

    @app.get("/csp")
    async def with_csp(request: Request, response: Response):
        policy = "default-src 'self'; script-src 'self' 'unsafe-inline'"
        return response.add_csp_header(policy).html("<h1>Secure Page</h1>")

    with test_client_factory(app) as client:
        resp = client.get("/csp")
        assert "content-security-policy" in resp.headers
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp


# ========== Combined Tests ==========


def test_headers_and_cookies_together(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test setting both headers and cookies"""
    app = NexiosApp()

    @app.get("/combined")
    async def combined(request: Request, response: Response):
        return (
            response.set_header("X-API-Version", "2.0")
            .set_cookie("session", "xyz")
            .json({"status": "ok"})
        )

    with test_client_factory(app) as client:
        resp = client.get("/combined")
        assert resp.headers.get("x-api-version") == "2.0"
        assert "session" in resp.cookies


def test_complex_response_chain(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test complex response with multiple operations"""
    app = NexiosApp()

    @app.get("/complex")
    async def complex_response(request: Request, response: Response):
        return (
            response
            .set_header("X-Custom", "value")
            .set_cookie("user", "alice")
            .cache(max_age=600)
            .json({"created": True})
            .status(201)
        )

    with test_client_factory(app) as client:
        resp = client.get("/complex")
        assert resp.status_code == 201
        assert resp.headers.get("x-custom") == "value"
        assert "user" in resp.cookies
        assert "cache-control" in resp.headers
        assert resp.json()["created"] is True
