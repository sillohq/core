from __future__ import annotations

import datetime
import json
import typing
from typing import Any, Dict, Optional

try:
    import jwt as pyjwt
    from jwt.exceptions import (
        ExpiredSignatureError,
        InvalidTokenError,
        DecodeError,
    )
    _jwt_available = True
except ImportError:
    _jwt_available = False
    pyjwt = None  # type: ignore
    ExpiredSignatureError = Exception
    InvalidTokenError = Exception
    DecodeError = Exception


class TokenError(Exception):
    pass


class ExpiredTokenError(TokenError):
    pass


class InvalidTokenError_(TokenError):
    pass


def _ensure_jwt():
    if not _jwt_available:
        raise ImportError(
            "PyJWT is required for JWT helpers. Install with: pip install pyjwt"
        )


def encode(
    payload: Dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
    headers: Optional[Dict[str, Any]] = None,
) -> str:
    _ensure_jwt()
    return pyjwt.encode(payload, secret, algorithm=algorithm, headers=headers)


def decode(
    token: str,
    secret: str,
    algorithms: Optional[typing.List[str]] = None,
    options: Optional[Dict[str, Any]] = None,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
    leeway: int = 0,
) -> Dict[str, Any]:
    _ensure_jwt()
    return pyjwt.decode(
        token,
        secret,
        algorithms=algorithms or ["HS256"],
        options=options,
        audience=audience,
        issuer=issuer,
        leeway=leeway,
    )


def sign(
    payload: Dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
    headers: Optional[Dict[str, Any]] = None,
) -> bytes:
    _ensure_jwt()
    encoded = pyjwt.encode(payload, secret, algorithm=algorithm, headers=headers)
    return encoded.encode("utf-8") if isinstance(encoded, str) else encoded


def verify(
    token: str,
    secret: str,
    algorithms: Optional[typing.List[str]] = None,
) -> bool:
    _ensure_jwt()
    try:
        pyjwt.decode(token, secret, algorithms=algorithms or ["HS256"])
        return True
    except (InvalidTokenError, ExpiredSignatureError, DecodeError):
        return False


def get_unverified_header(token: str) -> Dict[str, Any]:
    _ensure_jwt()
    return pyjwt.get_unverified_header(token)


def get_unverified_claims(token: str) -> Optional[Dict[str, Any]]:
    _ensure_jwt()
    try:
        return json.loads(
            pyjwt.utils.base64url_decode(token.split(".")[1].encode()).decode()
        )
    except Exception:
        return None


def create_access_token(
    data: Dict[str, Any],
    secret: str,
    expires_delta: Optional[datetime.timedelta] = None,
    algorithm: str = "HS256",
    issuer: Optional[str] = None,
) -> str:
    _ensure_jwt()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire, "iat": datetime.datetime.now(datetime.timezone.utc)})
    if issuer:
        to_encode["iss"] = issuer
    return pyjwt.encode(to_encode, secret, algorithm=algorithm)


def create_refresh_token(
    data: Dict[str, Any],
    secret: str,
    expires_delta: Optional[datetime.timedelta] = None,
    algorithm: str = "HS256",
) -> str:
    _ensure_jwt()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    to_encode.update({"exp": expire, "iat": datetime.datetime.now(datetime.timezone.utc)})
    return pyjwt.encode(to_encode, secret, algorithm=algorithm)


def decode_without_verification(token: str) -> Dict[str, Any]:
    _ensure_jwt()
    try:
        return pyjwt.decode(token, options={"verify_signature": False})
    except Exception:
        raise InvalidTokenError_("Cannot decode token")


def validate_claims(
    payload: Dict[str, Any],
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
    leeway: int = 0,
) -> bool:
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()

    if "exp" in payload:
        exp = payload["exp"]
        if isinstance(exp, datetime.datetime):
            exp = exp.timestamp()
        if now > exp + leeway:
            return False

    if "nbf" in payload:
        nbf = payload["nbf"]
        if isinstance(nbf, datetime.datetime):
            nbf = nbf.timestamp()
        if now < nbf - leeway:
            return False

    if audience and payload.get("aud") != audience:
        return False

    if issuer and payload.get("iss") != issuer:
        return False

    return True
