"""
Tests for parameter extractors in nested dependencies.
"""

import pytest
from nexios import NexiosApp, Query, Header, Cookie, Depend
from nexios.http import Request, Response
from nexios.testclient import TestClient


@pytest.fixture
def app():
    return NexiosApp()


@pytest.fixture
def client(app):
    return TestClient(app)


def test_nested_query_dependency(app, client):
    """Test Query extractor works in nested dependency."""

    def get_pagination(page: int = Query(1), limit: int = Query(10)):
        return {"page": page, "limit": limit}

    @app.get("/test")
    async def handler(
        request: Request, response: Response, pagination: dict = Depend(get_pagination)
    ):
        return pagination

    response = client.get("/test")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["limit"] == 10


def test_nested_query_override(app, client):
    """Test Query in nested dependency uses provided values."""

    def get_pagination(page: int = Query(1), limit: int = Query(10)):
        return {"page": page, "limit": limit}

    @app.get("/test")
    async def handler(
        request: Request, response: Response, pagination: dict = Depend(get_pagination)
    ):
        return pagination

    response = client.get("/test?page=3&limit=25")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 3
    assert data["limit"] == 25


def test_nested_header_dependency(app, client):
    """Test Header extractor works in nested dependency."""

    def get_auth(authorization: str = Header()):
        return {"token": authorization}

    @app.get("/test")
    async def handler(
        request: Request, response: Response, auth: dict = Depend(get_auth)
    ):
        return auth

    response = client.get("/test", headers={"Authorization": "Bearer secret"})
    assert response.status_code == 200
    assert response.json()["token"] == "Bearer secret"


def test_nested_header_no_value(app, client):
    """Test Header in nested dependency returns None when not provided."""

    def get_auth(authorization: str = Header()):
        return {"token": authorization}

    @app.get("/test")
    async def handler(
        request: Request, response: Response, auth: dict = Depend(get_auth)
    ):
        return auth

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["token"] is None


def test_nested_cookie_dependency(app, client):
    """Test Cookie extractor works in nested dependency."""

    def get_prefs(theme: str = Cookie("dark")):
        return {"theme": theme}

    @app.get("/test")
    async def handler(
        request: Request, response: Response, prefs: dict = Depend(get_prefs)
    ):
        return prefs

    response = client.get("/test", cookies={"theme": "purple"})
    assert response.status_code == 200
    assert response.json()["theme"] == "purple"


def test_nested_cookie_default(app, client):
    """Test Cookie in nested dependency uses default."""

    def get_prefs(theme: str = Cookie("dark")):
        return {"theme": theme}

    @app.get("/test")
    async def handler(
        request: Request, response: Response, prefs: dict = Depend(get_prefs)
    ):
        return prefs

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["theme"] == "dark"


def test_deeply_nested_query(app, client):
    """Test Query in deeply nested dependency."""

    def get_page(page: int = Query(1)):
        return page

    def get_pagination(page: int = Depend(get_page), limit: int = Query(10)):
        return {"page": page, "limit": limit}

    @app.get("/test")
    async def handler(
        request: Request, response: Response, pagination: dict = Depend(get_pagination)
    ):
        return pagination

    response = client.get("/test?page=5&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 5
    assert data["limit"] == 20


def test_mixed_params_in_dependency(app, client):
    """Test mixed Query, Header, Cookie in same dependency."""

    def get_context(
        page: int = Query(1),
        authorization: str = Header(),
        theme: str = Cookie("dark"),
    ):
        return {"page": page, "auth": authorization, "theme": theme}

    @app.get("/test")
    async def handler(
        request: Request, response: Response, ctx: dict = Depend(get_context)
    ):
        return ctx

    response = client.get(
        "/test?page=2",
        headers={"Authorization": "Bearer token"},
        cookies={"theme": "light"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert data["auth"] == "Bearer token"
    assert data["theme"] == "light"


def test_handler_and_nested_both_have_query(app, client):
    """Test Query works in both handler and nested dependency."""

    def get_pagination(limit: int = Query(10)):
        return {"limit": limit}

    @app.get("/test")
    async def handler(
        request: Request,
        response: Response,
        page: int = Query(1),
        pagination: dict = Depend(get_pagination),
    ):
        return {"page": page, "limit": pagination["limit"]}

    response = client.get("/test?page=5&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 5
    assert data["limit"] == 20


def test_nested_dep_with_own_dep_and_query(app, client):
    """Test nested dependency with its own dependency and Query param."""

    def get_db():
        return {"db": "sqlite"}

    def get_config(db: dict = Depend(get_db), page: int = Query(1)):
        return {**db, "page": page}

    @app.get("/test")
    async def handler(
        request: Request, response: Response, config: dict = Depend(get_config)
    ):
        return config

    response = client.get("/test?page=7")
    assert response.status_code == 200
    data = response.json()
    assert data["db"] == "sqlite"
    assert data["page"] == 7
