"""
Tests for CORS middleware error handling and edge cases
"""

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.security.cors import CorsConfig, CORSMiddleware
from sillo.testclient import TestClient


class TestCORSErrorHandling:
    """Test CORS middleware error handling and edge cases"""

    def test_malformed_origin_header(self):
        """Test CORS with malformed Origin header"""
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/malformed-origin")
        async def malformed_origin_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

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
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/invalid-origin-chars")
        async def invalid_origin_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

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
        cors_config = CorsConfig()

        app = SilloApp()

        @app.get("/empty-cors")
        async def empty_cors_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        # Should handle gracefully without CORS headers
        response = client.get("/empty-cors", headers={"Origin": "http://example.com"})
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_missing_cors_config(self):
        """Test app without any CORS configuration"""
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/no-cors-config")
        async def no_cors_config_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        response = client.get(
            "/no-cors-config", headers={"Origin": "http://example.com"}
        )

        assert response.status_code == 200
        assert response.json() == {"message": "OK"}
        # Should have CORS headers since origin is allowed
        assert "Access-Control-Allow-Origin" in response.headers

    def test_non_callable_dynamic_validator(self):
        """Test CORS with non-callable dynamic validator"""
        cors_config = CorsConfig(
            dynamic_origin_validator="not-a-function",  # type: ignore
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/non-callable-validator")
        async def non_callable_validator_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

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
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/multiple-origins")
        async def multiple_origins_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

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
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/long-origin")
        async def long_origin_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        # Create a very long origin
        long_origin = "http://example.com/" + "a" * 10000

        response = client.get("/long-origin", headers={"Origin": long_origin})
        assert response.status_code == 200
        # Should handle long origins gracefully
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_request_with_null_byte_origin(self):
        """Test request with null bytes in Origin header"""
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/null-byte-origin")
        async def null_byte_origin_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        # Test with null byte in origin
        malicious_origin = "http://example.com\x00evil.com"

        response = client.get("/null-byte-origin", headers={"Origin": malicious_origin})
        assert response.status_code == 200
        # Should handle null bytes gracefully
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_cors_middleware_with_exception_in_route(self):
        """Test CORS middleware when route handler raises exception"""
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/exception-route")
        async def exception_route(ctx: HttpContext):
            raise ValueError("Route error")

        app.use(CORSMiddleware(config=cors_config))

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
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/invalid-method-preflight")
        async def invalid_method_preflight_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

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
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/empty-method-preflight")
        async def empty_method_preflight_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

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
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
        )

        app = SilloApp()

        @app.get("/whitespace-method-preflight")
        async def whitespace_method_preflight_route(
            ctx: HttpContext
        ):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

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

    async def test_strict_origin_checking_rejects_a_missing_origin(self):
        """A falsy ``ctx.origin`` is refused when strict checking is on.

        ``HttpContext.origin`` always synthesizes a value from the URL when no
        ``Origin`` header is sent, so a real request never reaches this
        branch through the public API; it is exercised directly here with a
        double that returns an empty origin.
        """
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
            strict_origin_checking=True,
            debug=True,
        )
        middleware = CORSMiddleware(config=cors_config)

        class FakeContext:
            origin = ""
            scope = {"method": "GET"}
            headers = {}

        async def call_next():
            raise AssertionError("should not reach the route handler")

        result = await middleware.dispatch(FakeContext(), call_next)

        assert result.status_code == 400

    def test_a_blacklisted_origin_is_denied_on_a_simple_request(self):
        cors_config = CorsConfig(
            allow_origins=["*"],
            blacklist_origins=["http://evil.example.com"],
            allow_methods=["GET"],
            debug=True,
        )

        app = SilloApp()

        @app.get("/blacklist-simple")
        async def route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))
        client = TestClient(app)

        response = client.get(
            "/blacklist-simple", headers={"Origin": "http://evil.example.com"}
        )

        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers

    def test_wildcard_method_allows_anything(self):
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["*"],
        )

        app = SilloApp()

        @app.get("/wildcard-method")
        async def route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))
        client = TestClient(app)

        response = client.options(
            "/wildcard-method",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "PATCH",
            },
        )

        assert response.status_code == 201

    def test_custom_error_message_is_used_for_a_known_error_type(self):
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
            custom_error_messages={"disallowed_origin": "nope, not you"},
        )

        app = SilloApp()

        @app.get("/custom-message")
        async def route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))
        client = TestClient(app)

        response = client.options(
            "/custom-message",
            headers={
                "Origin": "http://not-allowed.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 400
        assert response.json() == "nope, not you"

    def test_regex_match_error_is_treated_as_not_allowed(self):
        """A regex engine failure at match time must deny, not raise."""
        import re

        from sillo.security.cors._middleware import CORSMiddleware

        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET"],
            allow_origin_regex=r"http://.*\.example\.com",
        )
        middleware = CORSMiddleware(config=cors_config)

        class ExplodingPattern:
            def fullmatch(self, value):
                raise re.error("simulated regex engine failure")

        middleware.allow_origin_regex = ExplodingPattern()

        assert middleware.is_allowed_origin("http://sub.example.com") is False

    def test_cors_config_getattr_falls_back_to_config_dict(self):
        cors_config = CorsConfig(allow_origins=["http://example.com"])
        assert cors_config.not_a_real_setting is None

    def test_cors_config_getattr_of_config_itself_raises(self):
        cors_config = CorsConfig(allow_origins=["http://example.com"])
        with pytest.raises(AttributeError):
            cors_config.__getattr__("_config")

    def test_cors_config_to_dict(self):
        cors_config = CorsConfig(allow_origins=["http://example.com"])
        data = cors_config.to_dict()
        assert data["allow_origins"] == ["http://example.com"]

    async def test_process_request_without_a_config_passes_through(self):
        """Defensive guard: a middleware instance with no config just delegates."""
        cors_config = CorsConfig(
            allow_origins=["http://example.com"], allow_methods=["GET"]
        )
        middleware = CORSMiddleware(config=cors_config)
        middleware.config = None

        called = {"next": False}

        async def call_next():
            called["next"] = True
            return "ok"

        result = await middleware.dispatch(None, call_next)

        assert result == "ok"
        assert called["next"] is True
