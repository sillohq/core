"""
Tests for route grouping using Group class
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.routing import Group, Route, Router
from nexios.testclient import TestClient

# ========== Basic Group Tests ==========


def test_group_initialization():
    """Test basic group initialization"""
    router = Router()

    @router.get("/users")
    async def list_users(request: Request, response: Response):
        return response.json({"users": []})

    group = Group(path="/api", app=router)

    assert group.path == "/api"
    assert group._base_app == router


def test_group_with_routes():
    """Test group initialization with routes"""

    async def handler1(request: Request, response: Response):
        return response.text("route1")

    async def handler2(request: Request, response: Response):
        return response.text("route2")

    route1 = Route("/route1", handler1, methods=["GET"])
    route2 = Route("/route2", handler2, methods=["GET"])

    group = Group(path="/api", routes=[route1, route2])

    assert len(group.routes) >= 2


def test_group_with_name():
    """Test group with name"""
    router = Router()
    group = Group(path="/api", app=router, name="api-group")

    assert group.name == "api-group"


# ========== Group Mounting Tests ==========


def test_group_mounted_to_app(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test group mounted to application"""
    app = NexiosApp()
    router = Router()

    @router.get("/users")
    async def get_users(request: Request, response: Response):
        return response.json({"users": ["Alice", "Bob"]})

    @router.get("/posts")
    async def get_posts(request: Request, response: Response):
        return response.json({"posts": ["Post 1", "Post 2"]})

    group = Group(path="/api/v1", app=router)
    app.add_route(group)

    with test_client_factory(app) as client:
        users_resp = client.get("/api/v1/users")
        assert users_resp.status_code == 200
        assert users_resp.json() == {"users": ["Alice", "Bob"]}

        posts_resp = client.get("/api/v1/posts")
        assert posts_resp.status_code == 200
        assert posts_resp.json() == {"posts": ["Post 1", "Post 2"]}


