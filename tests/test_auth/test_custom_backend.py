"""
Custom Authentication Backend Tests

This module tests custom authentication backends including:
- Custom backend implementation
- Backend failure scenarios
- Integration with middleware
"""

from functools import partial

import pytest

from sillo.application import SilloApp
from sillo import json
from sillo.auth import AuthenticationMiddleware, BaseUser, useAuth
from sillo.auth.backend import AuthenticationBackend
from sillo.auth.model import AuthResult
from sillo.users import SimpleUser
from sillo.core.http import HttpContext
from sillo.testclient import AsyncTestClient


# -------------------------
# Fixtures
# -------------------------
@pytest.fixture
def test_client():
    return partial(AsyncTestClient)


# -------------------------
# Custom Test User
# -------------------------
class CustomTestUser(BaseUser):
    def __init__(self, user_id: str, username: str, permissions: list = None):
        self.user_id = user_id
        self.username = username
        self.permissions = permissions or []

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def identity(self) -> str:
        return self.user_id

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    @classmethod
    async def load_user(cls, identity: str):
        users_db = {
            "custom1": cls("custom1", "customuser", ["custom_read", "custom_write"]),
            "custom2": cls(
                "custom2",
                "customadmin",
                ["custom_read", "custom_write", "custom_admin"],
            ),
        }
        return users_db.get(str(identity))


# -------------------------
# Tests
# -------------------------


async def test_custom_auth_backend_success(test_client):
    app = SilloApp()
    client = test_client(app)

    class CustomAuthBackend(AuthenticationBackend):
        async def authenticate(self, request: HttpContext):
            auth_header = request.headers.get("X-Custom-Auth")
            if auth_header == "valid_token_123":
                return AuthResult(success=True, identity="custom1", scope="custom")
            return AuthResult(success=False, identity="", scope="")

    app.use(AuthenticationMiddleware(CustomTestUser, CustomAuthBackend()))

    @app.get("/protected", auth=useAuth(schemes=["custom"]))
    async def protected_route(req: HttpContext):
        return json(
            {"user_id": req.user.identity, "permissions": req.user.permissions}
        )

    async with client:
        res = await client.get(
            "/protected", headers={"X-Custom-Auth": "valid_token_123"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "custom1"
        assert "custom_read" in data["permissions"]


async def test_custom_auth_backend_failure(test_client):
    app = SilloApp()
    client = test_client(app)

    class CustomAuthBackend(AuthenticationBackend):
        async def authenticate(self, request: HttpContext):
            auth_header = request.headers.get("X-Custom-Auth")
            if auth_header == "valid_token_123":
                return AuthResult(success=True, identity="custom1", scope="custom")
            return AuthResult(success=False, identity="", scope="")

    app.use(AuthenticationMiddleware(CustomTestUser, CustomAuthBackend()))

    @app.get("/protected", auth=useAuth(schemes=["custom"]))
    async def protected_route(req: HttpContext):
        return json({"user": req.user})

    async with client:
        res = await client.get("/protected", headers={"X-Custom-Auth": "invalid_token"})
        assert res.status_code == 401


async def test_custom_auth_backend_exception_handling(test_client):
    app = SilloApp()
    client = test_client(app)

    class FaultyAuthBackend(AuthenticationBackend):
        async def authenticate(self, request: HttpContext):
            raise Exception("Backend error")

    class WorkingAuthBackend(AuthenticationBackend):
        async def authenticate(self, request: HttpContext):
            if request.headers.get("X-Backup-Auth") == "backup_valid":
                return AuthResult(success=True, identity="backup_user", scope="backup")
            return AuthResult(success=False, identity="", scope="")

    app.use(
        AuthenticationMiddleware(
            SimpleUser, [FaultyAuthBackend(), WorkingAuthBackend()]
        )
    )

    @app.get("/protected", auth=useAuth(schemes=["backup"]))
    async def protected_route(req: HttpContext):
        return json({"user_id": req.user.identity})

    async with client:
        res = await client.get("/protected", headers={"X-Backup-Auth": "backup_valid"})
        assert res.status_code == 200
        assert res.json()["user_id"] == "backup_user"


async def test_custom_auth_backend_complex_logic(test_client):
    app = SilloApp()
    client = test_client(app)

    class ComplexAuthBackend(AuthenticationBackend):
        async def authenticate(self, request: HttpContext):
            api_key = request.headers.get("X-API-Key")
            token = request.headers.get("Authorization")
            user_param = request.query_params.get("user")

            if (
                api_key == "complex_key"
                and token == "Bearer complex_token"
                and user_param == "complex_user"
            ):
                return AuthResult(
                    success=True, identity="complex_user", scope="complex"
                )
            return AuthResult(success=False, identity="", scope="")

    app.use(AuthenticationMiddleware(SimpleUser, ComplexAuthBackend()))

    @app.get("/protected", auth=useAuth(schemes=["complex"]))
    async def protected_route(req: HttpContext):
        return json({"user_id": req.user.identity})

    async with client:
        # Valid case
        res = await client.get(
            "/protected?user=complex_user",
            headers={
                "X-API-Key": "complex_key",
                "Authorization": "Bearer complex_token",
            },
        )
        assert res.status_code == 200
        assert res.json()["user_id"] == "complex_user"

        # Invalid case
        res = await client.get("/protected")
        assert res.status_code == 401
