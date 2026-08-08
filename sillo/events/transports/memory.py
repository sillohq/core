"""sillo.events.transports.memory — In-process transport (default backend).

Keeps the original sillo behaviour: emitted events dispatch to local
listeners within the same process.  No external services, no serialisation
round-trip beyond the envelope bookkeeping.  This is the backend selected when
``backend="memory"`` (the default) or when no backend is given.
"""

from __future__ import annotations

from typing import Any

from .base import BaseTransport


class MemoryTransport(BaseTransport):
    """Default in-process transport that delivers events synchronously.

    This transport provides backwards-compatible, in-process event delivery
    where emitted events dispatch to local listeners within the same Python
    process.  No external services, network connections, or serialization
    round-trips are involved beyond the standard envelope bookkeeping.

    The :meth:`publish` method calls :meth:`~BaseTransport._deliver` directly,
    so delivery is immediate and in-order.  No background loop is required,
    although :meth:`start` and :meth:`stop` are still honoured as no-ops for
    API symmetry with the networked backends (Redis, persistent).

    This is the backend selected when ``backend="memory"`` (the default) or
    when no backend argument is supplied to the emitter or transport factory.

    Attributes:
        name: The backend identifier string, always ``"memory"`` for this class.
            Used by the factory function and logging infrastructure.

    Example:
        >>> from sillo.events.emitter import EventEmitter
        >>> emitter = EventEmitter("memory")
        >>> emitter.on("ping")(lambda: print("pong"))
        >>> emitter.emit("ping")            # synchronous, in-process
        {'event_id': '...', 'listeners_executed': 1, ...}
    """

    name = "memory"

    async def publish(self, channel: str, envelope: dict[str, Any]) -> None:
        """Deliver an envelope to local listeners immediately and in-process.

        Because the memory transport has no remote hop, this method simply
        delegates to :meth:`~BaseTransport._deliver`, which runs the matching
        listeners in the caller's async context.  This is why the emitter's
        synchronous :meth:`~sillo.events.emitter.EventEmitter.emit` works on
        this backend without requiring an explicit event loop.

        The method preserves the full envelope structure (event ID, args,
        kwargs, timestamp) so that de-duplication and error isolation behave
        identically to the networked backends.

        Args:
            channel: The fully-qualified channel name (including any namespace
                prefix) on which the envelope was published.  Passed through
                to the dispatch callback for listener matching.
            envelope: The envelope dictionary produced by
                :func:`~sillo.events.transports.base.serialize_payload`,
                containing ``"event_id"``, ``"args"``, ``"kwargs"``, and
                ``"ts"`` keys.

        Raises:
            This method does not raise.  All listener errors are isolated by
            :meth:`~BaseTransport._deliver` and routed to the configured
            ``on_error`` handler if one is registered.

        Example:
            >>> envelope = serialize_payload(("hello",), {"target": "world"})
            >>> await transport.publish("greeting", envelope)
        """
        await self._deliver(channel, envelope)
