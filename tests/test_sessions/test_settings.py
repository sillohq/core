"""A misspelled session setting must be an error, not a silent default.

Session settings used to be collected with ``**kwargs`` and either merged into
the config dictionary unchecked or handed to ``BaseMiddleware``, which accepts
anything and reads none of it. Both paths accepted a name nothing would ever
read, and the damage was not theoretical: ``cookie_secure=False`` left the real
``session_cookie_secure`` at ``True``, so the cookie went out marked ``Secure``,
browsers stopped returning it over plain HTTP, and sessions did nothing at all
in local development — with no error anywhere to explain why.
"""

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.session import SessionConfig
from sillo.session.middleware import SessionMiddleware
from sillo.testclient import TestClient

SECRET = "x" * 32


class TestUnknownSettingsAreRejected:
    @pytest.mark.parametrize(
        "wrong, right",
        [
            ("cookie_secure", "session_cookie_secure"),
            ("cookie_httponly", "session_cookie_httponly"),
            ("cookie_samesite", "session_cookie_samesite"),
            ("cookie_path", "session_cookie_path"),
            ("cookie_domain", "session_cookie_domain"),
        ],
    )
    def test_config_rejects_a_near_miss_and_names_the_real_setting(self, wrong, right):
        with pytest.raises(TypeError) as caught:
            SessionConfig(**{wrong: False})

        message = str(caught.value)
        assert wrong in message
        assert right in message

    @pytest.mark.parametrize(
        "wrong, right",
        [
            ("cookie_secure", "session_cookie_secure"),
            ("cookie_samesite", "session_cookie_samesite"),
        ],
    )
    def test_middleware_rejects_the_same_names(self, wrong, right):
        with pytest.raises(TypeError) as caught:
            SessionMiddleware(secret_key=SECRET, **{wrong: False})

        message = str(caught.value)
        assert wrong in message
        assert right in message

    def test_a_name_with_no_near_miss_still_lists_the_settings(self):
        with pytest.raises(TypeError) as caught:
            SessionConfig(entirely_made_up=1)

        message = str(caught.value)
        assert "entirely_made_up" in message
        assert "session_cookie_secure" in message

    def test_reading_a_setting_that_does_not_exist_raises(self):
        """Returning None made every misspelled read look like an unset value."""
        config = SessionConfig()
        with pytest.raises(AttributeError, match="cookie_secure"):
            config.cookie_secure

    def test_config_and_settings_together_are_refused(self):
        """One of the two would have to win silently."""
        with pytest.raises(TypeError, match="both a config="):
            SessionMiddleware(
                config=SessionConfig(),
                secret_key=SECRET,
                session_cookie_path="/elsewhere",
            )


class TestSettingsOnTheMiddlewareTakeEffect:
    """Settings passed to the middleware went to BaseMiddleware and vanished."""

    def build(self, **settings):
        app = SilloApp()
        app.use(SessionMiddleware(secret_key=SECRET, **settings))

        @app.get("/set")
        async def set_value(ctx: HttpContext):
            ctx.session["user_id"] = 7
            return json({"ok": True})

        return app

    def test_cookie_name(self):
        with TestClient(self.build(session_cookie_name="my_session")) as client:
            cookie = client.get("/set").headers["set-cookie"]
        assert cookie.startswith("my_session=")

    def test_secure_can_be_turned_off(self):
        """The one that broke local development."""
        with TestClient(self.build(session_cookie_secure=False)) as client:
            cookie = client.get("/set").headers["set-cookie"]
        assert "Secure" not in cookie

    def test_secure_is_still_on_by_default(self):
        with TestClient(self.build()) as client:
            cookie = client.get("/set").headers["set-cookie"]
        assert "Secure" in cookie

    def test_samesite(self):
        with TestClient(self.build(session_cookie_samesite="strict")) as client:
            cookie = client.get("/set").headers["set-cookie"]
        assert "SameSite=strict" in cookie

    def test_path(self):
        with TestClient(self.build(session_cookie_path="/scoped")) as client:
            cookie = client.get("/set").headers["set-cookie"]
        assert "Path=/scoped" in cookie

    def test_httponly_can_be_turned_off(self):
        with TestClient(self.build(session_cookie_httponly=False)) as client:
            cookie = client.get("/set").headers["set-cookie"]
        assert "HttpOnly" not in cookie


class TestSessionsSurviveOverPlainHttp:
    """The end-to-end shape of the original bug."""

    def test_a_session_round_trips_without_secure(self):
        app = SilloApp()
        app.use(SessionMiddleware(secret_key=SECRET, session_cookie_secure=False))

        @app.get("/login")
        async def login(ctx: HttpContext):
            ctx.session["user_id"] = 7
            ctx.session["cart"] = "abc"
            return json({"ok": True})

        @app.get("/whoami")
        async def whoami(ctx: HttpContext):
            return json(
                {
                    "user_id": ctx.session.get("user_id"),
                    "cart": ctx.session.get("cart"),
                }
            )

        @app.get("/drop-cart")
        async def drop_cart(ctx: HttpContext):
            del ctx.session["cart"]
            return json({"dropped": True})

        with TestClient(app) as client:
            client.get("/login")
            assert client.get("/whoami").json() == {"user_id": 7, "cart": "abc"}

            # Removing one key must not take the rest of the session with it.
            client.get("/drop-cart")
            assert client.get("/whoami").json() == {"user_id": 7, "cart": None}


class TestExpiry:
    def test_a_permanent_session_can_be_asked_whether_it_expired(self):
        """get_expiration_time() returned a naive datetime.max for permanent
        sessions while every other branch returned an aware one, so
        has_expired() raised TypeError instead of answering False."""
        config = SessionConfig(session_permanent=True)

        class Interface:
            class config_holder:
                session = config

        interface = Interface()
        interface.config = Interface.config_holder

        from sillo.session.session_objects import Session

        assert Session(interface, "key").has_expired() is False

    def test_a_non_permanent_session_has_not_expired_yet(self):
        config = SessionConfig(session_permanent=False, session_expiration_time=3600)

        class Interface:
            class config_holder:
                session = config

        interface = Interface()
        interface.config = Interface.config_holder

        from sillo.session.session_objects import Session

        assert Session(interface, "key").has_expired() is False
