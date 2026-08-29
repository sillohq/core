"""
Integration tests for sillo session functionality
"""

import time

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.session import SessionConfig
from sillo.session.middleware import SessionMiddleware
from sillo.testclient import TestClient


class TestSessionIntegration:
    """Integration tests for session functionality"""

    def test_signed_cookie_integration_flow(self):
        """Test complete signed cookie session flow"""
        app = SilloApp()

        @app.post("/login")
        async def login(request: HttpContext):
            user_data = await request.json
            user_id = user_data.get("user_id", 1)
            request.session["user_id"] = user_id
            request.session["login_time"] = time.time()
            return json({"success": True, "user_id": user_id})

        @app.get("/profile")
        async def profile(request: HttpContext):
            user_id = request.session.get("user_id")
            if not user_id:
                return json({"error": "Not logged in"}, status_code=401)

            login_time = request.session.get("login_time", 0)
            return json(
                {"user_id": user_id, "login_time": login_time, "session_active": True}
            )

        @app.post("/logout")
        async def logout(request: HttpContext):
            request.session.clear()
            return json({"logged_out": True})

        app.use(
            SessionMiddleware(
                config=SessionConfig(session_cookie_name="test_session"),
                secret_key="test-secret-key-integration",
            )
        )

        client = TestClient(app)

        login_response = client.post("/login", json={"user_id": 123})
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data["success"] is True
        assert login_data["user_id"] == 123

        session_cookie = login_response.cookies.get("test_session")
        assert session_cookie is not None

        profile_response = client.get(
            "/profile", cookies={"test_session": session_cookie}
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["user_id"] == 123
        assert profile_data["session_active"] is True
        assert "login_time" in profile_data

        logout_response = client.post(
            "/logout", cookies={"test_session": session_cookie}
        )
        assert logout_response.status_code == 200
        logout_data = logout_response.json()
        assert logout_data["logged_out"] is True

    def test_session_persistence_across_requests(self):
        """Test session persistence across multiple requests"""
        app = SilloApp()

        @app.get("/counter")
        async def counter(request: HttpContext):
            count = request.session.get("count", 0)
            count += 1
            request.session["count"] = count
            return json({"count": count})

        @app.get("/reset")
        async def reset(request: HttpContext):
            request.session.clear()
            return json({"reset": True})

        app.use(
            SessionMiddleware(
                config=SessionConfig(), secret_key="test-secret-key-integration"
            )
        )

        client = TestClient(app)

        response1 = client.get("/counter")
        assert response1.status_code == 200
        assert response1.json()["count"] == 1

        response2 = client.get("/counter",headers = {"Cookie": response1.headers["Set-Cookie"]})
        assert response2.status_code == 200
        assert response2.json()["count"] == 2

        response3 = client.get("/reset",headers = {"Cookie": response2.headers["Set-Cookie"]})
        assert response3.status_code == 200

        response4 = client.get("/counter",headers = {"Cookie": response3.headers["Set-Cookie"]})
        assert response4.status_code == 200
        assert response4.json()["count"] == 1
