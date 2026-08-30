"""What the CSRF middleware got wrong, and must not get wrong again.

Four separate faults, each of which looked like it worked:

* ``exempt_urls`` never excused anything, because ``required_urls`` defaults to
  ``["*"]`` and was tested first;
* a fresh token was minted on every request and the cookie overwritten with it,
  so a second tab or two requests in flight invalidated each other;
* the cookie defaulted to ``HttpOnly``, which is the one thing that makes a
  double-submit token unusable -- the page cannot read it to send it back;
* enabling CSRF without a ``secret_key`` raised ``AttributeError`` from inside
  the request path rather than at startup.
"""

from __future__ import annotations

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.security.csrf import CSRFConfig, CSRFMiddleware
from sillo.testclient import TestClient

SECRET = "k" * 32


def build(**config):
    app = SilloApp()
    app.use(CSRFMiddleware(config=CSRFConfig(enabled=True, secret_key=SECRET, **config)))

    @app.get("/token")
    async def token(ctx: HttpContext):
        return json({"token": ctx.state.csrf_token})

    @app.post("/protected")
    async def protected(ctx: HttpContext):
        return json({"status": "ok"})

    @app.post("/webhooks/stripe")
    async def webhook(ctx: HttpContext):
        return json({"status": "ok"})

    return app


class TestConstruction:
    def test_enabling_without_a_secret_is_refused_at_startup(self):
        """It used to leave ``self.serializer`` unassigned and 500 on every
        request with ``AttributeError``."""
        with pytest.raises(ValueError, match="secret_key"):
            CSRFMiddleware(config=CSRFConfig(enabled=True))

    def test_a_disabled_config_without_a_secret_is_fine(self):
        assert CSRFMiddleware(config=CSRFConfig()).use_csrf is False

    def test_a_misspelled_setting_is_refused(self):
        """``secure=True`` left the real ``cookie_secure`` at False and the
        token cookie went out over plain HTTP, with nothing to say so."""
        with pytest.raises(TypeError, match="cookie_secure"):
            CSRFConfig(secure=True)


class TestExemptUrls:
    def test_an_exempt_url_is_actually_exempt(self):
        """The whole point of the setting, and it did nothing: the test was
        ``required(url) or (exempt(url) and ...)``, and ``required`` is true
        for everything by default."""
        with TestClient(build(exempt_urls=[r"/webhooks/.*"])) as client:
            assert client.post("/webhooks/stripe").status_code == 200

    def test_a_url_that_is_not_exempt_still_needs_a_token(self):
        with TestClient(build(exempt_urls=[r"/webhooks/.*"])) as client:
            assert client.post("/protected").status_code == 403

    def test_everything_is_protected_when_nothing_is_exempt(self):
        with TestClient(build()) as client:
            assert client.post("/protected").status_code == 403
            assert client.post("/webhooks/stripe").status_code == 403


class TestSensitiveCookies:
    def test_a_request_without_one_does_not_need_a_token(self):
        """For an API authenticated by a header: no ambient authority means
        the request cannot be a CSRF."""
        with TestClient(build(sensitive_cookies=["sessionid"])) as client:
            assert client.post("/protected").status_code == 200

    def test_a_request_carrying_one_does(self):
        with TestClient(build(sensitive_cookies=["sessionid"])) as client:
            client.cookies.set("sessionid", "abc")
            assert client.post("/protected").status_code == 403

    def test_naming_none_protects_everything(self):
        with TestClient(build()) as client:
            assert client.post("/protected").status_code == 403


