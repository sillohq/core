"""
Tests for CORS preflight requests (OPTIONS)
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
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-Custom-Header",
                "X-Another-Header",
            ],
            allow_credentials=True,
            expose_headers=["X-Exposed-Header"],
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

    app.add_middleware(CORSMiddleware())
    return app


@pytest.fixture
def client(cors_app):
    """Create test client"""
    return TestClient(cors_app)


class TestPreflightRequests:
    """Test CORS preflight OPTIONS requests"""

    def test_successful_preflight_request(self, client):
        """Test successful OPTIONS preflight request"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type, Authorization",
            },
        )

        assert response.status_code == 201
        assert response.json() == "OK"
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert response.headers["Access-Control-Allow-Methods"] == "GET"
        assert (
            response.headers["Access-Control-Allow-Headers"]
            == "content-type, authorization"
        )
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
        assert response.headers["Access-Control-Max-Age"] == "3600"

    def test_preflight_with_multiple_methods(self, client):
        """Test preflight request with multiple requested methods"""
        response = client.options(
            "/data",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        assert response.status_code == 201
        assert response.headers["Access-Control-Allow-Methods"] == "POST"

    def test_preflight_with_wildcard_headers(self, client):
        """Test preflight with wildcard allowed headers"""
        # Create app with wildcard headers
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["http://example.com"],
                allow_methods=["GET"],
                allow_headers=["*"],  # Allow all headers
                allow_credentials=True,
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/wildcard-headers")
        async def wildcard_headers_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        wildcard_client = TestClient(app)

        response = wildcard_client.options(
            "/wildcard-headers",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Custom-Header, X-Another-Header, X-Third-Header",
            },
        )

        assert response.status_code == 201
        assert (
            response.headers["Access-Control-Allow-Headers"]
            == "x-custom-header, x-another-header, x-third-header"
        )

    def test_preflight_disallowed_origin(self, client):
        """Test OPTIONS request with disallowed origin"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://disallowed.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 400
        assert "CORS request denied" in response.json()

    def test_preflight_disallowed_method(self, client):
        """Test OPTIONS request with disallowed method"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "PATCH",  # Not in allow_methods
            },
        )

        assert response.status_code == 400
        assert "CORS request denied" in response.json()

    def test_preflight_disallowed_header(self, client):
        """Test OPTIONS request with disallowed header"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Disallowed-Header",
            },
        )

        assert response.status_code == 400
        assert "CORS request denied" in response.json()

    def test_preflight_mixed_allowed_disallowed_headers(self, client):
        """Test preflight with mix of allowed and disallowed headers"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, X-Disallowed-Header, Authorization",
            },
        )

        assert response.status_code == 400
        assert "CORS request denied" in response.json()

    def test_preflight_no_request_headers(self, client):
        """Test preflight request without requesting specific headers"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 201
        assert response.json() == "OK"
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert response.headers["Access-Control-Allow-Methods"] == "GET"
        # Should not have Access-Control-Allow-Headers if not requested
        assert "Access-Control-Allow-Headers" not in response.headers

    def test_preflight_case_insensitive_headers(self, client):
        """Test preflight with case variations in headers"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "CONTENT-TYPE, X-CUSTOM-HEADER",
            },
        )

        assert response.status_code == 201
        assert (
            response.headers["Access-Control-Allow-Headers"]
            == "content-type, x-custom-header"
        )

    def test_preflight_header_normalization(self, client):
        """Test that requested headers are normalized (lowercased)"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Custom-Header, CONTENT-TYPE, x-another-header",
            },
        )

        assert response.status_code == 201
        # Headers should be lowercased in response
        assert (
            response.headers["Access-Control-Allow-Headers"]
            == "x-custom-header, content-type, x-another-header"
        )

    def test_preflight_multiple_origins(self, client):
        """Test preflight requests with different allowed origins"""
        origins = ["http://example.com", "https://example.org"]

        for origin in origins:
            response = client.options(
                "/test",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                },
            )

            assert response.status_code == 201
            assert response.headers["Access-Control-Allow-Origin"] == origin

    def test_preflight_with_credentials_false(self, client):
        """Test preflight when credentials are disabled"""
        # Create app without credentials
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["http://example.com"],
                allow_methods=["GET"],
                allow_credentials=False,
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/no-creds-preflight")
        async def no_creds_preflight_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        no_creds_client = TestClient(app)

        response = no_creds_client.options(
            "/no-creds-preflight",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 201
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        # Should not have credentials header when disabled
        assert "Access-Control-Allow-Credentials" not in response.headers

    def test_preflight_max_age_configuration(self, client):
        """Test preflight max-age configuration"""
        # Create app with different max_age
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["http://example.com"],
                allow_methods=["GET"],
                max_age=86400,  # 24 hours
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/max-age-test")
        async def max_age_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        max_age_client = TestClient(app)

        response = max_age_client.options(
            "/max-age-test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 201
        assert response.headers["Access-Control-Max-Age"] == "86400"

    def test_preflight_blacklisted_origin(self, client):
        """Test preflight with blacklisted origin"""
        # Create app with blacklisted origin
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["*"],
                blacklist_origins=["http://evil.com"],
                allow_methods=["GET"],
                allow_credentials=True,
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/blacklist-preflight")
        async def blacklist_preflight_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        blacklist_client = TestClient(app)

        # Should reject blacklisted origin
        response = blacklist_client.options(
            "/blacklist-preflight",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 400
        assert "CORS request denied" in response.json()

    def test_preflight_empty_headers_list(self, client):
        """Test preflight with empty Access-Control-Request-Headers"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "",
            },
        )

        assert response.status_code == 201
        assert response.json() == "OK"
        # Should not have Access-Control-Allow-Headers for empty request
        assert "Access-Control-Allow-Headers" not in response.headers

    def test_preflight_whitespace_in_headers(self, client):
        """Test preflight with whitespace in requested headers"""
        response = client.options(
            "/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type,  X-Custom-Header  ,  Authorization  ",
            },
        )

        assert response.status_code == 201
        # Headers should be trimmed and lowercased
        assert (
            response.headers["Access-Control-Allow-Headers"]
            == "content-type, x-custom-header, authorization"
        )
