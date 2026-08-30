from functools import partial

import pytest

from sillo.application import SilloApp
from sillo import redirect
from sillo import json
from sillo.auth import AuthenticationMiddleware, BaseUser, useAuth
from sillo.auth.backend import AuthenticationBackend
from sillo.auth.exceptions import AuthenticationFailed
from sillo.auth.model import AuthResult
from sillo.core.http import HttpContext
from sillo.testclient import AsyncTestClient
from sillo.users import SimpleUser, UnauthenticatedUser


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
    name = "bearerAuth"

    async def authenticate(self, ctx: HttpContext):
        if ctx.headers.get("X-Auth") == "valid":
            return AuthResult(success=True, identity="1", scope="bearerAuth")
        return AuthResult(success=False, identity="", scope="")


class AdminBackend(AuthenticationBackend):
    name = "bearerAuth"

    async def authenticate(self, ctx: HttpContext):
        if ctx.headers.get("X-Auth") == "admin":
            return AuthResult(success=True, identity="2", scope="bearerAuth")
        return AuthResult(success=False, identity="", scope="")


class SessionBackend(AuthenticationBackend):
    name = "sessionCookie"

    async def authenticate(self, ctx: HttpContext):
        if ctx.headers.get("X-Session") == "valid":
            return AuthResult(success=True, identity="1", scope="sessionCookie")
        return AuthResult(success=False, identity="", scope="")


class APIKeyBackend(AuthenticationBackend):
    name = "apiKeyHeader"

    async def authenticate(self, ctx: HttpContext):
        if ctx.headers.get("X-API-Key") == "secret":
            return AuthResult(success=True, identity="apikey_user", scope="apiKeyHeader")
        return AuthResult(success=False, identity="", scope="")


# ---------------------------------------------------------------------------
# useAuth: required (no scopes, any authenticated user)
# ---------------------------------------------------------------------------


