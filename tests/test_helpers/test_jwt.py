"""
JWT encoding, decoding, and claim validation.

PyJWT is an optional dependency, so the whole module is skipped when it is
absent. Signature-tampering and expiry are covered explicitly — those are the
cases that matter if this is guarding an API.
"""

from datetime import datetime, timedelta, timezone

import pytest

from sillo.helpers.jwt import (
    ExpiredTokenError,
    InvalidTokenError_,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode,
    decode_without_verification,
    encode,
    get_unverified_claims,
    get_unverified_header,
    sign,
    validate_claims,
    verify,
)

pytest.importorskip("jwt", reason="PyJWT is an optional dependency")

SECRET = "test-secret-key"


# ── round trip ───────────────────────────────────────────────────────────


def test_encode_produces_three_segments():
    assert encode({"sub": "1"}, SECRET).count(".") == 2


def test_round_trip():
    token = encode({"sub": "123", "role": "admin"}, SECRET)
    claims = decode(token, SECRET)
    assert claims["sub"] == "123"
    assert claims["role"] == "admin"


def test_sign_is_an_alias_for_encode():
    assert decode(sign({"sub": "1"}, SECRET), SECRET)["sub"] == "1"


def test_custom_headers_are_carried():
    token = encode({"sub": "1"}, SECRET, headers={"kid": "key-1"})
    assert get_unverified_header(token)["kid"] == "key-1"


def test_a_different_algorithm():
    token = encode({"sub": "1"}, SECRET, algorithm="HS512")
    assert decode(token, SECRET, algorithms=["HS512"])["sub"] == "1"


# ── verification failures ────────────────────────────────────────────────


def test_the_wrong_secret_is_rejected():
    token = encode({"sub": "1"}, SECRET)
    with pytest.raises(TokenError):
        decode(token, "the-wrong-secret")


def test_a_tampered_payload_is_rejected():
    """The whole point of a signature: editing the claims must invalidate it."""
    import base64
    import json

    header, payload, signature = encode({"sub": "1"}, SECRET).split(".")
    forged = base64.urlsafe_b64encode(
        json.dumps({"sub": "admin"}).encode()
    ).decode().rstrip("=")

    with pytest.raises(TokenError):
        decode(f"{header}.{forged}.{signature}", SECRET)


def test_a_malformed_token_is_rejected():
    with pytest.raises(TokenError):
        decode("not-a-token", SECRET)


def test_an_empty_token_is_rejected():
    with pytest.raises(TokenError):
        decode("", SECRET)


def test_verify_reports_true_for_a_good_token():
    assert verify(encode({"sub": "1"}, SECRET), SECRET) is True


def test_verify_reports_false_rather_than_raising():
    assert verify(encode({"sub": "1"}, SECRET), "wrong") is False


def test_verify_on_garbage():
    assert verify("garbage", SECRET) is False


# ── expiry ───────────────────────────────────────────────────────────────


def test_an_expired_token_is_rejected():
    expired = encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}, SECRET
    )
    with pytest.raises((ExpiredTokenError, TokenError)):
        decode(expired, SECRET)


def test_a_future_expiry_is_accepted():
    token = encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, SECRET
    )
    assert decode(token, SECRET)["sub"] == "1"


def test_expiry_verification_can_be_disabled():
    expired = encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}, SECRET
    )
    claims = decode(expired, SECRET, options={"verify_exp": False})
    assert claims["sub"] == "1"


# ── token factories ──────────────────────────────────────────────────────


def test_access_token_carries_its_data():
    token = create_access_token({"sub": "42"}, SECRET)
    assert decode(token, SECRET)["sub"] == "42"


def test_access_token_has_an_expiry():
    assert "exp" in decode(create_access_token({"sub": "1"}, SECRET), SECRET)


def test_access_token_expiry_is_configurable():
    token = create_access_token({"sub": "1"}, SECRET, expires_delta=timedelta(days=7))
    short = create_access_token({"sub": "1"}, SECRET, expires_delta=timedelta(minutes=1))
    assert decode(token, SECRET)["exp"] > decode(short, SECRET)["exp"]


def test_refresh_token_carries_its_data():
    assert decode(create_refresh_token({"sub": "42"}, SECRET), SECRET)["sub"] == "42"


