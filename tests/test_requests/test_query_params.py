"""
Tests for request query parameters
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.testclient import TestClient

# ========== Query Parameters Tests ==========


def test_request_query_params(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test basic query parameters"""
    app = SilloApp()

    @app.get("/search")
    async def handler(request: HttpContext):
        q = request.query_params.get("q")
        page = request.query_params.get("page")
        return json({"q": q, "page": page})

    with test_client_factory(app) as client:
        resp = client.get("/search?q=test&page=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["q"] == "test"
        assert data["page"] == "1"


def test_request_query_params_multiple_values(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test query parameters with multiple values"""
    app = SilloApp()

    @app.get("/filter")
    async def handler(request: HttpContext):
        tags = request.query_params.getlist("tag")
        return json({"tags": tags})

    with test_client_factory(app) as client:
        resp = client.get("/filter?tag=python&tag=web&tag=async")
        assert resp.status_code == 200
        tags = resp.json()["tags"]
        assert len(tags) == 3
        assert "python" in tags
        assert "web" in tags
        assert "async" in tags


def test_request_query_params_empty(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test request with no query parameters"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        return json(
            {
                "has_params": bool(request.query_params),
                "count": len(request.query_params),
            }
        )

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["count"] == 0


def test_request_query_params_special_characters(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test query parameters with special characters"""
    app = SilloApp()

    @app.get("/search")
    async def handler(request: HttpContext):
        q = request.query_params.get("q")
        return json({"q": q})

    with test_client_factory(app) as client:
        resp = client.get("/search?q=hello%20world")
        assert resp.json()["q"] == "hello world"


def test_request_query_params_unicode(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test query parameters with unicode characters"""
    app = SilloApp()

    @app.get("/search")
    async def handler(request: HttpContext):
        q = request.query_params.get("q")
        return json({"q": q})

    with test_client_factory(app) as client:
        resp = client.get("/search?q=café")
        assert resp.json()["q"] == "café"


def test_request_get_query_params_flat(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test get_query_params with flat=True"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        params = request.get_query_params(flat=True)
        return json(params)

    with test_client_factory(app) as client:
        resp = client.get("/test?a=1&b=2&c=3")
        data = resp.json()
        assert data["a"] == "1"
        assert data["b"] == "2"
        assert data["c"] == "3"


def test_request_get_query_params_not_flat(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test get_query_params with flat=False"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        params = request.get_query_params(flat=False)
        return json({"params_type": str(type(params).__name__)})

    with test_client_factory(app) as client:
        resp = client.get("/test?a=1&b=2")
        assert resp.status_code == 200


def test_request_query_params_boolean_like(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test query parameters with boolean-like values"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        active = request.query_params.get("active")
        enabled = request.query_params.get("enabled")
        return json({"active": active, "enabled": enabled})

    with test_client_factory(app) as client:
        resp = client.get("/test?active=true&enabled=false")
        data = resp.json()
        assert data["active"] == "true"
        assert data["enabled"] == "false"


def test_request_query_params_numbers(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test query parameters with numeric values"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        page = request.query_params.get("page")
        limit = request.query_params.get("limit")
        return json(
            {
                "page": page,
                "limit": limit,
                "page_int": int(page) if page else None,
                "limit_int": int(limit) if limit else None,
            }
        )

    with test_client_factory(app) as client:
        resp = client.get("/test?page=5&limit=20")
        data = resp.json()
        assert data["page"] == "5"
        assert data["limit"] == "20"
        assert data["page_int"] == 5
        assert data["limit_int"] == 20


def test_request_query_params_empty_value(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test query parameters with empty values"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        q = request.query_params.get("q", "default")
        return json({"q": q})

    with test_client_factory(app) as client:
        resp = client.get("/test?q=")
        assert resp.json()["q"] == ""


def test_request_query_params_default_value(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test query parameters with default values"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        page = request.query_params.get("page", "1")
        limit = request.query_params.get("limit", "10")
        return json({"page": page, "limit": limit})

    with test_client_factory(app) as client:
        resp = client.get("/test")
        data = resp.json()
        assert data["page"] == "1"
        assert data["limit"] == "10"


def test_request_query_params_mixed(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test mixed query parameters"""
    app = SilloApp()

    @app.get("/search")
    async def handler(request: HttpContext):
        q = request.query_params.get("q")
        page = request.query_params.get("page", "1")
        sort = request.query_params.get("sort", "asc")
        tags = request.query_params.getlist("tag")
        return json({"q": q, "page": page, "sort": sort, "tags": tags})

    with test_client_factory(app) as client:
        resp = client.get("/search?q=python&page=2&tag=web&tag=framework")
        data = resp.json()
        assert data["q"] == "python"
        assert data["page"] == "2"
        assert data["sort"] == "asc"
        assert len(data["tags"]) == 2


def test_request_query_params_iteration(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test iterating over query parameters"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        params_dict = dict(request.query_params)
        return json(params_dict)

    with test_client_factory(app) as client:
        resp = client.get("/test?a=1&b=2&c=3")
        data = resp.json()
        assert "a" in data
        assert "b" in data
        assert "c" in data


def test_request_query_params_contains(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test checking if query parameter exists"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        has_q = "q" in request.query_params
        has_page = "page" in request.query_params
        has_missing = "missing" in request.query_params
        return json(
            {"has_q": has_q, "has_page": has_page, "has_missing": has_missing}
        )

    with test_client_factory(app) as client:
        resp = client.get("/test?q=test&page=1")
        data = resp.json()
        assert data["has_q"] is True
        assert data["has_page"] is True
        assert data["has_missing"] is False


def test_request_query_params_keys(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test getting query parameter keys"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        keys = list(request.query_params.keys())
        return json({"keys": keys})

    with test_client_factory(app) as client:
        resp = client.get("/test?a=1&b=2&c=3")
        keys = resp.json()["keys"]
        assert "a" in keys
        assert "b" in keys
        assert "c" in keys


def test_request_query_params_values(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test getting query parameter values"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        values = list(request.query_params.values())
        return json({"values": values})

    with test_client_factory(app) as client:
        resp = client.get("/test?a=1&b=2&c=3")
        values = resp.json()["values"]
        assert "1" in values
        assert "2" in values
        assert "3" in values


def test_request_query_params_items(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test getting query parameter items"""
    app = SilloApp()

    @app.get("/test")
    async def handler(request: HttpContext):
        items = dict(request.query_params.items())
        return json(items)

    with test_client_factory(app) as client:
        resp = client.get("/test?name=John&age=30")
        data = resp.json()
        assert data["name"] == "John"
        assert data["age"] == "30"
