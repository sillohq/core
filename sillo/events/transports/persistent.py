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
from typing import Any

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

    This transport serialises every emitted event into a Redis list (the
    *backlog*) rather than publishing it to a pub/sub channel.  A dedicated
    background worker blocks on ``BRPOP`` and dispatches each message to the
    registered local listeners, acknowledging it only after successful delivery.
    Because the message remains in Redis until it is explicitly acknowledged,
    events survive process restarts and are delivered with at-least-once
    semantics.  Failed deliveries are requeued with a bounded retry count so
    that permanently broken events are eventually dropped rather than retried
    forever.

    The ``redis`` package is imported lazily, mirroring the strategy used by
    :class:`~sillo.events.transports.redis.RedisTransport`, so that the base
    ``events`` package can be imported without ``redis`` installed.

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
        """Initialise the persistent transport with Redis connection parameters.

        Stores the connection URL, arbitrary keyword arguments forwarded to the
        ``redis.asyncio`` client factory, and the maximum retry budget for
        failed deliveries.  Internal bookkeeping attributes (``_client``,
        ``_worker``) are initialised to ``None`` and populated lazily when
        :meth:`start` is first called.

        Args:
            url: Redis connection URL passed to ``redis.asyncio.from_url``.
            namespace: Channel prefix used to scope the backlog key so that
                multiple applications sharing a single Redis instance do not
                collide on each other's events.
            max_retries: Maximum number of redelivery attempts for a single
                event before it is permanently dropped from the backlog.
            on_error: Optional callback invoked when a listener raises during
                dispatch; forwarded to the base transport.
            loop: Optional asyncio event loop for the background worker task.
            **kwargs: Additional keyword arguments forwarded verbatim to
                ``redis.asyncio.from_url`` (e.g. ``decode_responses``).

        Returns:
            None.

        Raises:
            None.
        """
        super().__init__(namespace=namespace, on_error=on_error, loop=loop)
        self._url = url
        self._kwargs = kwargs
        self._max_retries = max_retries
        self._client: Any = None
        self._worker: asyncio.Task | None = None

    def _backlog_key(self) -> str:
        """Compute the Redis list key holding the unacknowledged backlog.

        Constructs a namespaced key of the form ``"<namespace>:sillo:events:backlog"``
        when a namespace is configured, or falls back to the bare key
        ``"sillo:events:backlog"`` when no namespace is set.  This ensures
        that multiple applications sharing a single Redis instance maintain
        isolated backlogs and do not accidentally consume each other's events.

        Args:
            None.

        Returns:
            str: The fully-qualified Redis list key for the backlog.

        Raises:
            None.
        """
        return (
            f"{self.namespace}:sillo:events:backlog"
            if self.namespace
            else "sillo:events:backlog"
        )

    def _connect(self):
        """Lazily create and return the ``redis.asyncio`` client instance.

        On the first invocation the ``redis.asyncio`` module is imported and a
        new async client is constructed via ``from_url`` using the stored URL
        and keyword arguments.  Subsequent calls return the cached client
        without re-importing or reconnecting, making this method safe to call
        repeatedly from both the public API and the background worker loop.

        Args:
            None.

        Returns:
            The ``redis.asyncio.Redis`` client instance used for all backlog
            operations (``RPUSH``, ``BRPOP``, ``PING``).

        Raises:
            TransportError: If the ``redis`` package is not installed in the
                current environment.
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
        """Check whether the Redis server backing this transport is reachable.

        Issues a ``PING`` command through the lazily-initialised async client
        and converts the result to a boolean.  Any exception raised during the
        round-trip (connection refused, timeout, authentication failure) is
        caught and mapped to ``False`` so that callers can use this method as
        a safe liveness probe in health-check endpoints without needing to
        handle transport-specific errors.

        Args:
            None.

        Returns:
            bool: ``True`` if Redis responded successfully, ``False`` if the
            server is unreachable or any error occurred.

        Raises:
            None.
        """
        try:
            return bool(await self._connect().ping())
        except Exception:
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
            except (asyncio.CancelledError, Exception):
                pass
            self._worker = None
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None

    async def publish(self, channel: str, envelope: dict[str, Any]) -> None:
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
                except Exception:
                    logger.warning("Dropped malformed persistent envelope")
                    continue
                channel = envelope.pop("_channel", "")
                attempts = envelope.get("_attempts", 0)
                try:
                    await self._deliver(channel, envelope)
                except Exception:
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
            except Exception as exc:
                logger.warning("Persistent worker error, reconnecting: %s", exc)
                await asyncio.sleep(RECONNECT_DELAY)
