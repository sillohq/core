"""sillo.events.transports.record — Persist emitted events as DB rows.

Every emitted event is stored as an :class:`EventMessage` Tortoise row
(channel, payload, status, timestamps).  This gives a durable audit log and
crash recovery: rows left ``pending``/``failed`` can be replayed via
:meth:`RecordTransport.replay`.  Local listeners still fire immediately via
the shared dispatch callback; the row is then marked ``delivered`` or
``failed``.

``sillo.record`` (Tortoise) must be configured with ``setup_record`` and the
``EventMessage`` model registered in its ``model_modules``.  Tortoise is
imported lazily so the base ``events`` package loads without it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base import BaseTransport, TransportError, deserialize_envelope, serialize_envelope

logger = logging.getLogger("sillo.events.record")


def build_event_message():
    """Build and return the concrete ``EventMessage`` model bound to
    ``sillo.record.Model``.  Called lazily so importing this module never
    requires Tortoise to be initialised."""
    from tortoise import fields

    from sillo.record import Model

    class EventMessage(Model):
        channel = fields.CharField(max_length=255, db_index=True)
        payload = fields.TextField()
        status = fields.CharField(
            max_length=16, default="pending", db_index=True
        )
        attempts = fields.IntField(default=0)

        class Meta:
            table = "sillo_event_messages"

        def __repr__(self) -> str:  # pragma: no cover - cosmetic
            return f"<EventMessage channel={self.channel!r} status={self.status!r}>"

    return EventMessage


# Populated by ``setup_event_record`` once Tortoise is available.
EventMessage: Any = None  # type: ignore[assignment]


class RecordTransport(BaseTransport):
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
        model = self._model or EventMessage
        if model is None:
            raise TransportError(
                "Record backend requires setup_event_record() after setup_record(), "
                "or pass model= explicitly."
            )
        return model

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def publish(self, channel: str, envelope: Dict[str, Any]) -> None:
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
        """Re-dispatch stored events not yet delivered.  Returns count replayed."""
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
