"""sillo.events.transports.persistent — Durable Redis-backed transport.

Events are pushed onto a Redis list (the *backlog*) instead of published.  A
worker loop blocks on ``BRPOP`` and dispatches each message to local listeners,
then acknowledges it (by removing it from the list).  Because the message lives
in Redis until acknowledged, events survive a process restart and are delivered
*at-least-once*.  Failed deliveries are requeued with a bounded retry count.

Lazy-imports ``redis`` like the :class:`~sillo.events.transports.redis.RedisTransport`.

When to use
-----------
Prefer this over the ``redis`` pub/sub backend when you cannot afford to lose
events emitted while a consumer is offline (billing, notifications, audit).
Accept the trade-off: higher latency (a worker must pop and dispatch) and one
extra Redis list per namespace.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from .base import (
    BaseTransport,
    TransportError,
    deserialize_envelope,
    serialize_envelope,
)

logger = logging.getLogger("sillo.events.persistent")

#: Default Redis connection URL used when no ``url`` is supplied.
DEFAULT_URL = "redis://localhost:6379/0"
#: Seconds to wait before retrying after a worker/connection failure.
RECONNECT_DELAY = 2.0
#: Maximum number of redelivery attempts before an event is dropped as
#: permanently failed.
MAX_RETRIES = 5


class PersistentTransport(BaseTransport):
    """Durable, at-least-once transport backed by a Redis backlog.

    Args:
        url: Redis connection URL.
        namespace: Channel prefix (also prefixes the backlog key).
        max_retries: Redelivery attempts for a failing event before it is
            dropped.  Set to ``0`` to disable retries.
        on_error: Optional listener-error callback.
        loop: Optional event loop for the worker task.
        **kwargs: Forwarded to ``redis.asyncio.from_url``.

    Requires:
        The ``redis`` package (``pip install redis`` / the ``events`` extra).

    Example:
        >>> from sillo.events.emitter import EventEmitter
        >>> emitter = EventEmitter("persistent", url="redis://localhost:6379/0")
        >>> await emitter.start()           # spawn the BRPOP worker
        >>> emitter.on("invoice.due")(lambda i: charge(i))
        >>> await emitter.emit_async("invoice.due", invoice)
    """

    name = "persistent"

    def __init__(
        self,
        *,
        url: str = DEFAULT_URL,
        namespace: str = "",
        max_retries: int = MAX_RETRIES,
        on_error=None,
        loop=None,
        **kwargs: Any,
    ) -> None:
        super().__init__(namespace=namespace, on_error=on_error, loop=loop)
        self._url = url
        self._kwargs = kwargs
        self._max_retries = max_retries
        self._client: Any = None
        self._worker: Optional[asyncio.Task] = None

    def _backlog_key(self) -> str:
        """Redis list key holding the unacknowledged backlog.

        Namespaced as ``"<namespace>:sillo:events:backlog"`` (or
        ``"sillo:events:backlog"`` with no namespace) so multiple apps share
        Redis safely.
        """
        return f"{self.namespace}:sillo:events:backlog" if self.namespace else "sillo:events:backlog"

    def _connect(self):
        """Lazily create the ``redis.asyncio`` client.

        Raises:
            TransportError: if the ``redis`` package is not installed.
        """
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:  # pragma: no cover - env dependent
            raise TransportError(
                "The 'redis' package is required for the persistent backend. "
                "Install it with: pip install redis"
            ) from exc
        if self._client is None:
            self._client = aioredis.from_url(self._url, **self._kwargs)
        return self._client

    async def ping(self) -> bool:
        """Return ``True`` if Redis is reachable, ``False`` otherwise."""
        try:
            return bool(await self._connect().ping())
        except Exception:  # noqa: BLE001
            return False

    async def start(self) -> None:
        """Connect and spawn the background ``BRPOP`` worker loop.

        Idempotent.  Must be called (typically from ``app.on_startup``) before
        any backlog is drained.
        """
        if self._running:
            return
        self._connect()
        self._running = True
        self._worker = asyncio.ensure_future(self._drain_loop())

    async def stop(self) -> None:
        """Cancel the worker loop and close the Redis connection.

        In-flight messages remain in the backlog and are drained on the next
        ``start`` — this is what makes delivery at-least-once across restarts.
        """
        self._running = False
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._worker = None
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:  # noqa: BLE001
                pass
            self._client = None

    async def publish(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Append *envelope* to the backlog for later draining.

        Stores ``_channel`` (the original, namespaced channel) and ``_attempts``
        (retry counter) alongside the envelope so the worker can route and
        requeue it.  Raises :class:`TransportError` if Redis is unreachable.
        """
        client = self._connect()
        envelope = dict(envelope, _channel=channel, _attempts=0)
        await client.rpush(self._backlog_key(), serialize_envelope(envelope))

    async def _drain_loop(self) -> None:
        while self._running:
            try:
                client = self._connect()
                result = await client.brpop(self._backlog_key(), timeout=1)
                if not result:
                    continue
                _, raw = result
                try:
                    envelope = deserialize_envelope(raw)
                except Exception:  # noqa: BLE001
                    logger.warning("Dropped malformed persistent envelope")
                    continue
                channel = envelope.pop("_channel", "")
                attempts = envelope.get("_attempts", 0)
                try:
                    await self._deliver(channel, envelope)
                except Exception:  # noqa: BLE001
                    attempts += 1
                    if attempts <= self._max_retries:
                        requeue = dict(envelope, _channel=channel, _attempts=attempts)
                        await client.rpush(
                            self._backlog_key(), serialize_envelope(requeue)
                        )
                        logger.warning(
                            "Event %s redelivered (attempt %d)",
                            envelope.get("event_id"),
                            attempts,
                        )
                    else:
                        logger.error(
                            "Event %s exhausted retries, dropped",
                            envelope.get("event_id"),
                        )
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001 - reconnect on failure
                logger.warning("Persistent worker error, reconnecting: %s", exc)
                await asyncio.sleep(RECONNECT_DELAY)
