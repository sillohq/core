"""sillo.events.transports.base — Transport abstraction for the event system.

A :class:`BaseTransport` decides *where* an emitted event goes.  The
:class:`~sillo.events.emitter.EventEmitter` owns the in-process listener
registry (the :class:`~sillo.events.core.Event` objects) and registers a
``dispatch`` callback with the transport.  When a transport receives a message
— locally (memory), over Redis pub/sub, from a durable backlog, or from a
record store — it calls that callback to run the matching local listeners.

This split keeps the rich :class:`~sillo.events.core.Event` semantics
(priority, capture/bubble, cancellation, weak refs, metrics) intact while
letting the *delivery* layer be swapped between ``memory``, ``redis``,
``persistent``, and ``record`` backends (see
:func:`~sillo.events.transports.get_transport`).

Wire format
-----------
Every backend speaks the same JSON "envelope"::

    {
        "event_id": "<uuid4>",
        "args": [...],           # JSON-safe positional args
        "kwargs": {...},         # JSON-safe keyword args
        "ts": 1718000000.123     # emit timestamp (epoch seconds)
    }

Args/kwargs are JSON-encoded so they survive Redis / record stores.  Listeners
still receive the *original* Python objects because the emitter decodes on the
dispatch side — see :func:`serialize_payload`.  Non-serialisable values fall
back to ``{"__unsupported__": repr(obj)}`` so a misbehaving emit never kills
the transport.

Lifecycle
---------
Memory and record transports deliver synchronously/in-process and need no
background loop.  Networked backends (``redis``, ``persistent``) spawn a
background task on :meth:`BaseTransport.start` (typically wired to the
application startup) and tear it down on :meth:`BaseTransport.stop`.

Example
-------
>>> from sillo.events.transports import get_transport
>>> transport = get_transport("memory")
>>> await transport.start()
>>> # ... emitter binds dispatch and emits ...
>>> await transport.stop()
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

#: A dispatch callback receives the (namespaced) channel name and the
#: already-decoded envelope dict, and runs the matching local listeners.
#: It must be awaitable and must *not* raise — failures are isolated by the
#: transport in :meth:`BaseTransport._deliver`.
DispatchFn = Callable[[str, Dict[str, Any]], Awaitable[None]]

#: Called when a listener raises, so hosts can observe failures without the
#: subscriber/worker loop dying.  Receives the exception, channel, and the
#: decoded envelope.
ErrorFn = Callable[[BaseException, str, Dict[str, Any]], Awaitable[None]]


class TransportError(Exception):
    """Raised when a transport cannot fulfil a request.

    Common causes:

    * the backend's optional dependency is missing (e.g. ``redis`` for the
      ``redis`` / ``persistent`` backends, ``tortoise-orm`` for ``record``);
    * the backing service is unreachable (Redis down, Tortoise not initialised).

    It is *not* raised for listener errors — those are routed to the
    :data:`ErrorFn` handler so the delivery loop survives.
    """


def serialize_payload(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Encode emit arguments into a transport-agnostic envelope.

    Args:
        args: Positional arguments passed to ``emit`` / ``emit_async``.
        kwargs: Keyword arguments passed to ``emit`` / ``emit_async``.

    Returns:
        An envelope dict with a fresh ``event_id``, JSON-safe ``args`` /
        ``kwargs``, and a ``ts`` timestamp.  The dict is the single wire
        format shared by every backend.

    Non-serialisable values (sockets, file handles, custom objects) fall back
    to ``{"__unsupported__": repr(obj)}`` so a misbehaving emit never kills
    the transport.  Use JSON-native types (dataclasses with ``asdict``,
    Pydantic ``model_dump``, dicts) for full fidelity.

    Example:
        >>> serialize_payload(("bob",), {"age": 3})["args"]
        ['bob']
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
    """Serialise an envelope dict to the JSON wire string.

    Uses ``default=str`` so any value that slipped past :func:`serialize_payload`
    (e.g. a ``datetime``) still encodes instead of raising.  The counterpart
    is :func:`deserialize_envelope`.
    """
    return json.dumps(envelope, default=str)


def deserialize_envelope(raw: str) -> Dict[str, Any]:
    """Parse a JSON wire string back into an envelope dict.

    Raises:
        json.JSONDecodeError: if *raw* is not valid JSON.  Callers (Redis /
        persistent loops) catch this and drop the malformed message.
    """
    return json.loads(raw)


class BaseTransport(abc.ABC):
    """Abstract delivery layer for an :class:`~sillo.events.emitter.EventEmitter`.

    Subclasses implement :meth:`publish` (send a message) and, if they receive
    messages remotely, a background receive loop started from :meth:`start`
    (see :class:`~sillo.events.transports.redis.RedisTransport` and
    :class:`~sillo.events.transports.persistent.PersistentTransport`).  The base
    class owns the shared responsibilities:

    * the dispatch callback registry (``bind`` / ``set_error_handler``);
    * the lifecycle flags and ``start`` / ``stop`` contract;
    * error isolation in :meth:`_deliver` (a failing listener never kills the
      loop);
    * best-effort de-duplication of ``event_id`` on reconnect.

    Args:
        namespace: Optional channel prefix.  When set, every channel is
            published/subscribed as ``"<namespace>:<name>"`` and stripped back
            to ``<name>`` before dispatch, so multiple apps can share one
            Redis instance without cross-talk.
        on_error: Optional :data:`ErrorFn` called when a listener raises.
        loop: Optional event loop to drive background tasks.  Defaults to the
            running loop (or a new one) via :meth:`_get_loop`.
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
        """Register the local dispatch callback (set by the emitter).

        The transport calls *dispatch* with ``(channel, envelope)`` for every
        message it receives — local or remote.  Must be called before
        :meth:`start` for networked backends.
        """
        self._dispatch = dispatch

    def set_error_handler(self, fn: ErrorFn) -> None:
        """Override or set the listener-error callback.

        Called from :meth:`_deliver` when a listener raises, so the host can
        log, metric, or re-raise without the delivery loop dying.
        """
        self._on_error = fn

    def _channel(self, name: str) -> str:
        """Build the fully-qualified channel name for *name*.

        Returns ``"<namespace>:<name>"`` when a namespace is configured, else
        *name* unchanged.
        """
        return f"{self.namespace}:{name}" if self.namespace else name

    async def start(self) -> None:
        """Begin receiving (no-op for memory/record).  Idempotent.

        Networked transports use this to spawn their subscriber/worker loop.
        Safe to call multiple times; the second call is a no-op if already
        running.
        """
        self._running = True

    async def stop(self) -> None:
        """Stop receiving and release resources.

        Cancels background tasks and closes connections.  After ``stop`` the
        transport should not be used until :meth:`start` is called again.
        """
        self._running = False

    @property
    def running(self) -> bool:
        """``True`` once :meth:`start` has been called and ``stop`` not yet."""
        return self._running

    @abc.abstractmethod
    async def publish(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Publish an envelope to *channel*.  Must be implemented by subclasses.

        Args:
            channel: The (already namespaced) channel name.
            envelope: The dict produced by :func:`serialize_payload`.
        """

    async def _deliver(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Run the local listeners for a received envelope.

        Error-isolated: a failing listener is reported via ``on_error`` and
        never propagates to the subscriber loop.  Also performs best-effort
        de-duplication on ``event_id`` so a redelivered envelope (e.g. Redis
        reconnect replay) is processed at most once per transport instance.
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
        """Return the configured loop, or the running/new loop.

        Used by networked transports to schedule their background listener
        task when no explicit ``loop`` was passed to the constructor.
        """
        if self._loop is not None:
            return self._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            self._loop = loop
            return loop
