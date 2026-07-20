"""sillo.events.transports.memory — In-process transport (default backend).

Keeps the original sillo behaviour: emitted events dispatch to local
listeners within the same process.  No external services, no serialisation
round-trip beyond the envelope bookkeeping.  This is the backend selected when
``backend="memory"`` (the default) or when no backend is given.
"""

from __future__ import annotations

from typing import Any, Dict

from .base import BaseTransport


class MemoryTransport(BaseTransport):
    """Default, in-process delivery.  Backwards compatible with the old
    synchronous :class:`~sillo.events.emitter.EventEmitter` semantics.

    ``publish`` simply calls :meth:`~sillo.events.transports.base.BaseTransport._deliver`
    directly, so delivery is immediate and in-order.  No ``start`` /
    background loop is required, although ``start`` / ``stop`` are still
    honoured as no-ops for API symmetry with the networked backends.

    Example:
        >>> from sillo.events.emitter import EventEmitter
        >>> emitter = EventEmitter("memory")
        >>> emitter.on("ping")(lambda: print("pong"))
        >>> emitter.emit("ping")            # synchronous, in-process
        {'event_id': '...', 'listeners_executed': 1, ...}
    """

    name = "memory"

    async def publish(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Deliver *envelope* to local listeners immediately.

        Because memory transport has no remote hop, this is equivalent to
        running the listeners in the caller's context — which is why the
        emitter's synchronous :meth:`~sillo.events.emitter.EventEmitter.emit`
        works on this backend without an event loop.
        """
        await self._deliver(channel, envelope)
