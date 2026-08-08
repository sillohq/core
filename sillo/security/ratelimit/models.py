"""
sillo.security.ratelimit.models — Record (ORM) model for the Record backend.

This model stores per-key rate-limit state. Register its module with
``setup_record`` (or ``DatabaseManager.register_models``) so Tortoise discovers
it, e.g. ``model_modules=["sillo.security.ratelimit.models"]``.
"""

from __future__ import annotations

import json
import time

from tortoise import fields

from sillo.record import Model


class RateLimitCounter(Model):
    """Persisted rate-limit state keyed by ``key`` (namespace-aware)."""

    key = fields.CharField(max_length=255, unique=True, db_index=True)
    state = fields.TextField()
    expires_at = fields.IntField()

    class Meta:
        """Meta"""

        table = "sillo_ratelimit_counters"

    @classmethod
    async def fetch(cls, key: str) -> dict | None:
        """Fetch"""
        row = await cls.get_or_none(key=key)
        if row is None:
            return None

        if row.expires_at <= int(time.time()):
            await row.delete()
            return None
        try:
            return json.loads(row.state)
        except (json.JSONDecodeError, TypeError):
            return None

    @classmethod
    async def save_state(cls, key: str, state: dict, ttl: int) -> None:
        """Save State"""
        payload = json.dumps(state)
        expires_at = int(time.time()) + ttl
        row = await cls.get_or_none(key=key)
        if row is None:
            await cls.create(key=key, state=payload, expires_at=expires_at)
        else:
            row.state = payload
            row.expires_at = expires_at
            await row.save()

    @classmethod
    async def clear_all(cls) -> None:
        """Clear All"""
        await cls.all().delete()