async def test_use_auth_required_allows_authenticated(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/protected", auth=useAuth())
    async def protected(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected", headers={"X-Auth": "valid"})
        assert res.status_code == 200


async def test_use_auth_required_rejects_unauthenticated(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/protected", auth=useAuth())
    async def protected(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# useAuth: schemes
# ---------------------------------------------------------------------------


async def test_use_auth_schemes_allows_matching(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/protected", auth=useAuth(schemes=["bearerAuth"]))
    async def protected(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected", headers={"X-Auth": "valid"})
        assert res.status_code == 200


async def test_use_auth_schemes_rejects_non_matching(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/protected", auth=useAuth(schemes=["apiKeyHeader"]))
    async def protected(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected", headers={"X-Auth": "valid"})
        assert res.status_code == 401


async def test_use_auth_schemes_multiple_allows_any(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, SessionBackend()))

    @app.get("/protected", auth=useAuth(schemes=["bearerAuth", "sessionCookie"]))
    async def protected(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected", headers={"X-Session": "valid"})
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# useAuth: optional
# ---------------------------------------------------------------------------


async def test_use_auth_optional_allows_unauthenticated(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/feed", auth=useAuth(required=False))
    async def feed(ctx: HttpContext):
        return json({"authenticated": ctx.user.is_authenticated})

    async with test_client(app) as client:
        res = await client.get("/feed")
        assert res.status_code == 200
        assert res.json() == {"authenticated": False}


async def test_use_auth_optional_attaches_user_if_present(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/feed", auth=useAuth(required=False))
    async def feed(ctx: HttpContext):
        return json({"authenticated": ctx.user.is_authenticated})

    async with test_client(app) as client:
        res = await client.get("/feed", headers={"X-Auth": "valid"})
        assert res.status_code == 200
        assert res.json() == {"authenticated": True}


# ---------------------------------------------------------------------------
# useAuth: permissions
# ---------------------------------------------------------------------------


async def test_use_auth_permissions_allows_matching(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/admin", auth=useAuth(permissions=["read"]))
    async def admin(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/admin", headers={"X-Auth": "valid"})
        assert res.status_code == 200


async def test_use_auth_permissions_rejects_non_matching(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/admin", auth=useAuth(permissions=["delete"]))
    async def admin(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/admin", headers={"X-Auth": "valid"})
        assert res.status_code == 403


async def test_use_auth_permissions_rejects_anonymous_as_401_not_403(test_client):
    """An anonymous caller is unauthenticated, not merely unauthorised.

    The removed ``@has_permission`` decorator answered 403 here, because it
    only ever asked ``user.has_permission(...)`` and ``UnauthenticatedUser``
    says no to everything. ``useAuth`` checks ``is_authenticated`` first, so
    the same request is now a 401 — which is the correct code, and the one
    that tells a client to go and log in rather than to give up.
    """
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/admin", auth=useAuth(permissions=["read"]))
    async def admin(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/admin")
        assert res.status_code == 401


async def test_use_auth_permissions_admin_user(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AdminBackend()))

    @app.get("/admin", auth=useAuth(permissions=["admin"]))
    async def admin(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/admin", headers={"X-Auth": "admin"})
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# useAuth: combined schemes + permissions
# ---------------------------------------------------------------------------


async def test_use_auth_schemes_and_permissions(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AdminBackend()))

    @app.get("/secure", auth=useAuth(schemes=["bearerAuth"], permissions=["admin"]))
    async def secure(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/secure", headers={"X-Auth": "admin"})
        assert res.status_code == 200


async def test_use_auth_schemes_and_permissions_scheme_mismatch(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AdminBackend()))

    @app.get("/secure", auth=useAuth(schemes=["apiKeyHeader"], permissions=["admin"]))
    async def secure(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/secure", headers={"X-Auth": "admin"})
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# useAuth: route-level backend override
# ---------------------------------------------------------------------------


async def test_use_auth_route_backends_override_middleware(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/api", auth=useAuth(backends=[APIKeyBackend()]))
    async def api(ctx: HttpContext):
        return json({"ok": True, "scope": ctx.scope.get("auth")})

    async with test_client(app) as client:
        res = await client.get("/api", headers={"X-API-Key": "secret"})
        assert res.status_code == 200
        assert res.json()["scope"] == "apiKeyHeader"


async def test_use_auth_route_backends_reject_if_override_fails(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/api", auth=useAuth(backends=[APIKeyBackend()]))
    async def api(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/api")
        assert res.status_code == 401


async def test_use_auth_route_backends_overrides_user(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/api", auth=useAuth(backends=[APIKeyBackend()]))
    async def api(ctx: HttpContext):
        return json({"display_name": ctx.user.display_name})

    async with test_client(app) as client:
        res = await client.get("/api", headers={"X-API-Key": "secret"})
        assert res.status_code == 200
        assert res.json()["display_name"] == "apikey_user"


# ---------------------------------------------------------------------------
# useAuth: subclass
# ---------------------------------------------------------------------------


async def test_use_auth_subclass_custom_logic(test_client):
    class HeaderAuth(useAuth):
        async def authenticate(self, ctx):
            if not await super().authenticate(ctx):
                return False
            if ctx.headers.get("X-Custom") != "granted":
                from sillo.auth.exceptions import AuthenticationFailed
                raise AuthenticationFailed
            return True

    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/custom", auth=HeaderAuth())
    async def custom(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/custom", headers={"X-Auth": "valid"})
        assert res.status_code == 401

        res = await client.get("/custom", headers={"X-Auth": "valid", "X-Custom": "granted"})
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# useAuth: unauthorized / forbidden hooks
# ---------------------------------------------------------------------------
#
# `unauthorized` answers the 401 a missing/mismatched-scheme authentication
# would have raised; `forbidden` answers the 403 a missing permission would
# have raised. Both are optional, independent, and — unset — change nothing:
# the gate keeps raising AuthenticationFailed/PermissionDenied exactly as it
# always did, which the tests in this section confirm as much as the new
# behaviour itself.


async def test_unauthorized_hook_replaces_the_401(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get(
        "/protected",
        auth=useAuth(unauthorized=lambda ctx: json({"custom": True}, status_code=401)),
    )
    async def protected(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected")
        assert res.status_code == 401
        assert res.json() == {"custom": True}


async def test_unauthorized_hook_can_redirect(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get(
        "/dashboard",
        auth=useAuth(unauthorized=lambda ctx: redirect("/login")),
    )
    async def dashboard(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/dashboard", follow_redirects=False)
        assert res.status_code == 302
        assert res.headers["location"] == "/login"


async def test_unauthorized_hook_fires_on_scheme_mismatch_too(test_client):
    """A wrong-scheme authentication is also `AuthenticationFailed` — the hook
    has to cover that path, not only "no user at all"."""
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get(
        "/scoped",
        auth=useAuth(
            schemes=["sessionCookie"],
            unauthorized=lambda ctx: json({"reason": "wrong-scheme"}, status_code=401),
        ),
    )
    async def scoped(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/scoped", headers={"X-Auth": "valid"})
        assert res.status_code == 401
        assert res.json() == {"reason": "wrong-scheme"}


async def test_forbidden_hook_replaces_the_403(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get(
        "/admin-only",
        auth=useAuth(
            permissions=["admin"],
            forbidden=lambda ctx: json({"custom": True}, status_code=403),
        ),
    )
    async def admin_only(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/admin-only", headers={"X-Auth": "valid"})
        assert res.status_code == 403
        assert res.json() == {"custom": True}


async def test_forbidden_hook_does_not_fire_on_401(test_client):
    """An anonymous caller against a permission-gated route is still a 401,
    not a 403 — `forbidden` must not be asked to answer for `unauthorized`."""
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get(
        "/admin-only",
        auth=useAuth(
            permissions=["admin"],
            forbidden=lambda ctx: json({"wrong_hook": True}, status_code=403),
        ),
    )
    async def admin_only(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/admin-only")
        assert res.status_code == 401
        assert res.json() != {"wrong_hook": True}


async def test_unauthorized_and_forbidden_are_independent(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get(
        "/both",
        auth=useAuth(
            permissions=["admin"],
            unauthorized=lambda ctx: json({"which": "unauthorized"}, status_code=401),
            forbidden=lambda ctx: json({"which": "forbidden"}, status_code=403),
        ),
    )
    async def both(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        anon = await client.get("/both")
        assert anon.status_code == 401 and anon.json() == {"which": "unauthorized"}

        non_admin = await client.get("/both", headers={"X-Auth": "valid"})
        assert non_admin.status_code == 403 and non_admin.json() == {"which": "forbidden"}


async def test_an_async_hook_is_awaited(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    async def hook(ctx: HttpContext):
        return json({"async": True}, status_code=401)

    @app.get("/protected", auth=useAuth(unauthorized=hook))
    async def protected(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected")
        assert res.status_code == 401
        assert res.json() == {"async": True}


async def test_a_sync_hook_still_runs_without_blocking_the_test(test_client):
    """Exercises the thread-pool path `_run_hook` takes for a plain function."""
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    def hook(ctx: HttpContext):
        return json({"sync": True}, status_code=401)

    @app.get("/protected", auth=useAuth(unauthorized=hook))
    async def protected(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected")
        assert res.status_code == 401
        assert res.json() == {"sync": True}


async def test_the_route_handler_never_runs_when_a_hook_fires(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))
    handler_calls = []

    @app.get(
        "/protected",
        auth=useAuth(unauthorized=lambda ctx: json({}, status_code=401)),
    )
    async def protected(ctx: HttpContext):
        handler_calls.append(1)
        return json({"ok": True})

    async with test_client(app) as client:
        await client.get("/protected")
        assert handler_calls == []


async def test_no_hooks_keeps_raising_authentication_failed(test_client):
    """The default behaviour, unchanged, when neither hook is set."""
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/protected", auth=useAuth())
    async def protected(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/protected")
        assert res.status_code == 401
        assert "Authentication failed" in res.text


async def test_no_forbidden_hook_keeps_raising_permission_denied(test_client):
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/admin-only", auth=useAuth(permissions=["admin"]))
    async def admin_only(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        res = await client.get("/admin-only", headers={"X-Auth": "valid"})
        assert res.status_code == 403
        assert "Permission denied" in res.text


async def test_hooks_are_stored_on_the_instance():
    """The plumbing `guard()` reads from — worth pinning directly, since a
    typo in the attribute name would otherwise only show up as a hook that
    silently never fires."""

    def unauthorized_hook(ctx):
        return None

    def forbidden_hook(ctx):
        return None

    gate = useAuth(unauthorized=unauthorized_hook, forbidden=forbidden_hook)
    assert gate.unauthorized is unauthorized_hook
    assert gate.forbidden is forbidden_hook

    bare = useAuth()
    assert bare.unauthorized is None
    assert bare.forbidden is None


async def test_guard_returns_none_when_authentication_passes():
    """`guard()` is what the router short-circuits on a non-None return —
    confirm the success path gives it nothing to short-circuit on."""
    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))
    gate = useAuth(unauthorized=lambda ctx: json({}, status_code=401))

    class FakeContext:
        def __init__(self):
            self.scope = {"user": TestUser("1", "testuser"), "auth": None, "auth_scheme": None}

    result = await gate.guard(FakeContext())
    assert result is None


async def test_a_custom_gate_without_guard_still_works(test_client):
    """`auth=` is duck-typed (`Any | None`), so a hand-built gate that only
    ever implemented `authenticate` — the extension point documented before
    `guard` existed — must keep working through the router's fallback."""

    class BareGate:
        async def authenticate(self, ctx):
            if ctx.headers.get("X-Auth") != "valid":
                raise AuthenticationFailed
            return True

    app = SilloApp()
    app.use(AuthenticationMiddleware(TestUser, AuthBackend()))

    @app.get("/bare", auth=BareGate())
    async def bare(ctx: HttpContext):
        return json({"ok": True})

    async with test_client(app) as client:
        denied = await client.get("/bare")
        assert denied.status_code == 401

        allowed = await client.get("/bare", headers={"X-Auth": "valid"})
        assert allowed.status_code == 200
