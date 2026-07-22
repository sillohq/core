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
    """Encode a dictionary payload into a signed JSON Web Token string.

    Wraps the project's JWT helper to produce a compact, URL-safe token
    string. When ``expires_in`` is provided and the payload does not already
    contain an ``exp`` claim, an expiration timestamp is automatically
    injected based on the current UTC time plus the given duration.

    Args:
        payload: A dictionary of claims to encode into the token body.
        secret: The symmetric secret key used to sign the token.
        algorithm: The signing algorithm identifier. Defaults to ``"HS256"``.
        expires_in: An optional duration after which the token should expire.
            If provided and ``payload`` lacks an ``exp`` key, the claim is
            set to ``utcnow() + expires_in``.

    Returns:
        A compact JWT string suitable for transmission in HTTP headers or
        response bodies.

    Raises:
        Exception: If the underlying JWT encoder fails due to an unsupported
            algorithm or invalid payload types.
    """
    if expires_in and "exp" not in payload:
        payload = {**payload, "exp": datetime.now(timezone.utc) + expires_in}
    return jwt_helpers.encode(payload, secret, algorithm)


def decode_jwt(
    token: str,
    secret: str,
    algorithms: Optional[list[str]] = None,
) -> dict:
    """Decode and verify a JSON Web Token, returning its claims as a dictionary.

    Wraps the project's JWT helper to decode the compact token string back
    into its original payload. The token's signature is verified against the
    provided secret, and expiration is enforced. Specific JWT error types are
    translated into :class:`ValueError` for a simpler caller interface.

    Args:
        token: The compact JWT string to decode and verify.
        secret: The symmetric secret key used to verify the token signature.
        algorithms: An optional list of acceptable signing algorithms. Defaults
            to ``["HS256"]`` when ``None``.

    Returns:
        A dictionary of decoded claims from the token payload.

    Raises:
        ValueError: With message ``"Token has expired"`` if the token's ``exp``
            claim is in the past, or ``"Invalid token"`` if the signature is
            invalid, the algorithm is not allowed, or the token is malformed.
    """
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