def test_a_refresh_token_outlives_an_access_token():
    access = decode(create_access_token({"sub": "1"}, SECRET), SECRET)
    refresh = decode(create_refresh_token({"sub": "1"}, SECRET), SECRET)
    assert refresh["exp"] > access["exp"]


# ── unverified inspection ────────────────────────────────────────────────


def test_unverified_claims_are_readable_without_the_secret():
    """Useful for reading a 'kid' before choosing a key — never for trust."""
    token = encode({"sub": "1"}, SECRET)
    assert get_unverified_claims(token)["sub"] == "1"


def test_unverified_claims_of_garbage_is_none():
    assert get_unverified_claims("garbage") is None


def test_unverified_header_reports_the_algorithm():
    assert get_unverified_header(encode({"sub": "1"}, SECRET))["alg"] == "HS256"


def test_decode_without_verification_ignores_a_bad_signature():
    token = encode({"sub": "1"}, SECRET)
    tampered = token[:-4] + "AAAA"
    assert decode_without_verification(tampered)["sub"] == "1"


# ── claim validation ─────────────────────────────────────────────────────


def test_claims_validate_when_they_match():
    payload = {"sub": "1", "aud": "my-api", "iss": "my-issuer"}
    assert validate_claims(payload, audience="my-api", issuer="my-issuer") is True


def test_a_wrong_audience_fails():
    payload = {"sub": "1", "aud": "other-api"}
    assert validate_claims(payload, audience="my-api") is False


def test_a_wrong_issuer_fails():
    payload = {"sub": "1", "iss": "someone-else"}
    assert validate_claims(payload, issuer="my-issuer") is False


def test_claims_without_constraints_pass():
    assert validate_claims({"sub": "1"}) is True


def test_an_expired_claim_set_fails():
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    assert validate_claims({"sub": "1", "exp": past.timestamp()}) is False


def test_leeway_tolerates_recent_expiry():
    just_past = datetime.now(timezone.utc) - timedelta(seconds=5)
    assert validate_claims({"sub": "1", "exp": just_past.timestamp()}, leeway=60) is True


# ── exception hierarchy ──────────────────────────────────────────────────


def test_specific_errors_derive_from_tokenerror():
    """One except clause should be able to catch every token problem."""
    assert issubclass(ExpiredTokenError, TokenError)
    assert issubclass(InvalidTokenError_, TokenError)


def test_ensure_jwt_raises_import_error_without_pyjwt(monkeypatch):
    import sillo.helpers.jwt as jwt_helpers

    monkeypatch.setattr(jwt_helpers, "_jwt_available", False)
    with pytest.raises(ImportError, match="PyJWT is required"):
        jwt_helpers._ensure_jwt()


def test_access_token_carries_the_issuer_claim():
    token = create_access_token({"sub": "1"}, SECRET, issuer="my-issuer")
    payload = decode(token, SECRET)
    assert payload["iss"] == "my-issuer"


def test_refresh_token_expiry_is_configurable():
    token = create_refresh_token(
        {"sub": "1"}, SECRET, expires_delta=timedelta(minutes=5)
    )
    payload = decode(token, SECRET)
    lifetime = payload["exp"] - payload["iat"]
    assert 290 <= lifetime <= 300


def test_decode_without_verification_rejects_unparseable_garbage():
    with pytest.raises(InvalidTokenError_, match="Cannot decode token"):
        decode_without_verification("not-a-real-token-at-all")


def test_validate_claims_accepts_a_datetime_expiry():
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert validate_claims({"sub": "1", "exp": future}) is True


def test_validate_claims_rejects_a_past_datetime_expiry():
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    assert validate_claims({"sub": "1", "exp": past}) is False


def test_validate_claims_rejects_a_not_yet_valid_token():
    future_nbf = datetime.now(timezone.utc) + timedelta(hours=1)
    assert validate_claims({"sub": "1", "nbf": future_nbf.timestamp()}) is False


def test_validate_claims_accepts_a_datetime_nbf_already_valid():
    past_nbf = datetime.now(timezone.utc) - timedelta(hours=1)
    assert validate_claims({"sub": "1", "nbf": past_nbf}) is True
