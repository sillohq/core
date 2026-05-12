from typing import Optional
import typing

try:
    import jwt
except ImportError:
    jwt = None
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from nexios.auth.model import AuthResult
from nexios.http import Request

from .base import AuthenticationBackend


def create_jwt(
    payload: Dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
    expires_in: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT token.
    Args:
        payload (dict): Data to include in the token.
        secret (str): Secret key to sign the token.
        algorithm (str): Algorithm to use for signing the token.
    Returns:
        str: Encoded JWT token.
    """
    if jwt is None:
        raise ImportError("JWT support is not installed.")

    if expires_in and not payload.get("exp"):
        payload["exp"] = datetime.now(timezone.utc) + expires_in
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_jwt(
    token: str, secret: str, algorithms: List[str] = ["HS256"]
) -> Dict[str, Any]:
    """
    Decode a JWT token.
    Args:
        token (str): Encoded JWT token.
        secret (str): Secret key used to sign the token.
        algorithms (list): List of algorithms to decode the token.
    Returns:
        dict: Decoded token payload.
    """
    if jwt is None:
        raise ImportError("JWT support is not installed.")
    try:
        return jwt.decode(token, secret, algorithms=algorithms)
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


class JWTAuthBackend(AuthenticationBackend):
    def __init__(self, identifier: str = "id", secret_key: typing.Optional[str] = None):
        self.identifier = identifier
        self.secret_key = secret_key

    async def authenticate(self, request: Request) -> Any:
        if not self.secret_key:
            raise RuntimeError("secret_key is required for JWTAuthBackend")

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return AuthResult(success=False, identity="", scope="")

        token = auth_header.split(" ")[1]
        try:
            payload = decode_jwt(token, self.secret_key)
        except ValueError as _:
            return AuthResult(success=False, identity="", scope="")

        return AuthResult(
            success=True, identity=payload.get(self.identifier, ""), scope="jwt"
        )
