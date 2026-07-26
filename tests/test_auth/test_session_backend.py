"""
Session Authentication Backend Tests

This module tests the session authentication backend including:
- Valid session authentication
- Missing session scenarios
- Login/logout functionality
- Custom session keys
"""

from functools import partial

import pytest

from sillo.application import silloApp
from sillo.auth import AuthenticationMiddleware, BaseUser, auth
from sillo.auth.session_auth import SessionAuthBackend, login, logout
from sillo.core.http import Request, Response
from sillo.session.middleware import SessionMiddleware
from sillo.testclient import AsyncTestClient


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


@pytest.fixture
def test_client():
    return partial(AsyncTestClient)


async def test_session_auth_backend_success(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, [SessionAuthBackend()]))
    app.use(SessionMiddleware(secret_key="secret"))

    @app.post("/login")
    async def login_route(req: Request, res: Response):
        user = TestUser("1", "testuser", ["read", "write"])
        login(req, user)
        return res.json({"message": "logged in"})

    @app.get("/protected")
    @auth("session")
    async def protected(req: Request, res: Response):
        return res.json(
            {"user_id": req.user.identity, "username": req.user.display_name}
        )

    client = test_client(app)
    res_login = await client.post("/login")
    assert res_login.status_code == 200

    session = res_login.cookies.get("session_id")
    res_protected = await client.get("/protected", cookies={"session_id": session})
    assert res_protected.status_code == 200
    data = res_protected.json()
    assert data["user_id"] == "1"
    assert data["username"] == "testuser"


async def test_session_auth_backend_no_session(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, SessionAuthBackend()))
    app.use(SessionMiddleware(secret_key="secret"))

    @app.get("/protected")
    @auth("session")
    async def protected(req: Request, res: Response):
        return res.json({"user": req.user})

    client = test_client(app)
    async with client:
        res = await client.get("/protected")
        assert res.status_code == 401


async def test_session_auth_backend_missing_session_middleware(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, SessionAuthBackend()))

    @app.get("/protected")
    @auth("session")
    async def protected(req: Request, res: Response):
        return res.json({"user": req.user})

    client = test_client(app)
    async with client:
        res = await client.get("/protected")
        assert res.status_code == 401


async def test_session_auth_backend_logout(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, SessionAuthBackend()))
    app.use(SessionMiddleware(secret_key="secret"))

    @app.post("/login")
    async def login_route(req: Request, res: Response):
        user = TestUser("1", "testuser", ["read", "write"])
        login(req, user)
        return res.json({"message": "logged in"})

    @app.post("/logout")
    async def logout_route(req: Request, res: Response):
        logout(req)
        return res.json({"message": "logged out"})

    @app.get("/protected")
    @auth(["session"])
    async def protected(req: Request, res: Response):
        return res.json({"user_id": req.user.identity})

    client = test_client(app)
    async with client:
        login_res = await client.post("/login")
        res1 = await client.get(
            "/protected",
            headers={"Cookie": f"session_id={login_res.cookies.get('session_id')}"},
        )
        assert res1.status_code == 200

        logout_res = await client.post(
            "/logout",
            headers={"Cookie": f"session_id={login_res.cookies.get('session_id')}"},
        )
        res2 = await client.get(
            "/protected",
            headers={"Cookie": f"session_id={logout_res.cookies.get('session_id')}"},
        )
        assert res2.status_code == 401


async def test_session_auth_backend_custom_session_key(test_client):
    app = silloApp()
    app.use(
        AuthenticationMiddleware(
            TestUser, SessionAuthBackend(session_key="custom_user")
        )
    )
    app.use(SessionMiddleware(secret_key="secret"))

    @app.post("/login")
    async def login_route(req: Request, res: Response):
        user = TestUser("1", "testuser", ["read", "write"])
        req.session["custom_user"] = {
            "id": user.identity,
            "display_name": user.display_name,
        }
        return res.json({"message": "logged in"})

    @app.get("/protected")
    @auth("session")
    async def protected(req: Request, res: Response):
        return res.json({"user_id": req.user.identity})

    client = test_client(app)
    async with client:
        login_res = await client.post("/login")
        res = await client.get(
            "/protected",
            headers={"Cookie": f"session_id={login_res.cookies.get('session_id')}"},
        )
        assert res.status_code == 200
        assert res.json()["user_id"] == "1"
