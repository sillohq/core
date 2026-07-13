"""
JWT Authentication Backend Tests

This module tests the JWT authentication backend including:
- Valid token authentication
- Missing/invalid/expired tokens
- User loading failures
- Custom identifier fields
"""

from datetime import datetime, timedelta, timezone
from functools import partial

import pytest

from sillo.application import silloApp
from sillo.auth import (
    AuthenticationMiddleware,
    BaseUser,
    JWTAuthBackend,
    auth,
    create_jwt,
    decode_jwt,
)
from sillo.auth.users.simple import SimpleUser
from sillo.http import Request, Response
from sillo.testclient import AsyncTestClient


# Test User Model for authentication
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


SECRET = "test_secret_key_1234567890123456"


@pytest.fixture
def test_client():
    return partial(AsyncTestClient)


@pytest.fixture
def jwt_payload():
    return {"id": "1", "username": "testuser", "roles": ["read", "write"]}


@pytest.fixture
def valid_jwt_token(jwt_payload):
    return create_jwt(jwt_payload, SECRET)


@pytest.fixture
def expired_jwt_token(jwt_payload):
    expired_payload = {**jwt_payload, "exp": 1}
    return create_jwt(expired_payload, SECRET)


@pytest.fixture
def invalid_jwt_token():
    return "invalid.jwt.token"


async def test_jwt_auth_backend_success(test_client, valid_jwt_token):
    app = silloApp()
    jwt_backend = JWTAuthBackend(secret_key=SECRET)
    app.use(AuthenticationMiddleware(TestUser, jwt_backend))

    @app.get("/protected")
    @auth("jwt")
    async def protected_route(req: Request, res: Response):
        return res.json(
            {"user_id": req.user.identity, "username": req.user.display_name}
        )

    client = test_client(app)
    async with client:
        res = await client.get(
            "/protected", headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "1"
        assert data["username"] == "testuser"


async def test_jwt_auth_backend_missing_header(test_client):
    app = silloApp()
    jwt_backend = JWTAuthBackend(secret_key=SECRET)
    app.use(AuthenticationMiddleware(TestUser, jwt_backend))

    @app.get("/protected")
    @auth("jwt")
    async def protected_route(req: Request, res: Response):
        return res.json(
            {"user_id": req.user.identity, "username": req.user.display_name}
        )

    client = test_client(app)
    async with client:
        res = await client.get(
            "/protected", headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "1"
        assert data["username"] == "testuser"


async def test_jwt_auth_backend_missing_header(test_client):
    app = silloApp()
    jwt_backend = JWTAuthBackend(secret_key=SECRET)
    app.use(AuthenticationMiddleware(TestUser, jwt_backend))

    @app.get("/protected")
    @auth("jwt")
    async def protected(req: Request, res: Response):
        return res.json({"user": req.user})

    client = test_client(app)
    async with client:
        res = await client.get("/protected")
        assert res.status_code == 401


async def test_jwt_auth_backend_invalid_header_format(test_client):
    app = silloApp()
    jwt_backend = JWTAuthBackend(secret_key=SECRET)
    app.use(AuthenticationMiddleware(TestUser, jwt_backend))

    @app.get("/protected")
    @auth("jwt")
    async def protected(req: Request, res: Response):
        return res.json({"user": req.user})

    client = test_client(app)
    async with client:
        res = await client.get("/protected", headers={"Authorization": "token123"})
        assert res.status_code == 401


async def test_jwt_auth_backend_invalid_token(test_client, invalid_jwt_token):
    app = silloApp()
    jwt_backend = JWTAuthBackend(secret_key=SECRET)
    app.use(AuthenticationMiddleware(TestUser, jwt_backend))

    @app.get("/protected")
    @auth("jwt")
    async def protected(req: Request, res: Response):
        return res.json({"user": req.user})

    client = test_client(app)
    async with client:
        res = await client.get(
            "/protected", headers={"Authorization": f"Bearer {invalid_jwt_token}"}
        )
        assert res.status_code == 401


async def test_jwt_auth_backend_expired_token(test_client, expired_jwt_token):
    app = silloApp()
    jwt_backend = JWTAuthBackend(secret_key=SECRET)
    app.use(AuthenticationMiddleware(TestUser, jwt_backend))

    @app.get("/protected")
    @auth("jwt")
    async def protected(req: Request, res: Response):
        return res.json({"user": req.user})

    client = test_client(app)
    async with client:
        res = await client.get(
            "/protected", headers={"Authorization": f"Bearer {expired_jwt_token}"}
        )
        assert res.status_code == 401


async def test_jwt_auth_backend_user_not_found(test_client):
    app = silloApp()
    jwt_backend = JWTAuthBackend(secret_key=SECRET)
    app.use(AuthenticationMiddleware(TestUser, jwt_backend))

    @app.get("/protected")
    @auth("jwt")
    async def protected(req: Request, res: Response):
        return res.json({"user": req.user})

    payload = {"id": "999", "username": "ghost"}
    token = create_jwt(payload, SECRET)

    client = test_client(app)
    async with client:
        res = await client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401


async def test_jwt_auth_backend_wrong_identifier_field(test_client):
    app = silloApp()
    jwt_backend = JWTAuthBackend(identifier="user_id", secret_key=SECRET)
    app.use(AuthenticationMiddleware(TestUser, jwt_backend))

    @app.get("/protected")
    @auth("jwt")
    async def protected(req: Request, res: Response):
        return res.json({"user": req.user})

    payload = {"user_id": "1", "username": "testuser"}
    token = create_jwt(payload, SECRET)

    client = test_client(app)
    async with client:
        res = await client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
