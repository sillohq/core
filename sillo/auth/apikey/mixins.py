from __future__ import annotations

from datetime import datetime
from typing import Optional

from sillo.auth.apikey.models import ApiKey, ApiKeyManager


class ApiKeyUserMixin:
    async def create_api_key(
        self,
        name: str,
        scopes: Optional[list[str]] = None,
        expires_at: Optional[datetime] = None,
        prefix: str = "sillo",
    ) -> tuple[str, object]:
        return await ApiKeyManager().create_key(
            user_id=int(str(self.identity)),
            name=name,
            scopes=scopes,
            expires_at=expires_at,
            prefix=prefix,
        )

    async def get_api_keys(self):
        return await ApiKeyManager().get_for_user(int(str(self.identity)))

    async def revoke_all_api_keys(self) -> int:
        return await ApiKeyManager().revoke_all_for_user(int(str(self.identity)))

    async def revoke_api_key(self, key_id: int) -> bool:
        apikey = await ApiKey.filter(
            id=key_id,
            user_id=int(str(self.identity)),
            is_active=True,
        ).first()
        if apikey:
            await apikey.revoke()
            return True
        return False
