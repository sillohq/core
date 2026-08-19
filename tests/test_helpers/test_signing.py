"""The HMAC signer under every signed cookie in the framework.

Sessions and CSRF tokens both rest on this, so its failure modes are theirs.
The ones that mattered: a timestamp nothing ever compared against, a salt that
separated two purposes only by luck of concatenation, and a malformed payload
that raised ``ValueError`` straight out of the request path.
"""

from __future__ import annotations

import base64
import time

import pytest

from sillo.helpers.signing import (
    BadSignature,
    SignatureExpired,
    URLSafeSerializer,
    URLSafeTimedSerializer,
)

SECRET = "k" * 32


class TestRoundTrip:
    def test_a_signed_value_comes_back(self):
        s = URLSafeSerializer(SECRET, "salt")

        assert s.loads(s.dumps({"user_id": 7})) == {"user_id": 7}

    def test_a_timed_value_comes_back(self):
        s = URLSafeTimedSerializer(SECRET, "salt")

        assert s.loads(s.dumps({"user_id": 7}), max_age=60) == {"user_id": 7}

    def test_the_payload_is_readable_by_anyone_holding_the_token(self):
        """Signed is not encrypted, and the difference decides what may go in
        one. Asserted so the property is documented rather than assumed."""
        token = URLSafeSerializer(SECRET, "salt").dumps({"user_id": 7})
        payload = token.rpartition(".")[0]

        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))

        assert b'"user_id":7' in decoded


class TestTampering:
    def test_an_edited_payload_is_refused(self):
        s = URLSafeSerializer(SECRET, "salt")
        payload, _, signature = s.dumps({"admin": False}).rpartition(".")
        edited = payload[:-1] + ("a" if payload[-1] != "a" else "b")

        with pytest.raises(BadSignature):
            s.loads(f"{edited}.{signature}")

    def test_another_secret_does_not_verify(self):
        token = URLSafeSerializer(SECRET, "salt").dumps({"user_id": 7})

        with pytest.raises(BadSignature):
            URLSafeSerializer("x" * 32, "salt").loads(token)

    @pytest.mark.parametrize("token", ["", ".", "nodot", "a.b", "..", "\x80.\x80"])
    def test_a_malformed_token_raises_bad_signature_and_nothing_else(self, token):
        """Every one of these arrives from a cookie, so the only acceptable
        failure is the one callers already catch."""
        with pytest.raises(BadSignature):
            URLSafeTimedSerializer(SECRET, "salt").loads(token, max_age=60)


class TestExpiry:
    def test_a_token_older_than_max_age_is_refused(self, monkeypatch):
        s = URLSafeTimedSerializer(SECRET, "salt")
        token = s.dumps({"user_id": 7})

        later = time.time() + 3600
        monkeypatch.setattr(time, "time", lambda: later)

        with pytest.raises(SignatureExpired):
            s.loads(token, max_age=60)

    def test_the_same_token_is_still_good_inside_max_age(self, monkeypatch):
        s = URLSafeTimedSerializer(SECRET, "salt")
        token = s.dumps({"user_id": 7})

        later = time.time() + 30
        monkeypatch.setattr(time, "time", lambda: later)

        assert s.loads(token, max_age=60) == {"user_id": 7}

    def test_without_max_age_age_is_not_checked_at_all(self, monkeypatch):
        """The default, and the reason the session backend never relies on it:
        a token nothing ages out is one a thief keeps forever."""
        s = URLSafeTimedSerializer(SECRET, "salt")
        token = s.dumps({"user_id": 7})

        later = time.time() + 10**7
        monkeypatch.setattr(time, "time", lambda: later)

        assert s.loads(token) == {"user_id": 7}

    def test_an_expired_token_is_still_a_bad_signature_to_older_callers(self):
        assert issubclass(SignatureExpired, BadSignature)

    def test_a_token_from_the_future_is_refused(self):
        """A clock far ahead cannot have produced a genuine token, and
        accepting one would let a stamp be pushed out of reach of max_age."""
        s = URLSafeTimedSerializer(SECRET, "salt")
        s.clock_skew = 0
        payload = base64.urlsafe_b64encode(
            f"{int(time.time()) + 3600}.".encode() + b'{"user_id":7}'
        ).rstrip(b"=")
        token = f"{payload.decode()}.{s._signature_for(payload)}"

        with pytest.raises(SignatureExpired):
            s.loads(token, max_age=86400)

    def test_a_small_clock_skew_is_tolerated(self):
        s = URLSafeTimedSerializer(SECRET, "salt")
        payload = base64.urlsafe_b64encode(
            f"{int(time.time()) + 5}.".encode() + b'{"user_id":7}'
        ).rstrip(b"=")
        token = f"{payload.decode()}.{s._signature_for(payload)}"

        assert s.loads(token, max_age=86400) == {"user_id": 7}


class TestUntimedTokenReachingATimedSerializer:
    def test_it_is_refused_rather_than_crashing(self):
        """It used to reach ``int()`` on the JSON body and raise ValueError --
        uncaught, so a 500 out of the session middleware rather than a
        request that simply carries no session."""
        untimed = URLSafeSerializer(SECRET, "shared")
        timed = URLSafeTimedSerializer(SECRET, "shared")

        with pytest.raises(BadSignature):
            timed.loads(untimed.dumps({"user_id": 7}), max_age=60)


class TestDomainSeparation:
    def test_two_salts_do_not_verify_each_other(self):
        token = URLSafeSerializer(SECRET, "csrftoken").dumps("x")

        with pytest.raises(BadSignature):
            URLSafeSerializer(SECRET, "session").loads(token)

    def test_a_salt_boundary_cannot_be_shifted(self):
        """The salt used to be prepended to the signed data, so ``("ab", data)``
        and ``("a", b"b" + data)`` signed identical bytes and a token minted
        for one purpose verified under the other.
        """
        one = URLSafeSerializer(SECRET, "ab")
        other = URLSafeSerializer(SECRET, "a")

        assert one._sign(b"cd") != other._sign(b"bcd")
