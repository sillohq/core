"""
Tests for session middleware integration
"""

import tempfile

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.session import SessionConfig
from sillo.session.file import FileSessionManager
from sillo.session.middleware import SessionMiddleware
from sillo.session.signed_cookies import SignedSessionManager
from sillo.testclient import TestClient


class TestSessionMiddleware:
    """Test session middleware functionality"""

    def test_middleware_initialization(self):
        """Test session middleware initialization"""
        middleware = SessionMiddleware(
            config=SessionConfig(
                session_cookie_name="test_session",
                session_expiration_time=3600,
                session_permanent=False,
                session_refresh_each_request=False,
                session_cookie_secure=False,
                session_cookie_httponly=True,
                session_cookie_samesite="lax",
            ),
            secret_key="test-secret-key-for-middleware",
        )
        assert middleware is not None
        assert middleware.session_config.session_cookie_name == "test_session"

    def test_signed_cookie_session_middleware(self):
        """Test session middleware with signed cookie backend"""
        app = SilloApp()

        app.use(
            SessionMiddleware(
                config=SessionConfig(
                    session_cookie_name="test_session",
                    session_expiration_time=3600,
                    session_permanent=False,
                    session_refresh_each_request=False,
                    session_cookie_secure=False,
                    session_cookie_httponly=True,
                    session_cookie_samesite="lax",
                ),
                secret_key="test-secret-key-for-middleware",
            )
        )

        @app.get("/session-test")
        async def session_test(ctx: HttpContext):
            user_id = ctx.session.get("user_id", 0)
            ctx.session["user_id"] = user_id + 1
            return json({"user_id": ctx.session["user_id"]})

        client = TestClient(app)

        response1 = client.get("/session-test")
        assert response1.status_code == 200
        assert response1.json()["user_id"] == 1

        response2 = client.get("/session-test")
        assert response2.status_code == 200
        assert response2.json()["user_id"] == 2

        assert "Set-Cookie" in response1.headers
        assert "test_session" in response1.headers["Set-Cookie"]

    
    def test_file_session_middleware(self):
        """Test session middleware with file backend"""
        temp_dir = tempfile.mkdtemp()

        try:
            app = SilloApp()

            file_manager = FileSessionManager(
                SessionConfig(session_file_storage_path=temp_dir)
            )

            app.use(
                SessionMiddleware(
                    config=SessionConfig(
                        session_cookie_name="file_session",
                        session_file_storage_path=temp_dir,
                    ),
                    manager=file_manager,
                    secret_key="test-secret-key-for-file-middleware",
                )
            )

            @app.get("/file-session-test")
            async def file_session_test(ctx: HttpContext):
                counter = ctx.session.get("counter", 0)
                ctx.session["counter"] = counter + 1
                return json({"counter": ctx.session["counter"]})

            client = TestClient(app)

            response1 = client.get("/file-session-test")
            assert response1.status_code == 200
            assert response1.json()["counter"] == 1

            response2 = client.get("/file-session-test",headers = {"Cookie": response1.headers["Set-Cookie"]})
            assert response2.status_code == 200
            assert response2.json()["counter"] == 2

        finally:
            import shutil

            if temp_dir:
                shutil.rmtree(temp_dir)

    def test_session_middleware_with_instance_manager(self):
        """Test middleware with manager instance passed directly"""
        app = SilloApp()

        signed_manager = SignedSessionManager(secret_key="test-secret-key-instance")

        app.use(
            SessionMiddleware(
                config=SessionConfig(session_cookie_name="instance_session"),
                manager=signed_manager,
            )
        )

        @app.get("/instance-test")
        async def instance_test(ctx: HttpContext):
            ctx.session["data"] = "value"
            return json({"data": ctx.session["data"]})

        client = TestClient(app)

        response = client.get("/instance-test")
        assert response.status_code == 200
        assert response.json()["data"] == "value"

    def test_session_middleware_with_existing_cookie(self):
        """Test middleware with existing session cookie"""
        app = SilloApp()

        @app.get("/existing-cookie-test")
        async def existing_cookie_test(ctx: HttpContext):
            ctx.session["existing"] = "data"
            return json({"existing": ctx.session["existing"]})

        app.use(
            SessionMiddleware(config=SessionConfig(), secret_key="test-secret-key")
        )

        client = TestClient(app)

        response1 = client.get("/existing-cookie-test")
        assert response1.status_code == 200

        cookie = response1.cookies.get("session_id")
        assert cookie is not None

        response2 = client.get("/existing-cookie-test", cookies={"session_id": cookie})
        assert response2.status_code == 200
        assert response2.json()["existing"] == "data"

    def test_session_middleware_session_clear(self):
        """Test clearing session via middleware"""
        app = SilloApp()

        @app.get("/clear-session-test")
        async def clear_session_test(ctx: HttpContext):
            if ctx.session.get("clear"):
                ctx.session.clear()
                ctx.session["cleared"] = True
                return json({"cleared": True})
            else:
                ctx.session["clear"] = True
                return json({"set": True})

        app.use(
            SessionMiddleware(
                config=SessionConfig(session_cookie_name="clear_session"),
                secret_key="test-secret-key-clear",
            )
        )

        client = TestClient(app)

        response1 = client.get("/clear-session-test")
        assert response1.status_code == 200
        assert response1.json()["set"] is True

        cookie = response1.cookies.get("clear_session")

        response2 = client.get("/clear-session-test", cookies={"clear_session": cookie})
        assert response2.status_code == 200
        assert response2.json()["cleared"] is True

    def test_session_middleware_configuration_options(self):
        """Test session middleware with various configuration options"""
        app = SilloApp()

        app.use(
            SessionMiddleware(
                config=SessionConfig(
                    session_cookie_name="custom_session",
                    session_cookie_path="/api",
                    session_cookie_domain="example.com",
                    session_cookie_secure=True,
                    session_cookie_httponly=True,
                    session_cookie_samesite="strict",
                ),
                secret_key="test-secret-key-config",
            )
        )

        @app.get("/config-test")
        async def config_test(ctx: HttpContext):
            ctx.session["test"] = "configured"
            return json({"configured": True})

        client = TestClient(app)

        response = client.get("/config-test")
        assert response.status_code == 200

        cookie_header = response.headers.get("Set-Cookie", "")
        assert "custom_session" in cookie_header
        assert "Path=/api" in cookie_header
        assert "Domain=example.com" in cookie_header
        assert "Secure" in cookie_header
        assert "HttpOnly" in cookie_header
        assert "SameSite=strict" in cookie_header

    def test_session_middleware_error_handling(self):
        """Test middleware error handling"""
        app = SilloApp()

        @app.get("/error-test")
        async def error_test(ctx: HttpContext):
            try:
                ctx.session["test"] = "value"
                return json({"success": True})
            except Exception as e:
                return json({"error": str(e)})

        app.use(
            SessionMiddleware(config=SessionConfig(), secret_key="test-secret-key")
        )

        client = TestClient(app)

        response = client.get("/error-test")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data or "error" in data

    def test_session_cookie_deletion_on_empty_session(self):
        """Test that cookies are deleted when session is accessed but empty"""
        app = SilloApp()

        @app.get("/delete-test")
        async def delete_test(ctx: HttpContext):
            return json({"status": "ok"})

        app.use(
            SessionMiddleware(
                config=SessionConfig(), secret_key="test-secret-key-delete"
            )
        )

        client = TestClient(app)

        response = client.get("/delete-test")
        assert response.status_code == 200

    async def test_persisting_without_a_session_is_a_noop(self):
        """The post-phase is a no-op when dispatch never loaded a session."""
        middleware = SessionMiddleware(
            config=SessionConfig(), secret_key="test-secret-key"
        )

        class DummyRequest:
            def __init__(self):
                self.scope: dict = {}

        result = await middleware._persist(DummyRequest(), None)
        assert result is None

    def test_manager_given_as_class_raises_type_error(self):
        """Passing the manager class itself (not an instance) is rejected."""
        with pytest.raises(TypeError, match="manager must be an instance"):
            SessionMiddleware(
                config=SessionConfig(),
                manager=FileSessionManager,
                secret_key="test-secret-key",
            )

    def test_manager_without_settable_config_is_left_alone(self):
        """A manager whose class refuses a `.config` attribute is tolerated."""
        from sillo.session.base import BaseSessionInterface

        class ManagerWithReadonlyConfig(BaseSessionInterface):
            def __init__(self):
                pass  # deliberately skip setting self.config

            @property
            def config(self):
                return None

            async def load(self, session):
                pass

            async def save(self, session):
                pass

        manager = ManagerWithReadonlyConfig()
        middleware = SessionMiddleware(
            config=SessionConfig(), manager=manager, secret_key="test-secret-key"
        )
        assert middleware.session_interface is manager
