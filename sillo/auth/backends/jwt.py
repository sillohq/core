from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sillo.auth.model import AuthResult
from sillo.helpers import jwt as jwt_helpers
from sillo.http import Request

from .base import AuthenticationBackend


def create_jwt(
    payload: Dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
    expires_in: Optional[timedelta] = None,
) -> str:
    if expires_in and "exp" not in payload:
        payload = {**payload, "exp": datetime.now(timezone.utc) + expires_in}
    return jwt_helpers.encode(payload, secret, algorithm)


def decode_jwt(
    token: str, secret: str, algorithms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    try:
        return jwt_helpers.decode(token, secret, algorithms=algorithms or ["HS256"])
    except jwt_helpers.ExpiredTokenError:
        raise ValueError("Token has expired")
    except jwt_helpers.InvalidTokenError_:
        raise ValueError("Invalid token")


class JWTAuthBackend(AuthenticationBackend):
    def __init__(self, identifier: str = "id", secret_key: Optional[str] = None):
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
        except ValueError:
            return AuthResult(success=False, identity="", scope="")

        return AuthResult(
            success=True, identity=payload.get(self.identifier, ""), scope="jwt"
        )
