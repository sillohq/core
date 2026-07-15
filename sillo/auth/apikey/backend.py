from __future__ import annotations

import hashlib
import secrets
from typing import Any, Optional

from sillo.auth.backends.base import AuthenticationBackend
from sillo.auth.apikey.models import ApiKeyManager
from sillo.auth.model import AuthResult
from sillo.http import Request


class APIKeyAuthBackend(AuthenticationBackend):
    def __init__(
        self,
        header_name: str = "X-API-Key",
        prefix: str = "key",
        verify_with_manager: bool = False,
    ):
        self.header_name = header_name
        self.prefix = prefix
        self.verify_with_manager = verify_with_manager

    async def authenticate(self, request: Request) -> Any:
        raw_token = request.headers.get(self.header_name)

        if not raw_token:
            return AuthResult(success=False, identity="", scope="")

        if self.verify_with_manager:
            apikey = await ApiKeyManager().verify(raw_token)
            if apikey is None:
                return AuthResult(success=False, identity="", scope="")
            return AuthResult(
                success=True,
                identity=str(apikey.user_id),
                scope="apikey",
            )

        return AuthResult(success=True, identity=raw_token, scope="apikey")
