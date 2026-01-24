"""
Tests for simple CORS requests (GET, POST, PUT, DELETE)
"""

import pytest

from nexios import NexiosApp
from nexios.config import MakeConfig, set_config
from nexios.middleware.cors import CorsConfig
from nexios.http import Request, Response
from nexios.middleware.cors import CORSMiddleware
from nexios.testclient import TestClient


@pytest.fixture
def cors_app():
    """Create a test app with CORS middleware configured"""
    config = MakeConfig(
        cors=CorsConfig(
            allow_origins=["http://example.com", "https://example.org"],
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "X-Custom-Header"],
            allow_credentials=True,
            expose_headers=["X-Exposed-Header", "X-Response-Time"],
            max_age=3600,
            debug=True,
        )
    )
    set_config(config)

    app = NexiosApp(config)

    # Add test routes
    @app.get("/test")
    async def test_route(request: Request, response: Response):
        return response.json({"message": "OK"})

    @app.post("/data")
    async def data_route(request: Request, response: Response):
        return response.json({"received": True})

    @app.put("/update")
    async def update_route(request: Request, response: Response):
        return response.json({"updated": True})

    @app.delete("/delete")
    async def delete_route(request: Request, response: Response):
        return response.json({"deleted": True})

    app.add_middleware(CORSMiddleware())
    return app


@pytest.fixture
def client(cors_app):
    """Create test client"""
    return TestClient(cors_app)


class TestSimpleRequests:
    """Test simple CORS requests with various HTTP methods"""

    def test_get_request_allowed_origin(self, client):
        """Test simple GET request with allowed origin"""
        response = client.get("/test", headers={"Origin": "http://example.com"})

        assert response.status_code == 200
        assert response.json() == {"message": "OK"}
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
        assert (
            response.headers["Access-Control-Expose-Headers"]
            == "X-Exposed-Header, X-Response-Time"
        )

    def test_get_request_disallowed_origin(self, client):
        """Test simple GET request with disallowed origin"""
        response = client.get("/test", headers={"Origin": "http://disallowed.com"})

        assert response.status_code == 200
        assert response.json() == {"message": "OK"}
        # Should not have CORS headers for disallowed origin
        assert "Access-Control-Allow-Origin" not in response.headers
        assert "Access-Control-Allow-Credentials" not in response.headers

    def test_get_request_no_origin_header(self, client):
        """Test simple request without Origin header"""
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json() == {"message": "OK"}
        # Should not have CORS headers without origin
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_post_request_allowed_origin(self, client):
        """Test simple POST request with allowed origin"""
        response = client.post("/data", headers={"Origin": "http://example.com"})

        assert response.status_code == 200
        assert response.json() == {"received": True}
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert response.headers["Access-Control-Allow-Credentials"] == "true"

    def test_put_request_allowed_origin(self, client):
        """Test simple PUT request with allowed origin"""
        response = client.put("/update", headers={"Origin": "http://example.com"})

        assert response.status_code == 200
        assert response.json() == {"updated": True}
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert response.headers["Access-Control-Allow-Credentials"] == "true"

    def test_delete_request_allowed_origin(self, client):
        """Test simple DELETE request with allowed origin"""
        response = client.delete("/delete", headers={"Origin": "http://example.com"})

        assert response.status_code == 200
        assert response.json() == {"deleted": True}
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert response.headers["Access-Control-Allow-Credentials"] == "true"

    def test_different_methods_same_origin(self, client):
        """Test multiple methods with the same allowed origin"""
        methods_and_routes = [
            ("GET", "/test"),
            ("POST", "/data"),
            ("PUT", "/update"),
            ("DELETE", "/delete"),
        ]

        for method, route in methods_and_routes:
            response = client.request(
                method, route, headers={"Origin": "http://example.com"}
            )

            assert response.status_code == 200
            assert (
                response.headers["Access-Control-Allow-Origin"] == "http://example.com"
            )
            assert response.headers["Access-Control-Allow-Credentials"] == "true"

    def test_multiple_origins_same_method(self, client):
        """Test same method with multiple allowed origins"""
        origins = ["http://example.com", "https://example.org"]

        for origin in origins:
            response = client.get("/test", headers={"Origin": origin})

            assert response.status_code == 200
            assert response.headers["Access-Control-Allow-Origin"] == origin
            assert response.headers["Access-Control-Allow-Credentials"] == "true"

    def test_case_sensitive_origin_handling(self, client):
        """Test that origin matching is case-sensitive"""
        # Test exact case match
        response1 = client.get("/test", headers={"Origin": "http://example.com"})
        assert response1.headers["Access-Control-Allow-Origin"] == "http://example.com"

        # Test different case should not match
        response2 = client.get("/test", headers={"Origin": "http://EXAMPLE.COM"})
        assert "Access-Control-Allow-Origin" not in response2.headers

    def test_origin_with_ports(self, client):
        """Test origins with explicit ports"""
        # Create app that allows specific port
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=[
                    "http://example.com:8080",
                    "https://example.org:3000",
                ],
                allow_methods=["GET"],
                allow_credentials=True,
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/port-test")
        async def port_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        port_client = TestClient(app)

        # Test allowed port
        response1 = port_client.get(
            "/port-test", headers={"Origin": "http://example.com:8080"}
        )
        assert response1.status_code == 200
        assert (
            response1.headers["Access-Control-Allow-Origin"]
            == "http://example.com:8080"
        )

        # Test different port should not match
        response2 = port_client.get(
            "/port-test", headers={"Origin": "http://example.com:9090"}
        )
        assert "Access-Control-Allow-Origin" not in response2.headers

    def test_request_without_origin_header_different_methods(self, client):
        """Test that missing Origin header works for all methods"""
        methods_and_routes = [
            ("GET", "/test"),
            ("POST", "/data"),
            ("PUT", "/update"),
            ("DELETE", "/delete"),
        ]

        for method, route in methods_and_routes:
            response = client.request(method, route)

            assert response.status_code == 200
            assert "Access-Control-Allow-Origin" not in response.headers

    def test_request_with_empty_origin_header(self, client):
        """Test request with empty Origin header"""
        response = client.get("/test", headers={"Origin": ""})

        assert response.status_code == 200
        assert response.json() == {"message": "OK"}
        # Empty origin should not be treated as valid
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_request_with_whitespace_origin(self, client):
        """Test request with whitespace-only Origin header"""
        response = client.get("/test", headers={"Origin": "   "})

        assert response.status_code == 200
        assert response.json() == {"message": "OK"}
        # Whitespace origin should not be treated as valid
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_request_with_null_origin(self, client):
        """Test request with null Origin header"""
        response = client.get("/test", headers={"Origin": "null"})

        assert response.status_code == 200
        assert response.json() == {"message": "OK"}
        # "null" origin should not be treated as valid
        assert "Access-Control-Allow-Origin" not in response.headers
