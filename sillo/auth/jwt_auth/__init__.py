from datetime import datetime, timedelta, timezone
from typing import Optional

from sillo.auth.jwt_auth.backend import JWTAuthBackend
from sillo.auth.jwt_auth.mixins import JWTUserMixin
from sillo.auth.jwt_auth.models import JWTToken, TokenBlacklist
from sillo.auth.jwt_auth.tokens import TokenForUser
from sillo.helpers import jwt as jwt_helpers


def create_jwt(
    payload: dict,
    secret: str,
    algorithm: str = "HS256",
    expires_in: Optional[timedelta] = None,
) -> str:
    if expires_in and "exp" not in payload:
        payload = {**payload, "exp": datetime.now(timezone.utc) + expires_in}
    return jwt_helpers.encode(payload, secret, algorithm)


def decode_jwt(
    token: str,
    secret: str,
    algorithms: Optional[list[str]] = None,
) -> dict:
    try:
        return jwt_helpers.decode(token, secret, algorithms=algorithms or ["HS256"])
    except jwt_helpers.ExpiredTokenError:
        raise ValueError("Token has expired")
    except jwt_helpers.InvalidTokenError_:
        raise ValueError("Invalid token")


__all__ = [
    "JWTAuthBackend",
    "TokenForUser",
    "create_jwt",
    "decode_jwt",
    "JWTToken",
    "TokenBlacklist",
    "JWTUserMixin",
]
