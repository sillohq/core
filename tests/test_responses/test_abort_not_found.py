"""
Tests for the abort() and not_found() response helpers.

Both methods raise instead of returning a response, so they are exercised two
ways:
  - unit: they raise the correct exception type with the right status/detail
  - integration: the framework's exception middleware renders them into a real
    HTTP response (JSON envelope / 404 handler).
"""

import pytest

from sillo import SilloApp
from sillo import abort, json, not_found
from sillo.exceptions import HTTPException, NotFoundException
from sillo.core.http import HttpContext
from sillo.testclient import TestClient


def test_abort_raises_http_exception():
    with pytest.raises(HTTPException) as exc_info:
        abort(403, detail="Admins only")
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Admins only"


def test_abort_default_detail_uses_status_phrase():
    with pytest.raises(HTTPException) as exc_info:
        abort(400)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Bad Request"


def test_abort_passes_headers():
    with pytest.raises(HTTPException) as exc_info:
        abort(401, detail="nope", headers={"X-Retry": "true"})
    assert exc_info.value.headers == {"X-Retry": "true"}


def test_not_found_raises_not_found_exception():
    with pytest.raises(NotFoundException) as exc_info:
        not_found(detail="Item 7 not found")
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Item 7 not found"


def test_not_found_default_detail():
    with pytest.raises(NotFoundException) as exc_info:
        not_found()
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Not Found"


def test_not_found_passes_headers():
    with pytest.raises(NotFoundException) as exc_info:
        not_found(headers={"X-Reason": "missing"})
    assert exc_info.value.headers == {"X-Reason": "missing"}


# ===== Integration: framework renders the raised exception =====


def test_abort_rendered_as_json(
    test_client_factory: callable,
):
    app = SilloApp()

    @app.get("/admin")
    async def admin(request: HttpContext):
        abort(403, detail="Admins only")
        return json({"ok": True})

    with test_client_factory(app) as client:
        resp = client.get("/admin")
        assert resp.status_code == 403
        assert resp.json() == "Admins only"


def test_abort_does_not_return_body_after_raise(
    test_client_factory: callable,
):
    app = SilloApp()

    @app.get("/boom")
    async def boom(request: HttpContext):
        abort(418, detail="teapot")
        return json({"unreachable": True})

    with test_client_factory(app) as client:
        resp = client.get("/boom")
        assert resp.status_code == 418
        assert resp.json() == "teapot"


def test_not_found_rendered_as_404(
    test_client_factory: callable,
):
    app = SilloApp()

    @app.get("/items/{item_id:int}")
    async def get_item(request: HttpContext, item_id: int):
        if item_id != 1:
            not_found(detail=f"Item {item_id} not found")
        return json({"item_id": item_id})

    with test_client_factory(app) as client:
        found = client.get("/items/1")
        assert found.status_code == 200
        assert found.json()["item_id"] == 1

        missing = client.get("/items/99")
        assert missing.status_code == 404
        assert missing.json()["message"] == "Item 99 not found"
