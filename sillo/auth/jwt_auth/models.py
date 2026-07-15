from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar, Optional

from tortoise import fields

from sillo.record import Model, TimestampsMixin


class JWTToken(Model, TimestampsMixin):
    """Issued JWT token — enables refresh chains, family rotation, and revocation.

    Each access + refresh pair shares a ``token_family``. On refresh, the old
    token is marked consumed and a new pair is created. Reuse detection:
    if a consumed refresh token is presented, the entire family is revoked.
    """

    id = fields.IntField(pk=True)
    user_id = fields.IntField(index=True)
    token_jti = fields.CharField(max_length=255, unique=True, index=True)
    token_family = fields.CharField(max_length=64, index=True)
    token_type: ClassVar[fields.CharField] = fields.CharField(max_length=16, default="access")
    expires_at = fields.DatetimeField()
    consumed_at = fields.DatetimeField(null=True, default=None)
    revoked: ClassVar[fields.BooleanField] = fields.BooleanField(default=False)

    class Meta:
        table = "jwt_tokens"

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.revoked and not self.is_expired

    async def consume(self) -> None:
        self.consumed_at = datetime.now(timezone.utc)
        await self.save(update_fields=["consumed_at"])

    async def revoke(self) -> None:
        self.revoked = True
        await self.save(update_fields=["revoked"])

    @classmethod
    async def revoke_family(cls, token_family: str) -> int:
        count = await cls.filter(token_family=token_family, revoked=False).count()
        await cls.filter(token_family=token_family).update(revoked=True)
        return count

    @classmethod
    async def revoke_all_for_user(cls, user_id: int) -> int:
        count = await cls.filter(user_id=user_id, revoked=False).count()
        await cls.filter(user_id=user_id).update(revoked=True)
        return count

    @classmethod
    async def cleanup_expired(cls) -> int:
        now = datetime.now(timezone.utc)
        expired = await cls.filter(expires_at__lt=now).all()
        count = len(expired)
        for token in expired:
            await token.delete()
        return count


class TokenBlacklist(Model, TimestampsMixin):
    """Token blacklist — for immediate invalidation of specific tokens."""

    id = fields.IntField(pk=True)
    token_jti = fields.CharField(max_length=512, unique=True, index=True)
    blacklisted_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField()

    class Meta:
        table = "token_blacklist"

    @classmethod
    async def prune_expired(cls) -> int:
        now = datetime.now(timezone.utc)
        expired = await cls.filter(expires_at__lt=now).all()
        count = len(expired)
        for entry in expired:
            await entry.delete()
        return count
