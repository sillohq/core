"""
End-to-end tests for OpenAPI integration.
Tests the actual /openapi.json endpoint with various configurations.
"""

import pytest
from sillo import SilloApp, Query, Header, Cookie, Depend, Router
from sillo.core.http import Request, Response
from sillo.testclient import TestClient


@pytest.fixture
def app():
    return SilloApp()


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


class TestUrlFieldsSerialize:
    """Spec fields typed ``AnyUrl`` must reach the wire as strings.

    ``model_dump()`` without ``mode="json"`` leaves them as ``AnyUrl``
    objects, which ``json.dumps`` refuses — so setting a license URL, the
    single most ordinary piece of API metadata, turned the document route
    into a 500. Nothing else in the application misbehaves, which is what
    made it hard to place.
    """

    def test_license_url_does_not_break_the_document(self):
        from sillo.openapi.models import License

        app = SilloApp(license=License(name="MIT", url="https://example.com/mit"))
        response = TestClient(app).get("/openapi.json")

        assert response.status_code == 200
        assert response.json()["info"]["license"]["url"] == "https://example.com/mit"

    def test_contact_url_does_not_break_the_document(self):
        from sillo.openapi.models import Contact

        app = SilloApp(contact=Contact(name="Team", url="https://example.com"))
        response = TestClient(app).get("/openapi.json")

        assert response.status_code == 200
        assert response.json()["info"]["contact"]["url"].startswith(
            "https://example.com"
        )

    def test_external_docs_url_does_not_break_the_document(self):
        from sillo.openapi.models import ExternalDocumentation

        app = SilloApp()
        app.openapi_config.set_external_docs(
            ExternalDocumentation(url="https://example.com/docs", description="More")
        )
        response = TestClient(app).get("/openapi.json")

        assert response.status_code == 200
        assert response.json()["externalDocs"]["url"].startswith("https://example.com")

    def test_every_url_field_at_once_is_json(self):
        import json

        from sillo.openapi.models import Contact, License, Server

        app = SilloApp(
            license=License(name="MIT", url="https://example.com/mit"),
            contact=Contact(name="Team", url="https://example.com", email="t@e.com"),
            servers=[Server(url="https://api.example.com", description="Prod")],
            terms_of_service="https://example.com/terms",
        )

        # build_openapi returns the serialized string; if anything in the
        # document is not JSON-native this raises rather than returning.
        document = json.loads(app.build_openapi())

        assert document["info"]["license"]["url"] == "https://example.com/mit"
        assert document["servers"][0]["url"] == "https://api.example.com"


class TestNestedSchemaReferences:
    """Every $ref in the document must resolve inside the document.

    Pydantic emits nested definitions under ``$defs`` and refers to them as
    ``#/$defs/X``. Those get hoisted into ``components.schemas``, but a model
    lifted out of a parent's ``$defs`` has no ``$defs`` key of its own — so
    it used to be stored with its sibling references untouched, leaving
    ``#/$defs/X`` pointers at a location that no longer exists.

    ReDoc stops on this with "Invalid reference token: $defs". Scalar renders
    an empty page. Swagger UI tolerates it, which is why it went unnoticed.
    """

    @staticmethod
    def _all_refs(node, out=None):
        out = [] if out is None else out
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "$ref" and isinstance(value, str):
                    out.append(value)
                else:
                    TestNestedSchemaReferences._all_refs(value, out)
        elif isinstance(node, list):
            for item in node:
                TestNestedSchemaReferences._all_refs(item, out)
        return out

    @pytest.fixture
    def nested_app(self):
        from enum import Enum
        from typing import List

        from pydantic import BaseModel

        class Colour(str, Enum):
            red = "red"
            blue = "blue"

        class Part(BaseModel):
            name: str
            colour: Colour  # a $ref from inside a nested definition

        class Assembly(BaseModel):
            parts: List[Part]  # forces Part into $defs

        app = SilloApp()

        @app.get("/assemblies", responses={200: Assembly})
        async def list_assemblies(request, response):
            return response.json({})

        @app.post("/assemblies", request_model=Assembly, responses={201: Assembly})
        async def create_assembly(request, response):
            return response.json({}, status_code=201)

        return app

    def test_no_defs_references_survive(self, nested_app):
        document = TestClient(nested_app).get("/openapi.json").text

        assert "#/$defs/" not in document

    def test_every_reference_resolves(self, nested_app):
        spec = TestClient(nested_app).get("/openapi.json").json()
        schemas = spec.get("components", {}).get("schemas", {})

        for ref in self._all_refs(spec):
            assert ref.startswith("#/components/schemas/"), ref
            assert ref.rsplit("/", 1)[-1] in schemas, f"{ref} points at nothing"

    def test_a_nested_definition_keeps_its_own_reference(self, nested_app):
        # Part lives in Assembly's $defs and itself refers to Colour. That
        # inner reference is the one that used to be left as #/$defs/Colour.
        spec = TestClient(nested_app).get("/openapi.json").json()
        part = spec["components"]["schemas"]["Part"]

        assert part["properties"]["colour"]["$ref"] == "#/components/schemas/Colour"

    def test_no_defs_key_is_left_in_components(self, nested_app):
        spec = TestClient(nested_app).get("/openapi.json").json()

        for name, schema in spec["components"]["schemas"].items():
            assert "$defs" not in schema, f"{name} still carries $defs"


