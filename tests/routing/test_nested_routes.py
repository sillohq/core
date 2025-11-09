"""
Tests for nested routes and router mounting
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.routing import Route, Router
from nexios.testclient import TestClient

# ========== Basic Router Mounting Tests ==========


def test_mount_router_basic(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test basic router mounting"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.get("/hello")
    async def hello(request: Request, response: Response):
        return response.text("Hello from router")

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/hello")
        assert resp.status_code == 200
        assert resp.text == "Hello from router"


def test_mount_router_without_path(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test mounting router without explicit path"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.get("/status")
    async def status(request: Request, response: Response):
        return response.json({"status": "ok"})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_mount_multiple_routers(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test mounting multiple routers"""
    app = NexiosApp()

    users_router = Router(prefix="/users")

    @users_router.get("/list")
    async def list_users(request: Request, response: Response):
        return response.json({"users": []})

    products_router = Router(prefix="/products")

    @products_router.get("/list")
    async def list_products(request: Request, response: Response):
        return response.json({"products": []})

    app.mount_router(users_router)
    app.mount_router(products_router)

    with test_client_factory(app) as client:
        users_resp = client.get("/users/list")
        assert "users" in users_resp.json()

        products_resp = client.get("/products/list")
        assert "products" in products_resp.json()


# ========== Nested Router Tests ==========


def test_nested_routers(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test nested router structure"""
    app = NexiosApp()

    # Inner router
    inner_router = Router(prefix="/inner")

    @inner_router.get("/data")
    async def get_data(request: Request, response: Response):
        return response.json({"data": "nested"})

    # Middle router
    middle_router = Router(prefix="/api")
    middle_router.mount_router(inner_router)

    # Mount to app
    app.mount_router(middle_router)

    with test_client_factory(app) as client:
        resp = client.get("/api/inner/data")
        assert resp.status_code == 200
        assert resp.json()["data"] == "nested"


def test_deeply_nested_routers(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test deeply nested router structure"""
    app = NexiosApp()

    # Level 3 (deepest)
    level3_router = Router(prefix="/level3")

    @level3_router.get("/endpoint")
    async def endpoint(request: Request, response: Response):
        return response.json({"level": 3})

    # Level 2
    level2_router = Router(prefix="/level2")
    level2_router.mount_router(level3_router)

    # Level 1
    level1_router = Router(prefix="/level1")
    level1_router.mount_router(level2_router)

    # Mount to app
    app.mount_router(level1_router)

    with test_client_factory(app) as client:
        resp = client.get("/level1/level2/level3/endpoint")
        assert resp.status_code == 200
        assert resp.json()["level"] == 3


# ========== Router with Prefix Tests ==========


def test_router_prefix_basic(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test router with prefix"""
    app = NexiosApp()
    router = Router(prefix="/api/v1")

    @router.get("/users")
    async def get_users(request: Request, response: Response):
        return response.json({"users": []})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        assert "users" in resp.json()


# ========== Sub-application Mounting Tests ==========


def test_mount_sub_application(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test mounting a sub-application"""
    main_app = NexiosApp()
    sub_app = NexiosApp()

    @sub_app.get("/hello")
    async def sub_hello(request: Request, response: Response):
        return response.text("Hello from sub-app")

    main_app.register(sub_app, "/sub")

    with test_client_factory(main_app) as client:
        resp = client.get("/sub/hello")
        assert resp.status_code == 200
        assert resp.text == "Hello from sub-app"


def test_multiple_sub_applications(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test mounting multiple sub-applications"""
    main_app = NexiosApp()

    admin_app = NexiosApp()

    @admin_app.get("/dashboard")
    async def admin_dashboard(request: Request, response: Response):
        return response.json({"area": "admin"})

    user_app = NexiosApp()

    @user_app.get("/dashboard")
    async def user_dashboard(request: Request, response: Response):
        return response.json({"area": "user"})

    main_app.register(admin_app, "/admin")
    main_app.register(user_app, "/user")

    with test_client_factory(main_app) as client:
        admin_resp = client.get("/admin/dashboard")
        assert admin_resp.json()["area"] == "admin"

        user_resp = client.get("/user/dashboard")
        assert user_resp.json()["area"] == "user"


# ========== Router Isolation Tests ==========


def test_router_isolation(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test that routers are properly isolated"""
    app = NexiosApp()

    router1 = Router(prefix="/r1")

    @router1.get("/test")
    async def test1(request: Request, response: Response):
        return response.json({"router": 1})

    router2 = Router(prefix="/r2")

    @router2.get("/test")
    async def test2(request: Request, response: Response):
        return response.json({"router": 2})

    app.mount_router(router1)
    app.mount_router(router2)

    with test_client_factory(app) as client:
        r1_resp = client.get("/r1/test")
        assert r1_resp.json()["router"] == 1

        r2_resp = client.get("/r2/test")
        assert r2_resp.json()["router"] == 2


def test_nested_router_route_priority(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route priority in nested routers"""
    app = NexiosApp()

    specific_router = Router(prefix="/items")

    @specific_router.get("/specific")
    async def specific_route(request: Request, response: Response):
        return response.json({"type": "specific"})

    general_router = Router(prefix="/api")

    @general_router.get("/{resource}")
    async def general_route(request: Request, response: Response, resource: str):
        return response.json({"type": "general", "resource": resource})

    general_router.mount_router(specific_router)
    app.mount_router(general_router)

    with test_client_factory(app) as client:
        specific_resp = client.get("/api/items/specific")
        assert specific_resp.status_code == 200

        general_resp = client.get("/api/other")
        assert general_resp.status_code == 200
