"""
Tests for basic request properties (method, path, url, headers, etc.)
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.testclient import TestClient

# ========== HttpContext Method Tests ==========


def test_request_method_get(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test GET request method"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"method": request.method})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json()["method"] == "GET"


def test_request_method_post(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test POST request method"""
    app = SilloApp()

    @app.post("/test")
    async def handler(request: HttpContext):
        return json({"method": request.method})

    with test_client_factory(app) as client:
        resp = client.post("/test")
        assert resp.status_code == 200
        assert resp.json()["method"] == "POST"


def test_request_method_put(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test PUT request method"""
    app = SilloApp()

    @app.put("/test")
    async def handler(request: HttpContext):
        return json({"method": request.method})

    with test_client_factory(app) as client:
        resp = client.put("/test")
        assert resp.status_code == 200
        assert resp.json()["method"] == "PUT"


def test_request_method_delete(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test DELETE request method"""
    app = SilloApp()

    @app.delete("/test")
    async def handler(request: HttpContext):
        return json({"method": request.method})

    with test_client_factory(app) as client:
        resp = client.delete("/test")
        assert resp.status_code == 200
        assert resp.json()["method"] == "DELETE"


def test_request_method_patch(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test PATCH request method"""
    app = SilloApp()

    @app.patch("/test")
    async def handler(request: HttpContext):
        return json({"method": request.method})

    with test_client_factory(app) as client:
        resp = client.patch("/test")
        assert resp.status_code == 200
        assert resp.json()["method"] == "PATCH"


def test_request_is_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test is_method helper"""
    app = SilloApp()

    @app.route("/test", methods=["GET", "POST"])
    async def handler(request: HttpContext):
        return json(
            {
                "is_get": request.is_method("GET"),
                "is_post": request.is_method("POST"),
                "is_put": request.is_method("PUT"),
            }
        )

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["is_get"] is True
        assert data["is_post"] is False
        assert data["is_put"] is False


# ========== HttpContext URL Tests ==========


def test_request_url(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test request URL property"""
    app = SilloApp()

    @app.get("/test/path")
    async def handler(request: HttpContext):
        return json({"url": str(request.url)})

    with test_client_factory(app) as client:
        resp = client.get("/test/path")
        assert resp.status_code == 200
        assert "/test/path" in resp.json()["url"]


def test_request_path(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test request path property"""
    app = SilloApp()

    @app.get("/api/users")
    async def handler(request: HttpContext):
        return json({"path": request.path})

    with test_client_factory(app) as client:
        resp = client.get("/api/users")
        assert resp.status_code == 200
        assert resp.json()["path"] == "/api/users"


def test_request_url_scheme(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test request URL scheme"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"scheme": request.url.scheme})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json()["scheme"] in ["http", "https"]


def test_request_url_netloc(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test request URL netloc"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"netloc": request.url.netloc})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json()["netloc"] != ""


def test_request_base_url(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test request base_url property"""
    app = SilloApp()

    @app.get("/test/path")
    async def handler(request: HttpContext):
        return json({"base_url": str(request.base_url)})

    with test_client_factory(app) as client:
        resp = client.get("/test/path")
        assert resp.status_code == 200
        base_url = resp.json()["base_url"]
        assert base_url.endswith("/")


# ========== Request Headers Tests ==========


def test_request_headers(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test accessing request headers"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json(
            {
                "has_headers": bool(request.headers),
                "user_agent": request.headers.get("user-agent", ""),
            }
        )

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"User-Agent": "TestClient/1.0"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_headers"] is True


def test_request_get_header(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test get_header method"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json(
            {
                "custom": request.get_header("X-Custom-Header", "default"),
            }
        )

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"X-Custom-Header": "custom-value"})
        data = resp.json()
        assert data["custom"] == "custom-value"


def test_request_has_header(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test has_header method"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json(
            {
                "has_custom": request.has_header("X-Custom"),
                "has_missing": request.has_header("X-Missing"),
            }
        )

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"X-Custom": "value"})
        data = resp.json()
        assert data["has_custom"] is True
        assert data["has_missing"] is False


def test_request_user_agent(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test user_agent property"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"user_agent": request.user_agent})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"User-Agent": "Mozilla/5.0"})
        assert resp.json()["user_agent"] == "Mozilla/5.0"


def test_request_content_type(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test content_type property"""
    app = SilloApp()

    @app.post("/test")
    async def handler(request: HttpContext):
        return json({"content_type": request.content_type})

    with test_client_factory(app) as client:
        resp = client.post("/test", json={"data": "test"})
        assert "json" in resp.json()["content_type"].lower()


def test_request_content_length(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test content_length property"""
    app = SilloApp()

    @app.post("/test")
    async def handler(request: HttpContext):
        return json({"content_length": request.content_length})

    with test_client_factory(app) as client:
        resp = client.post("/test", json={"data": "test"})
        assert resp.json()["content_length"] >= 0


def test_request_get_client_ip(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test get_client_ip method"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"client_ip": request.get_client_ip()})

    with test_client_factory(
        app,
    ) as client:
        resp = client.get("/test", headers={"X-Forwarded-For": "192.168.1.1, 10.0.0.1"})
        assert resp.json()["client_ip"] != ""


def test_request_get_client_ip_with_forwarded_for(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test get_client_ip with X-Forwarded-For header"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"client_ip": request.get_client_ip()})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"X-Forwarded-For": "192.168.1.1, 10.0.0.1"})
        assert resp.json()["client_ip"] == "192.168.1.1"


def test_request_get_client_ip_with_real_ip(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test get_client_ip with X-Real-IP header"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"client_ip": request.get_client_ip()})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"X-Real-IP": "203.0.113.1"})
        assert resp.json()["client_ip"] == "203.0.113.1"


# ========== HttpContext Validation Tests ==========


def test_request_valid(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test valid() method"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"valid": request.valid()})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.json()["valid"] is True


# ========== HttpContext String Representation Tests ==========


def test_request_str_representation(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test __str__ method"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        req_str = str(request)
        return json(
            {
                "str": req_str,
                "has_method": "GET" in req_str,
                "has_url": "/test" in req_str,
            }
        )

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["has_method"] is True
        assert data["has_url"] is True


# ========== HttpContext Origin and Referrer Tests ==========


def test_request_origin(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test origin property"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"origin": request.origin})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"Origin": "https://example.com"})
        assert resp.json()["origin"] == "https://example.com"


def test_request_origin_without_header(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test origin property without Origin header"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"origin": request.origin})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        origin = resp.json()["origin"]
        assert origin is not None


def test_request_referrer(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test referrer property"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"referrer": request.referrer})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"Referer": "https://example.com/page"})
        assert resp.json()["referrer"] == "https://example.com/page"


def test_request_referrer_empty(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test referrer property when not set"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"referrer": request.referrer})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.json()["referrer"] == ""


# ========== HttpContext Security Tests ==========


def test_request_is_secure_http(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test is_secure property with HTTP"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json({"is_secure": request.is_secure})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        # TestClient typically uses http
        assert resp.json()["is_secure"] is False


# ========== HttpContext Build Absolute URI Tests ==========


def test_request_build_absolute_uri(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test build_absolute_uri method"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        uri = request.build_absolute_uri("/api/users")
        return json({"uri": uri})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        uri = resp.json()["uri"]
        assert "/api/users" in uri


def test_request_build_absolute_uri_with_query(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test build_absolute_uri with query parameters"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        uri = request.build_absolute_uri("/search", {"q": "test", "page": "1"})
        return json({"uri": uri})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        uri = resp.json()["uri"]
        assert "/search" in uri
        assert "q=test" in uri
        assert "page=1" in uri
