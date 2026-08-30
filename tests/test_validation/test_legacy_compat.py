"""
Markers written in the pre-Pydantic style must behave exactly as they always
have, including the rough edges. These tests pin that contract so the Pydantic
engine cannot silently change an existing application's behavior.
"""

from sillo import Cookie, Header, Query
from sillo import json
from sillo.testclient import TestClient


def test_int_default_still_coerces(app, client):
    """A default value's type still drives coercion when no type is declared."""

    @app.get("/legacy")
    async def handler(ctx, page=Query(1)):
        return json({"page": page, "type": type(page).__name__})

    data = client.get("/legacy?page=42").json()
    assert data == {"page": 42, "type": "int"}


def test_missing_param_without_default_is_none(app, client):
    """Query() with no default yields None rather than a 422."""

    @app.get("/legacy")
    async def handler(ctx, q=Query()):
        return json({"q": q})

    assert client.get("/legacy").json() == {"q": None}


def test_no_default_returns_raw_string(app, client):
    """Without a default there is nothing to infer from, so the string is raw."""

    @app.get("/legacy")
    async def handler(ctx, q=Query()):
        return json({"type": type(q).__name__})

    assert client.get("/legacy?q=123").json() == {"type": "str"}


def test_required_missing_is_500(app):
    """The historical 500 on a missing required param is preserved.

    This is a bad response for what is really a client error, which is exactly
    why ``strict_validation`` exists. It stays the default so applications
    relying on the current behavior are not broken by an upgrade.
    """

    @app.get("/legacy")
    async def handler(ctx, q=Query(required=True)):
        return json({"q": q})

    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/legacy").status_code == 500


def test_list_default_comma_splits(app, client):
    """A list default keeps the legacy comma-splitting behavior."""

    @app.get("/legacy")
    async def handler(ctx, tags=Query([])):
        return json({"tags": tags})

    assert client.get("/legacy?tags=a,b,c").json() == {"tags": ["a", "b", "c"]}


def test_bool_default_coerces_yes(app, client):
    """Legacy bool coercion accepts 'yes', which plain Pydantic would reject."""

    @app.get("/legacy")
    async def handler(ctx, active=Query(False)):
        return json({"active": active})

    assert client.get("/legacy?active=yes").json() == {"active": True}


def test_header_and_cookie_defaults(app, client):
    """Header casing and cookie defaults are unchanged."""

    @app.get("/legacy")
    async def handler(ctx, x_api_key=Header(), theme=Cookie("dark")):
        return json({"key": x_api_key, "theme": theme})

    data = client.get("/legacy", headers={"X-Api-Key": "abc"}).json()
    assert data == {"key": "abc", "theme": "dark"}


def test_metadata_only_does_not_change_behavior(app, client):
    """Adding a description documents a param without opting it into validation.

    Documentation keywords must never flip the runtime path, or enriching an
    OpenAPI entry could break a running endpoint.
    """

    @app.get("/legacy")
    async def handler(ctx, q=Query(description="a query")):
        return json({"q": q})

    assert client.get("/legacy").json() == {"q": None}
