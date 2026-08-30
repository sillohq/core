"""
Validated-mode parameters: declaring a type or a constraint on a marker opts it
into Pydantic validation, which turns malformed input into a 422 carrying the
location that failed.
"""

from typing import List

from sillo import Cookie, Header, Path, Query
from sillo import json
from sillo.testclient import TestClient


def test_constraint_violation_is_422_with_location(app, client):
    @app.get("/items")
    async def handler(ctx, page=Query(1, type=int, ge=1, le=100)):
        return json({"page": page})

    resp = client.get("/items?page=0")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail[0]["loc"] == ["query", "page"]
    assert detail[0]["type"] == "greater_than_equal"


def test_unparseable_value_is_422_not_500(app, client):
    """The legacy path let int('abc') escape as a 500; this must be a 422."""

    @app.get("/items")
    async def handler(ctx, page=Query(1, type=int)):
        return json({"page": page})

    resp = client.get("/items?page=abc")
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["query", "page"]


def test_missing_required_is_422_not_500(app, client):
    """A declared type with no default is required and reports as such."""

    @app.get("/items")
    async def handler(ctx, q=Query(type=str)):
        return json({"q": q})

    resp = client.get("/items")
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["type"] == "missing"


def test_repeated_query_params_build_a_list(app, client):
    @app.get("/items")
    async def handler(ctx, tags=Query([], type=List[str])):
        return json({"tags": tags})

    assert client.get("/items?tags=a&tags=b").json() == {"tags": ["a", "b"]}


def test_default_is_applied_when_absent(app, client):
    @app.get("/items")
    async def handler(ctx, page=Query(7, type=int, ge=1)):
        return json({"page": page})

    assert client.get("/items").json() == {"page": 7}


def test_alias_is_reported_in_errors(app, client):
    """Errors name the wire parameter, not the Python identifier."""

    @app.get("/items")
    async def handler(ctx, page_num=Query(type=int, alias="page")):
        return json({"page": page_num})

    resp = client.get("/items?page=nope")
    assert resp.json()["detail"][0]["loc"] == ["query", "page"]


def test_header_validation_uses_header_casing(app, client):
    @app.get("/items")
    async def handler(ctx, x_count=Header(type=int)):
        return json({"count": x_count})

    assert client.get("/items", headers={"X-Count": "5"}).json() == {"count": 5}
    resp = client.get("/items")
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["header", "X-Count"]


def test_cookie_validation(app, client):
    @app.get("/items")
    async def handler(ctx, visits=Cookie(0, type=int)):
        return json({"visits": visits})

    client.cookies.set("visits", "12")
    assert client.get("/items").json() == {"visits": 12}


def test_path_marker_validates(app, client):
    """A Path marker types a plain {id} segment without changing the pattern."""

    @app.get("/items/{item_id}")
    async def handler(ctx, item_id=Path(type=int)):
        return json({"id": item_id, "type": type(item_id).__name__})

    assert client.get("/items/42").json() == {"id": 42, "type": "int"}
    resp = client.get("/items/abc")
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["path", "item_id"]


def test_path_marker_does_not_duplicate_kwarg(app, client):
    """Path params also arrive as **kwargs; the validated value must win once."""

    @app.get("/items/{item_id}")
    async def handler(ctx, item_id=Path(type=int)):
        return json({"id": item_id})

    assert client.get("/items/9").status_code == 200


def test_errors_from_several_locations_are_reported_together(app, client):
    """One round trip should surface every problem, not just the first."""

    @app.get("/items/{item_id}")
    async def handler(
        ctx,
        item_id=Path(type=int),
        page=Query(type=int),
        x_count=Header(type=int),
    ):
        return json({})

    resp = client.get("/items/bad?page=bad", headers={"X-Count": "bad"})
    assert resp.status_code == 422
    locations = {tuple(e["loc"]) for e in resp.json()["detail"]}
    assert ("path", "item_id") in locations
    assert ("query", "page") in locations
    assert ("header", "X-Count") in locations


def test_strict_mode_upgrades_legacy_markers(strict_app):
    """strict_validation turns the legacy 500s into proper 422s."""

    @strict_app.get("/items")
    async def handler(ctx, q=Query(required=True), page=Query(1)):
        return json({"q": q, "page": page})

    client = TestClient(strict_app)

    resp = client.get("/items")
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["query", "q"]

    resp = client.get("/items?q=a&page=zz")
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["query", "page"]

    assert client.get("/items?q=a&page=4").json() == {"q": "a", "page": 4}


def test_shared_marker_instance_binds_per_handler(app, client):
    """A marker held in a constant must not leak its binding across handlers.

    Binding mutates the marker's name and alias. Without a per-handler copy the
    first handler to bind would win, and a second handler reusing the constant
    under a different parameter name would read the wrong key off the wire.
    """
    shared = Query(1, type=int)

    @app.get("/a")
    async def handler_a(ctx, page=shared):
        return json({"page": page})

    @app.get("/b")
    async def handler_b(ctx, offset=shared):
        return json({"offset": offset})

    assert client.get("/a?page=5").json() == {"page": 5}
    assert client.get("/b?offset=9").json() == {"offset": 9}