class TestTheTokenIsStable:
    def test_the_same_token_comes_back_on_a_second_request(self):
        """Minting a new one each time meant the form rendered a moment ago
        answered 403, and two tabs could never both work."""
        with TestClient(build()) as client:
            first = client.get("/token").json()["token"]
            second = client.get("/token").json()["token"]

        assert first == second

    def test_the_cookie_matches_what_the_page_was_given(self):
        with TestClient(build()) as client:
            response = client.get("/token")

        assert response.json()["token"] == response.cookies["csrftoken"]

    def test_a_token_survives_being_used(self):
        with TestClient(build()) as client:
            token = client.get("/token").json()["token"]

            assert (
                client.post("/protected", headers={"X-CSRFToken": token}).status_code
                == 200
            )
            assert client.get("/token").json()["token"] == token

    def test_a_forged_cookie_is_replaced_rather_than_trusted(self):
        with TestClient(build()) as client:
            client.cookies.set("csrftoken", "not-a-signed-token")
            issued = client.get("/token").json()["token"]

        assert issued != "not-a-signed-token"

    def test_a_stolen_token_from_another_application_does_not_pass(self):
        other = CSRFMiddleware(config=CSRFConfig(enabled=True, secret_key="z" * 32))

        with TestClient(build()) as client:
            client.get("/token")
            forged = other._generate_csrf_token()
            response = client.post("/protected", headers={"X-CSRFToken": forged})

        assert response.status_code == 403


class TestTheCookieIsReadable:
    def test_it_is_not_httponly_by_default(self):
        """HttpOnly is what makes double-submit impossible: the page cannot
        read the cookie to echo it back. Sillo's own GraphiQL client does
        exactly that and could never have worked."""
        with TestClient(build()) as client:
            cookie = client.get("/token").headers["set-cookie"]

        assert "HttpOnly" not in cookie

    def test_it_can_still_be_turned_on(self):
        with TestClient(build(cookie_httponly=True)) as client:
            cookie = client.get("/token").headers["set-cookie"]

        assert "HttpOnly" in cookie


class TestSubmissionChannels:
    def test_a_header_is_accepted(self):
        with TestClient(build()) as client:
            token = client.get("/token").json()["token"]
            response = client.post("/protected", headers={"X-CSRFToken": token})

        assert response.status_code == 200

    def test_a_urlencoded_form_field_is_accepted(self):
        with TestClient(build()) as client:
            token = client.get("/token").json()["token"]
            response = client.post("/protected", data={"csrftoken": token})

        assert response.status_code == 200

    def test_a_multipart_form_field_is_accepted(self):
        """A file-upload form cannot set a header, and multipart was not
        checked -- so every upload form was a 403 with no way to pass."""
        with TestClient(build()) as client:
            token = client.get("/token").json()["token"]
            response = client.post(
                "/protected",
                data={"csrftoken": token},
                files={"upload": ("a.txt", b"hello")},
            )

        assert response.status_code == 200

    def test_the_form_field_name_is_configurable(self):
        with TestClient(build(form_field="_csrf")) as client:
            token = client.get("/token").json()["token"]

            assert client.post("/protected", data={"_csrf": token}).status_code == 200
            assert (
                client.post("/protected", data={"csrftoken": token}).status_code == 403
            )

    def test_a_wrong_token_is_still_refused(self):
        with TestClient(build()) as client:
            client.get("/token")
            response = client.post("/protected", headers={"X-CSRFToken": "nope"})

        assert response.status_code == 403


class TestFailedValidationKeepsTheToken:
    def test_a_rejected_request_does_not_destroy_a_valid_cookie(self):
        """The 403 used to delete the cookie, and ``process_response`` does not
        run on a short-circuited request -- so a client that merely forgot the
        header lost the token it already held and had to fetch a page again."""
        with TestClient(build()) as client:
            token = client.get("/token").json()["token"]

            assert client.post("/protected").status_code == 403
            assert client.cookies["csrftoken"] == token
            assert (
                client.post("/protected", headers={"X-CSRFToken": token}).status_code
                == 200
            )


class TestSafeMethods:
    @pytest.mark.parametrize("method", ["get", "head", "options"])
    def test_they_never_need_a_token(self, method):
        """Not "200" -- OPTIONS has no route here and answers 405. The claim is
        that CSRF never turns a safe method away."""
        with TestClient(build()) as client:
            assert getattr(client, method)("/token").status_code != 403
