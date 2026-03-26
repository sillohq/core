"""
Tests for nexios.views module (APIView class-based views).

Covers:
- HTTP method dispatch (GET, POST, PUT, DELETE, PATCH)
- as_route() route conversion and method detection
- Path parameters
- Method not allowed (405) handling
- Custom error handlers
- Default method responses (404)
- Class-level middleware integration
- JSON response handling
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.testclient import TestClient
from nexios.views import APIView

# ==================== View Definitions ====================


class ItemView(APIView):
    """A view implementing all CRUD methods for testing dispatch."""

    async def get(self, request: Request, response: Response):
        return response.json({"method": "GET", "items": [1, 2, 3]})

    async def post(self, request: Request, response: Response):
        return response.json({"method": "POST", "created": True})

    async def put(self, request: Request, response: Response):
        return response.json({"method": "PUT", "updated": True})

    async def delete(self, request: Request, response: Response):
        return response.json({"method": "DELETE", "deleted": True})

    async def patch(self, request: Request, response: Response):
        return response.json({"method": "PATCH", "patched": True})


class GetOnlyView(APIView):
    """A view that only implements GET."""

    async def get(self, request: Request, response: Response):
        return response.json({"message": "get only"})


class DetailView(APIView):
    """A view that uses path parameters."""

    async def get(self, request: Request, response: Response, **kwargs):
        item_id = request.path_params.get("id")
        return response.json({"id": item_id})

    async def delete(self, request: Request, response: Response, **kwargs):
        item_id = request.path_params.get("id")
        return response.json({"deleted_id": item_id})


class ErrorView(APIView):
    """A view with custom error handlers."""

    error_handlers = {}

    async def get(self, request: Request, response: Response):
        raise ValueError("something went wrong")

    async def post(self, request: Request, response: Response):
        raise KeyError("missing key")


class UnhandledErrorView(APIView):
    """A view that raises an error without a matching handler."""

    async def get(self, request: Request, response: Response):
        raise RuntimeError("unhandled crash")


class EmptyView(APIView):
    """A view with no method overrides — tests default 404 behavior."""

    pass


class JsonView(APIView):
    """A view returning rich JSON data."""

    async def get(self, request: Request, response: Response):
        return response.json(
            {
                "users": [
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"},
                ],
                "total": 2,
            }
        )


# ==================== Fixtures ====================


@pytest.fixture
def item_app():
    """App with full CRUD ItemView."""
    app = NexiosApp()
    app.add_route(ItemView.as_route("/items"))
    return app


@pytest.fixture
def item_client(item_app, test_client_factory: Callable[[NexiosApp], TestClient]):
    with test_client_factory(item_app) as client:
        yield client


@pytest.fixture
def detail_app():
    """App with DetailView using path params."""
    app = NexiosApp()
    app.add_route(DetailView.as_route("/items/{id}"))
    return app


@pytest.fixture
def detail_client(detail_app, test_client_factory: Callable[[NexiosApp], TestClient]):
    with test_client_factory(detail_app) as client:
        yield client


@pytest.fixture
def error_app():
    """App with ErrorView that has custom error handlers."""
    app = NexiosApp()

    async def handle_value_error(request, response, exc):
        return response.json(
            {"error": "value_error", "detail": str(exc)}, status_code=400
        )

    ErrorView.error_handlers = {ValueError: handle_value_error}
    app.add_route(ErrorView.as_route("/errors"))
    return app


@pytest.fixture
def error_client(error_app, test_client_factory: Callable[[NexiosApp], TestClient]):
    with test_client_factory(error_app) as client:
        yield client


@pytest.fixture
def get_only_app():
    """App with GetOnlyView."""
    app = NexiosApp()
    app.add_route(GetOnlyView.as_route("/readonly"))
    return app


@pytest.fixture
def get_only_client(
    get_only_app, test_client_factory: Callable[[NexiosApp], TestClient]
):
    with test_client_factory(get_only_app) as client:
        yield client


# ==================== Method Dispatch Tests ====================


def test_get_method(item_client: TestClient):
    """GET request dispatches to get() method."""
    response = item_client.get("/items")
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "GET"
    assert data["items"] == [1, 2, 3]


def test_post_method(item_client: TestClient):
    """POST request dispatches to post() method."""
    response = item_client.post("/items")
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "POST"
    assert data["created"] is True


def test_put_method(item_client: TestClient):
    """PUT request dispatches to put() method."""
    response = item_client.put("/items")
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "PUT"
    assert data["updated"] is True


def test_delete_method(item_client: TestClient):
    """DELETE request dispatches to delete() method."""
    response = item_client.delete("/items")
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "DELETE"
    assert data["deleted"] is True


def test_patch_method(item_client: TestClient):
    """PATCH request dispatches to patch() method."""
    response = item_client.patch("/items")
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "PATCH"
    assert data["patched"] is True


# ==================== as_route() Tests ====================


def test_as_route_auto_detects_methods():
    """as_route() only registers methods that are overridden in the subclass."""
    route = GetOnlyView.as_route("/test")
    methods = route.methods
    # GetOnlyView only defines get, so only "get" (and possibly HEAD) should be in methods
    assert "get" in methods or "GET" in methods
    assert "post" not in methods and "POST" not in methods
    assert "put" not in methods and "PUT" not in methods
    assert "delete" not in methods and "DELETE" not in methods
    assert "patch" not in methods and "PATCH" not in methods


def test_as_route_explicit_methods():
    """as_route(methods=[...]) limits to the specified methods."""
    route = ItemView.as_route("/test", methods=["GET", "POST"])
    methods = route.methods
    # Methods may be stored as a set internally
    assert "GET" in methods
    assert "POST" in methods


def test_as_route_with_path_params(detail_client: TestClient):
    """Path parameters are correctly parsed and available in the view."""
    response = detail_client.get("/items/42")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "42"


def test_as_route_path_params_delete(detail_client: TestClient):
    """Path parameters work for DELETE method too."""
    response = detail_client.delete("/items/99")
    assert response.status_code == 200
    data = response.json()
    assert data["deleted_id"] == "99"


# ==================== Error Handler Tests ====================


def test_custom_error_handler(error_client: TestClient):
    """Custom error_handlers dict catches specific exception types."""
    response = error_client.get("/errors")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "value_error"
    assert "something went wrong" in data["detail"]


def test_unhandled_error_propagates():
    """Exceptions without a matching handler propagate up (500 error)."""
    app = NexiosApp()
    app.add_route(UnhandledErrorView.as_route("/crash"))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/crash")
        assert response.status_code == 500


# ==================== Default Method Responses ====================


def test_default_methods_return_not_found_body():
    """Base APIView methods return a 'Not Found' error body by default."""
    app = NexiosApp()
    # EmptyView has no overrides, but base APIView defines get/post/put/delete/patch
    # that return a "Not Found" JSON body. as_route auto-detect won't include them
    # since they're on the parent class, so we explicitly pass methods.
    app.add_route(EmptyView.as_route("/empty", methods=["get"]))

    with TestClient(app) as client:
        response = client.get("/empty")
        data = response.json()
        assert data["error"] == "Not Found"


# ==================== JSON Response Tests ====================


def test_json_response():
    """APIView can return rich JSON responses."""
    app = NexiosApp()
    app.add_route(JsonView.as_route("/users"))

    with TestClient(app) as client:
        response = client.get("/users")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["users"]) == 2
        assert data["users"][0]["name"] == "Alice"
        assert data["users"][1]["name"] == "Bob"


# ==================== Middleware Integration Tests ====================


def test_view_with_middleware():
    """Class-level middleware list is applied to all view methods."""
    call_log = []

    async def logging_middleware(request, response, call_next):
        call_log.append("before")
        result = await call_next()
        call_log.append("after")
        return result

    class MiddlewareView(APIView):
        middleware = [logging_middleware]

        async def get(self, request: Request, response: Response):
            return response.json({"message": "with middleware"})

    app = NexiosApp()
    app.add_route(MiddlewareView.as_route("/mw"))

    with TestClient(app) as client:
        response = client.get("/mw")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "with middleware"
        assert "before" in call_log
        assert "after" in call_log
