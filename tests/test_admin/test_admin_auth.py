"""Coverage for sillo.admin.auth: AuthBackend's default (permissive) methods,
SessionAuth.current_user/authenticate/get_user/login/logout, and
_AuthMiddleware's path-based bypass and redirect logic. Only ``may_enter`` had
prior coverage (see test_admin_models.py).
"""

from __future__ import annotations

import pytest

from sillo.admin.auth import AuthBackend, SessionAuth, _AuthMiddleware


class FakeSession:
    def __init__(self, data=None):
        self._data = data or {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def delete(self, key):
        self._data.pop(key, None)


class FakeContext:
    def __init__(self, session=None):
        self.session = session


class FakeUser:
    def __init__(self, uid="1", is_active=True, is_staff=True, is_superuser=False):
        self.uid = uid
        self.is_active = is_active
        self.is_staff = is_staff
        self.is_superuser = is_superuser


class FakeUserModel:
    users_by_id: dict = {}
    valid_credentials: dict = {}

    @classmethod
    async def load_user(cls, identity):
        return cls.users_by_id.get(identity)

    @classmethod
    async def verify_credentials(cls, username, password):
        expected = cls.valid_credentials.get(username)
        if expected == password:
            return cls.users_by_id.get(username)
        return None


# ── AuthBackend defaults ─────────────────────────────────────────────────


async def test_auth_backend_default_authenticate_is_permissive():
    backend = AuthBackend()
    assert await backend.authenticate(FakeContext()) is True


async def test_auth_backend_default_get_user_returns_anonymous():
    backend = AuthBackend()
    user = await backend.get_user(FakeContext())
    assert user == {"id": "anonymous", "username": "Anonymous"}


async def test_auth_backend_default_login_is_permissive():
    backend = AuthBackend()
    assert await backend.login(FakeContext(), "u", "p") is True


async def test_auth_backend_default_logout_is_a_noop():
    backend = AuthBackend()
    assert await backend.logout(FakeContext()) is None


def test_auth_backend_middleware_property_wraps_backend():
    backend = AuthBackend()
    middleware = backend.middleware
    assert isinstance(middleware, _AuthMiddleware)
    assert middleware.backend is backend


# ── SessionAuth.current_user ─────────────────────────────────────────────


async def test_current_user_none_without_a_session():
    auth = SessionAuth(user_model=FakeUserModel)
    assert await auth.current_user(FakeContext(session=None)) is None


async def test_current_user_none_when_session_has_no_entry():
    auth = SessionAuth(user_model=FakeUserModel)
    ctx = FakeContext(session=FakeSession({}))
    assert await auth.current_user(ctx) is None


async def test_current_user_none_when_identity_missing_from_entry():
    auth = SessionAuth(user_model=FakeUserModel)
    # A non-empty dict entry with no "id" key: reaches the identity-is-None
    # check without short-circuiting on the earlier "not entry" guard.
    ctx = FakeContext(session=FakeSession({"user": {"username": "bob"}}))
    assert await auth.current_user(ctx) is None


async def test_current_user_loads_from_plain_identity_value():
    model = type("Model", (FakeUserModel,), {"users_by_id": {"7": FakeUser("7")}})
    auth = SessionAuth(user_model=model)
    ctx = FakeContext(session=FakeSession({"admin_user": "7"}))
    user = await auth.current_user(ctx)
    assert user.uid == "7"


async def test_current_user_none_when_load_user_raises():
    class ExplodingModel(FakeUserModel):
        @classmethod
        async def load_user(cls, identity):
            raise RuntimeError("db is down")

    auth = SessionAuth(user_model=ExplodingModel)
    ctx = FakeContext(session=FakeSession({"user": {"id": "1"}}))
    assert await auth.current_user(ctx) is None


async def test_current_user_none_when_loaded_user_is_none():
    model = type("Model", (FakeUserModel,), {"users_by_id": {}})
    auth = SessionAuth(user_model=model)
    ctx = FakeContext(session=FakeSession({"user": {"id": "missing"}}))
    assert await auth.current_user(ctx) is None


async def test_current_user_none_when_not_permitted():
    non_staff = FakeUser("1", is_staff=False, is_superuser=False)
    model = type("Model", (FakeUserModel,), {"users_by_id": {"1": non_staff}})
    auth = SessionAuth(user_model=model)
    ctx = FakeContext(session=FakeSession({"user": {"id": "1"}}))
    assert await auth.current_user(ctx) is None


# ── SessionAuth.authenticate / get_user ──────────────────────────────────


async def test_authenticate_true_when_current_user_present():
    staff = FakeUser("1")
    model = type("Model", (FakeUserModel,), {"users_by_id": {"1": staff}})
    auth = SessionAuth(user_model=model)
    ctx = FakeContext(session=FakeSession({"user": {"id": "1"}}))
    assert await auth.authenticate(ctx) is True


async def test_get_user_none_when_not_authenticated():
    auth = SessionAuth(user_model=FakeUserModel)
    assert await auth.get_user(FakeContext(session=FakeSession({}))) is None


async def test_get_user_returns_session_entry_when_authenticated():
    staff = FakeUser("1")
    model = type("Model", (FakeUserModel,), {"users_by_id": {"1": staff}})
    auth = SessionAuth(user_model=model)
    entry = {"id": "1", "username": "staffer"}
    ctx = FakeContext(session=FakeSession({"user": entry}))
    assert await auth.get_user(ctx) == entry


# ── SessionAuth.login / logout ───────────────────────────────────────────


async def test_login_fails_without_username_or_password():
    auth = SessionAuth(user_model=FakeUserModel)
    assert await auth.login(FakeContext(), "", "pw") is False
    assert await auth.login(FakeContext(), "user", "") is False


async def test_login_fails_for_bad_credentials():
    model = type(
        "Model", (FakeUserModel,), {"users_by_id": {}, "valid_credentials": {}}
    )
    auth = SessionAuth(user_model=model)
    assert await auth.login(FakeContext(), "nope", "wrong") is False


async def test_login_fails_when_user_is_not_permitted():
    non_staff = FakeUser("bob", is_staff=False)
    model = type(
        "Model",
        (FakeUserModel,),
        {
            "users_by_id": {"bob": non_staff},
            "valid_credentials": {"bob": "secret"},
        },
    )
    auth = SessionAuth(user_model=model)
    assert await auth.login(FakeContext(), "bob", "secret") is False


async def test_login_succeeds_and_calls_sillo_login(monkeypatch):
    staff = FakeUser("bob", is_staff=True)
    model = type(
        "Model",
        (FakeUserModel,),
        {
            "users_by_id": {"bob": staff},
            "valid_credentials": {"bob": "secret"},
        },
    )
    auth = SessionAuth(user_model=model)

    called = {}

    def fake_login(ctx, user):
        called["request"] = ctx
        called["user"] = user

    monkeypatch.setattr("sillo.auth.session_auth.login", fake_login)

    ctx = FakeContext()
    assert await auth.login(ctx, "bob", "secret") is True
    assert called["user"] is staff


async def test_logout_clears_admin_session_keys():
    auth = SessionAuth(user_model=FakeUserModel)
    session = FakeSession(
        {"admin_authenticated": True, "admin_user": {"id": "1"}, "user": {"id": "1"}}
    )
    ctx = FakeContext(session=session)
    await auth.logout(ctx)
    assert session.get("admin_authenticated") is None
    assert session.get("admin_user") is None
    assert session.get("user") is None


async def test_logout_without_a_session_is_a_noop():
    auth = SessionAuth(user_model=FakeUserModel)
    await auth.logout(FakeContext(session=None))


def test_session_auth_middleware_property():
    auth = SessionAuth(user_model=FakeUserModel)
    middleware = auth.middleware
    assert isinstance(middleware, _AuthMiddleware)
    assert middleware.backend is auth


# ── _AuthMiddleware ───────────────────────────────────────────────────────


class FakeResponse:
    def redirect(self, path, status_code=302):
        return ("redirect", path, status_code)


async def test_middleware_bypasses_non_admin_paths():
    backend = AuthBackend()
    middleware = _AuthMiddleware(backend)

    class FakeCtx:
        class url:
            path = "/api/widgets"

    called = {"next": False}

    async def call_next():
        called["next"] = True
        return "ok"

    result = await middleware(FakeCtx(), call_next)
    assert result == "ok"
    assert called["next"] is True


@pytest.mark.parametrize("path", ["/admin/login/", "/admin/static/app.css"])
async def test_middleware_bypasses_login_and_static_paths(path):
    class NeverAuthenticate(AuthBackend):
        async def authenticate(self, ctx):
            raise AssertionError("should not be called")

    middleware = _AuthMiddleware(NeverAuthenticate())

    class FakeCtx:
        class url:
            pass

    FakeCtx.url.path = path

    async def call_next():
        return "ok"

    assert await middleware(FakeCtx(), call_next) == "ok"


async def test_middleware_redirects_when_not_authenticated():
    class NeverAuthenticate(AuthBackend):
        async def authenticate(self, ctx):
            return False

    middleware = _AuthMiddleware(NeverAuthenticate())

    class FakeCtx:
        class url:
            path = "/admin/dashboard"

        scope = {"path": "/admin/dashboard"}

    async def call_next():
        raise AssertionError("should not reach the handler")

    result = await middleware(FakeCtx(), call_next)
    assert result.status_code == 302
    assert result.headers["location"] == "/admin/login/"


async def test_middleware_uses_scope_path_when_url_has_no_path_attr():
    class AlwaysAuthenticate(AuthBackend):
        async def authenticate(self, ctx):
            assert ctx.scope["path"] == "/admin/dashboard"
            return True

    middleware = _AuthMiddleware(AlwaysAuthenticate())

    class FakeCtx:
        url = object()  # no `.path` attribute
        scope = {"path": "/admin/dashboard"}

    async def call_next():
        return "ok"

    assert await middleware(FakeCtx(), call_next) == "ok"
