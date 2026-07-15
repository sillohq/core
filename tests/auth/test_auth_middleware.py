"""
Authentication Middleware Tests

This module tests the authentication middleware including:
- Multiple backends processing
- Error handling in backends
- User loading failures
- Backend fallback scenarios
"""

from functools import partial

import pytest

from sillo.application import silloApp
from sillo.auth import AuthenticationMiddleware, BaseUser, auth
from sillo.auth.backends.base import AuthenticationBackend
from sillo.auth.model import AuthResult
from sillo.users import SimpleUser, UnauthenticatedUser
from sillo.http import Request, Response
from sillo.testclient import AsyncTestClient


# -------------------------
# Fixtures
# -------------------------
@pytest.fixture
def test_client():
    return partial(AsyncTestClient)


# -------------------------
# Mock Users
# -------------------------
class TestUser(BaseUser):
    __test__ = False
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
    def is_authenticated(self):
        return self._is_authenticated

    @property
    def display_name(self):
        return self.username

    @property
    def identity(self):
        return self.user_id

    def has_permission(self, permission: str):
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


class CustomUser(BaseUser):

    def __init__(self, user_id: str, username: str):
        self.user_id = user_id
        self.username = username

    @classmethod
    async def load_user(cls, identity: str):
        if identity == "fail_user":
            raise Exception("User loading failed")
        return cls("1", "test")

    @property
    def is_authenticated(self):
        return True

    @property
    def display_name(self):
        return "test"

    @property
    def identity(self):
        return "1"

    def has_permission(self, permission: str):
        return False


# -------------------------
# Tests
# -------------------------


async def test_auth_middleware_multiple_backends_success(test_client):
    app = silloApp()
    client = test_client(app)

    class FirstBackend(AuthenticationBackend):
        async def authenticate(self, request: Request):
            if request.headers.get("X-First-Auth") == "first_valid":
                return AuthResult(success=True, identity="first_user", scope="first")
            return AuthResult(success=False, identity="", scope="")

    class SecondBackend(AuthenticationBackend):
        async def authenticate(self, request: Request):
            if request.headers.get("X-Second-Auth") == "second_valid":
                return AuthResult(success=True, identity="second_user", scope="second")
            return AuthResult(success=False, identity="", scope="")

    app.use(
        AuthenticationMiddleware(SimpleUser, [FirstBackend(), SecondBackend()])
    )

    @app.get("/protected")
    @auth("first")
    async def protected_route(req: Request, res: Response):
        return res.json(
            {"user_id": req.user.identity, "auth_method": req.scope.get("auth")}
        )

    async with client:
        res = await client.get("/protected", headers={"X-First-Auth": "first_valid"})
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "first_user"
        assert data["auth_method"] == "first"


async def test_auth_middleware_multiple_backends_fallback(test_client):
    app = silloApp()
    client = test_client(app)

    class FirstBackend(AuthenticationBackend):
        async def authenticate(self, request: Request):
            return AuthResult(success=False, identity="", scope="")

    class SecondBackend(AuthenticationBackend):
        async def authenticate(self, request: Request):
            if request.headers.get("X-Second-Auth") == "second_valid":
                return AuthResult(success=True, identity="second_user", scope="second")
            return AuthResult(success=False, identity="", scope="")

    app.use(
        AuthenticationMiddleware(SimpleUser, [FirstBackend(), SecondBackend()])
    )

    @app.get("/protected")
    @auth("second")
    async def protected_route(req: Request, res: Response):
        return res.json({"user_id": req.user.identity})

    async with client:
        res = await client.get("/protected", headers={"X-Second-Auth": "second_valid"})
        assert res.status_code == 200
        assert res.json()["user_id"] == "second_user"


async def test_auth_middleware_no_backends_succeed(test_client):
    app = silloApp()
    client = test_client(app)

    class FailingBackend(AuthenticationBackend):
        async def authenticate(self, request: Request):
            return AuthResult(success=False, identity="", scope="")

    app.use(AuthenticationMiddleware(TestUser, FailingBackend()))

    @app.get("/protected")
    @auth("jwt")
    async def protected_route(req: Request, res: Response):
        return res.json({"user": req.user})

    async with client:
        res = await client.get("/protected")
        assert res.status_code == 401


async def test_auth_middleware_user_loading_failure(test_client):
    app = silloApp()
    client = test_client(app)

    from sillo.auth import JWTAuthBackend, create_jwt

    jwt_backend = JWTAuthBackend(secret_key="a-test-jwt-secret-key-for-hs256")
    app.use(AuthenticationMiddleware(CustomUser, jwt_backend))

    @app.get("/protected")
    @auth("jwt")
    async def protected_route(req: Request, res: Response):
        return res.json({"user": req.user})

    payload = {"id": "fail_user"}
    token = create_jwt(payload, "a-test-jwt-secret-key-for-hs256")

    async with client:
        res = await client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401


async def test_auth_middleware_backend_exception_handling(test_client):
    app = silloApp()
    client = test_client(app)

    class FaultyAuthBackend(AuthenticationBackend):
        async def authenticate(self, request: Request):
            raise Exception("Backend error")

    class WorkingAuthBackend(AuthenticationBackend):
        async def authenticate(self, request: Request):
            if request.headers.get("X-Backup-Auth") == "backup_valid":
                return AuthResult(success=True, identity="backup_user", scope="backup")
            return AuthResult(success=False, identity="", scope="")

    app.use(
        AuthenticationMiddleware(
            SimpleUser, [FaultyAuthBackend(), WorkingAuthBackend()]
        )
    )

    @app.get("/protected")
    @auth("backup")
    async def protected_route(req: Request, res: Response):
        return res.json({"user_id": req.user.identity})

    async with client:
        res = await client.get("/protected", headers={"X-Backup-Auth": "backup_valid"})
        assert res.status_code == 200
        assert res.json()["user_id"] == "backup_user"
