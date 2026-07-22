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

    Attributes:
        message: A human-readable description of the transport failure,
            typically including the backend name and the underlying cause.
        args: Positional arguments forwarded to the base :class:`Exception`.

    Example:
        >>> try:
        ...     transport = get_transport("redis", url="redis://bad-host:6379")
        ...     await transport.start()
        ... except TransportError as exc:
        ...     logger.error("Transport failure: %s", exc)
    """


def serialize_payload(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Encode emit arguments into a transport-agnostic envelope dictionary.

    Constructs the canonical wire-format envelope that every backend uses to
    represent a single emitted event.  The envelope contains a freshly
    generated UUID4 event identifier, the JSON-safe positional and keyword
    arguments, and a high-resolution epoch timestamp.  Non-serializable values
    (file handles, sockets, arbitrary objects) are replaced with a fallback
    marker dict so that a misbehaving emit call never crashes the transport.

    This function is called internally by the emitter before handing the
    envelope to the transport's :meth:`~BaseTransport.publish` method.  It is
    exposed at module level so that custom transports and test harnesses can
    build compatible envelopes without reimplementing the encoding logic.

    Args:
        args: Positional arguments passed to ``emit`` or ``emit_async``.  Each
            element is tested for JSON serializability and replaced with a
            ``{"__unsupported__": repr(obj)}`` fallback if encoding fails.
        kwargs: Keyword arguments passed to ``emit`` or ``emit_async``.  Values
            undergo the same serializability check as positional arguments.

    Returns:
        A dictionary with four keys: ``"event_id"`` (a UUID4 string), ``"args"``
        (a list of JSON-safe positional values), ``"kwargs"`` (a dict of
        JSON-safe keyword values), and ``"ts"`` (a :func:`time.time` float).
        The returned dict is a fresh object; mutating it does not affect the
        caller's original arguments.

    Example:
        >>> envelope = serialize_payload(("bob",), {"age": 3})
        >>> envelope["args"]
        ['bob']
        >>> "event_id" in envelope and "ts" in envelope
        True
    """

    def _safe(obj: Any) -> Any:
        """Attempt JSON serialization of *obj*, returning a fallback on failure.

        Tests whether *obj* can be encoded by :func:`json.dumps` without raising.
        If encoding succeeds the original object is returned unchanged.  If a
        :class:`TypeError` or :class:`ValueError` is raised (indicating the
        object is not JSON-native), a marker dictionary containing the
        ``repr()`` of the object is returned instead.

        This ensures that non-serializable values such as file handles, open
        sockets, or custom class instances never propagate into the wire format
        and crash the transport layer.

        Args:
            obj: Any Python object to be tested for JSON serializability.

        Returns:
            The original *obj* if it is JSON-serializable, otherwise a dict of
            the form ``{"__unsupported__": repr(obj)}`` serving as a lossy
            fallback that preserves debugging information.
        """
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
    """Serialize an envelope dictionary to a JSON wire-format string.

    Converts the in-memory envelope dict (as produced by :func:`serialize_payload`)
    into its JSON string representation for transmission over a network or
    storage backend.  Uses ``default=str`` as the JSON encoder fallback so
    that any value which slipped past the payload serializer (such as a
    :class:`datetime.datetime` or :class:`uuid.UUID`) is coerced to its string
    representation rather than raising a :class:`TypeError`.

    The counterpart is :func:`deserialize_envelope`, which parses the string
    back into a dictionary on the receiving side.

    Args:
        envelope: A dictionary conforming to the transport wire format, as
            produced by :func:`serialize_payload`.  Must contain at minimum
            ``"event_id"``, ``"args"``, ``"kwargs"``, and ``"ts"`` keys.

    Returns:
        A UTF-8 JSON string suitable for writing to a Redis channel, database
        column, or HTTP request body.  The string is deterministic for the
        same input (dict key ordering may vary across Python versions).

    Example:
        >>> raw = serialize_envelope({"event_id": "abc", "args": [], "kwargs": {}, "ts": 0})
        >>> import json
        >>> json.loads(raw)["event_id"]
        'abc'
    """
    return json.dumps(envelope, default=str)


