from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar, Optional

from tortoise import fields

from sillo.record import Model, TimestampsMixin


class Session(Model, TimestampsMixin):
    """Active session tracking — per-user, per-device.

    Enables "logout everywhere" and session audit.
    """

    id = fields.IntField(pk=True)
    user_id = fields.IntField(index=True)
    session_key = fields.CharField(max_length=255, unique=True, index=True)
    ip_address = fields.CharField(max_length=45, null=True, default=None)
    user_agent = fields.TextField(null=True, default=None)
    last_activity = fields.DatetimeField(auto_now=True)
    expires_at = fields.DatetimeField()
    is_active: ClassVar[fields.BooleanField] = fields.BooleanField(default=True)
    device_name = fields.CharField(max_length=255, null=True, default=None)

    class Meta:
        table = "user_sessions"

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    async def mark_activity(self) -> None:
        self.last_activity = datetime.now(timezone.utc)
        await self.save(update_fields=["last_activity"])

    async def terminate(self) -> None:
        self.is_active = False
        await self.save(update_fields=["is_active"])

    async def extend(self, duration_seconds: int = 3600) -> None:
        self.expires_at = datetime.now(timezone.utc).timestamp() + duration_seconds
        await self.save(update_fields=["expires_at"])

    @classmethod
    async def terminate_all_for_user(cls, user_id: int) -> int:
        count = await cls.filter(user_id=user_id, is_active=True).count()
        await cls.filter(user_id=user_id).update(is_active=False)
        return count

    @classmethod
    async def cleanup_expired(cls) -> int:
        now = datetime.now(timezone.utc)
        expired = await cls.filter(is_active=True, expires_at__lt=now).all()
        for session in expired:
            session.is_active = False
            await session.save(update_fields=["is_active"])
        return len(expired)
