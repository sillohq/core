"""sillo.events.transports.redis — Cross-instance transport via Redis pub/sub.

Each ``emit`` publishes a JSON envelope to a Redis channel named after the
event.  Every emitter subscribes to the channels it has listeners for and
re-dispatches received envelopes to its local :class:`~sillo.events.core.Event`
listeners.  This gives true fan-out across processes/instances — e.g. a
web app on instance A and a worker on instance B both react to
``"order.placed"``.

The ``redis`` package is imported lazily so the base ``events`` package (and
``backend="memory"``) works without it installed.  A background listener task
is spawned on :meth:`start`; it auto-reconnects and isolates per-message
errors so one bad listener cannot kill the subscription.

Delivery semantics
------------------
Redis pub/sub is *fire-and-forget*: a message is delivered only to subscribers
connected *at the moment of publish*.  There is no backlog, so an instance
that is down misses events.  If you need at-least-once delivery across
restarts, use the :class:`~sillo.events.transports.persistent.PersistentTransport`
instead.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

from .base import (
    BaseTransport,
    TransportError,
    deserialize_envelope,
    serialize_envelope,
)

logger = logging.getLogger("sillo.events.redis")

#: Default Redis connection URL used when no ``url`` is supplied.
DEFAULT_URL = "redis://localhost:6379/0"
#: Seconds to wait before retrying after a subscriber/connection failure.
RECONNECT_DELAY = 2.0


class RedisTransport(BaseTransport):
    """Cross-instance transport backed by Redis pub/sub.

    Args:
        url: Redis connection URL passed to ``redis.asyncio.from_url``.
        namespace: Channel prefix (see
            :meth:`~sillo.events.transports.base.BaseTransport._channel`).
        on_error: Optional listener-error callback.
        loop: Optional event loop for the listener task.
        **kwargs: Forwarded to ``redis.asyncio.from_url`` (e.g. ``decode_responses``).

    Requires:
        The ``redis`` package (``pip install redis`` / the ``events`` extra).

    Example:
        >>> from sillo.events.emitter import EventEmitter
        >>> emitter = EventEmitter("redis", url="redis://localhost:6379/0")
        >>> await emitter.start()           # spawn the subscriber loop
        >>> emitter.on("order.placed")(lambda o: ship(o))
        >>> await emitter.emit_async("order.placed", order)
        >>> # ... on shutdown ...
        >>> await emitter.stop()
    """

    name = "redis"

    def __init__(
        self,
        *,
        url: str = DEFAULT_URL,
        namespace: str = "",
        on_error=None,
        loop=None,
        **kwargs: Any,
    ) -> None:
        super().__init__(namespace=namespace, on_error=on_error, loop=loop)
        self._url = url
        self._kwargs = kwargs
        self._client: Any = None
        self._pubsub: Any = None
        self._listener_task: Optional[asyncio.Task] = None
        self._subscribed: Set[str] = set()

    def _connect(self):
        """Lazily create the ``redis.asyncio`` client.

        Raises:
            TransportError: if the ``redis`` package is not installed.
        """
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:  # pragma: no cover - env dependent
            raise TransportError(
                "The 'redis' package is required for the redis backend. "
                "Install it with: pip install redis"
            ) from exc
        if self._client is None:
            self._client = aioredis.from_url(self._url, **self._kwargs)
        return self._client

    async def ping(self) -> bool:
        """Return ``True`` if Redis is reachable, ``False`` otherwise.

        A safe liveness probe useful for health checks and startup asserts;
        never raises.
        """
        try:
            client = self._connect()
            return bool(await client.ping())
        except Exception:  # noqa: BLE001
            return False

    async def start(self) -> None:
        """Connect and spawn the background subscriber loop.

        Idempotent: if already running, returns immediately.  Must be called
        (typically from ``app.on_startup``) before any ``subscribe`` /
        cross-instance delivery can occur.
        """
        if self._running:
            return
        self._connect()
        self._running = True
        self._listener_task = asyncio.ensure_future(self._listen_loop())

    async def stop(self) -> None:
        """Cancel the subscriber loop and close the client/pubsub connection."""
        self._running = False
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._listener_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.close()
            except Exception:  # noqa: BLE001
                pass
            self._pubsub = None
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:  # noqa: BLE001
                pass
            self._client = None

    async def subscribe(self, channel: str) -> None:
        """Subscribe the listener loop to *channel*'s Redis channel.

        Called automatically by the emitter when a listener is registered
        (see :meth:`~sillo.events.emitter.EventEmitter.on`).  If the transport
        is not yet running it starts the loop first, so a listener added
        before ``start()`` still connects.  Idempotent per channel.
        """
        full = self._channel(channel)
        if full in self._subscribed:
            return
        client = self._connect()
        if self._pubsub is None:
            self._pubsub = client.pubsub()
        await self._pubsub.subscribe(full)
        self._subscribed.add(full)
        if not self._running:
            await self.start()

    async def publish(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Publish *envelope* to the Redis channel for *channel*.

        This is a live ``PUBLISH`` — only currently-connected subscribers
        receive it.  Raises :class:`TransportError` if Redis is unreachable.
        """
        client = self._connect()
        await client.publish(self._channel(channel), serialize_envelope(envelope))

    async def _listen_loop(self) -> None:
        while self._running:
            try:
                if self._pubsub is None:
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue
                async for message in self._pubsub.listen():
                    if not self._running:
                        break
                    if message is None or message.get("type") != "message":
                        continue
                    raw = message.get("data")
                    if not raw:
                        continue
                    try:
                        envelope = deserialize_envelope(raw)
                    except Exception:  # noqa: BLE001
                        logger.warning("Dropped malformed redis envelope")
                        continue
                    # Channel comes back with the namespace prefix.
                    chan = message.get("channel")
                    chan = chan.decode() if isinstance(chan, bytes) else chan
                    local = (
                        chan[len(self.namespace) + 1 :]
                        if (self.namespace and chan.startswith(self.namespace + ":"))
                        else chan
                    )
                    await self._deliver(local, envelope)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001 - reconnect on failure
                logger.warning("Redis listener error, reconnecting: %s", exc)
                await asyncio.sleep(RECONNECT_DELAY)
                try:
                    if self._pubsub is not None:
                        await self._pubsub.close()
                except Exception:  # noqa: BLE001
                    pass
                self._pubsub = None
                try:
                    self._connect()
                    self._pubsub = self._client.pubsub()
                    if self._subscribed:
                        await self._pubsub.subscribe(*self._subscribed)
                except Exception:  # noqa: BLE001
                    pass
