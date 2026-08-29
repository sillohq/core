"""When a session stops being usable.

Three settings claimed to control this and none of them reached anything:
``Session`` looked for the settings under ``config.session`` while the
middleware held them directly and handed the backend no config at all, so
every branch fell through to a hardcoded seven days. Underneath that, the
signed cookie carried a timestamp that was never compared against anything,
so the only expiry a signed session had was one the browser was politely
asked to enforce.
"""

from __future__ import annotations

import time
import warnings
from datetime import datetime, timedelta, timezone

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.session import SessionConfig
from sillo.session.middleware import SessionMiddleware
from sillo.session.signed_cookies import SignedSessionManager
from sillo.testclient import TestClient

SECRET = "x" * 32


def app_with(**settings):
    app = SilloApp()
    app.use(SessionMiddleware(secret_key=SECRET, session_cookie_secure=False, **settings))

    @app.get("/login")
    async def login(request: HttpContext):
        request.session["user_id"] = 7
        return json({"ok": True})

    @app.get("/whoami")
    async def whoami(request: HttpContext):
        return json({"user_id": request.session.get("user_id")})

    return app


class TestTheBackendGetsTheConfig:
    def test_the_default_backend_is_handed_the_settings(self):
        """It was constructed with only the secret, so it had no lifetime to
        bound its cookie with and `Session` had no settings to read."""
        middleware = SessionMiddleware(secret_key=SECRET, session_expiration_time=60)

        assert middleware.session_interface.config is middleware.session_config

    def test_the_lifetime_reaches_the_signature(self):
        middleware = SessionMiddleware(secret_key=SECRET, session_expiration_time=60)

        assert middleware.session_interface.max_age == 60

    def test_a_supplied_backend_without_a_config_is_given_one(self):
        config = SessionConfig(session_expiration_time=99)
        manager = SignedSessionManager(secret_key=SECRET)

        middleware = SessionMiddleware(config=config, manager=manager)

        assert manager.config is config


class TestSignedCookiesExpireServerSide:
    """The cookie's ``Expires`` is a request to the browser. Anyone replaying a
    captured cookie simply does not honour it, so the bound has to be inside
    the signature."""

    def test_a_token_older_than_the_lifetime_is_not_accepted(self, monkeypatch):
        manager = SignedSessionManager(
            secret_key=SECRET, config=SessionConfig(session_expiration_time=60)
        )
        token = manager.sign_session_data({"user_id": 7})

        assert manager.verify_session_data(token) == {"user_id": 7}

        later = time.time() + 61
        monkeypatch.setattr(time, "time", lambda: later)

        assert manager.verify_session_data(token) == {}

    async def test_a_stale_cookie_no_longer_authenticates(self, monkeypatch):
        with TestClient(app_with(session_expiration_time=60)) as client:
            client.get("/login")
            assert client.get("/whoami").json() == {"user_id": 7}

            later = time.time() + 3600
            monkeypatch.setattr(time, "time", lambda: later)

            assert client.get("/whoami").json() == {"user_id": None}

    def test_a_lifetime_is_applied_even_with_no_configuration(self):
        """A backend built by hand still gets a bound, rather than none."""
        assert SignedSessionManager(secret_key=SECRET).max_age == 86400

    def test_a_non_ascii_cookie_is_refused_rather_than_raising(self):
        """It arrives from the client, so its bytes are the client's to pick.
        ``str.encode('ascii')`` and ``compare_digest`` both raise on non-ASCII,
        uncaught, which made a one-byte cookie a 500."""
        manager = SignedSessionManager(secret_key=SECRET)

        assert manager.verify_session_data("café.café") == {}


class TestCookieExpiry:
    def test_a_permanent_session_expires_after_the_configured_lifetime(self):
        """It used to get ``datetime.max`` -- so the default configuration
        issued a cookie that never expired, and the lifetime applied only to
        the non-permanent case that did not need it."""
        manager = SignedSessionManager(
            secret_key=SECRET,
            config=SessionConfig(session_permanent=True, session_expiration_time=3600),
        )
        expiry = manager.create_session().get_expiration_time()

        assert expiry is not None
        expected = datetime.now(timezone.utc) + timedelta(seconds=3600)
        assert abs((expiry - expected).total_seconds()) < 5

    def test_a_non_permanent_session_gets_no_expiry_at_all(self):
        """"Not permanent" means the browser drops it on close, which is an
        absent ``Expires``, not one far in the future."""
        manager = SignedSessionManager(
            secret_key=SECRET, config=SessionConfig(session_permanent=False)
        )

        assert manager.create_session().get_expiration_time() is None

    def test_the_cookie_carries_no_expires_when_not_permanent(self):
        with TestClient(app_with(session_permanent=False)) as client:
            cookie = client.get("/login").headers["set-cookie"]

        assert "expires" not in cookie.lower()

    def test_the_cookie_carries_the_configured_expiry_when_permanent(self):
        with TestClient(app_with(session_expiration_time=3600)) as client:
            cookie = client.get("/login").headers["set-cookie"]

        assert "expires" in cookie.lower()

    def test_an_explicit_expiry_still_wins(self):
        manager = SignedSessionManager(secret_key=SECRET)
        session = manager.create_session()
        chosen = datetime.now(timezone.utc) + timedelta(days=3)
        session.set_expiration_time(chosen)

        assert session.get_expiration_time() == chosen

    def test_a_permanent_session_can_be_asked_whether_it_expired(self):
        manager = SignedSessionManager(
            secret_key=SECRET, config=SessionConfig(session_permanent=True)
        )

        assert manager.create_session().has_expired() is False

    def test_a_non_permanent_session_has_not_expired_either(self):
        manager = SignedSessionManager(
            secret_key=SECRET, config=SessionConfig(session_permanent=False)
        )

        assert manager.create_session().has_expired() is False


class TestRefreshEachRequest:
    def test_a_permanent_session_re_sends_its_cookie(self):
        """This is what slides the expiry forward for an active visitor. It
        read ``config.session``, found nothing, and returned ``modified``."""
        manager = SignedSessionManager(
            secret_key=SECRET,
            config=SessionConfig(
                session_permanent=True, session_refresh_each_request=True
            ),
        )

        assert manager.create_session().should_set_cookie is True

    def test_it_can_be_turned_off(self):
        manager = SignedSessionManager(
            secret_key=SECRET,
            config=SessionConfig(
                session_permanent=True, session_refresh_each_request=False
            ),
        )

        assert manager.create_session().should_set_cookie is False

    def test_a_modified_session_is_always_written(self):
        manager = SignedSessionManager(
            secret_key=SECRET,
            config=SessionConfig(
                session_permanent=True, session_refresh_each_request=False
            ),
        )
        session = manager.create_session()
        session["user_id"] = 7

        assert session.should_set_cookie is True


class TestOversizedCookies:
    def test_a_session_too_large_for_a_browser_warns(self):
        """Browsers drop a cookie over ~4096 bytes and say nothing, so the
        session silently stops persisting while every response looks fine."""
        app = SilloApp()
        app.use(SessionMiddleware(secret_key=SECRET, session_cookie_secure=False))

        @app.get("/fill")
        async def fill(request: HttpContext):
            request.session["blob"] = "x" * 5000
            return json({"ok": True})

        with TestClient(app) as client:
            with pytest.warns(RuntimeWarning, match="over the"):
                client.get("/fill")

    def test_an_ordinary_session_does_not_warn(self):
        with TestClient(app_with()) as client:
            with warnings.catch_warnings():
                warnings.simplefilter("error", RuntimeWarning)
                client.get("/login")
