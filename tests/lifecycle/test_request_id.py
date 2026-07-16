from sillo import silloApp
from sillo.http import Request, Response
from sillo.lifecycle import (
    RequestIdMiddleware,
    generate_request_id,
    validate_request_id,
    get_request_id_from_header,
    get_or_generate_request_id,
    store_request_id_in_request,
)
from sillo.testclient import TestClient


class TestRequestIdMiddleware:
    def test_basic_request_id_generation(self):
        app = silloApp()
        app.use(RequestIdMiddleware())

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert validate_request_id(response.headers["X-Request-ID"])

    def test_request_id_stored_in_state(self):
        app = silloApp()
        app.use(RequestIdMiddleware(store_in_request=True))

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            rid = getattr(request.state, "request_id", None)
            return response.json({"request_id": rid})

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] is not None

    def test_force_generate_ignores_incoming_header(self):
        app = silloApp()
        app.use(RequestIdMiddleware(force_generate=True))

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            return response.json({"ok": True})

        client = TestClient(app)
        incoming_id = "incoming-test-id"
        response = client.get("/test", headers={"X-Request-ID": incoming_id})
        assert response.headers["X-Request-ID"] != incoming_id

    def test_custom_header_name(self):
        app = silloApp()
        app.use(RequestIdMiddleware(header_name="X-Custom-ID"))

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            return response.json({"ok": True})

        client = TestClient(app)
        response = client.get("/test")
        assert "X-Custom-ID" in response.headers

    def test_include_in_response_disabled(self):
        app = silloApp()
        app.use(RequestIdMiddleware(include_in_response=False))

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            return response.json({"ok": True})

        client = TestClient(app)
        response = client.get("/test")
        assert "X-Request-ID" not in response.headers


class TestRequestIdHelpers:
    def test_generate_request_id_is_valid_uuid(self):
        rid = generate_request_id()
        assert validate_request_id(rid)

    def test_validate_invalid_id(self):
        assert not validate_request_id("not-a-uuid")
        assert not validate_request_id("")
        assert not validate_request_id("123")

    def test_get_or_generate_creates_new(self):
        app = silloApp()

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            rid = get_or_generate_request_id(request)
            store_request_id_in_request(request, rid)
            return response.json({"rid": rid})

        client = TestClient(app)
        response = client.get("/test")
        assert validate_request_id(response.json()["rid"])
