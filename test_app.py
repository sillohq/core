# ty:ignore[invalid-parameter-default]
import pytest
from nexios import NexiosApp, Query, Header, Cookie, Depend
from nexios.http import Request, Response
from nexios.testclient import TestClient


app = NexiosApp()


@app.get("/query")
async def query_params(
    request: Request,
    response: Response,
    page: int = Query(1),  
    limit: int = Query(10),
    search: str = Query(""),
):
    return {"page": page, "limit": limit, "search": search}


@app.get("/query-lists")
async def query_lists(
    request: Request, response: Response, tags: list[str] = Query([])
):
    return {"tags": tags}


@app.get("/headers")
async def header_params(
    request: Request,
    response: Response,
    authorization: str = Header(),
    x_request_id: str = Header(alias="X-Request-ID"),
):
    return {"auth": authorization, "request_id": x_request_id}


@app.get("/cookies")
async def cookie_params(
    request: Request,
    response: Response,
    user_id: str = Cookie(),
    theme: str = Cookie("light"),
):
    return {"user_id": user_id, "theme": theme}


def get_pagination(page: int = Query(1), limit: int = Query(10)):
    return {"page": page, "limit": limit}


@app.get("/nested-pagination")
async def nested_pagination(
    request: Request, response: Response, pagination: dict = Depend(get_pagination)
):
    return pagination


def get_auth_token(authorization: str = Header()):
    if not authorization:
        raise ValueError("No authorization header")
    return {"token": authorization}




@app.get("/nested-header")
async def nested_header(
    request: Request, response: Response, auth: dict = Depend(get_auth_token)
):
    return auth


def get_user_preferences(theme: str = Cookie("dark"), lang: str = Cookie("en")):
    return {"theme": theme, "language": lang}


@app.get("/nested-cookie")
async def nested_cookie(
    request: Request, response: Response, prefs: dict = Depend(get_user_preferences)
):
    return prefs


client = TestClient(app)


def test_query_params_defaults():
    response = client.get("/query")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["limit"] == 10
    assert data["search"] == ""


def test_query_params_override():
    response = client.get("/query?page=5&limit=20&search=hello")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 5
    assert data["limit"] == 20
    assert data["search"] == "hello"


def test_query_lists():
    response = client.get("/query-lists?tags=a,b,c")
    assert response.status_code == 200
    data = response.json()
    assert data["tags"] == ["a", "b", "c"]


def test_headers_required():
    response = client.get("/headers", headers={"Authorization": "Bearer token123"})
    assert response.status_code == 200
    data = response.json()
    assert data["auth"] == "Bearer token123"


def test_headers_with_alias():
    response = client.get(
        "/headers",
        headers={"Authorization": "Bearer token123", "X-Request-ID": "req-456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req-456"


def test_cookies():
    response = client.get("/cookies", cookies={"user_id": "user123", "theme": "dark"})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user123"
    assert data["theme"] == "dark"


def test_cookies_defaults():
    response = client.get("/cookies")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] is None
    assert data["theme"] == "light"


def test_nested_pagination():
    response = client.get("/nested-pagination?page=3&limit=25")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 3
    assert data["limit"] == 25


def test_nested_header_dependency():
    response = client.get("/nested-header", headers={"Authorization": "Bearer secret"})
    assert response.status_code == 200
    data = response.json()
    assert data["token"] == "Bearer secret"


def test_nested_cookie_dependency():
    response = client.get("/nested-cookie", cookies={"theme": "blue", "lang": "fr"})
    assert response.status_code == 200
    data = response.json()
    assert data["theme"] == "blue"
    assert data["language"] == "fr"


def test_nested_cookie_defaults():
    response = client.get("/nested-cookie")
    assert response.status_code == 200
    data = response.json()
    assert data["theme"] == "dark"
    assert data["language"] == "en"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
