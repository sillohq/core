from functools import partial

import pytest

from sillo.application import silloApp
from sillo.auth.session_auth.backend import login, logout
from sillo.auth.session_auth.guard import SessionGuard
from sillo.http import Request, Response
from sillo.session.middleware import SessionMiddleware
from sillo.testclient import AsyncTestClient
from sillo.users import SimpleUser


@pytest.fixture
def test_client():
    return partial(AsyncTestClient)


class MockUser(SimpleUser):
    __test__ = False

    def __init__(self, username, permissions=None, user_id="1"):
        super().__init__(username, permissions)
        self._id = user_id

    @property
    def identity(self):
        return self._id

    def check_password(self, password):
        return password == "secret"

    async def set_last_login(self):
        pass


def make_mock_model(return_user):
    from unittest.mock import AsyncMock

    class Models:
        pass

    Models.objects = AsyncMock()
    Models.objects.get_by_email = AsyncMock(return_value=return_user)
    Models.objects.get_by_id = AsyncMock(return_value=return_user)
    return Models


async def test_login_sets_session(test_client):
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        login(req, SimpleUser("alice"))
        return res.json({"ok": True})

    @app.get("/check")
    async def check(req: Request, res: Response):
        d = req.session.get("user")
        return res.json({"has_user": d is not None, "id": str(d["id"]) if d else None})

    client = test_client(app)
    login_res = await client.post("/login")
    session = login_res.cookies.get("session_id")
    res = await client.get("/check", cookies={"session_id": session})
    assert res.json() == {"has_user": True, "id": "alice"}
    await client.aclose()


async def test_logout_clears_session(test_client):
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        login(req, SimpleUser("alice"))
        return res.json({"ok": True})

    @app.post("/logout")
    async def do_logout(req: Request, res: Response):
        logout(req)
        return res.json({"ok": True})

    @app.get("/check")
    async def check(req: Request, res: Response):
        return res.json({"authenticated": bool(req.session.get("user"))})

    client = test_client(app)

    login_res = await client.post("/login")
    login_cookie = login_res.cookies.get("session_id")

    res = await client.get("/check", cookies={"session_id": login_cookie})
    assert res.json()["authenticated"] is True

    logout_res = await client.post("/logout", cookies={"session_id": login_cookie})
    cleared_cookie = logout_res.cookies.get("session_id")

    res = await client.get("/check", cookies={"session_id": cleared_cookie})
    assert res.json()["authenticated"] is False
    await client.aclose()


async def test_guard_attempt_and_check(test_client):
    mock_model = make_mock_model(MockUser("alice", user_id="1"))
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_model)

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        form = await req.form
        ok = await guard.attempt(req, email=form["email"], password=form["password"])
        return res.json({"status": "ok" if ok else "fail"})

    @app.get("/check")
    async def check(req: Request, res: Response):
        return res.json({"authenticated": await guard.check(req)})

    @app.get("/id")
    async def get_id(req: Request, res: Response):
        uid = await guard.id(req)
        return res.json({"id": uid})

    client = test_client(app)
    login_res = await client.post("/login", data={"email": "a@b.com", "password": "secret"})
    assert login_res.status_code == 200
    session = login_res.cookies.get("session_id")

    res = await client.get("/check", cookies={"session_id": session})
    assert res.json()["authenticated"] is True

    res = await client.get("/id", cookies={"session_id": session})
    assert res.json()["id"] == "1"
    await client.aclose()


async def test_guard_attempt_wrong_password(test_client):
    mock_model = make_mock_model(MockUser("alice", user_id="1"))
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_model)

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        form = await req.form
        ok = await guard.attempt(req, email=form["email"], password=form["password"])
        return res.json({"status": "ok" if ok else "fail"})

    client = test_client(app)
    res = await client.post("/login", data={"email": "a@b.com", "password": "wrong"})
    assert res.json() == {"status": "fail"}
    await client.aclose()


async def test_guard_attempt_user_not_found(test_client):
    mock_model = make_mock_model(None)
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_model)

    @app.post("/login")
    async def do_login(req: Request, res: Response):
        form = await req.form
        ok = await guard.attempt(req, email=form["email"], password=form["password"])
        return res.json({"status": "ok" if ok else "fail"})

    client = test_client(app)
    res = await client.post("/login", data={"email": "ghost@b.com", "password": "any"})
    assert res.json() == {"status": "fail"}
    await client.aclose()


async def test_guard_logout(test_client):
    mock_model = make_mock_model(MockUser("alice", user_id="1"))
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_model)

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
        return res.json({"authenticated": await guard.check(req)})

    client = test_client(app)

    login_res = await client.post("/login", data={"email": "a@b.com", "password": "secret"})
    login_cookie = login_res.cookies.get("session_id")

    res = await client.get("/check", cookies={"session_id": login_cookie})
    assert res.json()["authenticated"] is True

    logout_res = await client.post("/logout", cookies={"session_id": login_cookie})
    cleared_cookie = logout_res.cookies.get("session_id")

    res = await client.get("/check", cookies={"session_id": cleared_cookie})
    assert res.json()["authenticated"] is False
    await client.aclose()


async def test_guard_validate(test_client):
    mock_model = make_mock_model(MockUser("alice", user_id="1"))
    app = silloApp()
    app.use(SessionMiddleware(secret_key="test-key"))
    guard = SessionGuard(backend=None, user_model=mock_model)

    @app.post("/validate")
    async def validate(req: Request, res: Response):
        body = await req.json
        ok = await guard.validate(req, body)
        return res.json({"valid": ok})

    client = test_client(app)
    res = await client.post("/validate", json={"email": "a@b.com", "password": "secret"})
    assert res.json()["valid"] is True

    res = await client.post("/validate", json={"email": "a@b.com", "password": "wrong"})
    assert res.json()["valid"] is False
    await client.aclose()
