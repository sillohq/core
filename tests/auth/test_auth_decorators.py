"""
Authentication Decorator Tests

This module tests:
- @auth decorator (single/multiple scopes)
- @has_permission decorator (single/multiple permissions)
- Edge cases (unauthenticated, invalid scope/permissions)
"""

from functools import partial

import pytest

from nexios.application import NexiosApp
from nexios.auth import AuthenticationMiddleware, BaseUser, auth, has_permission
from nexios.auth.backends.base import AuthenticationBackend
from nexios.auth.model import AuthResult
from nexios.auth.users.simple import SimpleUser, UnauthenticatedUser
from nexios.http import Request, Response
from nexios.testclient import AsyncTestClient

# --------------------------------------------------------------------------
# Test User Model
# --------------------------------------------------------------------------


class TestUser(BaseUser):
    def __init__(
        self,
        user_id: str,
        username: str,
        roles: list = None,
        is_authenticated: bool = True,
    ):
        self.user_id = user_id
        self.username = username
        self.roles = roles or []
        self._is_authenticated = is_authenticated

    @property
    def is_authenticated(self) -> bool:
        return self._is_authenticated

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def identity(self) -> str:
        return self.user_id

    def has_permission(self, permission: str) -> bool:
        return permission in self.roles

    @classmethod
    async def load_user(cls, identity: str):
        users_db = {
            "1": cls("1", "testuser", ["read", "write"]),
            "2": cls("2", "admin", ["read", "write", "admin", "delete"]),
            "3": cls("3", "guest", ["read"]),
            "4": cls("4", "banned", [], False),
        }
        return users_db.get(str(identity))


# --------------------------------------------------------------------------
# Fixture
# --------------------------------------------------------------------------


@pytest.fixture
def test_client():
    return partial(AsyncTestClient)


# --------------------------------------------------------------------------
# Auth Decorator Tests
# --------------------------------------------------------------------------


async def test_auth_decorator_single_scope(test_client):
    app = NexiosApp()

    class TestBackend(AuthenticationBackend):
        async def authenticate(self, request: Request, response):
            if request.headers.get("X-Auth") == "valid":
                return AuthResult(success=True, identity="test_user", scope="test")
            return AuthResult(success=False, identity="", scope="")

    app.add_middleware(AuthenticationMiddleware(SimpleUser, TestBackend()))

    @app.get("/protected")
    @auth("test")
    async def protected(req: Request, res: Response):
        return res.json({"authenticated": True})

    async with test_client(app) as client:
        res = await client.get("/protected", headers={"X-Auth": "valid"})
        assert res.status_code == 200

        res = await client.get("/protected")
        assert res.status_code == 401


async def test_auth_decorator_no_scopes(test_client):
    app = NexiosApp()

    class AnyBackend(AuthenticationBackend):
        async def authenticate(self, request: Request, response):
            if request.headers.get("X-Auth") == "any_valid":
                return AuthResult(success=True, identity="any_user", scope="any")
            return AuthResult(success=False, identity="", scope="")

    app.add_middleware(AuthenticationMiddleware(SimpleUser, AnyBackend()))

    @app.get("/protected")
    @auth()
    async def protected(req: Request, res: Response):
        return res.json({"authenticated": True})

    async with test_client(app) as client:
        res = await client.get("/protected", headers={"X-Auth": "any_valid"})
        assert res.status_code == 200


# --------------------------------------------------------------------------
# Permission Decorator Tests
# --------------------------------------------------------------------------


async def test_has_permission_single_permission(test_client):
    app = NexiosApp()

    class TestBackend(AuthenticationBackend):
        async def authenticate(self, request: Request, response):
            if request.headers.get("X-Auth") == "valid":
                return AuthResult(success=True, identity="1", scope="test")
            return AuthResult(success=False, identity="", scope="")

    app.add_middleware(AuthenticationMiddleware(TestUser, TestBackend()))

    @app.get("/read")
    @has_permission("read")
    async def read(req: Request, res: Response):
        return res.json({"access": "read"})

    @app.get("/admin")
    @has_permission("admin")
    async def admin(req: Request, res: Response):
        return res.json({"access": "admin"})

    async with test_client(app) as client:
        res = await client.get("/read", headers={"X-Auth": "valid"})
        assert res.status_code == 200

        res = await client.get("/admin", headers={"X-Auth": "valid"})
        assert res.status_code == 403


async def test_has_permission_multiple_permissions(test_client):
    app = NexiosApp()

    class TestBackend(AuthenticationBackend):
        async def authenticate(self, request: Request, response):
            if request.headers.get("X-Auth") == "valid":
                return AuthResult(success=True, identity="1", scope="test")
            return AuthResult(success=False, identity="", scope="")

    app.add_middleware(AuthenticationMiddleware(TestUser, TestBackend()))

    @app.get("/multi")
    @has_permission(["read", "write"])
    async def multi(req: Request, res: Response):
        return res.json({"access": "multi"})

    async with test_client(app) as client:
        res = await client.get("/multi", headers={"X-Auth": "valid"})
        assert res.status_code == 200

        class GuestBackend(AuthenticationBackend):
            async def authenticate(self, request: Request, response):
                if request.headers.get("X-Auth") == "guest":
                    return AuthResult(success=True, identity="3", scope="test")
                return AuthResult(success=False, identity="", scope="")

        app.add_middleware(AuthenticationMiddleware(TestUser, GuestBackend()))
        res = await client.get("/multi", headers={"X-Auth": "guest"})
        assert res.status_code == 403


async def test_has_permission_no_permissions(test_client):
    app = NexiosApp()

    class TestBackend(AuthenticationBackend):
        async def authenticate(self, request: Request, response):
            if request.headers.get("X-Auth") == "valid":
                return AuthResult(success=True, identity="1", scope="test")
            return AuthResult(success=False, identity="", scope="")

    app.add_middleware(AuthenticationMiddleware(TestUser, TestBackend()))

    @app.get("/any")
    @has_permission()
    async def any(req: Request, res: Response):
        return res.json({"access": "any"})

    async with test_client(app) as client:
        res = await client.get("/any", headers={"X-Auth": "valid"})
        assert res.status_code == 200


async def test_has_permission_unauthenticated_user(test_client):
    app = NexiosApp()

    class DummyMiddleware(AuthenticationMiddleware):
        def __init__(self):
            super().__init__(TestUser, AuthenticationBackend())

        async def process_request(
            self, request: Request, response: Response, call_next
        ):
            request.scope["user"] = UnauthenticatedUser()
            request.scope["auth"] = None
            return await call_next()

    app.add_middleware(DummyMiddleware())

    @app.get("/protected")
    @has_permission("read")
    async def protected(req: Request, res: Response):
        return res.json({"access": True})

    async with test_client(app) as client:
        res = await client.get("/protected")
        assert res.status_code == 403
