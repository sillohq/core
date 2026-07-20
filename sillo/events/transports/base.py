"""sillo.events.transports.base — Transport abstraction for the event system.

A :class:`BaseTransport` decides *where* an emitted event goes.  The
:class:`~sillo.events.emitter.EventEmitter` owns the in-process listener
registry (the ``Event`` objects) and registers a ``dispatch`` callback with
the transport.  When a transport receives a message — locally (memory), over
Redis pub/sub, from a durable backlog, or from a record store — it calls that
callback to run the matching local listeners.

This split keeps the rich ``Event`` semantics (priority, capture/bubble,
cancellation, weak refs, metrics) intact while letting the *delivery* layer be
swapped between memory, Redis, persistent, and record backends.
"""

from __future__ import annotations

import abc
import asyncio
import json
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger("sillo.events.transport")

# A dispatch callback receives the channel name and the already-decoded
# payload dict (``{"args": [...], "kwargs": {...}, "event_id": str}``).
DispatchFn = Callable[[str, Dict[str, Any]], Awaitable[None]]

# Called when a listener raises, so hosts can observe failures without the
# subscriber loop dying.
ErrorFn = Callable[[BaseException, str, Dict[str, Any]], Awaitable[None]]


class TransportError(Exception):
    """Raised when a transport cannot fulfil a request (e.g. Redis down)."""


def serialize_payload(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Encode emit arguments into a transport-agnostic envelope.

    Args/kwargs are JSON-encoded so they survive Redis / record stores.
    Listeners still receive the *original* Python objects because the
    emitter decodes on the dispatch side.  Non-serialisable values fall back
    to ``repr`` so a misbehaving emit never kills the transport.
    """

    def _safe(obj: Any) -> Any:
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return {"__unsupported__": repr(obj)}

    return {
        "event_id": str(uuid.uuid4()),
        "args": [_safe(a) for a in args],
        "kwargs": {k: _safe(v) for k, v in kwargs.items()},
        "ts": time.time(),
    }


def serialize_envelope(envelope: Dict[str, Any]) -> str:
    return json.dumps(envelope, default=str)


def deserialize_envelope(raw: str) -> Dict[str, Any]:
    return json.loads(raw)


class BaseTransport(abc.ABC):
    """Abstract delivery layer for an :class:`EventEmitter`.

    Subclasses implement :meth:`publish` (send a message) and, if they
    receive messages remotely, :meth:`_listen` (the receive loop).  The base
    class owns lifecycle (``start``/``stop``), the dispatch callback registry,
    and error isolation.
    """

    #: Backend identifier (used by the factory and for logging).
    name: str = "base"

    def __init__(
        self,
        *,
        namespace: str = "",
        on_error: Optional[ErrorFn] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.namespace = namespace
        self._on_error = on_error
        self._loop = loop
        self._dispatch: Optional[DispatchFn] = None
        self._running = False
        # Per-instance seen event_ids for lightweight dedup on reconnect.
        self._seen: "set[str]" = set()
        self._seen_max = 10_000

    def bind(self, dispatch: DispatchFn) -> None:
        """Register the local dispatch callback (set by the emitter)."""
        self._dispatch = dispatch

    def set_error_handler(self, fn: ErrorFn) -> None:
        self._on_error = fn

    def _channel(self, name: str) -> str:
        return f"{self.namespace}:{name}" if self.namespace else name

    async def start(self) -> None:
        """Begin receiving (no-op for memory). Idempotent."""
        self._running = True

    async def stop(self) -> None:
        """Stop receiving and release resources."""
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    @abc.abstractmethod
    async def publish(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Publish an envelope to *channel*. Must be implemented."""

    async def _deliver(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Run the local listeners for a received envelope.

        Error-isolated: a failing listener is reported via ``on_error`` and
        never propagates to the subscriber loop.
        """
        if self._dispatch is None:
            return
        event_id = envelope.get("event_id")
        if event_id:
            if event_id in self._seen:
                # Duplicate delivery (e.g. Redis reconnect replay) — drop.
                return
            self._seen.add(event_id)
            if len(self._seen) > self._seen_max:
                # Bound memory: drop the oldest entries.
                self._seen = set(list(self._seen)[-self._seen_max // 2 :])
        try:
            await self._dispatch(channel, envelope)
        except Exception as exc:  # noqa: BLE001 - isolate listener failures
            logger.exception("Listener error on channel %r", channel)
            if self._on_error is not None:
                try:
                    await self._on_error(exc, channel, envelope)
                except Exception:  # noqa: BLE001
                    logger.exception("on_error handler raised")

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None:
            return self._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            self._loop = loop
            return loop
