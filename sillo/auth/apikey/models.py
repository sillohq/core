from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import ClassVar, Optional

from tortoise import fields

from sillo.record import Model, TimestampsMixin


def generate_api_key(prefix: str = "sillo") -> tuple[str, str, str]:
    raw = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, raw, key_hash


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    computed = hashlib.sha256(raw_key.encode()).hexdigest()
    return secrets.compare_digest(computed, stored_hash)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKey(Model, TimestampsMixin):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    key_hash = fields.CharField(max_length=255, unique=True, index=True)
    last_used_at = fields.DatetimeField(null=True, default=None)
    expires_at = fields.DatetimeField(null=True, default=None)
    is_active: ClassVar[fields.BooleanField] = fields.BooleanField(default=True)
    scopes = fields.JSONField(null=True, default=None)
    user_id = fields.IntField(index=True)

    class Meta:
        table = "api_keys"

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    async def mark_used(self) -> None:
        self.last_used_at = datetime.now(timezone.utc)
        await self.save(update_fields=["last_used_at"])

    async def revoke(self) -> None:
        self.is_active = False
        await self.save(update_fields=["is_active"])


class ApiKeyManager:
    model = ApiKey

    async def create_key(
        self,
        user_id: int,
        name: str,
        scopes: Optional[list[str]] = None,
        expires_at: Optional[datetime] = None,
        prefix: str = "sillo",
    ) -> tuple[str, ApiKey]:
        full_key, _, key_hash = generate_api_key(prefix=prefix)
        apikey = await self.model.create(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            scopes=scopes or [],
            expires_at=expires_at,
        )
        return full_key, apikey

    async def verify(self, raw_key: str) -> Optional[ApiKey]:
        key_hash = hash_api_key(raw_key)
        apikey = await self.model.filter(key_hash=key_hash, is_active=True).first()
        if apikey is None or apikey.is_expired:
            return None
        await apikey.mark_used()
        return apikey

    async def get_for_user(self, user_id: int) -> list[ApiKey]:
        return await self.model.filter(user_id=user_id, is_active=True).all()

    async def revoke_all_for_user(self, user_id: int) -> int:
        count = await self.model.filter(user_id=user_id, is_active=True).count()
        await self.model.filter(user_id=user_id).update(is_active=False)
        return count