def deserialize_envelope(raw: str) -> Dict[str, Any]:
    """Parse a JSON wire-format string back into an envelope dictionary.

    Reverses the encoding performed by :func:`serialize_envelope`, converting
    the JSON string received from a transport channel back into the in-memory
    dictionary that the dispatch pipeline expects.  The parsed dict is passed
    directly to :meth:`BaseTransport._deliver` for listener execution.

    This function is a thin wrapper around :func:`json.loads` and inherits its
    strictness: malformed input raises :class:`json.JSONDecodeError`.  Callers
    (the Redis subscriber loop, the persistent backlog worker) catch this
    exception and drop the malformed message with a warning log rather than
    crashing the entire receive loop.

    Args:
        raw: A JSON-encoded string previously produced by
            :func:`serialize_envelope`.  Expected to decode into a dict with
            ``"event_id"``, ``"args"``, ``"kwargs"``, and ``"ts"`` keys.

    Returns:
        The decoded envelope dictionary, ready for dispatch.  All values are
        native Python types as determined by the JSON decoder (strings, lists,
        dicts, numbers, booleans, and ``None``).

    Raises:
        json.JSONDecodeError: If *raw* is not valid JSON.  Callers should
            catch this and log a warning rather than propagating the error,
            to maintain receive-loop stability.

    Example:
        >>> envelope = deserialize_envelope('{"event_id": "abc", "args": []}')
        >>> envelope["event_id"]
        'abc'
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
        """Initialize the base transport with namespace, error handler, and loop.

        Sets up the shared internal state that all transport backends rely on:
        the dispatch callback slot, the running flag, the error handler, and
        the de-duplication seen-set.  Subclasses should call ``super().__init__()``
        before performing their own backend-specific initialization.

        Args:
            namespace: Optional channel prefix applied to all published and
                subscribed channel names.  When empty (the default), channels
                are used as-is without any prefix.
            on_error: Optional async callback invoked when a listener raises
                during dispatch.  Receives the exception, channel name, and
                envelope dict.  If ``None``, listener errors are logged but
                no external notification is sent.
            loop: Optional event loop for scheduling background tasks.  If
                ``None``, the transport will attempt to use the running loop
                at :meth:`start` time, or create a new one as a fallback.
        """
        self.namespace = namespace
        self._on_error = on_error
        self._loop = loop
        self._dispatch: Optional[DispatchFn] = None
        self._running = False
        # Per-instance seen event_ids for lightweight dedup on reconnect.
        self._seen: "set[str]" = set()
        self._seen_max = 10_000

    def bind(self, dispatch: DispatchFn) -> None:
        """Register the local dispatch callback set by the emitter.

        Stores a reference to the async dispatch function that the transport
        will call for every received message — whether local (memory) or
        remote (Redis, persistent).  The dispatch function is responsible for
        looking up the matching :class:`~sillo.events.core.Event` object and
        executing its registered listeners in priority order.

        This method must be called before :meth:`start` for networked backends,
        because the background receive loop will invoke dispatch as soon as
        messages arrive.  For memory transports the ordering is less critical
        since delivery is synchronous.

        Args:
            dispatch: An async callable with the signature
                ``async def dispatch(channel: str, envelope: dict) -> None``.
                The transport guarantees that *channel* is already
                de-namespaced and *envelope* is the decoded dict from
                :func:`deserialize_envelope`.

        Raises:
            TypeError: If *dispatch* is not callable.  No runtime type check
                is performed; the error surfaces when the transport first
                attempts to invoke the callback.

        Example:
            >>> async def my_dispatch(channel, envelope):
            ...     print(f"Received on {channel}")
            >>> transport.bind(my_dispatch)
        """
        self._dispatch = dispatch

    def set_error_handler(self, fn: ErrorFn) -> None:
        """Override or set the listener-error callback after construction.

        Replaces the ``on_error`` handler that was optionally passed to the
        constructor.  This is useful when the error handler needs to be
        configured after the transport is already instantiated — for example,
        when the handler depends on application-level logging or metrics
        infrastructure that is not available at transport creation time.

        The new handler takes effect immediately for all subsequent listener
    failures.  It does not retroactively apply to errors that were already
        routed to the previous handler.

        Args:
            fn: An async callable with the signature
                ``async def on_error(exc, channel, envelope) -> None``.
                Receives the exception raised by the listener, the channel
                name on which it occurred, and the decoded envelope dict.
                The handler should not raise; if it does, the transport logs
                the secondary failure and continues.

        Example:
            >>> async def log_errors(exc, channel, envelope):
            ...     logger.error("Listener failed on %s: %s", channel, exc)
            >>> transport.set_error_handler(log_errors)
        """
        self._on_error = fn

    def _channel(self, name: str) -> str:
        """Build the fully-qualified channel name by prepending the namespace.

        Constructs the wire-level channel identifier used for publishing and
        subscribing.  When a namespace is configured, the result is
        ``"<namespace>:<name>"``; otherwise the name is returned unchanged.
        This ensures that multiple applications sharing the same Redis instance
        or database do not collide on channel names.

        The inverse operation (stripping the namespace prefix on receive) is
        handled internally by the networked transport subclasses before
        invoking the dispatch callback.

        Args:
            name: The bare channel name (e.g. ``"user.created"``) without any
                namespace prefix.

        Returns:
            The fully-qualified channel string.  If ``self.namespace`` is
            non-empty, returns ``"<namespace>:<name>"``; otherwise returns
            *name* unchanged.

        Example:
            >>> transport = BaseTransport.__subclasses__()[0]  # any subclass
            >>> t = MemoryTransport(namespace="myapp")
            >>> t._channel("ping")
            'myapp:ping'
        """
        return f"{self.namespace}:{name}" if self.namespace else name

    async def start(self) -> None:
        """Begin the transport's receive loop and mark it as running.

        Transitions the transport into the running state.  For in-process
        backends (memory, record) this is effectively a no-op beyond setting
        the ``_running`` flag.  Networked backends (Redis, persistent) override
        this method to spawn their subscriber or worker background task.

        The method is idempotent: calling it on an already-running transport
        is safe and has no side effects.  It must be called before the
        transport can receive remote messages, though :meth:`publish` may work
        without an explicit ``start`` for some backends.

        Raises:
            TransportError: If the backend cannot establish its connection
                (e.g. Redis is unreachable).  Subclasses define the specific
                failure conditions.

        Example:
            >>> await transport.start()
            >>> transport.running
            True
        """
        self._running = True

    async def stop(self) -> None:
        """Stop the transport's receive loop and release held resources.

        Transitions the transport out of the running state.  For networked
        backends this cancels the background subscriber/worker task and closes
        any open connections (Redis, database).  For in-process backends it
        simply clears the ``_running`` flag.

        After ``stop`` returns, the transport should not be used for publishing
        or receiving until :meth:`start` is called again.  Calling ``stop`` on
        an already-stopped transport is a safe no-op.

        Raises:
            TransportError: If the backend encounters an error while tearing
                down its connection.  Subclasses define the specific failure
                conditions.

        Example:
            >>> await transport.stop()
            >>> transport.running
            False
        """
        self._running = False

    @property
    def running(self) -> bool:
        """Indicate whether the transport is currently active and receiving.

        Returns ``True`` once :meth:`start` has been called successfully and
        ``stop`` has not yet been called.  This property is useful for health
        checks, conditional startup logic, and test assertions.

        The flag is managed internally by :meth:`start` and :meth:`stop`;
        external code should not modify ``_running`` directly.

        Returns:
            ``True`` if the transport is in the running state and actively
            processing messages, ``False`` otherwise.  The value reflects
            the most recent ``start`` / ``stop`` call.

        Example:
            >>> transport.running
            False
            >>> await transport.start()
            >>> transport.running
            True
        """
        return self._running

    @abc.abstractmethod
    async def publish(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Publish an envelope to the given channel.  Must be implemented by subclasses.

        Sends the serialized envelope dictionary to the specified channel using
        the backend's delivery mechanism.  In-process backends (memory) call
        :meth:`_deliver` directly; networked backends (Redis, persistent) write
        to the external service.

        The *channel* argument is already namespaced (i.e. it has been passed
        through :meth:`_channel`), so the subclass implementation should use
        it as-is without further prefixing.

        Args:
            channel: The fully-qualified channel name, including any namespace
                prefix.  For example ``"myapp:user.created"``.
            envelope: The envelope dictionary produced by
                :func:`serialize_payload`, containing ``"event_id"``,
                ``"args"``, ``"kwargs"``, and ``"ts"`` keys.

        Raises:
            TransportError: If the backend cannot deliver the message (e.g.
                Redis connection lost, database write failed).
            NotImplementedError: If a concrete subclass fails to override
                this abstract method.

        Example:
            >>> envelope = serialize_payload(("hello",), {})
            >>> await transport.publish("my_channel", envelope)
        """

    async def _deliver(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Execute the local dispatch callback for a received envelope.

        This is the central delivery method that bridges the transport layer
        to the emitter's listener registry.  It performs three responsibilities:
        (1) best-effort de-duplication on ``event_id`` to prevent redelivered
        envelopes from being processed twice, (2) invocation of the bound
        dispatch callback, and (3) error isolation so that a failing listener
        is reported via the ``on_error`` handler without killing the receive
        loop.

        If no dispatch callback has been bound (i.e. :meth:`bind` was not
        called), the method returns silently.  This allows transports to be
        constructed and started before the emitter is fully wired.

        Args:
            channel: The de-namespaced channel name on which the envelope was
                received.  Passed verbatim to the dispatch callback.
            envelope: The decoded envelope dictionary containing ``"event_id"``,
                ``"args"``, ``"kwargs"``, and ``"ts"``.

        Raises:
            This method does not raise.  All exceptions from the dispatch
            callback and the error handler are caught and logged.  If the
            error handler itself raises, a secondary log entry is emitted.

        Example:
            >>> await transport._deliver("ping", {"event_id": "abc", "args": []})
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
        """Return the event loop to use for background tasks.

        Resolves the event loop in the following priority order: (1) the
        explicit ``loop`` passed to the constructor, (2) the currently running
        event loop (if one exists), or (3) a newly created event loop stored
        on the instance for future calls.

        This method is used by networked transport subclasses when they need
        to schedule their background subscriber or worker task but were not
        given an explicit loop at construction time.

        Returns:
            An :class:`asyncio.AbstractEventLoop` instance suitable for
            scheduling background tasks.  The returned loop is guaranteed to
            be usable — either already running or freshly created and not yet
            closed.

        Example:
            >>> loop = transport._get_loop()
            >>> isinstance(loop, asyncio.AbstractEventLoop)
            True
        """
        if self._loop is not None:
            return self._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            self._loop = loop
            return loop
