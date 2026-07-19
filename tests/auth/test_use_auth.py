from functools import partial

import pytest

from sillo.application import silloApp
from sillo.auth import AuthenticationMiddleware, BaseUser, useAuth
from sillo.auth.backend import AuthenticationBackend
from sillo.auth.model import AuthResult
from sillo.users import SimpleUser, UnauthenticatedUser
from sillo.http import Request, Response
from sillo.testclient import AsyncTestClient


class TestUser(BaseUser):
    __test__ = False

    def __init__(
        self,
        user_id: str,
        username: str,
        roles: list[str] | None = None,
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
            "2": cls("2", "admin", ["read", "write", "admin"]),
            "3": cls("3", "guest", ["read"]),
        }
        return users_db.get(str(identity))


@pytest.fixture
def test_client():
    return partial(AsyncTestClient)


class AuthBackend(AuthenticationBackend):
    async def authenticate(self, request: Request):
        if request.headers.get("X-Auth") == "valid":
            return AuthResult(success=True, identity="1", scope="jwt")
        return AuthResult(success=False, identity="", scope="")


class AdminBackend(AuthenticationBackend):
    async def authenticate(self, request: Request):
        if request.headers.get("X-Auth") == "admin":
            return AuthResult(success=True, identity="2", scope="jwt")
        return AuthResult(success=False, identity="", scope="")


class SessionBackend(AuthenticationBackend):
    async def authenticate(self, request: Request):
        if request.headers.get("X-Session") == "valid":
            return AuthResult(success=True, identity="1", scope="session")
        return AuthResult(success=False, identity="", scope="")


class APIKeyBackend(AuthenticationBackend):
    async def authenticate(self, request: Request):
        if request.headers.get("X-API-Key") == "secret":
            return AuthResult(success=True, identity="apikey_user", scope="apikey")
        return AuthResult(success=False, identity="", scope="")


# ---------------------------------------------------------------------------
# useAuth: required (no scopes, any authenticated user)
# ---------------------------------------------------------------------------


async def test_use_auth_required_allows_authenticated(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/protected", auth=useAuth())
    async def protected(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected", headers={"X-Auth": "valid"})
        assert res.status_code == 200


async def test_use_auth_required_rejects_unauthenticated(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/protected", auth=useAuth())
    async def protected(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# useAuth: scopes
# ---------------------------------------------------------------------------


async def test_use_auth_scopes_allows_matching(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/protected", auth=useAuth(scopes=["jwt"]))
    async def protected(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected", headers={"X-Auth": "valid"})
        assert res.status_code == 200


async def test_use_auth_scopes_rejects_non_matching(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/protected", auth=useAuth(scopes=["apikey"]))
    async def protected(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected", headers={"X-Auth": "valid"})
        assert res.status_code == 401


async def test_use_auth_scopes_multiple_allows_any(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, SessionBackend()))

    @app.get("/protected", auth=useAuth(scopes=["jwt", "session"]))
    async def protected(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected", headers={"X-Session": "valid"})
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# useAuth: optional
# ---------------------------------------------------------------------------


async def test_use_auth_optional_allows_unauthenticated(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/feed", auth=useAuth(required=False))
    async def feed(req: Request, res: Response):
        return res.json({"authenticated": req.user.is_authenticated})

    async with test_client(app) as client:
        res = await client.get("/feed")
        assert res.status_code == 200
        assert res.json() == {"authenticated": False}


async def test_use_auth_optional_attaches_user_if_present(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/feed", auth=useAuth(required=False))
    async def feed(req: Request, res: Response):
        return res.json({"authenticated": req.user.is_authenticated})

    async with test_client(app) as client:
        res = await client.get("/feed", headers={"X-Auth": "valid"})
        assert res.status_code == 200
        assert res.json() == {"authenticated": True}


# ---------------------------------------------------------------------------
# useAuth: permissions
# ---------------------------------------------------------------------------


async def test_use_auth_permissions_allows_matching(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/admin", auth=useAuth(permissions=["read"]))
    async def admin(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/admin", headers={"X-Auth": "valid"})
        assert res.status_code == 200


async def test_use_auth_permissions_rejects_non_matching(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/admin", auth=useAuth(permissions=["delete"]))
    async def admin(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/admin", headers={"X-Auth": "valid"})
        assert res.status_code == 403


async def test_use_auth_permissions_admin_user(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AdminBackend()))

    @app.get("/admin", auth=useAuth(permissions=["admin"]))
    async def admin(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/admin", headers={"X-Auth": "admin"})
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# useAuth: combined scopes + permissions
# ---------------------------------------------------------------------------


async def test_use_auth_scopes_and_permissions(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AdminBackend()))

    @app.get("/secure", auth=useAuth(scopes=["jwt"], permissions=["admin"]))
    async def secure(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/secure", headers={"X-Auth": "admin"})
        assert res.status_code == 200


async def test_use_auth_scopes_and_permissions_scope_mismatch(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AdminBackend()))

    @app.get("/secure", auth=useAuth(scopes=["apikey"], permissions=["admin"]))
    async def secure(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/secure", headers={"X-Auth": "admin"})
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# useAuth: route-level backend override
# ---------------------------------------------------------------------------


async def test_use_auth_route_backends_override_middleware(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/api", auth=useAuth(backends=[APIKeyBackend()]))
    async def api(req: Request, res: Response):
        return res.json({"ok": True, "scope": req.scope.get("auth")})

    async with test_client(app) as client:
        res = await client.get("/api", headers={"X-API-Key": "secret"})
        assert res.status_code == 200
        assert res.json()["scope"] == "apikey"


async def test_use_auth_route_backends_reject_if_override_fails(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/api", auth=useAuth(backends=[APIKeyBackend()]))
    async def api(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/api")
        assert res.status_code == 401


async def test_use_auth_route_backends_overrides_user(test_client):
    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/api", auth=useAuth(backends=[APIKeyBackend()]))
    async def api(req: Request, res: Response):
        return res.json({"display_name": req.user.display_name})

    async with test_client(app) as client:
        res = await client.get("/api", headers={"X-API-Key": "secret"})
        assert res.status_code == 200
        assert res.json()["display_name"] == "apikey_user"


# ---------------------------------------------------------------------------
# useAuth: subclass
# ---------------------------------------------------------------------------


async def test_use_auth_subclass_custom_logic(test_client):
    class HeaderAuth(useAuth):
        async def authenticate(self, request):
            if not await super().authenticate(request):
                return False
            if request.headers.get("X-Custom") != "granted":
                from sillo.auth.exceptions import AuthenticationFailed
                raise AuthenticationFailed
            return True

    app = silloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/custom", auth=HeaderAuth())
    async def custom(req: Request, res: Response):
        return res.json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/custom", headers={"X-Auth": "valid"})
        assert res.status_code == 401

        res = await client.get("/custom", headers={"X-Auth": "valid", "X-Custom": "granted"})
        assert res.status_code == 200
