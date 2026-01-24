"""
Tests for CORS middleware error handling and edge cases
"""

import pytest

from nexios import NexiosApp
from nexios.config import MakeConfig, set_config
from nexios.middleware.cors import CorsConfig
from nexios.http import Request, Response
from nexios.middleware.cors import CORSMiddleware
from nexios.testclient import TestClient


class TestCORSErrorHandling:
    """Test CORS middleware error handling and edge cases"""

    def test_malformed_origin_header(self):
        """Test CORS with malformed Origin header"""
        config = MakeConfig(
            {
                "cors": {
                    "allow_origins": ["http://example.com"],
                    "allow_methods": ["GET"],
                }
            }
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/malformed-origin")
        async def malformed_origin_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Test with malformed origin
        response = client.get(
            "/malformed-origin", headers={"Origin": "not-a-valid-url"}
        )
        assert response.status_code == 200
        # Should not add CORS headers for invalid origins
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_origin_with_invalid_characters(self):
        """Test CORS with Origin header containing invalid characters"""
        config = MakeConfig(
            {
                "cors": {
                    "allow_origins": ["http://example.com"],
                    "allow_methods": ["GET"],
                }
            }
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/invalid-origin-chars")
        async def invalid_origin_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Test with various invalid origin formats
        invalid_origins = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "file:///etc/passwd",
            "ftp://example.com",
            "http://example.com<script>",
            "http://example.com\r\nSet-Cookie: evil=value",
        ]

        for invalid_origin in invalid_origins:
            response = client.get(
                "/invalid-origin-chars", headers={"Origin": invalid_origin}
            )
            assert response.status_code == 200
            # Should not add CORS headers for invalid origins
            assert "Access-Control-Allow-Origin" not in response.headers

    def test_empty_configuration_handling(self):
        """Test CORS middleware with empty configuration"""
        config = MakeConfig(cors=CorsConfig())
        set_config(config)

        app = NexiosApp(config)

        @app.get("/empty-cors")
        async def empty_cors_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Should handle gracefully without CORS headers
        response = client.get("/empty-cors", headers={"Origin": "http://example.com"})
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_none_configuration_handling(self):
        """Test CORS middleware with None configuration"""
        config = MakeConfig(cors=None)
        set_config(config)

        app = NexiosApp(config)

        @app.get("/none-cors")
        async def none_cors_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Should handle gracefully without CORS headers
        response = client.get("/none-cors", headers={"Origin": "http://example.com"})
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_missing_cors_config(self):
        """Test app without any CORS configuration"""
        config = MakeConfig({})  # No CORS config at all
        set_config(config)

        app = NexiosApp(config)

        @app.get("/no-cors-config")
        async def no_cors_config_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        response = client.get(
            "/no-cors-config", headers={"Origin": "http://example.com"}
        )

        assert response.status_code == 200
        assert response.json() == {"message": "OK"}
        # Should not have any CORS headers
        cors_headers = [
            h for h in response.headers.keys() if h.startswith("Access-Control-")
        ]
        assert len(cors_headers) == 0

    def test_non_callable_dynamic_validator(self):
        """Test CORS with non-callable dynamic validator"""
        config = MakeConfig(
            cors=CorsConfig(
                dynamic_origin_validator="not-a-function",  # type: ignore
                allow_methods=["GET"],
            )
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/non-callable-validator")
        async def non_callable_validator_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Should handle non-callable validator gracefully
        response = client.get(
            "/non-callable-validator", headers={"Origin": "http://example.com"}
        )
        assert response.status_code == 200
        # Should not add CORS headers when validator is not callable
        print(response.headers)
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_request_with_multiple_origin_headers(self):
        """Test request with multiple Origin headers (HTTP header injection)"""
        config = MakeConfig(
            {
                "cors": {
                    "allow_origins": ["http://example.com"],
                    "allow_methods": ["GET"],
                }
            }
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/multiple-origins")
        async def multiple_origins_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Most HTTP clients will use the last Origin header
        response = client.get(
            "/multiple-origins",
            headers={
                "Origin": "http://evil.com",
                "Origin": "http://example.com",  # This should be the effective one
            },
        )
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"

    def test_request_with_very_long_origin(self):
        """Test request with extremely long Origin header"""
        config = MakeConfig(
            {
                "cors": {
                    "allow_origins": ["http://example.com"],
                    "allow_methods": ["GET"],
                }
            }
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/long-origin")
        async def long_origin_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Create a very long origin
        long_origin = "http://example.com/" + "a" * 10000

        response = client.get("/long-origin", headers={"Origin": long_origin})
        assert response.status_code == 200
        # Should handle long origins gracefully
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_request_with_null_byte_origin(self):
        """Test request with null bytes in Origin header"""
        config = MakeConfig(
            {
                "cors": {
                    "allow_origins": ["http://example.com"],
                    "allow_methods": ["GET"],
                }
            }
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/null-byte-origin")
        async def null_byte_origin_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Test with null byte in origin
        malicious_origin = "http://example.com\x00evil.com"

        response = client.get("/null-byte-origin", headers={"Origin": malicious_origin})
        assert response.status_code == 200
        # Should handle null bytes gracefully
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_cors_middleware_with_exception_in_route(self):
        """Test CORS middleware when route handler raises exception"""
        config = MakeConfig(
            {
                "cors": {
                    "allow_origins": ["http://example.com"],
                    "allow_methods": ["GET"],
                }
            }
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/exception-route")
        async def exception_route(request: Request, response: Response):
            raise ValueError("Route error")

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # CORS middleware should still add headers before the exception
        response = client.get(
            "/exception-route", headers={"Origin": "http://example.com"}
        )
        assert response.status_code == 500  # Internal server error
        # CORS headers should still be present
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"

    def test_cors_preflight_with_invalid_method_header(self):
        """Test preflight request with invalid Access-Control-Request-Method"""
        config = MakeConfig(
            {
                "cors": {
                    "allow_origins": ["http://example.com"],
                    "allow_methods": ["GET"],
                }
            }
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/invalid-method-preflight")
        async def invalid_method_preflight_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Test with invalid method header
        response = client.options(
            "/invalid-method-preflight",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "INVALID_METHOD",
            },
        )

        assert response.status_code == 400
        assert "CORS request denied" in response.json()

    def test_cors_preflight_with_empty_method_header(self):
        """Test preflight request with empty Access-Control-Request-Method"""
        config = MakeConfig(
            {
                "cors": {
                    "allow_origins": ["http://example.com"],
                    "allow_methods": ["GET"],
                }
            }
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/empty-method-preflight")
        async def empty_method_preflight_route(request: Request, response: Response):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Test with empty method header
        response = client.options(
            "/empty-method-preflight",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "",
            },
        )

        assert response.status_code == 400
        assert "CORS request denied" in response.json()

    def test_cors_preflight_with_whitespace_method(self):
        """Test preflight request with whitespace in method header"""
        config = MakeConfig(
            {
                "cors": {
                    "allow_origins": ["http://example.com"],
                    "allow_methods": ["GET"],
                }
            }
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/whitespace-method-preflight")
        async def whitespace_method_preflight_route(
            request: Request, response: Response
        ):
            return response.json({"message": "OK"})

        app.add_middleware(CORSMiddleware())

        client = TestClient(app)

        # Test with whitespace in method
        response = client.options(
            "/whitespace-method-preflight",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "  GET  ",
            },
        )

        assert response.status_code == 400
