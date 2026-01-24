"""
Tests for session middleware integration
"""

import pytest

from nexios import NexiosApp
from nexios.config import MakeConfig, set_config
from nexios.session import SessionConfig
from nexios.http import Request, Response
from nexios.session.file import FileSessionManager
from nexios.session.middleware import SessionMiddleware
from nexios.session.signed_cookies import SignedSessionManager
from nexios.testclient import TestClient


class TestSessionMiddleware:
    """Test session middleware functionality"""

    def setup_method(self):
        """Set up test configuration"""
        config = MakeConfig(
            secret_key="test-secret-key-for-middleware",
            session=SessionConfig(
                session_cookie_name="test_session",
                # The following are still supported via kwargs or if we added them to SessionConfig
                session_expiration_time=3600,
                session_permanent=False,
                session_refresh_each_request=False,
                session_cookie_secure=False,
                session_cookie_httponly=True,
                session_cookie_samesite="lax",
            ),
        )
        set_config(config)

    def test_middleware_initialization(self):
        """Test session middleware initialization"""
        middleware = SessionMiddleware()
        assert middleware is not None

    def test_signed_cookie_session_middleware(self):
        """Test session middleware with signed cookie backend"""
        app = NexiosApp()

        @app.get("/session-test")
        async def session_test(request: Request, response: Response):
            # Access session to trigger middleware
            user_id = request.session.get("user_id", 0)
            request.session["user_id"] = user_id + 1
            return response.json({"user_id": request.session["user_id"]})

        app.add_middleware(SessionMiddleware())

        client = TestClient(app)

        # First request
        response1 = client.get("/session-test")
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["user_id"] == 1

        # Second request should increment
        response2 = client.get("/session-test")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["user_id"] == 2

        # Check that session cookie is set
        assert "Set-Cookie" in response1.headers
        cookie_header = response1.headers["Set-Cookie"]
        assert "test_session" in cookie_header

    def test_file_session_middleware(self):
        """Test session middleware with file backend"""
        import os
        import tempfile

        temp_dir = tempfile.mkdtemp()

        try:
            config = MakeConfig(
                secret_key="test-secret-key-for-file-middleware",
                session=SessionConfig(
                    session_cookie_name="file_session",
                    session_file_storage_path=temp_dir,
                    manager=FileSessionManager,
                ),
            )
            set_config(config)

            app = NexiosApp()

            @app.get("/file-session-test")
            async def file_session_test(request: Request, response: Response):
                counter = request.session.get("counter", 0)
                request.session["counter"] = counter + 1
                return response.json({"counter": request.session["counter"]})

            app.add_middleware(SessionMiddleware())

            client = TestClient(app)

            # First request
            response1 = client.get("/file-session-test")
            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["counter"] == 1

            # Second request
            response2 = client.get("/file-session-test")
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["counter"] == 2

        finally:
            # Clean up
            import shutil

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def test_session_middleware_without_secret_key(self):
        """Test middleware behavior without secret key"""
        config = MakeConfig(secret_key=None, session=SessionConfig())  # No secret key
        set_config(config)

        app = NexiosApp()

        @app.get("/no-secret-test")
        async def no_secret_test(request: Request, response: Response):
            return response.json({"message": "no session"})

        app.add_middleware(SessionMiddleware())

        client = TestClient(app)

        response = client.get("/no-secret-test")
        assert response.status_code == 200

    def test_session_middleware_with_existing_cookie(self):
        """Test middleware with existing session cookie"""
        app = NexiosApp()

        @app.get("/existing-cookie-test")
        async def existing_cookie_test(request: Request, response: Response):
            # Set some session data
            request.session["existing"] = "data"
            return response.json({"existing": request.session["existing"]})

        app.add_middleware(SessionMiddleware())

        client = TestClient(app)

        # First request to set session
        response1 = client.get("/existing-cookie-test")
        assert response1.status_code == 200

        # Get the session cookie
        cookie = response1.cookies.get("test_session")
        assert cookie is not None

        # Second request with existing cookie
        response2 = client.get(
            "/existing-cookie-test", cookies={"test_session": cookie}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["existing"] == "data"

    def test_session_middleware_session_clear(self):
        """Test clearing session via middleware"""
        app = NexiosApp()

        @app.get("/clear-session-test")
        async def clear_session_test(request: Request, response: Response):
            if request.session.get("clear"):
                request.session.clear()
                return response.json({"cleared": True})
            else:
                request.session["clear"] = True
                return response.json({"set": True})

        app.add_middleware(SessionMiddleware())

        client = TestClient(app)

        # First request sets session data
        response1 = client.get("/clear-session-test")
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["set"] is True

        # Second request clears session
        response2 = client.get("/clear-session-test")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["cleared"] is True

    def test_session_middleware_configuration_options(self):
        """Test session middleware with various configuration options"""
        config = MakeConfig(
            secret_key="test-secret-key-config",
            session=SessionConfig(
                session_cookie_name="custom_session",
                session_cookie_path="/api",
                session_cookie_domain="example.com",
                session_cookie_secure=True,
                session_cookie_httponly=True,
                session_cookie_samesite="strict",
            ),
        )
        set_config(config)

        app = NexiosApp()

        @app.get("/config-test")
        async def config_test(request: Request, response: Response):
            request.session["test"] = "configured"
            return response.json({"configured": True})

        app.add_middleware(SessionMiddleware())

        client = TestClient(app)

        response = client.get("/config-test")
        assert response.status_code == 200

        # Check cookie configuration in headers
        cookie_header = response.headers.get("Set-Cookie", "")
        assert "custom_session" in cookie_header
        assert "Path=/api" in cookie_header
        assert "Domain=example.com" in cookie_header
        assert "Secure" in cookie_header
        assert "HttpOnly" in cookie_header
        assert "SameSite=strict" in cookie_header

    def test_session_middleware_error_handling(self):
        """Test middleware error handling"""
        app = NexiosApp()

        @app.get("/error-test")
        async def error_test(request: Request, response: Response):
            # Try to access session that might cause issues
            try:
                request.session["test"] = "value"
                return response.json({"success": True})
            except Exception as e:
                return response.json({"error": str(e)})

        app.add_middleware(SessionMiddleware())

        client = TestClient(app)

        response = client.get("/error-test")
        # Should handle gracefully and not crash
        assert response.status_code == 200
        data = response.json()
        assert "success" in data or "error" in data