class TestSchemaExamples:
    """`examples` on a Schema Object is an array, not a mapping.

    JSON Schema draft 2020-12 defines it as an array of sample values, and
    OpenAPI 3.1 adopts that. The `{name: Example}` mapping belongs to
    Parameter, MediaType and Header.

    Typing it as the mapping meant any model using `Field(examples=[...])`
    failed validation — and since the document is built in one pass, a
    single such field returned 422 for the entire API rather than for the
    one endpoint that used it.
    """

    def test_a_field_with_examples_does_not_break_the_document(self):
        from pydantic import BaseModel, Field

        class Money(BaseModel):
            amount: int = Field(..., examples=[1299])
            currency: str = Field("USD", examples=["USD", "EUR"])

        app = SilloApp()

        @app.post("/prices", request_model=Money, responses={200: Money})
        async def create_price(request, response):
            return response.json({})

        response = TestClient(app).get("/openapi.json")

        assert response.status_code == 200, response.text

    def test_the_examples_array_survives_into_the_document(self):
        from pydantic import BaseModel, Field

        class Money(BaseModel):
            amount: int = Field(..., examples=[1299])

        app = SilloApp()

        @app.post("/prices", request_model=Money, responses={200: Money})
        async def create_price(request, response):
            return response.json({})

        spec = TestClient(app).get("/openapi.json").json()
        # A top-level request model is inlined rather than hoisted into
        # components; only nested definitions land there.
        schema = spec["paths"]["/prices"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]

        assert schema["properties"]["amount"]["examples"] == [1299]

    def test_one_bad_field_does_not_take_the_whole_api_with_it(self):
        # The failure mode that made this hard to place: an unrelated
        # endpoint stops working because of a model it never references.
        from pydantic import BaseModel, Field

        class WithExamples(BaseModel):
            value: int = Field(..., examples=[1])

        app = SilloApp()

        @app.get("/unrelated")
        async def unrelated(request, response):
            return response.json({"ok": True})

        @app.post("/withexamples", request_model=WithExamples)
        async def with_examples(request, response):
            return response.json({})

        spec = TestClient(app).get("/openapi.json").json()

        assert "/unrelated" in spec["paths"]


class TestDiscriminatorMapping:
    """A discriminator's mapping holds references too.

    `_update_schema_references` rewrote values under a `"$ref"` key. A
    discriminator mapping is `{"email": "#/$defs/EmailNotification"}` —
    references under arbitrary keys — so it was skipped. The oneOf branches
    then pointed into `components` while the mapping that selects between
    them still pointed at `$defs`, and a viewer following the discriminator
    resolved nothing.
    """

    @pytest.fixture
    def union_app(self):
        from typing import Literal, Union

        from pydantic import BaseModel, Field
        from typing_extensions import Annotated

        class Email(BaseModel):
            channel: Literal["email"]
            to: str

        class Sms(BaseModel):
            channel: Literal["sms"]
            to: str

        class Send(BaseModel):
            payload: Annotated[Union[Email, Sms], Field(discriminator="channel")]

        app = SilloApp()

        @app.post("/send", request_model=Send, responses={200: Send})
        async def send(request, response):
            return response.json({})

        return app

    def test_no_defs_reference_survives_anywhere(self, union_app):
        document = TestClient(union_app).get("/openapi.json").text

        assert "#/$defs/" not in document

    def test_the_mapping_points_into_components(self, union_app):
        spec = TestClient(union_app).get("/openapi.json").json()
        schema = spec["paths"]["/send"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        mapping = schema["properties"]["payload"]["discriminator"]["mapping"]

        for name, target in mapping.items():
            assert target.startswith("#/components/schemas/"), f"{name} -> {target}"

    def test_every_mapping_target_resolves(self, union_app):
        spec = TestClient(union_app).get("/openapi.json").json()
        schemas = spec["components"]["schemas"]
        schema = spec["paths"]["/send"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        mapping = schema["properties"]["payload"]["discriminator"]["mapping"]

        for name, target in mapping.items():
            assert target.rsplit("/", 1)[-1] in schemas, f"{name} points at nothing"
