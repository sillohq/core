"""
Tests for CORS middleware configuration and advanced features
"""

import pytest

from nexios import NexiosApp
from nexios.config import MakeConfig, set_config
from nexios.middleware.cors import CorsConfig
from nexios.http import Request, Response
from nexios.middleware.cors import CORSMiddleware
from nexios.testclient import TestClient


class TestCORSConfiguration:
    """Test CORS middleware configuration options"""

    def test_wildcard_origin_configuration(self):
        """Test CORS with wildcard origin configuration"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["*"],
                allow_methods=["GET", "POST"],
                allow_credentials=False,
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/wildcard")
        async def wildcard_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        response = client.get("/wildcard", headers={"Origin": "http://any-origin.com"})

        assert response.status_code == 200
        assert (
            response.headers["Access-Control-Allow-Origin"] == "http://any-origin.com"
        )
        assert "Access-Control-Allow-Credentials" not in response.headers

    def test_regex_origin_configuration(self):
        """Test CORS with regex-based origin validation"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origin_regex=r"https://.*\.example\.com",
                allow_methods=["GET"],
                allow_credentials=True,
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/regex-test")
        async def regex_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Should allow subdomain
        response1 = client.get(
            "/regex-test", headers={"Origin": "https://api.example.com"}
        )
        assert response1.status_code == 200
        assert (
            response1.headers["Access-Control-Allow-Origin"]
            == "https://api.example.com"
        )

        # Should allow different subdomain
        response2 = client.get(
            "/regex-test", headers={"Origin": "https://app.example.com"}
        )
        assert response2.status_code == 200
        assert (
            response2.headers["Access-Control-Allow-Origin"]
            == "https://app.example.com"
        )

        # Should reject non-matching domain
        response3 = client.get("/regex-test", headers={"Origin": "https://example.org"})
        assert response3.status_code == 200
        assert "Access-Control-Allow-Origin" not in response3.headers

    def test_regex_origin_case_sensitive(self):
        """Test that regex origin matching is case-sensitive"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origin_regex=r"https://.*\.EXAMPLE\.COM",
                allow_methods=["GET"],
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/regex-case-test")
        async def regex_case_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Should allow exact case match
        response1 = client.get(
            "/regex-case-test", headers={"Origin": "https://api.EXAMPLE.COM"}
        )
        assert response1.status_code == 200
        assert (
            response1.headers["Access-Control-Allow-Origin"]
            == "https://api.EXAMPLE.COM"
        )

        # Should reject different case
        response2 = client.get(
            "/regex-case-test", headers={"Origin": "https://api.example.com"}
        )
        assert response2.status_code == 200
        assert "Access-Control-Allow-Origin" not in response2.headers

    def test_regex_origin_with_ports(self):
        """Test regex origin matching with ports"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origin_regex=r"https://.*\.example\.com(:[0-9]+)?",
                allow_methods=["GET"],
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/regex-port-test")
        async def regex_port_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Should allow with port
        response1 = client.get(
            "/regex-port-test", headers={"Origin": "https://api.example.com:8080"}
        )
        assert response1.status_code == 200
        assert (
            response1.headers["Access-Control-Allow-Origin"]
            == "https://api.example.com:8080"
        )

        # Should allow without port
        response2 = client.get(
            "/regex-port-test", headers={"Origin": "https://api.example.com"}
        )
        assert response2.status_code == 200
        assert (
            response2.headers["Access-Control-Allow-Origin"]
            == "https://api.example.com"
        )

    def test_dynamic_origin_validator(self):
        """Test CORS with dynamic origin validator function"""

        def validate_origin(origin):
            return origin and origin.endswith(".trusted-domain.com")

        config = MakeConfig(
            cors=CorsConfig(
                dynamic_origin_validator=validate_origin,
                allow_methods=["GET"],
                allow_credentials=True,
            )
        )
        set_config(config)
        app = NexiosApp(config=config)

        @app.get("/dynamic-test")
        async def dynamic_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Should allow trusted domain
        response1 = client.get(
            "/dynamic-test", headers={"Origin": "https://app.trusted-domain.com"}
        )
        assert response1.status_code == 200
        assert (
            response1.headers["Access-Control-Allow-Origin"]
            == "https://app.trusted-domain.com"
        )

        # Should reject non-trusted domain
        response2 = client.get(
            "/dynamic-test", headers={"Origin": "https://malicious.com"}
        )
        assert response2.status_code == 200
        assert "Access-Control-Allow-Origin" not in response2.headers

    def test_blacklisted_origins(self):
        """Test CORS with blacklisted origins"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["*"],
                blacklist_origins=["https://evil.com", "http://malicious.org"],
                allow_methods=["GET"],
                allow_credentials=False,
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/blacklist-test")
        async def blacklist_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Should allow normal origin
        response1 = client.get(
            "/blacklist-test", headers={"Origin": "https://good.com"}
        )
        assert response1.status_code == 200
        assert response1.headers["Access-Control-Allow-Origin"] == "https://good.com"

        # Should reject blacklisted origin
        response2 = client.get(
            "/blacklist-test", headers={"Origin": "https://evil.com"}
        )
        assert response2.status_code == 200
        assert "Access-Control-Allow-Origin" not in response2.headers

    def test_blacklist_with_regex_origins(self):
        """Test blacklisting combined with regex origins"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origin_regex=r"https://.*\.example\.com",
                blacklist_origins=["https://bad.example.com"],
                allow_methods=["GET"],
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/blacklist-regex-test")
        async def blacklist_regex_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Should allow good subdomain
        response1 = client.get(
            "/blacklist-regex-test", headers={"Origin": "https://good.example.com"}
        )
        assert response1.status_code == 200
        assert (
            response1.headers["Access-Control-Allow-Origin"]
            == "https://good.example.com"
        )

        # Should reject blacklisted subdomain even though regex matches
        response2 = client.get(
            "/blacklist-regex-test", headers={"Origin": "https://bad.example.com"}
        )
        assert response2.status_code == 200
        assert "Access-Control-Allow-Origin" not in response2.headers

    def test_credentials_disabled_configuration(self):
        """Test CORS configuration without credentials"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["http://example.com"],
                allow_methods=["GET"],
                allow_credentials=False,
                expose_headers=["X-Custom-Header"],
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/no-creds-test")
        async def no_creds_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        response = client.get(
            "/no-creds-test", headers={"Origin": "http://example.com"}
        )

        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert response.headers["Access-Control-Expose-Headers"] == "X-Custom-Header"
        # Should not have credentials header when disabled
        assert "Access-Control-Allow-Credentials" not in response.headers

    def test_expose_headers_configuration(self):
        """Test CORS expose headers configuration"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["http://example.com"],
                allow_methods=["GET"],
                allow_credentials=True,
                expose_headers=[
                    "X-Request-ID",
                    "X-Response-Time",
                    "X-Custom-Header",
                ],
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/expose-headers-test")
        async def expose_headers_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        response = client.get(
            "/expose-headers-test", headers={"Origin": "http://example.com"}
        )

        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
        assert (
            response.headers["Access-Control-Expose-Headers"]
            == "X-Request-ID, X-Response-Time, X-Custom-Header"
        )

    def test_empty_expose_headers(self):
        """Test CORS with empty expose headers"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["http://example.com"],
                allow_methods=["GET"],
                allow_credentials=True,
                expose_headers=[],
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/empty-expose-test")
        async def empty_expose_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        response = client.get(
            "/empty-expose-test", headers={"Origin": "http://example.com"}
        )

        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
        # Should not have expose headers when empty
        assert "Access-Control-Expose-Headers" not in response.headers

    def test_max_age_configuration(self):
        """Test CORS max-age configuration"""
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

        client = TestClient(app)

        response = client.get("/max-age-test", headers={"Origin": "http://example.com"})
        # Simple request shouldn't include max-age
        # assert "Access-Control-Max-Age" not in response.headers

        # Only preflight requests include max-age
        preflight_response = client.options(
            "/max-age-test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert preflight_response.status_code == 201
        assert preflight_response.headers["Access-Control-Max-Age"] == "86400"

    def test_strict_origin_checking_disabled(self):
        """Test CORS with strict origin checking disabled (default)"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["http://example.com"],
                allow_methods=["GET"],
                strict_origin_checking=False,
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/non-strict-test")
        async def non_strict_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Should allow request without Origin header when strict checking is disabled
        response = client.get("/non-strict-test")
        assert response.status_code == 200
        assert response.json() == {"message": "OK"}

    def test_debug_mode_configuration(self):
        """Test CORS debug mode configuration"""
        config = MakeConfig(
            cors=CorsConfig(
                allow_origins=["http://example.com"],
                allow_methods=["GET"],
                debug=True,
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/debug-test")
        async def debug_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Debug mode doesn't affect normal operation
        response = client.get("/debug-test", headers={"Origin": "http://example.com"})
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
