"""
sillo.security.ratelimit.backends.redis — Redis-backed shared backend.

Recommended for multi-instance deployments. State is stored as a JSON string
with a TTL. A Lua script performs the read-modify-write atomically so that
concurrent hits from different workers can't double-count or race.

The backend depends on ``redis`` (``redis.asyncio``). If it is not installed,
constructing the backend raises ``ImportError`` with an actionable message.
"""

from __future__ import annotations

import json
import time
import typing
from typing import Any, Optional

from typing_extensions import Doc

from .base import RateLimitBackend

# Atomic fetch-modify-save. KEYS[1] = state key, ARGV[1] = ttl seconds,
# ARGV[2] = new JSON state. Returns the stored JSON.
_LUA_SET = """
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[1])
return ARGV[2]
"""


class RedisBackend(RateLimitBackend):
    """Persist rate-limit state in Redis, shared across all app instances."""

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        prefix: str = "sillo:ratelimit:",
        **kwargs: Any,
    ) -> None:
        """Init

            Args:
                url: [description]
                prefix: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "RedisBackend requires the 'redis' package. "
                "Install it with: pip install redis"
            ) from exc

        self._prefix = prefix
        self._client = aioredis.from_url(url, **kwargs)
        self._script = self._client.register_script(_LUA_SET)

    def _key(self, key: str) -> str:
        """Key

            Args:
                key: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return f"{self._prefix}{key}"

    async def fetch_state(self, key: str) -> Optional[dict]:
        """Fetch State

            Args:
                key: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        raw = await self._client.get(self._key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def save_state(self, key: str, state: dict, ttl: int) -> None:
        """Save State

            Args:
                key: [description]
                state: [description]
                ttl: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        payload = json.dumps(state)
        await self._script(keys=[self._key(key)], args=[ttl, payload])

    async def clear(self) -> None:
        """Clear

            Returns:
                [description]

            Raises:
                [description]
        """
        async for name in self._client.scan_iter(match=f"{self._prefix}*"):
            await self._client.delete(name)
