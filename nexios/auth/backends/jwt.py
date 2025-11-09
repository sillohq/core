try:
    import jwt
except ImportError:
    jwt = None
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from nexios.auth.model import AuthResult
from nexios.config import get_config
from nexios.http import Request, Response

from .base import AuthenticationBackend


def create_jwt(
    payload: Dict[str, Any],
    secret: Optional[str] = None,
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

    secret = secret or get_config().secret_key
    if expires_in and not payload.get("exp"):
        payload["exp"] = datetime.now(timezone.utc) + expires_in
    return jwt.encode(payload, secret, algorithm=algorithm)  # type:ignore


def decode_jwt(
    token: str, secret: Optional[str] = None, algorithms: List[str] = ["HS256"]
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
    secret = secret or get_config().secret_key
    try:
        return jwt.decode(token, secret, algorithms=algorithms)  # type:ignore
    except jwt.ExpiredSignatureError:  # type:ignore
        raise ValueError("Token has expired")  # type:ignore
    except jwt.InvalidTokenError:  # type:ignore
        raise ValueError("Invalid token")


class JWTAuthBackend(AuthenticationBackend):
    def __init__(self, identifier: str = "id"):  # type:ignore
        self.identifier = identifier

    async def authenticate(self, request: Request, response: Response) -> Any:  # type:ignore
        app_config = get_config()
        self.secret = app_config.secret_key
        self.algorithms = app_config.jwt_algorithms or ["HS256"]

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            response.set_header("WWW-Authenticate", 'Bearer realm="Access to the API"')
            return AuthResult(success=False, identity="", scope="")

        token = auth_header.split(" ")[1]
        try:
            payload = decode_jwt(token, self.secret, self.algorithms)
        except ValueError as _:
            return AuthResult(success=False, identity="", scope="")

        return AuthResult(
            success=True, identity=payload.get(self.identifier, ""), scope="jwt"
        )
