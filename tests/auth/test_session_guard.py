from functools import partial

import pytest

from sillo.application import silloApp
from sillo.auth.backends.base import AuthenticationBackend
from sillo.auth.model import AuthResult
from sillo.auth.session_auth.backend import login, logout
from sillo.auth.session_auth.guard import SessionGuard
from sillo.users import SimpleUser
from sillo.http import Request, Response
from sillo.session.middleware import SessionMiddleware
from sillo.testclient import AsyncTestClient


class MockUser(SimpleUser):
    def __init__(self, username, permissions=None, user_id="1"):
        super().__init__(username, permissions)
        self.user_id = user_id

    @property
    def identity(self):
        return self.user_id

    def check_password(self, password):
        return password == "secret"

    async def set_last_login(self):
        pass


@pytest.fixture
def test_client():
    return partial(AsyncTestClient)


@pytest.fixture
def mock_user_model():
    class Models:
        objects = None

    from unittest.mock import AsyncMock

    Models.objects = AsyncMock()
    Models.objects.get_by_email = AsyncMock()
    Models.objects.get_by_id = AsyncMock()
    return Models


async def test_guard_attempt_success(test_client, mock_user_model):
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_user_model)

    mock_user_model.objects.get_by_email.return_value = MockUser("alice", user_id="1")

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        form = await req.form
        ok = await guard.attempt(req, email=form["email"], password=form["password"])
        if ok:
            return res.json({"status": "ok"})
        return res.json({"status": "fail"}, status_code=401)

    async with test_client(app) as client:
        res = await client.post("/login", data={"email": "a@b.com", "password": "secret"})
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


async def test_guard_attempt_wrong_password(test_client, mock_user_model):
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_user_model)

    mock_user_model.objects.get_by_email.return_value = MockUser("alice", user_id="1")

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        form = await req.form
        ok = await guard.attempt(req, email=form["email"], password=form["password"])
        if ok:
            return res.json({"status": "ok"})
        return res.json({"status": "fail"}, status_code=401)

    async with test_client(app) as client:
        res = await client.post("/login", data={"email": "a@b.com", "password": "wrong"})
        assert res.status_code == 401


async def test_guard_attempt_user_not_found(test_client, mock_user_model):
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_user_model)

    mock_user_model.objects.get_by_email.return_value = None

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        form = await req.form
        ok = await guard.attempt(req, email=form["email"], password=form["password"])
        if ok:
            return res.json({"status": "ok"})
        return res.json({"status": "fail"}, status_code=401)

    async with test_client(app) as client:
        res = await client.post("/login", data={"email": "ghost@b.com", "password": "any"})
        assert res.status_code == 401


async def test_guard_check_returns_true_when_logged_in(test_client, mock_user_model):
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_user_model)

    mock_user_model.objects.get_by_email.return_value = MockUser("alice", user_id="1")

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        form = await req.form
        await guard.attempt(req, email=form["email"], password=form["password"])
        return res.json({"ok": True})

    @app.get("/check")
    async def check(req: Request, res: Response):
        is_logged = await guard.check(req)
        return res.json({"authenticated": is_logged})

    async with test_client(app) as client:
        await client.post("/login", data={"email": "a@b.com", "password": "secret"})
        res = await client.get("/check")
        assert res.json()["authenticated"] is True


async def test_guard_check_returns_false_when_not_logged_in(test_client, mock_user_model):
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_user_model)

    @app.get("/check")
    async def check(req: Request, res: Response):
        is_logged = await guard.check(req)
        return res.json({"authenticated": is_logged})

    async with test_client(app) as client:
        res = await client.get("/check")
        assert res.json()["authenticated"] is False


async def test_guard_id_returns_user_id(test_client, mock_user_model):
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_user_model)

    mock_user_model.objects.get_by_email.return_value = MockUser("alice", user_id="42")

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        form = await req.form
        await guard.attempt(req, email=form["email"], password=form["password"])
        return res.json({"ok": True})

    @app.get("/id")
    async def get_id(req: Request, res: Response):
        uid = await guard.id(req)
        return res.json({"id": uid})

    async with test_client(app) as client:
        await client.post("/login", data={"email": "a@b.com", "password": "secret"})
        res = await client.get("/id")
        assert res.json()["id"] == "42"


async def test_guard_logout_clears_session(test_client, mock_user_model):
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_user_model)

    mock_user_model.objects.get_by_email.return_value = MockUser("alice", user_id="1")

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        form = await req.form
        await guard.attempt(req, email=form["email"], password=form["password"])
        return res.json({"ok": True})

    @app.post("/logout")
    async def do_logout(req: Request, res: Response):
        await guard.logout(req)
        return res.json({"ok": True})

    @app.get("/check")
    async def check(req: Request, res: Response):
        is_logged = await guard.check(req)
        return res.json({"authenticated": is_logged})

    async with test_client(app) as client:
        await client.post("/login", data={"email": "a@b.com", "password": "secret"})
        res = await client.get("/check")
        assert res.json()["authenticated"] is True

        await client.post("/logout")
        res = await client.get("/check")
        assert res.json()["authenticated"] is False


async def test_guard_login_logout_helpers(test_client):
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        user = SimpleUser("alice")
        user.identity = "42"
        login(req, user)
        return res.json({"ok": True})

    @app.get("/check")
    async def check(req: Request, res: Response):
        session_data = req.session.get("user")
        return res.json({"has_user": session_data is not None, "id": str(session_data["id"]) if session_data else None})

    @app.post("/logout")
    async def do_logout(req: Request, res: Response):
        logout(req)
        return res.json({"ok": True})

    async with test_client(app) as client:
        await client.post("/login")
        res = await client.get("/check")
        assert res.json() == {"has_user": True, "id": "42"}

        await client.post("/logout")
        res = await client.get("/check")
        assert res.json() == {"has_user": False, "id": None}
