"""
End-to-end tests for OpenAPI integration.
Tests the actual /openapi.json endpoint with various configurations.
"""

import pytest
from nexios import NexiosApp, Query, Header, Cookie, Depend, Router
from nexios.http import Request, Response
from nexios.testclient import TestClient


@pytest.fixture
def app():
    return NexiosApp()


@pytest.fixture
def client(app):
    return TestClient(app)


class TestOpenAPIEndpoint:
    def test_openapi_endpoint_returns_json(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_openapi_has_required_fields(self, client):
        response = client.get("/openapi.json")
        spec = response.json()

        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec
        assert spec["openapi"].startswith("3.")

    def test_openapi_info_fields(self, client):
        response = client.get("/openapi.json")
        spec = response.json()

        assert "title" in spec["info"]
        assert "version" in spec["info"]

    def test_openapi_paths_exist(self, client, app):
        @app.get("/test")
        async def test_handler(request: Request, response: Response):
            return {"ok": True}

        response = client.get("/openapi.json")
        spec = response.json()

        assert "/test" in spec["paths"]


class TestPathParametersOpenAPI:
    def test_path_params_extracted(self, client, app):
        @app.get("/users/{user_id}")
        async def get_user(request: Request, response: Response, user_id: int):
            return {"user_id": user_id}

        response = client.get("/openapi.json")
        spec = response.json()

        params = spec["paths"]["/users/{user_id}"]["get"]["parameters"]
        param_names = [p["name"] for p in params]

        assert "user_id" in param_names
        assert any(p["in"] == "path" and p["name"] == "user_id" for p in params)


class TestQueryParametersOpenAPI:
    def test_query_params_in_openapi(self, client, app):
        @app.get("/items")
        async def get_items(request: Request, response: Response, page: int = Query(1)):
            return {"page": page}

        response = client.get("/openapi.json")
        spec = response.json()

        params = spec["paths"]["/items"]["get"]["parameters"]
        page_param = next((p for p in params if p["name"] == "page"), None)

        assert page_param is not None
        assert page_param["in"] == "query"
        assert page_param["schema"]["type"] == "integer"
        assert page_param["schema"]["default"] == 1

    def test_query_params_multiple(self, client, app):
        @app.get("/search")
        async def search(
            request: Request,
            response: Response,
            q: str = Query(""),
            limit: int = Query(10),
        ):
            return {"q": q, "limit": limit}

        response = client.get("/openapi.json")
        spec = response.json()

        params = spec["paths"]["/search"]["get"]["parameters"]
        assert len(params) == 2

        names = {p["name"] for p in params}
        assert "q" in names
        assert "limit" in names

    def test_query_params_with_alias(self, client, app):
        @app.get("/alias-test")
        async def alias_test(
            request: Request, response: Response, page_num: int = Query(1, alias="page")
        ):
            return {"page": page_num}

        response = client.get("/openapi.json")
        spec = response.json()

        params = spec["paths"]["/alias-test"]["get"]["parameters"]
        param = next((p for p in params if p["name"] == "page"), None)

        assert param is not None
        assert param["in"] == "query"

    def test_query_params_required(self, client, app):
        @app.get("/required")
        async def required(
            request: Request, response: Response, q: str = Query(required=True)
        ):
            return {"q": q}

        response = client.get("/openapi.json")
        spec = response.json()

        params = spec["paths"]["/required"]["get"]["parameters"]
        param = next((p for p in params if p["name"] == "q"), None)

        assert param is not None
        assert param["required"] is True


class TestHeaderParametersOpenAPI:
    def test_header_params_in_openapi(self, client, app):
        @app.get("/auth")
        async def auth(
            request: Request, response: Response, authorization: str = Header()
        ):
            return {"auth": authorization}

        response = client.get("/openapi.json")
        spec = response.json()

        params = spec["paths"]["/auth"]["get"]["parameters"]
        header_param = next((p for p in params if p["in"] == "header"), None)

        assert header_param is not None
        assert header_param["name"] == "Authorization"
        assert header_param["schema"]["type"] == "string"

    def test_header_name_conversion(self, client, app):
        @app.get("/headers")
        async def headers(
            request: Request,
            response: Response,
            x_request_id: str = Header(),
            user_agent: str = Header(),
        ):
            return {"request_id": x_request_id}

        response = client.get("/openapi.json")
        spec = response.json()

        params = spec["paths"]["/headers"]["get"]["parameters"]
        header_params = [p for p in params if p["in"] == "header"]
        names = {p["name"] for p in header_params}

        assert "X-Request-Id" in names
        assert "User-Agent" in names


class TestCookieParametersOpenAPI:
    def test_cookie_params_in_openapi(self, client, app):
        @app.get("/settings")
        async def settings(
            request: Request, response: Response, theme: str = Cookie("light")
        ):
            return {"theme": theme}

        response = client.get("/openapi.json")
        spec = response.json()

        params = spec["paths"]["/settings"]["get"]["parameters"]
        cookie_param = next((p for p in params if p["in"] == "cookie"), None)

        assert cookie_param is not None
        assert cookie_param["name"] == "theme"
        assert cookie_param["schema"]["type"] == "string"
        assert cookie_param["schema"]["default"] == "light"


class TestSummaryAndDescription:
    def test_default_summary(self, client, app):
        @app.get("/test")
        async def test(request: Request, response: Response):
            return {"ok": True}

        response = client.get("/openapi.json")
        spec = response.json()

        summary = spec["paths"]["/test"]["get"]["summary"]
        assert "GET /test" in summary

    def test_custom_summary(self, client, app):
        @app.get("/custom", summary="Get custom data")
        async def custom(request: Request, response: Response):
            return {"ok": True}

        response = client.get("/openapi.json")
        spec = response.json()

        assert spec["paths"]["/custom"]["get"]["summary"] == "Get custom data"

    def test_description(self, client, app):
        @app.get("/described", description="This endpoint returns custom data")
        async def described(request: Request, response: Response):
            return {"ok": True}

        response = client.get("/openapi.json")
        spec = response.json()

        assert (
            spec["paths"]["/described"]["get"]["description"]
            == "This endpoint returns custom data"
        )


class TestTagsOpenAPI:
    def test_tags(self, client, app):
        @app.get("/tagged", tags=["users", "profile"])
        async def tagged(request: Request, response: Response):
            return {"ok": True}

        response = client.get("/openapi.json")
        spec = response.json()

        tags = spec["paths"]["/tagged"]["get"]["tags"]
        assert "users" in tags
        assert "profile" in tags


class TestOperationId:
    def test_auto_operation_id(self, client, app):
        @app.get("/items")
        async def items(request: Request, response: Response):
            return {"items": []}

        response = client.get("/openapi.json")
        spec = response.json()

        op_id = spec["paths"]["/items"]["get"]["operationId"]
        assert op_id is not None

    def test_custom_operation_id(self, client, app):
        @app.get("/custom-id", operation_id="getCustomItems")
        async def custom_id(request: Request, response: Response):
            return {"ok": True}

        response = client.get("/openapi.json")
        spec = response.json()

        assert spec["paths"]["/custom-id"]["get"]["operationId"] == "getCustomItems"


class TestResponsesOpenAPI:
    def test_default_response(self, client, app):
        @app.get("/test")
        async def test(request: Request, response: Response):
            return {"ok": True}

        response = client.get("/openapi.json")
        spec = response.json()

        responses = spec["paths"]["/test"]["get"]["responses"]
        assert "200" in responses
        assert "description" in responses["200"]


class TestRouterOpenAPI:
    def test_router_routes_in_openapi(self, client, app):
        router = Router(prefix="/api")

        @router.get("/items")
        async def router_items(request: Request, response: Response):
            return {"items": []}

        app.mount_router(router)

        response = client.get("/openapi.json")
        spec = response.json()

        assert "/api/items" in spec["paths"]


class TestDeprecatedEndpoints:
    def test_deprecated_flag(self, client, app):
        @app.get("/old", deprecated=True)
        async def old_endpoint(request: Request, response: Response):
            return {"ok": True}

        response = client.get("/openapi.json")
        spec = response.json()

        assert spec["paths"]["/old"]["get"]["deprecated"] is True


class TestMixedParameterTypes:
    def test_all_param_types(self, client, app):
        @app.get("/full")
        async def full(
            request: Request,
            response: Response,
            page: int = Query(1),
            auth: str = Header(),
            session: str = Cookie(),
        ):
            return {"page": page}

        response = client.get("/openapi.json")
        spec = response.json()

        params = spec["paths"]["/full"]["get"]["parameters"]
        assert len(params) == 3

        locations = {p["in"] for p in params}
        assert "query" in locations
        assert "header" in locations
        assert "cookie" in locations


class TestExcludedFromSchema:
    def test_excluded_endpoint_not_in_openapi(self, client, app):
        @app.get("/visible")
        async def visible(request: Request, response: Response):
            return {"ok": True}

        @app.get("/hidden", exclude_from_schema=True)
        async def hidden(request: Request, response: Response):
            return {"ok": True}

        response = client.get("/openapi.json")
        spec = response.json()

        assert "/visible" in spec["paths"]
        assert "/hidden" not in spec["paths"]


class TestMultipleMethods:
    def test_get_and_head_methods(self, client, app):
        @app.get("/multi")
        async def multi(request: Request, response: Response):
            return {"ok": True}

        response = client.get("/openapi.json")
        spec = response.json()

        path_spec = spec["paths"]["/multi"]
        assert "get" in path_spec
        assert "head" in path_spec


class TestFullIntegration:
    def test_complete_endpoint_spec(self, client, app):
        @app.get(
            "/users/{user_id}/posts",
            summary="List user posts",
            description="Returns paginated list of posts for a specific user",
            tags=["users", "posts"],
            operation_id="listUserPosts",
        )
        async def list_user_posts(
            request: Request,
            response: Response,
            user_id: int,
            page: int = Query(1),
            limit: int = Query(10),
            authorization: str = Header(),
        ):
            return {"user_id": user_id, "page": page}

        response = client.get("/openapi.json")
        spec = response.json()

        path_spec = spec["paths"]["/users/{user_id}/posts"]["get"]

        assert path_spec["summary"] == "List user posts"
        assert (
            path_spec["description"]
            == "Returns paginated list of posts for a specific user"
        )
        assert "users" in path_spec["tags"]
        assert "posts" in path_spec["tags"]
        assert path_spec["operationId"] == "listUserPosts"

        params = path_spec["parameters"]
        param_names = {p["name"] for p in params}

        assert "user_id" in param_names
        assert "page" in param_names
        assert "limit" in param_names
        assert "Authorization" in param_names
