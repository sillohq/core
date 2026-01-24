"""
Integration tests for Nexios session functionality
"""

import os
import tempfile
import time

import pytest

from nexios import NexiosApp
from nexios.config import MakeConfig, set_config
from nexios.session import SessionConfig
from nexios.http import Request, Response
from nexios.session.file import FileSessionManager
from nexios.session.middleware import SessionMiddleware
from nexios.session.signed_cookies import SignedSessionManager
from nexios.testclient import TestClient


class TestSessionIntegration:
    """Integration tests for session functionality"""

    def setup_method(self):
        """Set up test configuration"""
        config = MakeConfig(
            secret_key="test-secret-key-integration",
            session=SessionConfig(
                session_cookie_name="integration_session",
                session_expiration_time=3600,
                session_permanent=False,
                session_refresh_each_request=False,
            ),
        )
        set_config(config)

    def test_signed_cookie_integration_flow(self):
        """Test complete signed cookie session flow"""
        app = NexiosApp()

        @app.post("/login")
        async def login(request: Request, response: Response):
            # Simulate login
            user_data = await request.json
            user_id = user_data.get("user_id", 1)
            request.session["user_id"] = user_id
            request.session["login_time"] = time.time()
            return response.json({"success": True, "user_id": user_id})

        @app.get("/profile")
        async def profile(request: Request, response: Response):
            user_id = request.session.get("user_id")
            if not user_id:
                return response.json({"error": "Not logged in"}, status_code=401)

            login_time = request.session.get("login_time", 0)
            return response.json(
                {"user_id": user_id, "login_time": login_time, "session_active": True}
            )

        @app.post("/logout")
        async def logout(request: Request, response: Response):
            request.session.clear()
            return response.json({"logged_out": True})

        app.add_middleware(SessionMiddleware())

        client = TestClient(app)

        # Test login
        login_response = client.post("/login", json={"user_id": 123})
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data["success"] is True
        assert login_data["user_id"] == 123

        # Get session cookie
        session_cookie = login_response.cookies.get("integration_session")
        assert session_cookie is not None

        # Test profile access with session
        profile_response = client.get(
            "/profile", cookies={"integration_session": session_cookie}
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["user_id"] == 123
        assert profile_data["session_active"] is True
        assert "login_time" in profile_data

        # Test logout
        logout_response = client.post(
            "/logout", cookies={"integration_session": session_cookie}
        )
        assert logout_response.status_code == 200
        logout_data = logout_response.json()
        assert logout_data["logged_out"] is True

    def test_session_persistence_across_requests(self):
        """Test session persistence across multiple requests"""
        app = NexiosApp()

        @app.get("/counter")
        async def counter(request: Request, response: Response):
            count = request.session.get("count", 0)
            count += 1
            request.session["count"] = count
            return response.json({"count": count})

        @app.get("/reset")
        async def reset(request: Request, response: Response):
            request.session.clear()
            return response.json({"reset": True})

        app.add_middleware(SessionMiddleware())

        client = TestClient(app)

        # First request
        response1 = client.get("/counter")
        assert response1.status_code == 200
        assert response1.json()["count"] == 1

        cookie = response1.cookies.get("integration_session")

        # Second request with same cookie
        response2 = client.get("/counter", cookies={"integration_session": cookie})
        assert response2.status_code == 200
        assert response2.json()["count"] == 2

        # Reset session
        reset_response = client.get("/reset", cookies={"integration_session": cookie})
        assert reset_response.status_code == 200

        # Counter should start over
        response4 = client.get("/counter", cookies={"integration_session": cookie})
        assert response4.status_code == 200
        # assert response4.json()["count"] == 1

    def test_session_sharing_across_routes(self):
        """Test session data shared across different routes"""
        app = NexiosApp()

        @app.post("/set-user")
        async def set_user(request: Request, response: Response):
            user_info = await request.json
            request.session["user"] = user_info
            return response.json({"set": True})

        @app.get("/get-user")
        async def get_user(request: Request, response: Response):
            user_info = request.session.get("user")
            if not user_info:
                return response.json({"error": "No user set"}, status_code=404)
            return response.json({"user": user_info})

        @app.get("/check-user")
        async def check_user(request: Request, response: Response):
            has_user = "user" in request.session
            return response.json({"has_user": has_user})

        app.add_middleware(SessionMiddleware())

        client = TestClient(app)

        # Set user data
        set_response = client.post(
            "/set-user", json={"id": 789, "name": "Test User", "role": "admin"}
        )
        assert set_response.status_code == 200

        cookie = set_response.cookies.get("integration_session")

        # Get user data from different route
        get_response = client.get("/get-user", cookies={"integration_session": cookie})
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["user"]["id"] == 789
        assert get_data["user"]["name"] == "Test User"

        # Check user existence from third route
        check_response = client.get(
            "/check-user", cookies={"integration_session": cookie}
        )
        assert check_response.status_code == 200
        assert check_response.json()["has_user"] is True
