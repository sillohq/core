"""
The OpenAPI document is generated from the same Pydantic schemas that perform
validation, so what is published is exactly what is enforced.
"""

from typing import List

from sillo import File, Form, Path, Query
from sillo import json

from .conftest import UserCreate, UserOut


def _op(client, path, method="get"):
    return client.get("/openapi.json").json()["paths"][path][method]


def test_constraints_appear_in_schema(app, client):
    @app.get("/items")
    async def handler(request, page=Query(1, type=int, ge=1, le=99)):
        return json({})

    param = next(p for p in _op(client, "/items")["parameters"] if p["name"] == "page")
    assert param["in"] == "query"
    assert param["schema"]["type"] == "integer"
    assert param["schema"]["minimum"] == 1
    assert param["schema"]["maximum"] == 99
    assert param["schema"]["default"] == 1


def test_description_appears_in_schema(app, client):
    @app.get("/items")
    async def handler(request, q=Query(type=str, description="Search text")):
        return json({})

    param = next(p for p in _op(client, "/items")["parameters"] if p["name"] == "q")
    assert param["schema"]["description"] == "Search text"
    assert param["required"] is True


def test_path_marker_types_the_path_param(app, client):
    @app.get("/items/{item_id}")
    async def handler(request, item_id=Path(type=int)):
        return json({})

    params = _op(client, "/items/{item_id}")["parameters"]
    param = next(p for p in params if p["name"] == "item_id")
    assert param["in"] == "path"
    assert param["schema"]["type"] == "integer"


def test_list_query_param_is_an_array(app, client):
    @app.get("/items")
    async def handler(request, tags=Query([], type=List[str])):
        return json({})

    param = next(p for p in _op(client, "/items")["parameters"] if p["name"] == "tags")
    assert param["schema"]["type"] == "array"
    assert param["schema"]["items"]["type"] == "string"


def test_body_model_schema(app, client):
    @app.post("/users", request_model=UserCreate)
    async def handler(request, user):
        return json({})

    body = _op(client, "/users", "post")["requestBody"]
    schema = body["content"]["application/json"]["schema"]
    assert set(schema["properties"]) == {"name", "age"}
    assert schema["properties"]["age"]["type"] == "integer"


def test_multipart_body_documents_binary_file(app, client):
    @app.post("/upload")
    async def handler(request, title=Form(type=str), avatar=File(...)):
        return json({})

    body = _op(client, "/upload", "post")["requestBody"]
    assert "multipart/form-data" in body["content"]
    props = body["content"]["multipart/form-data"]["schema"]["properties"]
    assert props["title"]["type"] == "string"
    assert props["avatar"] == {"type": "string", "format": "binary"}


def test_urlencoded_body_when_no_file(app, client):
    @app.post("/form")
    async def handler(request, title=Form(type=str)):
        return json({})

    body = _op(client, "/form", "post")["requestBody"]
    assert "application/x-www-form-urlencoded" in body["content"]


def test_response_model_schema(app, client):
    @app.get("/user", response_model=UserOut)
    async def handler(request):
        return {}

    schema = _op(client, "/user")["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert set(schema["properties"]) == {"id", "name"}


def test_legacy_param_schema_is_unchanged(app, client):
    """Legacy markers keep producing exactly the schema they always did."""

    @app.get("/items")
    async def handler(request, page=Query(1), limit=Query(10)):
        return json({})

    params = _op(client, "/items")["parameters"]
    page = next(p for p in params if p["name"] == "page")
    assert page["schema"] == {"type": "integer", "default": 1}


def test_dependency_params_are_documented(app, client):
    """Parameters declared on a dependency belong in the route's docs."""
    from sillo.core.dependencies import Depend

    def pager(page=Query(1, type=int, ge=1)):
        return page

    @app.get("/items")
    async def handler(request, p=Depend(pager)):
        return json({})

    names = [p["name"] for p in _op(client, "/items")["parameters"]]
    assert "page" in names
