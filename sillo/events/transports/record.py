"""sillo.events.transports.record — Persist emitted events as DB rows.

Every emitted event is stored as an :class:`EventMessage` Tortoise row
(channel, payload, status, attempts).  This gives a durable audit log and crash
recovery: events left ``pending``/``failed`` can be replayed via
:meth:`RecordTransport.replay`.  Local listeners still fire immediately via the
shared dispatch callback; the row is then marked ``delivered`` or ``failed``.

``sillo.record`` (Tortoise) must be configured with ``setup_record`` and the
``EventMessage`` model registered in its ``model_modules`` (see
:func:`setup_event_record`).  Tortoise is imported lazily so the base
``events`` package loads without it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base import (
    BaseTransport,
    TransportError,
    deserialize_envelope,
    serialize_envelope,
)

logger = logging.getLogger("sillo.events.record")


def build_event_message():
    """Build and return the concrete ``EventMessage`` model bound to
    ``sillo.record.Model``.

    Called lazily (via :func:`setup_event_record`) so importing this module
    never requires Tortoise to be initialised.  The returned class is a normal
    Tortoise model — register it in your ``model_modules`` before
    ``tortoise.init`` (or import it from your models package).

    Returns:
        A ``Model`` subclass with columns ``channel`` (indexed), ``payload``
        (text, the JSON envelope), ``status`` (``pending``/``delivered``/
        ``failed``, indexed) and ``attempts`` (int).
    """
    from tortoise import fields

    from sillo.record import Model

    class EventMessage(Model):
        channel = fields.CharField(max_length=255, db_index=True)
        payload = fields.TextField()
        status = fields.CharField(max_length=16, default="pending", db_index=True)
        attempts = fields.IntField(default=0)

        class Meta:
            table = "sillo_event_messages"

        def __repr__(self) -> str:  # pragma: no cover - cosmetic
            return f"<EventMessage channel={self.channel!r} status={self.status!r}>"

    return EventMessage


# Populated by :func:`setup_event_record` once Tortoise is available.  ``Any``
# because the concrete type is created at runtime (see :func:`build_event_message`).
EventMessage: Any = None  # type: ignore[assignment]


class RecordTransport(BaseTransport):
    """Persist-everything transport backed by a Tortoise ``EventMessage`` table.

    Unlike the Redis backends, ``record`` is about **durability and audit**, not
    cross-instance fan-out: every emit writes a row and also fires local
    listeners (in-process).  Use :meth:`replay` on startup to recover events
    that were ``pending``/``failed`` when the process last stopped.

    Args:
        namespace: Channel prefix applied to stored ``channel`` values.
        model: Optional ``EventMessage`` class.  Defaults to the module-level
            :data:`EventMessage` populated by :func:`setup_event_record`.
        on_error: Optional listener-error callback.
        loop: Optional event loop (unused; record delivery is in-process).

    Requires:
        ``sillo.record`` configured (``setup_record``) and ``EventMessage``
        registered, or an explicit ``model=``.

    Example:
        >>> from sillo.events.transports import get_transport, setup_event_record
        >>> EventMessage = setup_event_record()   # add to your model_modules
        >>> emitter = EventEmitter("record")
        >>> emitter.on("audit.trail")(lambda e: ...)
        >>> await emitter.emit_async("audit.trail", event)
    """

    name = "record"

    def __init__(
        self,
        *,
        namespace: str = "",
        model=None,
        on_error=None,
        loop=None,
    ) -> None:
        super().__init__(namespace=namespace, on_error=on_error, loop=loop)
        self._model = model

    @property
    def model(self):
        """Resolve the ``EventMessage`` model to use.

        Raises:
            TransportError: if neither ``model=`` was passed nor
                :func:`setup_event_record` has been called.
        """
        model = self._model or EventMessage
        if model is None:
            raise TransportError(
                "Record backend requires setup_event_record() after setup_record(), "
                "or pass model= explicitly."
            )
        return model

    async def start(self) -> None:
        """Mark the transport running (no background loop needed)."""
        self._running = True

    async def stop(self) -> None:
        """Mark the transport stopped."""
        self._running = False

    async def publish(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Persist *envelope* as a row, then fire local listeners.

        The row starts as ``pending``; on success it becomes ``delivered``, on
        listener failure ``failed`` (with ``attempts`` incremented).  A DB
        write failure propagates as :class:`TransportError` — the event is not
        delivered locally in that case.
        """
        model = self.model
        row = await model.create(
            channel=self._channel(channel),
            payload=serialize_envelope(envelope),
            status="pending",
        )
        try:
            await self._deliver(channel, envelope)
            row.status = "delivered"
        except Exception:  # noqa: BLE001
            row.status = "failed"
            row.attempts = row.attempts + 1
            logger.exception("Event %s dispatch failed", envelope.get("event_id"))
        await row.save(update_fields=["status", "attempts"])

    async def replay(
        self,
        *,
        statuses: tuple = ("pending", "failed"),
        limit: int = 100,
    ) -> int:
        """Re-dispatch stored events not yet delivered.

        Reads rows whose ``status`` is in *statuses* (default ``pending`` and
        ``failed``), re-runs their local listeners via the dispatch callback,
        and marks each ``delivered`` on success (or bumps ``attempts`` on
        failure).  Useful on startup to recover events from a previous run.

        Args:
            statuses: Tuple of statuses to include.
            limit: Maximum number of rows to replay in one call (0 = no limit
                is not supported; pass a large int for "all").

        Returns:
            The number of events successfully replayed.
        """
        model = self.model
        rows = await model.filter(status__in=statuses).limit(limit).all()
        replayed = 0
        for row in rows:
            try:
                envelope = deserialize_envelope(row.payload)
                local = row.channel
                if self.namespace and local.startswith(self.namespace + ":"):
                    local = local[len(self.namespace) + 1 :]
                await self._deliver(local, envelope)
                row.status = "delivered"
                await row.save(update_fields=["status"])
                replayed += 1
            except Exception:  # noqa: BLE001
                row.attempts = row.attempts + 1
                await row.save(update_fields=["attempts"])
                logger.exception("Replay failed for event row %s", row.id)
        return replayed
