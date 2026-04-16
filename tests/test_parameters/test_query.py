"""
Tests for Query parameter extractor.
"""

import pytest
from nexios import NexiosApp, Query
from nexios.http import Request, Response
from nexios.testclient import TestClient


@pytest.fixture
def app():
    return NexiosApp()


@pytest.fixture
def client(app):
    return TestClient(app)


def test_query_with_defaults(app, client):
    """Test Query extractor returns defaults when no params provided."""

    @app.get("/test")
    async def handler(request: Request, response: Response, page: int = Query(1)):
        return {"page": page}

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["page"] == 1


def test_query_override(app, client):
    """Test Query extractor uses provided value."""

    @app.get("/test")
    async def handler(request: Request, response: Response, page: int = Query(1)):
        return {"page": page}

    response = client.get("/test?page=5")
    assert response.status_code == 200
    assert response.json()["page"] == 5


def test_query_multiple_params(app, client):
    """Test multiple Query parameters."""

    @app.get("/test")
    async def handler(
        request: Request,
        response: Response,
        page: int = Query(1),
        limit: int = Query(10),
        search: str = Query(""),
    ):
        return {"page": page, "limit": limit, "search": search}

    response = client.get("/test?page=3&limit=25&search=hello")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 3
    assert data["limit"] == 25
    assert data["search"] == "hello"


def test_query_with_string_default(app, client):
    """Test Query with string default."""

    @app.get("/test")
    async def handler(
        request: Request, response: Response, name: str = Query("anonymous")
    ):
        return {"name": name}

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["name"] == "anonymous"

    response = client.get("/test?name=john")
    assert response.status_code == 200
    assert response.json()["name"] == "john"


def test_query_no_default(app, client):
    """Test Query with no default returns None."""

    @app.get("/test")
    async def handler(request: Request, response: Response, q: str = Query()):
        return {"q": q}

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["q"] is None


def test_query_type_conversion_int(app, client):
    """Test Query converts string to int."""

    @app.get("/test")
    async def handler(request: Request, response: Response, count: int = Query(0)):
        return {"count": count, "type": type(count).__name__}

    response = client.get("/test?count=42")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 42
    assert data["type"] == "int"


def test_query_type_conversion_float(app, client):
    """Test Query converts string to float."""

    @app.get("/test")
    async def handler(request: Request, response: Response, price: float = Query(0.0)):
        return {"price": price, "type": type(price).__name__}

    response = client.get("/test?price=19.99")
    assert response.status_code == 200
    data = response.json()
    assert data["price"] == 19.99
    assert data["type"] == "float"


def test_query_type_conversion_bool(app, client):
    """Test Query converts string to bool."""

    @app.get("/test")
    async def handler(
        request: Request, response: Response, active: bool = Query(False)
    ):
        return {"active": active, "type": type(active).__name__}

    response = client.get("/test?active=true")
    assert response.status_code == 200
    assert response.json()["active"] is True

    response = client.get("/test?active=1")
    assert response.json()["active"] is True

    response = client.get("/test?active=no")
    assert response.json()["active"] is False


def test_query_list_type(app, client):
    """Test Query with list type."""

    @app.get("/test")
    async def handler(
        request: Request, response: Response, tags: list[str] = Query([])
    ):
        return {"tags": tags}

    response = client.get("/test?tags=a,b,c")
    assert response.status_code == 200
    assert response.json()["tags"] == ["a", "b", "c"]


def test_query_list_int_type(app, client):
    """Test Query with list - note: type inference from empty list is limited."""

    @app.get("/test")
    async def handler(request: Request, response: Response, ids: list[str] = Query([])):
        return {"ids": ids}

    response = client.get("/test?ids=1,2,3")
    assert response.status_code == 200
    assert response.json()["ids"] == ["1", "2", "3"]


def test_query_alias(app, client):
    """Test Query with alias."""

    @app.get("/test")
    async def handler(
        request: Request, response: Response, page_num: int = Query(1, alias="page")
    ):
        return {"page": page_num}

    response = client.get("/test?page=7")
    assert response.status_code == 200
    assert response.json()["page"] == 7


def test_query_required(app, client):
    """Test Query with required=True raises error."""

    @app.get("/test")
    async def handler(
        request: Request, response: Response, q: str = Query(required=True)
    ):
        return {"q": q}

    response = client.get("/test")
    assert response.status_code == 500


def test_query_partial_override(app, client):
    """Test partial query param override."""

    @app.get("/test")
    async def handler(
        request: Request,
        response: Response,
        page: int = Query(1),
        limit: int = Query(10),
    ):
        return {"page": page, "limit": limit}

    response = client.get("/test?page=5")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 5
    assert data["limit"] == 10
