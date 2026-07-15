from __future__ import annotations

from typing import Any, Optional

from sillo.auth.backends.base import AuthenticationBackend
from sillo.auth.jwt_auth.models import TokenBlacklist
from sillo.auth.model import AuthResult
from sillo.helpers import jwt as jwt_helpers
from sillo.http import Request


def _decode_jwt(token: str, secret: str) -> dict:
    try:
        return jwt_helpers.decode(token, secret, algorithms=["HS256"])
    except jwt_helpers.ExpiredTokenError:
        raise ValueError("Token has expired")
    except jwt_helpers.InvalidTokenError_:
        raise ValueError("Invalid token")


class JWTAuthBackend(AuthenticationBackend):
    def __init__(
        self,
        identifier: str = "id",
        secret_key: Optional[str] = None,
        check_blacklist: bool = True,
    ):
        self.identifier = identifier
        self.secret_key = secret_key
        self.check_blacklist = check_blacklist

    async def authenticate(self, request: Request) -> Any:
        if not self.secret_key:
            raise RuntimeError("secret_key is required for JWTAuthBackend")

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return AuthResult(success=False, identity="", scope="")

        token = auth_header.split(" ")[1]

        if self.check_blacklist:
            if await self._is_blacklisted(token):
                return AuthResult(success=False, identity="", scope="")

        try:
            payload = _decode_jwt(token, self.secret_key)
        except ValueError:
            return AuthResult(success=False, identity="", scope="")

        return AuthResult(
            success=True,
            identity=payload.get(self.identifier, ""),
            scope="jwt",
        )

    async def _is_blacklisted(self, token: str) -> bool:
        try:
            return await TokenBlacklist.filter(token_jti=token).exists()
        except Exception:
            return False
