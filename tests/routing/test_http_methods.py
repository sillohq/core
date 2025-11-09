"""
Tests for HTTP methods routing (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.routing import Route, Router
from nexios.testclient import TestClient

# ========== GET Method Tests ==========


def test_get_method(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test GET method routing"""
    app = NexiosApp()

    @app.get("/items")
    async def get_items(request: Request, response: Response):
        return response.json({"items": ["item1", "item2"]})

    with test_client_factory(app) as client:
        resp = client.get("/items")
        assert resp.status_code == 200
        assert resp.json() == {"items": ["item1", "item2"]}


def test_get_with_router(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test GET method on router"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.get("/products")
    async def get_products(request: Request, response: Response):
        return response.json({"products": []})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/products")
        assert resp.status_code == 200
        assert resp.json() == {"products": []}


# ========== POST Method Tests ==========


def test_post_method(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test POST method routing"""
    app = NexiosApp()

    @app.post("/items")
    async def create_item(request: Request, response: Response):
        data = await request.json
        return response.json({"created": data}, status_code=201)

    with test_client_factory(app) as client:
        resp = client.post("/items", json={"name": "test"})
        assert resp.status_code == 201
        assert resp.json() == {"created": {"name": "test"}}


def test_post_with_router(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test POST method on router"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.post("/users")
    async def create_user(request: Request, response: Response):
        data = await request.json
        return response.json({"user": data, "id": 123})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.post("/api/users", json={"username": "alice"})
        assert resp.status_code == 200
        assert resp.json()["user"]["username"] == "alice"


# ========== PUT Method Tests ==========


def test_put_method(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test PUT method routing"""
    app = NexiosApp()

    @app.put("/items/{item_id}")
    async def update_item(request: Request, response: Response, item_id: str):
        data = await request.json
        return response.json({"id": item_id, "updated": data})

    with test_client_factory(app) as client:
        resp = client.put("/items/123", json={"name": "updated"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "123"
        assert resp.json()["updated"]["name"] == "updated"


def test_put_with_router(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test PUT method on router"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.put("/products/{product_id}")
    async def update_product(request: Request, response: Response, product_id: str):
        return response.json({"product_id": product_id, "status": "updated"})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.put("/api/products/456")
        assert resp.status_code == 200
        assert resp.json()["product_id"] == "456"


# ========== DELETE Method Tests ==========


def test_delete_method(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test DELETE method routing"""
    app = NexiosApp()

    @app.delete("/items/{item_id}")
    async def delete_item(request: Request, response: Response, item_id: str):
        return response.json({"deleted": item_id})

    with test_client_factory(app) as client:
        resp = client.delete("/items/789")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "789"


def test_delete_with_router(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test DELETE method on router"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.delete("/users/{user_id}")
    async def delete_user(request: Request, response: Response, user_id: str):
        return response.json({"message": f"User {user_id} deleted"})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.delete("/api/users/999")
        assert resp.status_code == 200
        assert "999" in resp.json()["message"]


# ========== PATCH Method Tests ==========


def test_patch_method(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test PATCH method routing"""
    app = NexiosApp()

    @app.patch("/items/{item_id}")
    async def patch_item(request: Request, response: Response, item_id: str):
        data = await request.json
        return response.json({"id": item_id, "patched": data})

    with test_client_factory(app) as client:
        resp = client.patch("/items/111", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "111"
        assert resp.json()["patched"]["status"] == "active"


def test_patch_with_router(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test PATCH method on router"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.patch("/settings")
    async def patch_settings(request: Request, response: Response):
        data = await request.json
        return response.json({"settings": data})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.patch("/api/settings", json={"theme": "dark"})
        assert resp.status_code == 200
        assert resp.json()["settings"]["theme"] == "dark"


# ========== HEAD Method Tests ==========


def test_head_method(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test HEAD method routing"""
    app = NexiosApp()

    @app.head("/items")
    async def head_items(request: Request, response: Response):
        return response.status(200)

    with test_client_factory(app) as client:
        resp = client.head("/items")
        assert resp.status_code == 200
        assert resp.text == ""


def test_head_with_router(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test HEAD method on router"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.head("/status")
    async def head_status(request: Request, response: Response):
        return response.status(200)

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.head("/api/status")
        assert resp.status_code == 200


# ========== OPTIONS Method Tests ==========


def test_options_method(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test OPTIONS method routing"""
    app = NexiosApp()

    @app.options("/items")
    async def options_items(request: Request, response: Response):
        return response.status(200)

    with test_client_factory(app) as client:
        resp = client.options("/items")
        assert resp.status_code == 200


def test_options_with_router(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test OPTIONS method on router"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.options("/resources")
    async def options_resources(request: Request, response: Response):
        return response.status(200)

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.options("/api/resources")
        assert resp.status_code == 200


# ========== Multiple Methods Tests ==========


def test_route_with_multiple_methods(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test route supporting multiple HTTP methods"""
    app = NexiosApp()

    @app.route("/resource", methods=["GET", "POST", "PUT"])
    async def handle_resource(request: Request, response: Response):
        method = request.method
        return response.json({"method": method})

    with test_client_factory(app) as client:
        get_resp = client.get("/resource")
        assert get_resp.json()["method"] == "GET"

        post_resp = client.post("/resource")
        assert post_resp.json()["method"] == "POST"

        put_resp = client.put("/resource")
        assert put_resp.json()["method"] == "PUT"


def test_routes_class_with_multiple_methods(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test Route class with multiple methods"""
    app = NexiosApp()

    async def handler(request: Request, response: Response):
        return response.json({"method": request.method})

    route = Route("/api/data", handler, methods=["GET", "POST", "DELETE"])
    app.add_route(route)

    with test_client_factory(app) as client:
        get_resp = client.get("/api/data")
        assert get_resp.status_code == 200
        assert get_resp.json()["method"] == "GET"

        post_resp = client.post("/api/data")
        assert post_resp.status_code == 200
        assert post_resp.json()["method"] == "POST"

        delete_resp = client.delete("/api/data")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["method"] == "DELETE"


def test_method_not_allowed(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test that non-allowed methods return appropriate error"""
    app = NexiosApp()

    @app.get("/only-get")
    async def only_get(request: Request, response: Response):
        return response.text("GET only")

    with test_client_factory(app) as client:
        get_resp = client.get("/only-get")
        assert get_resp.status_code == 200

        # POST should not be allowed
        post_resp = client.post("/only-get")
        assert post_resp.status_code != 200


# ========== Router Method Decorators Tests ==========


def test_all_router_method_decorators(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test all HTTP method decorators on router"""
    app = NexiosApp()
    router = Router(prefix="/api")

    @router.get("/get")
    async def get_handler(request: Request, response: Response):
        return response.text("GET")

    @router.post("/post")
    async def post_handler(request: Request, response: Response):
        return response.text("POST")

    @router.put("/put")
    async def put_handler(request: Request, response: Response):
        return response.text("PUT")

    @router.delete("/delete")
    async def delete_handler(request: Request, response: Response):
        return response.text("DELETE")

    @router.patch("/patch")
    async def patch_handler(request: Request, response: Response):
        return response.text("PATCH")

    @router.head("/head")
    async def head_handler(request: Request, response: Response):
        return response.status(200)

    @router.options("/options")
    async def options_handler(request: Request, response: Response):
        return response.status(200)

    app.mount_router(router)

    with test_client_factory(app) as client:
        assert client.get("/api/get").text == "GET"
        assert client.post("/api/post").text == "POST"
        assert client.put("/api/put").text == "PUT"
        assert client.delete("/api/delete").text == "DELETE"
        assert client.patch("/api/patch").text == "PATCH"
        assert client.head("/api/head").status_code == 200
        assert client.options("/api/options").status_code == 200


def test_case_insensitive_methods(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test that HTTP methods are case-insensitive"""
    app = NexiosApp()

    async def handler(request: Request, response: Response):
        return response.text("ok")

    # Test with lowercase methods
    route = Route("/test", handler, methods=["get", "post"])
    app.add_route(route)

    with test_client_factory(app) as client:
        get_resp = client.get("/test")
        assert get_resp.status_code == 200

        post_resp = client.post("/test")
        assert post_resp.status_code == 200
