"""
Request bodies come from the ``request_model=`` route argument — the single way
to declare one — plus forms and multipart uploads via markers.
"""

from sillo import File, Form, Path, Query
from sillo import json
from sillo.core.dependencies import Depend
from sillo.testclient import TestClient

from .conftest import UserCreate


def test_request_model_injects_into_bare_param(app, client):
    @app.post("/users", request_model=UserCreate)
    async def handler(ctx, user):
        return json({"name": user.name, "age": user.age})

    assert client.post("/users", json={"name": "Alice", "age": 30}).json() == {
        "name": "Alice",
        "age": 30,
    }


def test_request_model_also_on_request(app, client):
    """The body is always reachable via ctx.validated_data."""

    @app.post("/users", request_model=UserCreate)
    async def handler(ctx):
        return json({"name": ctx.validated_data.name})

    assert client.post("/users", json={"name": "Al", "age": 1}).json() == {"name": "Al"}


def test_request_model_composes_with_depend(app, client):
    """A Depend no longer blocks body injection the way positional binding did."""

    def get_db():
        return "db"

    @app.post("/users", request_model=UserCreate)
    async def handler(ctx, user, db=Depend(get_db)):
        return json({"name": user.name, "db": db})

    assert client.post("/users", json={"name": "Al", "age": 1}).json() == {
        "name": "Al",
        "db": "db",
    }


def test_request_model_composes_with_markers(app, client):
    @app.post("/users", request_model=UserCreate)
    async def handler(ctx, user, notify=Query(False, type=bool)):
        return json({"name": user.name, "notify": notify})

    assert client.post("/users?notify=true", json={"name": "Al", "age": 1}).json() == {
        "name": "Al",
        "notify": True,
    }


def test_request_model_composes_with_path_params(app, client):
    """A path parameter must not be mistaken for the body target."""

    @app.post("/teams/{team_id}/users", request_model=UserCreate)
    async def handler(ctx, team_id, user):
        return json({"team": team_id, "name": user.name})

    assert client.post("/teams/7/users", json={"name": "Al", "age": 1}).json() == {
        "team": "7",
        "name": "Al",
    }


def test_request_model_with_everything(app, client):
    """Body, path marker, query marker, and a dependency in one handler."""

    def get_db():
        return "db"

    @app.post("/teams/{team_id}/users", request_model=UserCreate)
    async def handler(
        ctx,
        user,
        team_id=Path(type=int),
        page=Query(1, type=int, ge=1),
        db=Depend(get_db),
    ):
        return json(
            {"name": user.name, "team": team_id, "page": page, "db": db}
        )

    resp = client.post("/teams/7/users?page=3", json={"name": "Al", "age": 1})
    assert resp.json() == {"name": "Al", "team": 7, "page": 3, "db": "db"}


def test_legacy_positional_binding_still_works(app, client):
    """A body parameter carrying a default keeps the original binding rule."""

    @app.post("/users", request_model=UserCreate)
    async def handler(ctx, data=None):
        return json({"name": data.name})

    assert client.post("/users", json={"name": "Al", "age": 1}).json() == {"name": "Al"}


def test_validation_error_keeps_legacy_shape(app, client):
    @app.post("/users", request_model=UserCreate)
    async def handler(ctx, user):
        return json({})

    resp = client.post("/users", json={"name": "Al"})
    assert resp.status_code == 422
    # The historical bare list, not the unified {"detail": [...]} envelope.
    assert isinstance(resp.json(), list)
    assert any(e["loc"] == ["age"] for e in resp.json())


def test_non_object_body_is_422_not_500(app, client):
    """The old ``Model(**body)`` splat raised TypeError on a JSON array."""

    @app.post("/users", request_model=UserCreate)
    async def handler(ctx, user):
        return json({})

    resp = client.post("/users", json=["not", "an", "object"])
    assert resp.status_code == 422


def test_malformed_json_is_422_not_500(app, client):
    @app.post("/users", request_model=UserCreate)
    async def handler(ctx, user):
        return json({})

    resp = client.post(
        "/users", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 422
    assert resp.json()[0]["type"] == "json_invalid"


def test_strict_mode_unifies_body_error_shape(strict_app):
    """strict_validation puts body errors in the same envelope as everything else."""

    @strict_app.post("/users", request_model=UserCreate)
    async def handler(ctx, user):
        return json({})

    resp = TestClient(strict_app).post("/users", json={"name": "Al"})
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["body", "age"]


def test_urlencoded_form(app, client):
    @app.post("/form")
    async def handler(ctx, title=Form(type=str), count=Form(0, type=int)):
        return json({"title": title, "count": count})

    assert client.post("/form", data={"title": "hello", "count": "3"}).json() == {
        "title": "hello",
        "count": 3,
    }


def test_form_validation_error_is_422(app, client):
    @app.post("/form")
    async def handler(ctx, count=Form(type=int)):
        return json({})

    resp = client.post("/form", data={"count": "abc"})
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["form", "count"]


def test_multipart_file_upload(app, client):
    @app.post("/upload")
    async def handler(ctx, title=Form(type=str), avatar=File(...)):
        content = await avatar.read()
        return json(
            {"title": title, "filename": avatar.filename, "size": len(content)}
        )

    resp = client.post(
        "/upload", data={"title": "pic"}, files={"avatar": ("a.txt", b"hello")}
    )
    assert resp.json() == {"title": "pic", "filename": "a.txt", "size": 5}


def test_missing_required_file_is_422(app, client):
    @app.post("/upload")
    async def handler(ctx, avatar=File(...)):
        return json({})

    resp = client.post("/upload", data={"other": "x"})
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["form", "avatar"]


def test_optional_file_defaults_to_none(app, client):
    @app.post("/upload")
    async def handler(ctx, avatar=File(None)):
        return json({"got": avatar is not None})

    assert client.post("/upload", data={"other": "x"}).json() == {"got": False}


def test_markers_work_inside_dependencies(app, client):
    """Validated markers must resolve in sub-dependencies, not only handlers."""

    def pagination(page=Query(1, type=int, ge=1), size=Query(10, type=int, le=50)):
        return {"page": page, "size": size}

    @app.get("/items")
    async def handler(ctx, pager=Depend(pagination)):
        return json(pager)

    assert client.get("/items?page=3&size=20").json() == {"page": 3, "size": 20}

    resp = client.get("/items?size=999")
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["query", "size"]
