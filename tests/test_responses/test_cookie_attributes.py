"""Writing cookies: round-tripping, deletion, and the attributes that decide
whether a browser keeps one at all.

Each of these failed quietly rather than loudly, which is the reason they are
worth pinning: a browser that rejects a ``Set-Cookie`` does not say so, and the
symptom lands somewhere else entirely -- a user who cannot sign out, a value
that comes back mangled, a cookie that was never stored.
"""

from __future__ import annotations

import pytest

from sillo.core.http.cookies import parse_cookies
from sillo.core.http.response import BaseResponse


def cookies_of(response: BaseResponse) -> list[str]:
    return [v.decode() for k, v in response.raw_headers if k == b"set-cookie"]


def only_cookie(response: BaseResponse) -> str:
    headers = cookies_of(response)
    assert len(headers) == 1
    return headers[0]


class TestRoundTrip:
    @pytest.mark.parametrize(
        "value",
        [
            "abc123",
            "a=b/c%20d",
            'he said "hi"',
            "café",
            "x;y,z",
            "/home/user",
            '{"k":1}',
            "100%",
            "eyJhIjoxfQ.RdgQSV8-_x",
        ],
    )
    def test_a_value_survives_being_written_and_read_back(self, value):
        """``SimpleCookie`` answers a value it dislikes by wrapping it in double
        quotes and backslash-escaping, and nothing undid that: the parser
        percent-decodes, as browsers do, so ``"a=b/c%20d"`` came back as
        ``'"a=b/c d"'`` -- quotes attached and an escape decoded nobody wrote.
        """
        response = BaseResponse()
        response.set_cookie("c", value)

        header = only_cookie(response).split(";")[0]

        assert parse_cookies(header) == {"c": value}

    def test_an_ordinary_token_is_not_encoded_at_all(self):
        """Percent-encoding must not churn the values that were already fine,
        or every session cookie in existence changes shape."""
        response = BaseResponse()
        response.set_cookie("session_id", "eyJhIjoxfQ.RdgQSV8-_x")

        assert only_cookie(response).startswith("session_id=eyJhIjoxfQ.RdgQSV8-_x;")

    def test_a_value_never_escapes_its_own_cookie(self):
        """The separators have to be encoded, or a value could append
        attributes -- or a second cookie -- of its own. The injected words
        survive inside the value, which is fine; what must not survive is the
        ``;`` that would make them attributes."""
        response = BaseResponse()
        response.set_cookie("c", "x; HttpOnly; Domain=evil.test", path="/")

        attributes = [part.strip() for part in only_cookie(response).split(";")[1:]]

        assert attributes == ["Path=/", "SameSite=lax"]

    def test_a_value_cannot_inject_a_second_header(self):
        response = BaseResponse()
        response.set_cookie("c", "x\r\nSet-Cookie: admin=1")

        header = only_cookie(response)

        assert "\r" not in header
        assert "\n" not in header


class TestDeletion:
    def test_the_expiry_is_in_the_past(self):
        response = BaseResponse()
        response.delete_cookie("sid")

        assert "expires=Thu, 01 Jan 1970 00:00:00 GMT" in only_cookie(response)

    def test_it_does_not_depend_on_the_client_clock(self):
        """``expires=0`` was passed through to ``SimpleCookie``, which reads a
        number as an offset from now -- so the deletion was stamped with the
        current time, and a client running slightly behind kept the cookie."""
        header = only_cookie(_deleted())

        assert "1970" in header

    def test_the_security_attributes_can_be_repeated(self):
        """A ``__Host-`` or ``__Secure-`` prefixed cookie is rejected outright
        when the deletion is not marked Secure, so signing out left the cookie
        in place and the user signed in."""
        response = BaseResponse()
        response.delete_cookie("__Host-sid", secure=True, httponly=True)

        header = only_cookie(response)

        assert "Secure" in header
        assert "HttpOnly" in header

    def test_max_age_is_zero(self):
        assert "Max-Age=0" in only_cookie(_deleted())


def _deleted() -> BaseResponse:
    response = BaseResponse()
    response.delete_cookie("sid")
    return response


class TestSameSiteNone:
    def test_it_is_refused_without_secure(self):
        """Browsers drop a ``SameSite=None`` cookie that is not ``Secure`` and
        report nothing, so the setting meant to allow cross-site use instead
        switched the cookie off."""
        with pytest.raises(ValueError, match="samesite='none'"):
            BaseResponse().set_cookie("c", "1", samesite="none")

    def test_it_is_allowed_with_secure(self):
        response = BaseResponse()
        response.set_cookie("c", "1", samesite="none", secure=True)

        header = only_cookie(response)

        assert "SameSite=none" in header
        assert "Secure" in header

    def test_lax_needs_nothing(self):
        response = BaseResponse()
        response.set_cookie("c", "1", samesite="lax")

        assert "SameSite=lax" in only_cookie(response)


class TestSeveralCookies:
    def test_each_gets_its_own_header(self):
        """They are appended rather than replaced, so a response can carry a
        session cookie and a CSRF cookie at once."""
        response = BaseResponse()
        response.set_cookie("a", "1")
        response.set_cookie("b", "2")

        assert len(cookies_of(response)) == 2
