"""
API Key Authentication Backend Tests

This module tests the API key authentication backend including:
- Valid key authentication
- Missing/invalid keys
- Custom header names
"""

from functools import partial

import pytest

from sillo.application import silloApp
from sillo.auth import APIKeyAuthBackend, AuthenticationMiddleware, BaseUser, useAuth
from sillo.auth.apikey import create_api_key, verify_key
from sillo.auth.model import AuthResult
from sillo.users import SimpleUser
from sillo.core.http import Request, Response
from sillo.testclient import AsyncTestClient


@pytest.fixture
def test_client():
    return partial(AsyncTestClient)


@pytest.fixture
def api_key_data():
    api_key, hashed_key = create_api_key()
    return {"api_key": api_key, "hashed_key": hashed_key}


async def test_apikey_auth_backend_success(test_client, api_key_data):
    app = silloApp()
    client = test_client(app)

    class TestAPIKeyBackend(APIKeyAuthBackend):
        def __init__(self):
            super().__init__(header_name="X-API-Key")

        async def authenticate(self, request: Request):
            raw_token = request.headers.get(self.header_name)
            if not raw_token:
                return AuthResult(success=False, identity="", scope="")

            if verify_key(raw_token, api_key_data["hashed_key"]):
                return AuthResult(
                    success=True, identity="test_api_user", scope="apikey"
                )

            return AuthResult(success=False, identity="", scope="")

    app.use(AuthenticationMiddleware(SimpleUser, TestAPIKeyBackend()))

    @app.get("/protected", auth=useAuth(schemes=["apikey"]))
    async def protected_route(req: Request, res: Response):
        return res.json(
            {"user_id": req.user.identity, "username": req.user.display_name}
        )

    async with client:
        response = await client.get(
            "/protected", headers={"X-API-Key": api_key_data["api_key"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test_api_user"
        assert data["username"] == "test_api_user"


async def test_apikey_auth_backend_missing_header(test_client):
    app = silloApp()
    client = test_client(app)

    class TestAPIKeyBackend(APIKeyAuthBackend):
        async def authenticate(self, request: Request):
            raw_token = request.headers.get("X-API-Key")
            if not raw_token:
                return AuthResult(success=False, identity="", scope="")
            return AuthResult(success=True, identity="test", scope="apikey")

    app.use(AuthenticationMiddleware(SimpleUser, TestAPIKeyBackend()))

    @app.get("/protected", auth=useAuth(schemes=["apikey"]))
    async def protected_route(req: Request, res: Response):
        return res.json({"user": req.user})

    async with client:
        response = await client.get("/protected")
        assert response.status_code == 401


async def test_apikey_auth_backend_invalid_key(test_client):
    app = silloApp()
    client = test_client(app)

    class Store(SimpleUser):
        def __init__(self):
            super().__init__("test", "test")

        @classmethod
        async def load_user(cls, identity: str):
            if identity == "test_api_user":
                return cls("test_api_user", "test_api_user")
            return None

    app.use(AuthenticationMiddleware(Store, APIKeyAuthBackend()))

    @app.get("/protected", auth=useAuth(schemes=["apikey"]))
    async def protected_route(req: Request, res: Response):
        return res.json({"user": req.user})

    async with client:
        response = await client.get("/protected", headers={"X-API-Key": "invalid_key"})
        assert response.status_code == 401


async def test_apikey_auth_backend_custom_header(test_client):
    app = silloApp()
    client = test_client(app)

    class TestAPIKeyBackend(APIKeyAuthBackend):
        def __init__(self):
            super().__init__(header_name="X-Custom-API-Key")

        async def authenticate(self, request: Request):
            raw_token = request.headers.get(self.header_name)
            if not raw_token:
                return AuthResult(success=False, identity="", scope="")
            if raw_token == "valid_custom_key":
                return AuthResult(success=True, identity="custom_user", scope="apikey")
            return AuthResult(success=False, identity="", scope="")

    app.use(AuthenticationMiddleware(SimpleUser, TestAPIKeyBackend()))

    @app.get("/protected", auth=useAuth(schemes=["apikey"]))
    async def protected_route(req: Request, res: Response):
        return res.json({"user_id": req.user.identity})

    async with client:
        response = await client.get(
            "/protected", headers={"X-Custom-API-Key": "valid_custom_key"}
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == "custom_user"
