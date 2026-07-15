from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from sillo.auth.jwt_auth.tokens import TokenForUser


@pytest.fixture
def user():
    u = MagicMock()
    u.identity = "42"
    u.display_name = "testuser"
    return u


@pytest.fixture
def tokens(user):
    return TokenForUser(user, secret="a-32-byte-secret-key-for-hs256")


class TestTokenForUser:
    """TokenForUser — JWT token creation, verification, inspection."""

    # -- creation ----------------------------------------------------------

    def test_access_token_creates_valid_jwt(self, tokens):
        token = tokens.access_token()
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_access_token_contains_sub_claim(self, tokens):
        token = tokens.access_token()
        payload = tokens.decode_unverified(token)
        assert payload["sub"] == "42"
        assert payload["typ"] == "access"
        assert "iat" in payload
        assert "exp" in payload

    def test_access_token_custom_expiry(self, tokens):
        token = tokens.access_token(expires_in=timedelta(hours=2))
        payload = tokens.decode_unverified(token)
        assert payload["exp"] - payload["iat"] == 7200

    def test_refresh_token_creates_valid_jwt(self, tokens):
        token = tokens.refresh_token()
        assert isinstance(token, str)
        payload = tokens.decode_unverified(token)
        assert payload["typ"] == "refresh"

    def test_refresh_token_custom_expiry(self, tokens):
        token = tokens.refresh_token(expires_in=timedelta(days=14))
        payload = tokens.decode_unverified(token)
        assert payload["exp"] - payload["iat"] == 14 * 86400

    def test_token_pair_returns_dict(self, tokens):
        pair = tokens.token_pair()
        assert "access_token" in pair
        assert "refresh_token" in pair
        assert pair["token_type"] == "bearer"
        assert isinstance(pair["access_token"], str)
        assert isinstance(pair["refresh_token"], str)

    def test_token_pair_tokens_are_different(self, tokens):
        pair = tokens.token_pair()
        assert pair["access_token"] != pair["refresh_token"]

    def test_token_pair_custom_expiry(self, tokens):
        pair = tokens.token_pair(
            access_expires=timedelta(minutes=30),
            refresh_expires=timedelta(days=30),
        )
        ap = tokens.decode_unverified(pair["access_token"])
        rp = tokens.decode_unverified(pair["refresh_token"])
        assert ap["exp"] - ap["iat"] == 1800
        assert rp["exp"] - rp["iat"] == 30 * 86400

    # -- verification ------------------------------------------------------

    def test_verify_decodes_valid_token(self, tokens):
        token = tokens.access_token()
        payload = tokens.verify(token)
        assert payload["sub"] == "42"

    def test_verify_no_expire_ignores_expiry(self, tokens):
        from datetime import datetime, timezone

        token = tokens.access_token(expires_in=timedelta(seconds=-1))
        payload = tokens.verify_no_expire(token)
        assert payload["sub"] == "42"

    def test_verify_raises_on_invalid(self, tokens):
        with pytest.raises(Exception):
            tokens.verify("not.a.valid.token")

    # -- issuer / audience -------------------------------------------------

    def test_issuer_in_payload(self, user):
        tokens = TokenForUser(user, secret="key", issuer="my-issuer")
        token = tokens.access_token()
        payload = tokens.verify(token)
        assert payload["iss"] == "my-issuer"

    def test_audience_in_payload(self, user):
        tokens = TokenForUser(user, secret="key", audience="my-aud")
        token = tokens.access_token()
        payload = tokens.verify(token)
        assert payload["aud"] == "my-aud"

    # -- inspection (static) -----------------------------------------------

    def test_decode_unverified(self, tokens):
        token = tokens.access_token()
        payload = TokenForUser.decode_unverified(token)
        assert payload["sub"] == "42"
        # Should NOT verify signature — any junk token with valid parts works
        import base64, json

        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
        body = base64.urlsafe_b64encode(json.dumps({"sub": "99"}).encode()).decode().rstrip("=")
        junk = f"{header}.{body}.badsignature"
        payload = TokenForUser.decode_unverified(junk)
        assert payload["sub"] == "99"

    def test_get_unverified_header(self, tokens):
        token = tokens.access_token()
        header = TokenForUser.get_unverified_header(token)
        assert header["alg"] == "HS256"
        assert header["typ"] == "JWT"

    # -- algorithm --------------------------------------------------------

    def test_custom_algorithm(self, user):
        tokens = TokenForUser(user, secret="key", algorithm="HS384")
        token = tokens.access_token()
        header = TokenForUser.get_unverified_header(token)
        assert header["alg"] == "HS384"


class TestTokenForUserEdgeCases:
    """Edge cases and error handling."""

    def test_tampered_token_fails_verification(self):
        from sillo.auth.jwt_auth.tokens import TokenForUser

        u = MagicMock()
        u.identity = "1"
        tokens = TokenForUser(u, secret="key")
        token = tokens.access_token()
        tampered = token[:-5] + "xxxxx"
        with pytest.raises(Exception):
            tokens.verify(tampered)

    def test_different_secret_fails_verification(self):
        u1 = MagicMock()
        u1.identity = "1"
        t1 = TokenForUser(u1, secret="secret-one")
        u2 = MagicMock()
        u2.identity = "1"
        t2 = TokenForUser(u2, secret="secret-two")
        token = t1.access_token()
        with pytest.raises(Exception):
            t2.verify(token)
