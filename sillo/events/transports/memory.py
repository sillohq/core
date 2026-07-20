"""sillo.events.transports.memory — In-process transport (default backend).

Keeps the original sillo behaviour: emitted events dispatch to local
listeners synchronously within the same process.  No external services, no
serialisation round-trip beyond the envelope bookkeeping.
"""

from __future__ import annotations

from typing import Any, Dict

from .base import BaseTransport


class MemoryTransport(BaseTransport):
    """Default, in-process delivery.  Backwards compatible with the old
    synchronous ``EventEmitter`` semantics."""

    name = "memory"

    async def publish(self, channel: str, envelope: Dict[str, Any]) -> None:
        await self._deliver(channel, envelope)