def test_multiple_groups(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test multiple groups mounted to app"""
    app = NexiosApp()

    # API v1 group
    v1_router = Router()

    @v1_router.get("/status")
    async def v1_status(request: Request, response: Response):
        return response.json({"version": "1.0"})

    v1_group = Group(path="/api/v1", app=v1_router)

    # API v2 group
    v2_router = Router()

    @v2_router.get("/status")
    async def v2_status(request: Request, response: Response):
        return response.json({"version": "2.0"})

    v2_group = Group(path="/api/v2", app=v2_router)

    app.add_route(v1_group)
    app.add_route(v2_group)

    with test_client_factory(app) as client:
        v1_resp = client.get("/api/v1/status")
        assert v1_resp.json()["version"] == "1.0"

        v2_resp = client.get("/api/v2/status")
        assert v2_resp.json()["version"] == "2.0"


# ========== Nested Groups Tests ==========


def test_nested_groups(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test nested group structure"""
    app = NexiosApp()

    # Inner router
    users_router = Router()

    @users_router.get("/list")
    async def list_users(request: Request, response: Response):
        return response.json({"users": []})

    @users_router.get("/{user_id}")
    async def get_user(request: Request, response: Response, user_id: str):
        return response.json({"user_id": user_id})

    # Outer group
    api_router = Router()
    users_group = Group(path="/users", app=users_router)
    api_router.add_route(users_group)

    main_group = Group(path="/api", app=api_router)
    app.add_route(main_group)

    with test_client_factory(app) as client:
        list_resp = client.get("/api/users/list")
        assert list_resp.status_code == 200
        assert list_resp.json() == {"users": []}

        user_resp = client.get("/api/users/123")
        assert user_resp.status_code == 200
        assert user_resp.json()["user_id"] == "123"


def test_deeply_nested_groups(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test deeply nested group structure"""
    app = NexiosApp()

    # Deepest level
    endpoint_router = Router()

    @endpoint_router.get("/data")
    async def get_data(request: Request, response: Response):
        return response.json({"data": "deep"})

    # Build nested structure
    level3 = Group(path="/resources", app=endpoint_router)

    level2_router = Router()
    level2_router.add_route(level3)
    level2 = Group(path="/v1", app=level2_router)

    level1_router = Router()
    level1_router.add_route(level2)
    level1 = Group(path="/api", app=level1_router)

    app.add_route(level1)

    with test_client_factory(app) as client:
        resp = client.get("/api/v1/resources/data")
        assert resp.status_code == 200
        assert resp.json()["data"] == "deep"


# ========== Group with Path Parameters Tests ==========


def test_group_route_isolation(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test that routes in different groups are isolated"""
    app = NexiosApp()

    # Group 1
    admin_router = Router()

    @admin_router.get("/dashboard")
    async def admin_dashboard(request: Request, response: Response):
        return response.json({"area": "admin"})

    admin_group = Group(path="/admin", app=admin_router)

    # Group 2
    user_router = Router()

    @user_router.get("/dashboard")
    async def user_dashboard(request: Request, response: Response):
        return response.json({"area": "user"})

    user_group = Group(path="/user", app=user_router)

    app.add_route(admin_group)
    app.add_route(user_group)

    with test_client_factory(app) as client:
        admin_resp = client.get("/admin/dashboard")
        assert admin_resp.json()["area"] == "admin"

        user_resp = client.get("/user/dashboard")
        assert user_resp.json()["area"] == "user"


# ========== Group with Empty Path Tests ==========


def test_group_with_empty_path(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test group with empty path"""
    app = NexiosApp()
    router = Router()

    @router.get("/test")
    async def test_route(request: Request, response: Response):
        return response.json({"test": "ok"})

    group = Group(path="", app=router)
    app.add_route(group)

    with test_client_factory(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json()["test"] == "ok"


# ========== Group Organization Tests ==========


def test_organized_api_structure(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test well-organized API structure using groups"""
    app = NexiosApp()

    # Users module
    users_router = Router()

    @users_router.get("/")
    async def list_users(request: Request, response: Response):
        return response.json({"users": []})

    @users_router.post("/")
    async def create_user(request: Request, response: Response):
        return response.json({"created": True})

    # Products module
    products_router = Router()

    @products_router.get("/")
    async def list_products(request: Request, response: Response):
        return response.json({"products": []})

    @products_router.post("/")
    async def create_product(request: Request, response: Response):
        return response.json({"created": True})

    # Create groups
    users_group = Group(path="/users", app=users_router)
    products_group = Group(path="/products", app=products_router)

    # API v1 container
    api_v1_router = Router()
    api_v1_router.add_route(users_group)
    api_v1_router.add_route(products_group)

    api_v1_group = Group(path="/api/v1", app=api_v1_router)
    app.add_route(api_v1_group)

    with test_client_factory(app) as client:
        users_resp = client.get("/api/v1/users/")
        assert users_resp.status_code == 200
        assert "users" in users_resp.json()

        products_resp = client.get("/api/v1/products/")
        assert products_resp.status_code == 200
        assert "products" in products_resp.json()


def test_group_with_different_http_methods(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test group containing routes with different HTTP methods"""
    app = NexiosApp()
    router = Router()

    @router.get("/items")
    async def get_items(request: Request, response: Response):
        return response.json({"method": "GET"})

    @router.post("/items")
    async def create_item(request: Request, response: Response):
        return response.json({"method": "POST"})

    @router.put("/items/{item_id}")
    async def update_item(request: Request, response: Response, item_id: str):
        return response.json({"method": "PUT", "item_id": item_id})

    @router.delete("/items/{item_id}")
    async def delete_item(request: Request, response: Response, item_id: str):
        return response.json({"method": "DELETE", "item_id": item_id})

    group = Group(path="/api", app=router)
    app.add_route(group)

    with test_client_factory(app) as client:
        assert client.get("/api/items").json()["method"] == "GET"
        assert client.post("/api/items").json()["method"] == "POST"
        assert client.put("/api/items/123").json()["method"] == "PUT"
        assert client.delete("/api/items/456").json()["method"] == "DELETE"
