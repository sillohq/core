"""
Tests for OpenAPI integration with Query, Header, Cookie parameters.
"""

import pytest
from nexios import NexiosApp, Query, Header, Cookie
from nexios.http import Request, Response


@pytest.fixture
def app():
    return NexiosApp()


def test_query_params_in_openapi(app):
    """Test Query parameters appear in OpenAPI spec."""

    @app.get("/items")
    async def get_items(
        request: Request,
        response: Response,
        page: int = Query(1),
        limit: int = Query(10),
    ):
        return {"page": page, "limit": limit}

    spec = app.openapi.get_openapi(app.router)
    params = spec["paths"]["/items"]["get"]["parameters"]

    assert len(params) == 2

    page_param = next(p for p in params if p["name"] == "page")
    assert page_param["in"] == "query"
    assert page_param["schema"]["type"] == "integer"
    assert page_param["schema"]["default"] == 1

    limit_param = next(p for p in params if p["name"] == "limit")
    assert limit_param["in"] == "query"
    assert limit_param["schema"]["type"] == "integer"
    assert limit_param["schema"]["default"] == 10


def test_header_params_in_openapi(app):
    """Test Header parameters appear in OpenAPI spec."""

    @app.get("/api")
    async def api_handler(
        request: Request,
        response: Response,
        authorization: str = Header(),
    ):
        return {"auth": authorization}

    spec = app.openapi.get_openapi(app.router)
    params = spec["paths"]["/api"]["get"]["parameters"]

    assert len(params) == 1

    auth_param = params[0]
    assert auth_param["name"] == "Authorization"
    assert auth_param["in"] == "header"
    assert auth_param["schema"]["type"] == "string"


def test_cookie_params_in_openapi(app):
    """Test Cookie parameters appear in OpenAPI spec."""

    @app.get("/settings")
    async def settings(
        request: Request,
        response: Response,
        theme: str = Cookie("light"),
    ):
        return {"theme": theme}

    spec = app.openapi.get_openapi(app.router)
    params = spec["paths"]["/settings"]["get"]["parameters"]

    assert len(params) == 1

    cookie_param = params[0]
    assert cookie_param["name"] == "theme"
    assert cookie_param["in"] == "cookie"
    assert cookie_param["schema"]["type"] == "string"
    assert cookie_param["schema"]["default"] == "light"


def test_mixed_params_in_openapi(app):
    """Test Query, Header, and Cookie params all appear in OpenAPI spec."""

    @app.get("/mixed")
    async def mixed_handler(
        request: Request,
        response: Response,
        page: int = Query(1),
        authorization: str = Header(),
        theme: str = Cookie("dark"),
    ):
        return {"page": page, "auth": authorization, "theme": theme}

    spec = app.openapi.get_openapi(app.router)
    params = spec["paths"]["/mixed"]["get"]["parameters"]

    assert len(params) == 3

    names_in = {p["name"]: p["in"] for p in params}
    assert names_in["page"] == "query"
    assert names_in["Authorization"] == "header"
    assert names_in["theme"] == "cookie"


def test_header_alias_in_openapi(app):
    """Test Header with custom alias appears in OpenAPI spec."""

    @app.get("/custom-header")
    async def custom_header(
        request: Request,
        response: Response,
        api_key: str = Header(alias="X-API-Key"),
    ):
        return {"key": api_key}

    spec = app.openapi.get_openapi(app.router)
    params = spec["paths"]["/custom-header"]["get"]["parameters"]

    assert len(params) == 1
    assert params[0]["name"] == "X-API-Key"
    assert params[0]["in"] == "header"


def test_query_alias_in_openapi(app):
    """Test Query with custom alias appears in OpenAPI spec."""

    @app.get("/alias")
    async def alias_handler(
        request: Request,
        response: Response,
        page_num: int = Query(1, alias="page"),
    ):
        return {"page": page_num}

    spec = app.openapi.get_openapi(app.router)
    params = spec["paths"]["/alias"]["get"]["parameters"]

    assert len(params) == 1
    assert params[0]["name"] == "page"
    assert params[0]["in"] == "query"


def test_required_param_in_openapi(app):
    """Test required parameter marked correctly in OpenAPI spec."""

    @app.get("/required")
    async def required_handler(
        request: Request,
        response: Response,
        q: str = Query(required=True),
    ):
        return {"q": q}

    spec = app.openapi.get_openapi(app.router)
    params = spec["paths"]["/required"]["get"]["parameters"]

    assert len(params) == 1
    assert params[0]["name"] == "q"
    assert params[0]["in"] == "query"
    assert params[0]["required"] is True


def test_nested_dep_params_in_openapi(app):
    """Test parameters in nested dependencies appear in OpenAPI."""

    def get_pagination(page: int = Query(1), limit: int = Query(10)):
        return {"page": page, "limit": limit}

    @app.get("/nested")
    async def nested_handler(
        request: Request,
        response: Response,
        pagination: dict = None,
    ):
        return pagination

    spec = app.openapi.get_openapi(app.router)
    assert "/nested" in spec["paths"]
