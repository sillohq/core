"""Regression tests for the session security findings reported 2026-08-12.

Each class here corresponds to one reported issue. They are written against
the outside of the framework where they can be — a cookie goes in, a filesystem
or a response header is inspected — because every one of these was reachable by
an ordinary HTTP request, and a unit test on the helper would not have proved
that.
"""

import os

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.session import SessionConfig
from sillo.session.file import FileSessionManager
from sillo.session.middleware import SessionMiddleware
from sillo.session.session_objects import Session
from sillo.testclient import TestClient

SECRET = "x" * 32


@pytest.fixture
def store(tmp_path):
    """A file session backend writing under a directory owned by the test."""
    path = tmp_path / "sessions"
    config = SessionConfig(
        session_file_storage_path=str(path),
        session_cookie_secure=False,
    )
    return FileSessionManager(config), path


def _app(manager):
    app = SilloApp()
    app.use(
        SessionMiddleware(
            manager=manager,
            secret_key=SECRET,
            session_cookie_secure=False,
        )
    )

    @app.get("/write")
    async def write(request: HttpContext):
        request.session["marker"] = "written"
        return json({"ok": True})

    @app.get("/read")
    async def read(request: HttpContext):
        return json({"marker": request.session.get("marker")})

    return app


class TestSessionKeyCannotEscapeTheStore:
    """The session cookie must never reach the filesystem as written.

    ``_get_file_path`` joined the cookie value straight into a path, so a
    request carrying ``session_id=../../x`` read and wrote outside the session
    directory. ``os.path.join`` makes it worse than traversal: an absolute
    value discards the configured directory entirely.
    """

    @pytest.mark.parametrize(
        "hostile",
        [
            "../escaped",
            "../../escaped",
            "..%2Fescaped",
            "/tmp/escaped",
            "sub/dir/escaped",
            "with.dot",
            "",
            "x" * 200,
        ],
    )
    def test_a_hostile_cookie_is_treated_as_no_cookie(self, store, hostile):
        manager, path = store

        with TestClient(_app(manager)) as client:
            client.cookies.set("session_id", hostile)
            response = client.get("/write")

        assert response.status_code == 200

        written = list(path.glob("*.json"))
        assert len(written) == 1
        # A fresh key was generated rather than the cookie being trusted.
        assert manager.is_valid_session_key(written[0].stem)

    def test_nothing_is_written_outside_the_store(self, store, tmp_path):
        manager, path = store
        outside = tmp_path / "outside.json"

        with TestClient(_app(manager)) as client:
            client.cookies.set("session_id", f"../{outside.stem}")
            client.get("/write")

        assert not outside.exists()
        assert not (tmp_path / "outside.json.json").exists()

    def test_the_path_builder_refuses_a_hostile_key_outright(self, store):
        manager, _ = store

        with pytest.raises(ValueError):
            manager._get_file_path("../escaped")

        with pytest.raises(ValueError):
            manager._get_file_path("/tmp/escaped")

    def test_a_generated_key_is_accepted(self, store):
        manager, path = store
        key = manager.generate_session_key()

        assert manager.is_valid_session_key(key)
        assert os.path.dirname(
            os.path.realpath(manager._get_file_path(key))
        ) == os.path.realpath(str(path))


class TestSessionIdentifierRotatesOnLogin:
    """Authenticating must not leave the pre-login identifier valid.

    ``login()`` only wrote into the session dictionary, so a key an attacker
    fixed in the victim's browser was authenticated the moment the victim
    signed in.
    """

    def test_cycle_key_changes_the_identifier_and_keeps_the_contents(self):
        manager = FileSessionManager(SessionConfig())
        session = Session(manager, "a" * 64)
        session["cart"] = "abc"

        session.cycle_key()

        assert session.session_key != "a" * 64
        assert session["cart"] == "abc"
        assert session.modified is True

    async def test_the_old_record_is_purged_once_the_new_one_is_written(self, store):
        manager, path = store

        session = manager.create_session(None)
        session["user"] = {"id": 1}
        old_key = await session.save()

        assert (path / f"{old_key}.json").exists()

        session.cycle_key()
        new_key = await session.save()

        assert new_key != old_key
        assert not (path / f"{old_key}.json").exists()
        assert (path / f"{new_key}.json").exists()

    def test_logging_in_issues_a_different_cookie(self, store):
        manager, _ = store
        app = SilloApp()
        app.use(
            SessionMiddleware(
                manager=manager, secret_key=SECRET, session_cookie_secure=False
            )
        )

        @app.get("/visit")
        async def visit(request: HttpContext):
            request.session["seen"] = True
            return json({"ok": True})

        @app.get("/login")
        async def login_route(request: HttpContext):
            from sillo.auth.session_auth.backend import login

            class _User:
                identity = "user-1"
                display_name = "Ada"

            login(request, _User())
            return json({"ok": True})

        with TestClient(app) as client:
            client.get("/visit")
            before = client.cookies.get("session_id")

            client.get("/login")
            after = client.cookies.get("session_id")

        assert before is not None
        assert after is not None
        assert before != after


