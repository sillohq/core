"""
Tests for path parameters and URL generation
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.core.routing import Route, Router
from sillo.testclient import TestClient

# ========== Basic Path Parameters Tests ==========


def test_single_path_parameter(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test route with single path parameter"""
    app = SilloApp()

    @app.get("/users/{user_id}")
    async def get_user(request: HttpContext, user_id: str):
        return json({"user_id": user_id})

    with test_client_factory(app) as client:
        resp = client.get("/users/123")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "123"


def test_multiple_path_parameters(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route with multiple path parameters"""
    app = SilloApp()

    @app.get("/users/{user_id}/posts/{post_id}")
    async def get_user_post(
        request: HttpContext, user_id: str, post_id: str
    ):
        return json({"user_id": user_id, "post_id": post_id})

    with test_client_factory(app) as client:
        resp = client.get("/users/456/posts/789")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "456"
        assert resp.json()["post_id"] == "789"


def test_path_parameter_with_router(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test path parameters on mounted router"""
    app = SilloApp()
    router = Router(prefix="/api")

    @router.get("/products/{product_id}")
    async def get_product(request: HttpContext, product_id: str):
        return json({"product_id": product_id})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/products/abc123")
        assert resp.status_code == 200
        assert resp.json()["product_id"] == "abc123"


# ========== Path Parameter Types Tests ==========


def test_integer_path_parameter(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test path parameter with integer type"""
    app = SilloApp()

    @app.get("/items/{item_id:int}")
    async def get_item(request: HttpContext, item_id: int):
        return json({"item_id": item_id, "type": type(item_id).__name__})

    with test_client_factory(app) as client:
        resp = client.get("/items/123")
        assert resp.status_code == 200
        assert resp.json()["item_id"] == 123


def test_float_path_parameter(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test path parameter with float type"""
    app = SilloApp()

    @app.get("/prices/{price:float}")
    async def get_price(request: HttpContext, price: float):
        return json({"price": price, "type": type(price).__name__})

    with test_client_factory(app) as client:
        resp = client.get("/prices/19.99")
        assert resp.status_code == 200
        assert resp.json()["price"] == 19.99


def test_path_path_parameter(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test path parameter with path type (captures slashes)"""
    app = SilloApp()

    @app.get("/files/{filepath:path}")
    async def get_file(request: HttpContext, filepath: str):
        return json({"filepath": filepath})

    with test_client_factory(app) as client:
        resp = client.get("/files/documents/reports/2024/report.pdf")
        assert resp.status_code == 200
        assert resp.json()["filepath"] == "documents/reports/2024/report.pdf"


# ========== URL Generation Tests ==========


def test_url_for_basic(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test basic URL generation with url_for"""
    app = SilloApp()

    @app.get("/users", name="list-users")
    async def list_users(request: HttpContext):
        return json({"users": []})

    with test_client_factory(app) as client:
        url = app.url_for("list-users")
        assert url == "/users"


def test_url_for_with_path_parameter(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test URL generation with path parameters"""
    app = SilloApp()

    @app.get("/users/{user_id}", name="get-user")
    async def get_user(request: HttpContext, user_id: str):
        return json({"user_id": user_id})

    with test_client_factory(app) as client:
        url = app.url_for("get-user", user_id="123")
        assert url == "/users/123"


def test_url_for_with_multiple_parameters(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test URL generation with multiple path parameters"""
    app = SilloApp()

    @app.get("/users/{user_id}/posts/{post_id}", name="get-user-post")
    async def get_user_post(
        request: HttpContext, user_id: str, post_id: str
    ):
        return json({"user_id": user_id, "post_id": post_id})

    with test_client_factory(app) as client:
        url = app.url_for("get-user-post", user_id="456", post_id="789")
        assert url == "/users/456/posts/789"


def test_url_for_on_router(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test URL generation on router"""
    app = SilloApp()
    router = Router(prefix="/api")

    @router.get("/products/{product_id}", name="get-product")
    async def get_product(request: HttpContext, product_id: str):
        return json({"product_id": product_id})

    app.mount_router(router, name="api")

    with test_client_factory(app) as client:
        url = app.url_for("api.get-product", product_id="abc")
        assert "/products/abc" in url


def test_url_for_missing_parameter():
    """Test that url_for raises error when parameter is missing"""
    app = SilloApp()

    @app.get("/users/{user_id}", name="get-user")
    async def get_user(request: HttpContext, user_id: str):
        return json({"user_id": user_id})

    with pytest.raises(ValueError):
        app.url_for("get-user")  # Missing user_id parameter


def test_url_for_nonexistent_route():
    """Test that url_for raises error for nonexistent route"""
    app = SilloApp()

    with pytest.raises(Exception):
        app.url_for("nonexistent-route")


# ========== Complex Path Patterns Tests ==========


def test_nested_path_parameters(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test deeply nested path parameters"""
    app = SilloApp()

    @app.get("/orgs/{org_id}/teams/{team_id}/members/{member_id}")
    async def get_member(
        request: HttpContext, org_id: str, team_id: str, member_id: str
    ):
        return json(
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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test path parameters with special characters"""
    app = SilloApp()

    @app.get("/search/{query}")
    async def search(request: HttpContext, query: str):
        return json({"query": query})

    with test_client_factory(app) as client:
        resp = client.get("/search/hello-world")
        assert resp.status_code == 200
        assert resp.json()["query"] == "hello-world"


def test_optional_trailing_slash(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test routes with and without trailing slashes"""
    app = SilloApp()

    @app.get("/items/{item_id}")
    async def get_item(request: HttpContext, item_id: str):
        return json({"item_id": item_id})

    with test_client_factory(app) as client:
        resp = client.get("/items/123")
        assert resp.status_code == 200
        assert resp.json()["item_id"] == "123"


# ========== Path Parameter Validation Tests ==========


def test_path_params_in_request_object(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test that path params are accessible in request.path_params"""
    app = SilloApp()

    @app.get("/api/{version}/users/{user_id}")
    async def get_user(request: HttpContext, *args, **kwargs):
        return json(
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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test routes with mixed static and dynamic segments"""
    app = SilloApp()

    @app.get("/api/v1/users/{user_id}/profile")
    async def get_profile(request: HttpContext, user_id: str):
        return json({"user_id": user_id, "endpoint": "profile"})

    with test_client_factory(app) as client:
        resp = client.get("/api/v1/users/alice/profile")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "alice"
        assert resp.json()["endpoint"] == "profile"


def test_uuid_path_parameter(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test path parameter with UUID format"""
    app = SilloApp()

    @app.get("/resources/{resource_id}")
    async def get_resource(request: HttpContext, resource_id: str):
        return json({"resource_id": resource_id})

    with test_client_factory(app) as client:
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        resp = client.get(f"/resources/{uuid}")
        assert resp.status_code == 200
        assert resp.json()["resource_id"] == uuid
