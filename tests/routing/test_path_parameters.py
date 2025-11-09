"""
Tests for path parameters and URL generation
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.routing import Route, Router
from nexios.testclient import TestClient

# ========== Basic Path Parameters Tests ==========


def test_single_path_parameter(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test route with single path parameter"""
    app = NexiosApp()

    @app.get("/users/{user_id}")
    async def get_user(request: Request, response: Response, user_id: str):
        return response.json({"user_id": user_id})

    with test_client_factory(app) as client:
        resp = client.get("/users/123")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "123"


def test_multiple_path_parameters(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route with multiple path parameters"""
    app = NexiosApp()

    @app.get("/users/{user_id}/posts/{post_id}")
    async def get_user_post(
        request: Request, response: Response, user_id: str, post_id: str
    ):
        return response.json({"user_id": user_id, "post_id": post_id})

    with test_client_factory(app) as client:
        resp = client.get("/users/456/posts/789")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "456"
        assert resp.json()["post_id"] == "789"


def test_path_parameter_with_router(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test path parameters on mounted router"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.get("/products/{product_id}")
    async def get_product(request: Request, response: Response, product_id: str):
        return response.json({"product_id": product_id})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/products/abc123")
        assert resp.status_code == 200
        assert resp.json()["product_id"] == "abc123"


def test_path_parameter_from_request_path_params(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test accessing path parameters from request.path_params"""
    app = NexiosApp()

    @app.get("/items/{item_id}")
    async def get_item(request: Request, response: Response):
        item_id = request.path_params.get("item_id")
        return response.json({"item_id": item_id})

    with test_client_factory(app) as client:
        resp = client.get("/items/xyz")
        assert resp.status_code == 200
        assert resp.json()["item_id"] == "xyz"


# ========== Path Parameter Types Tests ==========


def test_integer_path_parameter(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test path parameter with integer type"""
    app = NexiosApp()

    @app.get("/items/{item_id:int}")
    async def get_item(request: Request, response: Response, item_id: int):
        return response.json({"item_id": item_id, "type": type(item_id).__name__})

    with test_client_factory(app) as client:
        resp = client.get("/items/123")
        assert resp.status_code == 200
        assert resp.json()["item_id"] == 123


def test_float_path_parameter(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test path parameter with float type"""
    app = NexiosApp()

    @app.get("/prices/{price:float}")
    async def get_price(request: Request, response: Response, price: float):
        return response.json({"price": price, "type": type(price).__name__})

    with test_client_factory(app) as client:
        resp = client.get("/prices/19.99")
        assert resp.status_code == 200
        assert resp.json()["price"] == 19.99


def test_path_path_parameter(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test path parameter with path type (captures slashes)"""
    app = NexiosApp()

    @app.get("/files/{filepath:path}")
    async def get_file(request: Request, response: Response, filepath: str):
        return response.json({"filepath": filepath})

    with test_client_factory(app) as client:
        resp = client.get("/files/documents/reports/2024/report.pdf")
        assert resp.status_code == 200
        assert resp.json()["filepath"] == "documents/reports/2024/report.pdf"


# ========== URL Generation Tests ==========


def test_url_for_basic(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test basic URL generation with url_for"""
    app = NexiosApp()

    @app.get("/users", name="list-users")
    async def list_users(request: Request, response: Response):
        return response.json({"users": []})

    with test_client_factory(app) as client:
        url = app.url_for("list-users")
        assert url == "/users"


def test_url_for_with_path_parameter(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test URL generation with path parameters"""
    app = NexiosApp()

    @app.get("/users/{user_id}", name="get-user")
    async def get_user(request: Request, response: Response, user_id: str):
        return response.json({"user_id": user_id})

    with test_client_factory(app) as client:
        url = app.url_for("get-user", user_id="123")
        assert url == "/users/123"


def test_url_for_with_multiple_parameters(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test URL generation with multiple path parameters"""
    app = NexiosApp()

    @app.get("/users/{user_id}/posts/{post_id}", name="get-user-post")
    async def get_user_post(
        request: Request, response: Response, user_id: str, post_id: str
    ):
        return response.json({"user_id": user_id, "post_id": post_id})

    with test_client_factory(app) as client:
        url = app.url_for("get-user-post", user_id="456", post_id="789")
        assert url == "/users/456/posts/789"


def test_url_for_on_router(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test URL generation on router"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.get("/products/{product_id}", name="get-product")
    async def get_product(request: Request, response: Response, product_id: str):
        return response.json({"product_id": product_id})

    app.mount_router(router, name="api")

    with test_client_factory(app) as client:
        url = app.url_for("api.get-product", product_id="abc")
        assert "/products/abc" in url


def test_url_for_missing_parameter():
    """Test that url_for raises error when parameter is missing"""
    app = NexiosApp()

    @app.get("/users/{user_id}", name="get-user")
    async def get_user(request: Request, response: Response, user_id: str):
        return response.json({"user_id": user_id})

    with pytest.raises(ValueError):
        app.url_for("get-user")  # Missing user_id parameter


def test_url_for_nonexistent_route():
    """Test that url_for raises error for nonexistent route"""
    app = NexiosApp()

    with pytest.raises(Exception):
        app.url_for("nonexistent-route")


# ========== Complex Path Patterns Tests ==========


def test_nested_path_parameters(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test deeply nested path parameters"""
    app = NexiosApp()

    @app.get("/orgs/{org_id}/teams/{team_id}/members/{member_id}")
    async def get_member(
        request: Request, response: Response, org_id: str, team_id: str, member_id: str
    ):
        return response.json(
            {"org_id": org_id, "team_id": team_id, "member_id": member_id}
        )

    with test_client_factory(app) as client:
        resp = client.get("/orgs/org1/teams/team2/members/member3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["org_id"] == "org1"
        assert data["team_id"] == "team2"
        assert data["member_id"] == "member3"


def test_path_parameter_with_special_characters(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test path parameters with special characters"""
    app = NexiosApp()

    @app.get("/search/{query}")
    async def search(request: Request, response: Response, query: str):
        return response.json({"query": query})

    with test_client_factory(app) as client:
        resp = client.get("/search/hello-world")
        assert resp.status_code == 200
        assert resp.json()["query"] == "hello-world"


def test_optional_trailing_slash(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test routes with and without trailing slashes"""
    app = NexiosApp()

    @app.get("/items/{item_id}")
    async def get_item(request: Request, response: Response, item_id: str):
        return response.json({"item_id": item_id})

    with test_client_factory(app) as client:
        resp = client.get("/items/123")
        assert resp.status_code == 200
        assert resp.json()["item_id"] == "123"


# ========== Path Parameter Validation Tests ==========


def test_path_params_in_request_object(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test that path params are accessible in request.path_params"""
    app = NexiosApp()

    @app.get("/api/{version}/users/{user_id}")
    async def get_user(request: Request, response: Response):
        return response.json(
            {
                "version": request.path_params["version"],
                "user_id": request.path_params["user_id"],
                "all_params": dict(request.path_params),
            }
        )

    with test_client_factory(app) as client:
        resp = client.get("/api/v1/users/999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v1"
        assert data["user_id"] == "999"
        assert len(data["all_params"]) == 2


def test_mixed_static_and_dynamic_segments(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test routes with mixed static and dynamic segments"""
    app = NexiosApp()

    @app.get("/api/v1/users/{user_id}/profile")
    async def get_profile(request: Request, response: Response, user_id: str):
        return response.json({"user_id": user_id, "endpoint": "profile"})

    with test_client_factory(app) as client:
        resp = client.get("/api/v1/users/alice/profile")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "alice"
        assert resp.json()["endpoint"] == "profile"


def test_uuid_path_parameter(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test path parameter with UUID format"""
    app = NexiosApp()

    @app.get("/resources/{resource_id}")
    async def get_resource(request: Request, response: Response, resource_id: str):
        return response.json({"resource_id": resource_id})

    with test_client_factory(app) as client:
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        resp = client.get(f"/resources/{uuid}")
        assert resp.status_code == 200
        assert resp.json()["resource_id"] == uuid
