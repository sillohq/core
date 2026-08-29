"""
response_model turns the documented output schema into an enforced one.
"""

from sillo.testclient import TestClient
from sillo import json

from .conftest import UserOut


def test_response_is_shaped_and_coerced(app, client):
    """Undeclared fields are dropped and declared ones coerced."""

    @app.get("/user", response_model=UserOut)
    async def handler(request):
        return {"id": "7", "name": "Ada", "password_hash": "SECRET"}

    assert client.get("/user").json() == {"id": 7, "name": "Ada"}


def test_leaked_field_never_reaches_the_client(app, client):
    @app.get("/user", response_model=UserOut)
    async def handler(request):
        return {"id": 1, "name": "Ada", "password_hash": "SECRET"}

    assert "SECRET" not in client.get("/user").text


def test_many_returns_a_list(app, client):
    @app.get("/users", response_model=UserOut, response_model_many=True)
    async def handler(request):
        return [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]

    assert client.get("/users").json() == [
        {"id": 1, "name": "a"},
        {"id": 2, "name": "b"},
    ]


def test_contract_violation_is_500(app):
    """A handler breaking its own contract is a server bug, not a client one."""

    @app.get("/user", response_model=UserOut)
    async def handler(request):
        return {"unexpected": True}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/user")
    assert resp.status_code == 500
    # The offending value must not leak; the response model exists to filter it.
    assert "unexpected" not in resp.text


def test_responder_return_passes_through_untouched(app, client):
    """A handler that builds its own response keeps full control of it."""

    @app.get("/user", response_model=UserOut)
    async def handler(request):
        return json({"anything": "goes"}, status_code=201)

    resp = client.get("/user")
    assert resp.status_code == 201
    assert resp.json() == {"anything": "goes"}


def test_exclude_none_option(app, client):
    from typing import Optional

    from pydantic import BaseModel

    class Partial(BaseModel):
        id: int
        nickname: Optional[str] = None

    @app.get("/p", response_model=Partial, response_model_exclude_none=True)
    async def handler(request):
        return {"id": 1}

    assert client.get("/p").json() == {"id": 1}


def test_orm_style_object_is_accepted(app, client):
    """Validation reads attributes, so ORM rows work without a manual dict."""

    class Row:
        id = 3
        name = "Ada"
        secret = "nope"

    @app.get("/user", response_model=UserOut)
    async def handler(request):
        return Row()

    assert client.get("/user").json() == {"id": 3, "name": "Ada"}
