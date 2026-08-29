"""
Tests for HTTP methods routing (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import empty
from sillo import json, text
from sillo.core.http import HttpContext
from sillo.core.routing import Route, Router
from sillo.core.routing._utils import MatchStatus
from sillo.testclient import TestClient


async def send_request(router: Router, method: str, path: str):
    """Drive *router* with one ASGI request, returning (status, headers).

    A raw scope rather than the test client, because the cases here turn on
    the exact method token — a client is free to normalise it.
    """
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
    }
    await router(scope, receive, send)

    start = next(
        message for message in sent if message["type"] == "http.response.start"
    )
    headers = {
        key.decode().lower(): value.decode() for key, value in start.get("headers", [])
    }
    return start["status"], headers

# ========== GET Method Tests ==========


def test_get_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test GET method routing"""
    app = SilloApp()

    @app.get("/items")
    async def get_items(request: HttpContext):
        return json({"items": ["item1", "item2"]})

    with test_client_factory(app) as client:
        resp = client.get("/items")
        assert resp.status_code == 200
        assert resp.json() == {"items": ["item1", "item2"]}


def test_get_with_router(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test GET method on router"""
    app = SilloApp()
    router = Router(prefix="/api")

    @router.get("/products")
    async def get_products(request: HttpContext):
        return json({"products": []})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/products")
        assert resp.status_code == 200
        assert resp.json() == {"products": []}


# ========== POST Method Tests ==========


def test_post_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test POST method routing"""
    app = SilloApp()

    @app.post("/items")
    async def create_item(request: HttpContext):
        data = await request.json
        return json({"created": data}, status_code=201)

    with test_client_factory(app) as client:
        resp = client.post("/items", json={"name": "test"})
        assert resp.status_code == 201
        assert resp.json() == {"created": {"name": "test"}}


def test_post_with_router(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test POST method on router"""
    app = SilloApp()
    router = Router(prefix="/api")

    @router.post("/users")
    async def create_user(request: HttpContext):
        data = await request.json
        return json({"user": data, "id": 123})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.post("/api/users", json={"username": "alice"})
        assert resp.status_code == 200
        assert resp.json()["user"]["username"] == "alice"


# ========== PUT Method Tests ==========


def test_put_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test PUT method routing"""
    app = SilloApp()

    @app.put("/items/{item_id}")
    async def update_item(request: HttpContext, item_id: str):
        data = await request.json
        return json({"id": item_id, "updated": data})

    with test_client_factory(app) as client:
        resp = client.put("/items/123", json={"name": "updated"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "123"
        assert resp.json()["updated"]["name"] == "updated"


def test_put_with_router(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test PUT method on router"""
    app = SilloApp()
    router = Router(prefix="/api")

    @router.put("/products/{product_id}")
    async def update_product(request: HttpContext, product_id: str):
        return json({"product_id": product_id, "status": "updated"})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.put("/api/products/456")
        assert resp.status_code == 200
        assert resp.json()["product_id"] == "456"


# ========== DELETE Method Tests ==========


def test_delete_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test DELETE method routing"""
    app = SilloApp()

    @app.delete("/items/{item_id}")
    async def delete_item(request: HttpContext, item_id: str):
        return json({"deleted": item_id})

    with test_client_factory(app) as client:
        resp = client.delete("/items/789")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "789"


def test_delete_with_router(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test DELETE method on router"""
    app = SilloApp()
    router = Router(prefix="/api")

    @router.delete("/users/{user_id}")
    async def delete_user(request: HttpContext, user_id: str):
        return json({"message": f"User {user_id} deleted"})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.delete("/api/users/999")
        assert resp.status_code == 200
        assert "999" in resp.json()["message"]


# ========== PATCH Method Tests ==========


def test_patch_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test PATCH method routing"""
    app = SilloApp()

    @app.patch("/items/{item_id}")
    async def patch_item(request: HttpContext, item_id: str):
        data = await request.json
        return json({"id": item_id, "patched": data})

    with test_client_factory(app) as client:
        resp = client.patch("/items/111", json={"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "111"
        assert resp.json()["patched"]["status"] == "active"


def test_patch_with_router(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test PATCH method on router"""
    app = SilloApp()
    router = Router(prefix="/api")

    @router.patch("/settings")
    async def patch_settings(request: HttpContext):
        data = await request.json
        return json({"settings": data})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.patch("/api/settings", json={"theme": "dark"})
        assert resp.status_code == 200
        assert resp.json()["settings"]["theme"] == "dark"


# ========== HEAD Method Tests ==========


def test_head_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test HEAD method routing"""
    app = SilloApp()

    @app.head("/items")
    async def head_items(request: HttpContext):
        return empty(200)

    with test_client_factory(app) as client:
        resp = client.head("/items")
        assert resp.status_code == 200
        assert resp.text == ""


def test_head_with_router(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test HEAD method on router"""
    app = SilloApp()
    router = Router(prefix="/api")

    @router.head("/status")
    async def head_status(request: HttpContext):
        return empty(200)

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.head("/api/status")
        assert resp.status_code == 200


# ========== OPTIONS Method Tests ==========


def test_options_method(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test OPTIONS method routing"""
    app = SilloApp()

    @app.options("/items")
    async def options_items(request: HttpContext):
        return empty(200)

    with test_client_factory(app) as client:
        resp = client.options("/items")
        assert resp.status_code == 200


def test_options_with_router(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test OPTIONS method on router"""
    app = SilloApp()
    router = Router(prefix="/api")

    @router.options("/resources")
    async def options_resources(request: HttpContext):
        return empty(200)

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.options("/api/resources")
        assert resp.status_code == 200


# ========== Multiple Methods Tests ==========


def test_route_with_multiple_methods(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test route supporting multiple HTTP methods"""
    app = SilloApp()

    @app.route("/resource", methods=["GET", "POST", "PUT"])
    async def handle_resource(request: HttpContext):
        method = request.method
        return json({"method": method})

    with test_client_factory(app) as client:
        get_resp = client.get("/resource")
        assert get_resp.json()["method"] == "GET"

        post_resp = client.post("/resource")
        assert post_resp.json()["method"] == "POST"

        put_resp = client.put("/resource")
        assert put_resp.json()["method"] == "PUT"


def test_routes_class_with_multiple_methods(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test Route class with multiple methods"""
    app = SilloApp()

    async def handler(request: HttpContext):
        return json({"method": request.method})

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


def test_method_not_allowed(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test that non-allowed methods return appropriate error"""
    app = SilloApp()

    @app.get("/only-get")
    async def only_get(request: HttpContext):
        return text("GET only")

    with test_client_factory(app) as client:
        get_resp = client.get("/only-get")
        assert get_resp.status_code == 200

        # POST should not be allowed
        post_resp = client.post("/only-get")
        assert post_resp.status_code != 200


def test_405_does_not_corrupt_the_route(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """A 405 must be a per-request response, not a replacement of the route.

    ``Route.handle`` used to assign ``self.app = JSONResponse(...)`` on the
    first disallowed method, permanently replacing the handler and its
    middleware chain: every later request, even with an allowed method,
    would then receive 405.
    """
    app = SilloApp()

    @app.get("/only-get")
    async def only_get(request: HttpContext):
        return text("GET only")

    with test_client_factory(app) as client:
        post_resp = client.post("/only-get")
        assert post_resp.status_code == 405
        assert post_resp.json() == {"detail": "Method Not Allowed"}

        get_resp = client.get("/only-get")
        assert get_resp.status_code == 200
        assert get_resp.text == "GET only"


async def test_405_route_params_come_from_the_partial_match():
    """The 405 path must carry the first partial match's params.

    The dispatch loop kept ``matched_params`` from the *last* route
    iteration and handed it to the first partial match, so ``route_params``
    on the scope could be empty or belong to an unrelated route.
    """
    router = Router()

    async def alpha_handler(request: HttpContext, x: str):
        return text(x)

    async def beta_handler(request: HttpContext):
        return text("beta")

    router.add_route(Route("/alpha/{x}", alpha_handler, methods=["GET"]))
    router.add_route(Route("/beta", beta_handler, methods=["GET"]))

    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/alpha/42",
        "raw_path": b"/alpha/42",
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
    }

    await router(scope, receive, send)

    status = next(
        message["status"]
        for message in sent
        if message["type"] == "http.response.start"
    )
    assert status == 405
    assert dict(scope["route_params"]) == {"x": "42"}  # ty: ignore[no-matching-overload]


async def test_the_method_is_decided_once():
    """``match`` decides; ``handle`` does not decide again.

    The check lived in both places, and the two disagreed: ``match`` compared
    ``method.upper()`` against the route's methods while ``handle`` compared
    the method as sent. A lowercase method therefore matched fully and was
    then refused 405 by the route it had just matched.
    """
    router = Router()

    async def handler(request: HttpContext):
        return text("ok")

    route = Route("/only-get", handler, methods=["GET"])
    router.add_route(route)

    # The method token is case-sensitive (RFC 9110 section 9.1), so "get" is
    # not GET. Both halves must reach that same conclusion.
    assert route.match({"type": "http", "method": "get", "path": "/only-get"})[0] is (
        MatchStatus.PARTIAL
    )
    assert route.match({"type": "http", "method": "GET", "path": "/only-get"})[0] is (
        MatchStatus.FULL
    )

    status, _ = await send_request(router, "get", "/only-get")
    assert status == 405


async def test_handle_does_not_re_check_the_method():
    """A full match reaches the handler without a second lookup.

    ``handle`` is only ever called after ``match`` returned FULL, so a method
    check there could only ever be a no-op — except when it disagreed.
    """
    async def handler(request: HttpContext):
        return text("reached")

    route = Route("/x", handler, methods=["GET"])

    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    # A method the route does not allow, handed straight to handle(). The
    # router never does this; the point is that handle() no longer owns the
    # decision, so it runs the handler it was given.
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "raw_path": b"/x",
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "route_params": {},
    }
    await route.handle(scope, receive, send)

    status = next(
        message["status"]
        for message in sent
        if message["type"] == "http.response.start"
    )
    assert status == 200


async def test_allow_names_every_method_the_path_supports():
    """RFC 9110: ``Allow`` describes the resource, not the matched route.

    One path is routinely split across several Route objects — ``@app.get``
    and ``@app.post`` on the same path build two. The router kept only the
    first partial match and asked it for the header, so the other methods
    went unnamed and a client was told the resource supports less than it
    does.
    """
    router = Router()

    async def handler(request: HttpContext):
        return text("ok")

    router.add_route(Route("/items", handler, methods=["GET"]))
    router.add_route(Route("/items", handler, methods=["POST"]))
    router.add_route(Route("/items", handler, methods=["PATCH"]))

    status, headers = await send_request(router, "DELETE", "/items")

    assert status == 405
    # HEAD comes along with GET, which the route adds for itself.
    assert headers["allow"] == "GET, HEAD, PATCH, POST"


async def test_allow_is_unchanged_for_a_single_route():
    """The common case keeps the header it already had."""
    router = Router()

    async def handler(request: HttpContext):
        return text("ok")

    router.add_route(Route("/only-get", handler, methods=["GET"]))

    status, headers = await send_request(router, "POST", "/only-get")

    assert status == 405
    assert headers["allow"] == "GET, HEAD"


async def test_allow_does_not_repeat_a_method():
    """Two routes offering the same method name it once."""
    router = Router()

    async def handler(request: HttpContext):
        return text("ok")

    router.add_route(Route("/items", handler, methods=["GET"]))
    router.add_route(Route("/items", handler, methods=["GET", "PUT"]))

    status, headers = await send_request(router, "DELETE", "/items")

    assert status == 405
    assert headers["allow"] == "GET, HEAD, PUT"


async def test_allow_only_counts_routes_whose_path_matched():
    """A method on a different path is not this resource's to offer."""
    router = Router()

    async def handler(request: HttpContext):
        return text("ok")

    router.add_route(Route("/items", handler, methods=["GET"]))
    router.add_route(Route("/other", handler, methods=["DELETE"]))

    status, headers = await send_request(router, "POST", "/items")

    assert status == 405
    assert "DELETE" not in headers["allow"]


async def test_allow_spans_routes_with_the_same_path_parameters():
    """Parameterised paths are collected the same way."""
    router = Router()

    async def handler(request: HttpContext, item_id: str):
        return text(item_id)

    router.add_route(Route("/items/{item_id}", handler, methods=["GET"]))
    router.add_route(Route("/items/{item_id}", handler, methods=["DELETE"]))

    status, headers = await send_request(router, "POST", "/items/42")

    assert status == 405
    assert headers["allow"] == "DELETE, GET, HEAD"


# ========== Router Method Decorators Tests ==========


def test_all_router_method_decorators(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test all HTTP method decorators on router"""
    app = SilloApp()
    router = Router(prefix="/api")

    @router.get("/get")
    async def get_handler(request: HttpContext):
        return text("GET")

    @router.post("/post")
    async def post_handler(request: HttpContext):
        return text("POST")

    @router.put("/put")
    async def put_handler(request: HttpContext):
        return text("PUT")

    @router.delete("/delete")
    async def delete_handler(request: HttpContext):
        return text("DELETE")

    @router.patch("/patch")
    async def patch_handler(request: HttpContext):
        return text("PATCH")

    @router.head("/head")
    async def head_handler(request: HttpContext):
        return empty(200)

    @router.options("/options")
    async def options_handler(request: HttpContext):
        return empty(200)

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test that HTTP methods are case-insensitive"""
    app = SilloApp()

    async def handler(request: HttpContext):
        return text("ok")

    # Test with lowercase methods
    route = Route("/test", handler, methods=["get", "post"])
    app.add_route(route)

    with test_client_factory(app) as client:
        get_resp = client.get("/test")
        assert get_resp.status_code == 200

        post_resp = client.post("/test")
        assert post_resp.status_code == 200
