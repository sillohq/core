"""
Tests for request body data (json, text, body, form)
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.testclient import TestClient

# ========== JSON Body Tests ==========


def test_request_json_body(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test parsing JSON request body"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        data = await ctx.json
        return json(data)

    with test_client_factory(app) as client:
        resp = client.post("/data", json={"name": "John", "age": 30})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "John"
        assert data["age"] == 30


def test_request_json_nested(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test parsing nested JSON"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        data = await ctx.json
        return json(data)

    with test_client_factory(app) as client:
        payload = {"user": {"name": "Alice", "profile": {"age": 25, "city": "NYC"}}}
        resp = client.post("/data", json=payload)
        data = resp.json()
        assert data["user"]["profile"]["city"] == "NYC"


def test_request_json_array(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test parsing JSON array"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        data = await ctx.json
        return json({"count": len(data), "items": data})

    with test_client_factory(app) as client:
        payload = [{"id": 1}, {"id": 2}, {"id": 3}]
        resp = client.post("/data", json=payload)
        data = resp.json()
        assert data["count"] == 3


def test_request_json_empty_object(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test parsing empty JSON object"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        data = await ctx.json
        return json({"received": data, "is_dict": isinstance(data, dict)})

    with test_client_factory(app) as client:
        resp = client.post("/data", json={})
        data = resp.json()
        assert data["received"] == {}
        assert data["is_dict"] is True


def test_request_json_with_null(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test JSON with null values"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        data = await ctx.json
        return json(data)

    with test_client_factory(app) as client:
        resp = client.post("/data", json={"value": None, "name": "test"})
        data = resp.json()
        assert data["value"] is None
        assert data["name"] == "test"


def test_request_json_with_boolean(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test JSON with boolean values"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        data = await ctx.json
        return json(data)

    with test_client_factory(app) as client:
        resp = client.post("/data", json={"active": True, "deleted": False})
        data = resp.json()
        assert data["active"] is True
        assert data["deleted"] is False


def test_request_json_with_numbers(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test JSON with various number types"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        data = await ctx.json
        return json(data)

    with test_client_factory(app) as client:
        resp = client.post(
            "/data", json={"integer": 42, "float": 3.14, "negative": -100, "zero": 0}
        )
        data = resp.json()
        assert data["integer"] == 42
        assert data["float"] == 3.14
        assert data["negative"] == -100


# ========== Text Body Tests ==========


def test_request_text_body(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test reading text request body"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        text = await ctx.text
        return json({"text": text, "length": len(text)})

    with test_client_factory(app) as client:
        resp = client.post("/data", content="Hello, World!")
        data = resp.json()
        assert data["text"] == "Hello, World!"
        assert data["length"] == 13


def test_request_text_multiline(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test reading multiline text"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        text = await ctx.text
        return json({"text": text})

    with test_client_factory(app) as client:
        content = "Line 1\nLine 2\nLine 3"
        resp = client.post("/data", content=content)
        assert resp.json()["text"] == content


def test_request_text_unicode(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test reading unicode text"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        text = await ctx.text
        return json({"text": text})

    with test_client_factory(app) as client:
        content = "Hello 世界 "
        resp = client.post("/data", content=content.encode("utf-8"))
        assert resp.json()["text"] == content


def test_request_text_empty(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test reading empty text body"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        text = await ctx.text
        return json({"text": text, "is_empty": text == ""})

    with test_client_factory(app) as client:
        resp = client.post("/data", content="")
        data = resp.json()
        assert data["text"] == ""
        assert data["is_empty"] is True


# ========== Raw Body Tests ==========


def test_request_raw_body(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test reading raw bytes body"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        body = await ctx.body
        return json({"length": len(body), "is_bytes": isinstance(body, bytes)})

    with test_client_factory(app) as client:
        resp = client.post("/data", content=b"Binary data")
        data = resp.json()
        assert data["length"] == 11
        assert data["is_bytes"] is True


def test_request_body_binary(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test reading binary body"""
    app = SilloApp()

    @app.post("/upload")
    async def handler(ctx: HttpContext):
        body = await ctx.body
        return json({"size": len(body)})

    with test_client_factory(app) as client:
        binary_data = bytes([i % 256 for i in range(1000)])
        resp = client.post("/upload", content=binary_data)
        assert resp.json()["size"] == 1000


def test_request_body_empty(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test reading empty body"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        body = await ctx.body
        return json({"length": len(body)})

    with test_client_factory(app) as client:
        resp = client.post("/data")
        assert resp.json()["length"] == 0


# ========== Form Data Tests ==========


def test_request_form_data_urlencoded(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test parsing URL-encoded form data"""
    app = SilloApp()

    @app.post("/form")
    async def handler(ctx: HttpContext):
        form = await ctx.form
        return json(
            {"username": form.get("username"), "email": form.get("email")}
        )

    with test_client_factory(app) as client:
        resp = client.post(
            "/form", data={"username": "john", "email": "john@example.com"}
        )
        data = resp.json()
        assert data["username"] == "john"
        assert data["email"] == "john@example.com"


def test_request_form_data_multiple_values(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test form data with multiple values"""
    app = SilloApp()

    @app.post("/form")
    async def handler(ctx: HttpContext):
        form = await ctx.form
        tags = form.getlist("tag")
        return json({"tags": tags})

    with test_client_factory(app) as client:
        resp = client.post("/form", data={"tag": ["python", "web", "async"]})
        tags = resp.json()["tags"]
        assert len(tags) >= 1


def test_request_form_data_empty(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test empty form data"""
    app = SilloApp()

    @app.post("/form")
    async def handler(ctx: HttpContext):
        form = await ctx.form
        return json({"has_data": bool(form)})

    with test_client_factory(app) as client:
        resp = client.post("/form", data={})
        assert resp.status_code == 200


# ========== Content Type Detection Tests ==========


def test_request_accepts_json(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test accepts_json property"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"accepts_json": ctx.accepts_json})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"Accept": "application/json"})
        assert resp.json()["accepts_json"] is True


def test_request_accepts_json_wildcard(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test accepts_json with wildcard accept header"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"accepts_json": ctx.accepts_json})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"Accept": "*/*"})
        assert resp.json()["accepts_json"] is True


def test_request_accepts_html(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test accepts_html property"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"accepts_html": ctx.accepts_html})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"Accept": "text/html"})
        assert resp.json()["accepts_html"] is True


def test_request_accepts_html_wildcard(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test accepts_html with wildcard"""
    app = SilloApp()

    @app.get("/test")
    async def handler(ctx: HttpContext):
        return json({"accepts_html": ctx.accepts_html})

    with test_client_factory(app) as client:
        resp = client.get("/test", headers={"Accept": "*/*"})
        assert resp.json()["accepts_html"] is True


# ========== Large Body Tests ==========


def test_request_large_json(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test parsing large JSON payload"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        data = await ctx.json
        return json({"count": len(data)})

    with test_client_factory(app) as client:
        large_payload = [{"id": i, "data": f"value_{i}"} for i in range(1000)]
        resp = client.post("/data", json=large_payload)
        assert resp.json()["count"] == 1000


def test_request_large_text(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test reading large text body"""
    app = SilloApp()

    @app.post("/data")
    async def handler(ctx: HttpContext):
        text = await ctx.text
        return json({"length": len(text)})

    with test_client_factory(app) as client:
        large_text = "x" * 100000  # 100KB
        resp = client.post("/data", content=large_text)
        assert resp.json()["length"] == 100000
