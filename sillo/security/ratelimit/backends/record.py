"""
sillo.security.ratelimit.backends.record — sillo Record (ORM) backend.

Stores rate-limit state in the application database via ``sillo.record``. Use
this when you want persistence without an external cache and can tolerate
single-instance-level atomicity. The ``RateLimitCounter`` model must be
registered with your Record setup (see ``sillo.security.ratelimit.models``).
"""

from __future__ import annotations

import json
import time
import typing
from typing import Any, Optional

from typing_extensions import Doc

from .base import RateLimitBackend
from ..models import RateLimitCounter


class RecordBackend(RateLimitBackend):
    """Persist rate-limit state using the sillo Record ORM."""

    async def fetch_state(self, key: str) -> Optional[dict]:
        """Fetch State

        Args:
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return await RateLimitCounter.fetch(key)

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
        await RateLimitCounter.save_state(key, state, ttl)

    async def clear(self) -> None:
        """Clear

        Returns:
            [description]

        Raises:
            [description]
        """
        await RateLimitCounter.clear_all()