class TestLoggingOutPurgesTheStoredSession:
    """The delete branch in the file backend was unreachable.

    ``Session.save()`` cleared ``deleted`` before handing the session to the
    backend, so ``if session.deleted`` was never true and logout overwrote the
    file with ``{}`` instead of removing it.
    """

    async def test_a_cleared_session_removes_its_file(self, store):
        manager, path = store

        session = manager.create_session(None)
        session["user"] = {"id": 1}
        key = await session.save()

        assert (path / f"{key}.json").exists()

        session.clear()
        await session.save()

        assert not (path / f"{key}.json").exists()

    async def test_save_hands_the_deleted_flag_to_the_backend(self, store):
        manager, _ = store

        session = manager.create_session(None)
        session["user"] = {"id": 1}
        await session.save()

        seen = {}

        async def record(sess):
            seen["deleted"] = sess.deleted
            return ""

        manager.save = record
        session.clear()
        await session.save()

        assert seen["deleted"] is True

    def test_logout_empties_the_session_and_drops_the_cookie(self, store):
        manager, path = store
        app = SilloApp()
        app.use(
            SessionMiddleware(
                manager=manager, secret_key=SECRET, session_cookie_secure=False
            )
        )

        @app.get("/login")
        async def login_route(request: HttpContext):
            from sillo.auth.session_auth.backend import login

            class _User:
                identity = "user-1"
                display_name = "Ada"

            login(request, _User())
            return json({"ok": True})

        @app.get("/logout")
        async def logout_route(request: HttpContext):
            from sillo.auth.session_auth.backend import logout

            logout(request)
            return json({"ok": True})

        with TestClient(app) as client:
            client.get("/login")
            assert list(path.glob("*.json"))

            client.get("/logout")

        assert list(path.glob("*.json")) == []


class TestRemovingOneKeyIsNotDeletingTheSession:
    """``deleted`` means "purge this session", and only ``clear()`` sets it.

    ``__delitem__`` used to set it as well, which was invisible only because
    the flag never reached a backend. Once it did, removing one key destroyed
    the whole session.
    """

    def test_delitem_marks_modified_not_deleted(self):
        manager = FileSessionManager(SessionConfig())
        session = Session(manager, "a" * 64)
        session["one"] = 1
        session["two"] = 2

        del session["one"]

        assert session.modified is True
        assert session.accessed is True
        assert session.deleted is False

    def test_delete_marks_modified_not_deleted(self):
        manager = FileSessionManager(SessionConfig())
        session = Session(manager, "a" * 64)
        session["one"] = 1

        session.delete("one")

        assert session.deleted is False

    def test_the_rest_of_the_session_survives_over_http(self, store):
        manager, _ = store
        app = SilloApp()
        app.use(
            SessionMiddleware(
                manager=manager, secret_key=SECRET, session_cookie_secure=False
            )
        )

        @app.get("/fill")
        async def fill(request: HttpContext):
            request.session["user_id"] = 7
            request.session["cart"] = "abc"
            return json({"ok": True})

        @app.get("/drop")
        async def drop(request: HttpContext):
            del request.session["cart"]
            return json({"ok": True})

        @app.get("/show")
        async def show(request: HttpContext):
            return json(
                {
                    "user_id": request.session.get("user_id"),
                    "cart": request.session.get("cart"),
                }
            )

        with TestClient(app) as client:
            client.get("/fill")
            client.get("/drop")
            assert client.get("/show").json() == {"user_id": 7, "cart": None}
