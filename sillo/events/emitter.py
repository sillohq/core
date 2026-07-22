import asyncio
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from .core import Event
from .enums import EventPriority
from .transports import get_transport
from .transports.base import BaseTransport, serialize_payload


class EventEmitter:
    """
    Advanced event emitter that manages multiple events and provides
    a namespace for event organization.

    The emitter owns the in-process listener registry (``Event`` objects).
    Delivery is delegated to a pluggable transport selected by ``backend``:

    * ``"memory"`` (default) — in-process, synchronous dispatch.
    * ``"redis"`` — cross-instance fan-out via Redis pub/sub.
    * ``"persistent"`` — durable Redis backlog, at-least-once delivery.
    * ``"record"`` — persist every event as a Tortoise ``EventMessage`` row.

    Networked backends require ``await emitter.start()`` (typically wired to
    ``app.on_startup``) so the subscriber/worker loops run.
    """

    def __init__(
        self,
        backend: str = "memory",
        *,
        namespace: str = "",
        transport: Optional[BaseTransport] = None,
        on_error=None,
        loop=None,
        **transport_opts: Any,
    ):
        """Create an event emitter.

        Args:
            backend: One of ``"memory"`` (default), ``"redis"``,
                ``"persistent"``, ``"record"``.  Selects the delivery
                transport.  See :mod:`sillo.events.transports`.
            namespace: Optional channel prefix.  Every event name is published
                as ``"<namespace>:<name>"`` and listeners registered under the
                bare name still match.
            transport: Optional pre-built :class:`~sillo.events.transports.base.BaseTransport`.
                When given, ``backend`` is ignored and the supplied transport is
                used directly (useful for tests or custom backends).
            on_error: Optional callback ``(exc, channel, envelope) -> awaitable``
                invoked when a listener raises.
            loop: Optional event loop for networked transports' background tasks.
            **transport_opts: Forwarded to the transport (e.g. ``url=`` for
                redis/persistent, ``model=`` for record).

        Note:
            Networked backends (``redis``/``persistent``) require
            ``await emitter.start()`` — typically wired to ``app.on_startup`` —
            before cross-instance delivery works.
        """
        self._events: Dict[str, Event] = {}
        self._lock = threading.RLock()
        self._namespace_separator = ":"
        self._backend = backend
        if transport is not None:
            self._transport = transport
        else:
            self._transport = get_transport(
                backend,
                namespace=namespace,
                on_error=on_error,
                loop=loop,
                **transport_opts,
            )
        self._transport.bind(self._dispatch)
        self._transport.set_error_handler(on_error or self._default_error_handler)

    async def _dispatch(self, channel: str, envelope: Dict[str, Any]) -> None:
        """Dispatch a received or locally-triggered event to its in-process listeners.

        This method serves as the transport-bound callback that is bound during
        emitter initialisation.  It decodes the serialised envelope produced by
        :func:`~sillo.events.transports.base.serialize_payload`, reconstructs
        the original positional and keyword arguments, and forwards them to
        every registered listener via :meth:`Event.trigger_async` so that both
        synchronous and coroutine listeners are handled uniformly.

        Args:
            channel: The fully-qualified event name (including any namespace
                prefix) that identifies which local listeners should fire.
            envelope: A dictionary produced by the transport layer containing
                at least ``"args"`` (a tuple of positional arguments) and
                ``"kwargs"`` (a dict of keyword arguments).

        Returns:
            None.

        Raises:
            Does not raise; exceptions raised by individual listeners are
            captured inside :meth:`Event.trigger_async` and forwarded to the
            configured error handler.
        """
        event = self._events.get(channel)
        if event is None:
            return
        args = tuple(envelope.get("args", ()))
        kwargs = envelope.get("kwargs", {})
        await event.trigger_async(*args, **kwargs)

    async def _default_error_handler(self, exc, channel, envelope) -> None:
        """Handle uncaught exceptions raised by event listeners.

        This is the fallback error handler bound to the transport when no
        custom ``on_error`` callback is supplied to the emitter constructor.
        It logs the exception at ``ERROR`` level using the ``sillo.events``
        logger so that failures are visible in standard logging output
        without crashing the dispatch loop.

        Args:
            exc: The exception instance raised by a listener callback.
            channel: The fully-qualified event name on which the listener
                was registered when the error occurred.
            envelope: The serialised event envelope (dict) that was being
                dispatched to listeners at the time of the failure.

        Returns:
            None.

        Raises:
            Does not raise; this method is itself an error boundary and
            swallows all exceptions to keep the dispatch loop running.
        """
        logger = __import__("logging").getLogger("sillo.events")
        logger.error("Listener error on %r: %s", channel, exc)

    async def start(self) -> None:
        """Start the underlying transport and its background subscriber/worker loops.

        For networked backends (``redis``, ``persistent``, ``record``) this
        method must be awaited before any cross-instance event delivery can
        occur.  It is typically wired to the application's ``on_startup``
        lifecycle hook.  The ``memory`` backend is a no-op since dispatch is
        entirely synchronous and in-process.

        Args:
            None.

        Returns:
            None.

        Raises:
            ConnectionError: If a networked transport cannot establish a
                connection to its backing store (e.g. Redis server unreachable).
            RuntimeError: If the transport has already been started or if the
                event loop is not running when background tasks are scheduled.
        """
        await self._transport.start()

    async def stop(self) -> None:
        """Stop the underlying transport and release all associated resources.

        Cancels any background subscriber or worker tasks started by
        :meth:`start`, closes network connections held by the transport, and
        ensures a clean shutdown.  After calling this method the emitter
        should not be used for further event delivery unless :meth:`start` is
        called again.  For the ``memory`` backend this is effectively a no-op.

        Args:
            None.

        Returns:
            None.

        Raises:
            RuntimeError: If the transport is not in a started state and
                therefore cannot be cleanly stopped.
        """
        await self._transport.stop()

    @property
    def transport(self) -> BaseTransport:
        """Return the transport instance used by this emitter for event delivery.

        The transport is responsible for publishing events to and receiving
        events from the configured backend (memory, redis, persistent, or
        record).  This property is read-only; the transport is set during
        ``__init__`` and cannot be replaced afterwards.  It is primarily
        useful for introspection, testing, and advanced transport-level
        configuration that is not exposed through the emitter API.

        Returns:
            The :class:`~sillo.events.transports.base.BaseTransport` subclass
            instance bound to this emitter.

        Raises:
            Does not raise.
        """
        return self._transport

    def _subscribe(self, event_name: str) -> None:
        """Subscribe the transport to a channel when a new listener is registered.

        This internal helper is called automatically by :meth:`on` and
        :meth:`once` after a listener has been added.  Only transports that
        implement a ``subscribe`` method (such as the Redis pub/sub transport)
        react to this call; the ``memory``, ``persistent``, and ``record``
        backends silently ignore it.  If the event loop is not yet running
        when this method is called, the ``RuntimeError`` is caught and the
        subscription is deferred until :meth:`start` is invoked.

        Args:
            event_name: The fully-qualified event name (including any
                namespace prefix) to subscribe the transport to.

        Returns:
            None.

        Raises:
            Does not raise; ``RuntimeError`` from a non-running event loop is
            caught and silently ignored so that early listener registration
            before ``start()`` does not fail.
        """
        subscribe = getattr(self._transport, "subscribe", None)
        if subscribe is not None:
            try:
                subscribe(event_name)
            except RuntimeError:
                # Loop not running yet — start() will subscribe on first emit.
                pass

    def __contains__(self, event_name: str) -> bool:
        """Check whether an event with the given name is registered in this emitter.

        Supports the ``in`` operator, e.g. ``"user.login" in emitter``.  The
        lookup is a simple dictionary membership check against the internal
        ``_events`` registry and does not create the event if it does not
        already exist (unlike :meth:`event` which lazily creates it).

        Args:
            event_name: The name of the event to look up, optionally
                including a namespace prefix (e.g. ``"ui:button.click"``).

        Returns:
            ``True`` if an :class:`Event` instance for *event_name* exists in
            the emitter's registry, ``False`` otherwise.

        Raises:
            Does not raise.
        """
        return event_name in self._events

    def __getitem__(self, event_name: str) -> Event:
        """Retrieve an event by name using bracket notation.

        Supports the ``emitter["event.name"]`` syntax as a convenient
        shorthand for :meth:`event`.  If the event does not already exist it
        is lazily created and registered in the emitter's internal registry,
        so accessing a name via ``[]`` has the same side-effect as calling
        :meth:`event` — an empty :class:`Event` is created if absent.

        Args:
            event_name: The name of the event to retrieve, optionally
                including a namespace prefix (e.g. ``"ui:button.click"``).

        Returns:
            The :class:`~sillo.events.core.Event` instance registered under
            *event_name*, created lazily if it did not previously exist.

        Raises:
            Does not raise; a missing event is created rather than raising
            ``KeyError``, matching :meth:`event` semantics.
        """
        return self.event(event_name)

    def event(self, event_name: str) -> Event:
        """Get or lazily create an :class:`Event` by name.

        If an event with *event_name* already exists in the emitter's internal
        registry it is returned directly.  Otherwise a new :class:`Event`
        instance is created, stored in the registry under *event_name*, and
        returned.  The lookup and optional creation are performed under the
        emitter's reentrant lock so this method is safe to call from multiple
        threads concurrently.

        Args:
            event_name: Name of the event to look up or create.  May include
                a namespace prefix separated by ``":"`` (e.g.
                ``"ui:button.click"``).

        Returns:
            The :class:`~sillo.events.core.Event` instance registered under
            *event_name*, either pre-existing or newly created.

        Raises:
            Does not raise; a missing event is created rather than raising.
        """
        with self._lock:
            if event_name not in self._events:
                self._events[event_name] = Event(event_name)
            return self._events[event_name]

    def namespace(self, namespace: str) -> "EventNamespace":
        """Create an :class:`EventNamespace` wrapper for organizing events hierarchically.

        Returns a lightweight namespace object that prefixes every event name
        with ``"<namespace>:"`` so you can group related events without
        repeating the prefix in every call.  Namespaces can be nested by
        calling :meth:`EventNamespace.namespace` on the returned object.

        Args:
            namespace: The namespace prefix to apply to all events accessed
                through the returned :class:`EventNamespace` instance.

        Returns:
            A new :class:`EventNamespace` bound to this emitter with the
            given *namespace* as its prefix.

        Raises:
            Does not raise.
        """
        return EventNamespace(self, namespace)

    def remove_event(self, event_name: str):
        """Remove an event and all its registered listeners from the emitter.

        Deletes the :class:`Event` instance for *event_name* from the
        emitter's internal registry.  After removal, any listeners that were
        attached to the event are discarded and will no longer be invoked on
        subsequent emissions.  The operation is performed under the emitter's
        reentrant lock for thread safety.  If *event_name* is not registered,
        this method is a silent no-op.

        Args:
            event_name: The name of the event to remove, optionally
                including a namespace prefix (e.g. ``"ui:button.click"``).

        Returns:
            None.

        Raises:
            Does not raise; removing a non-existent event is a no-op.
        """
        with self._lock:
            if event_name in self._events:
                del self._events[event_name]

    def remove_all_events(self):
        """Remove all events and their listeners"""
        with self._lock:
            self._events.clear()

    def event_names(self) -> List[str]:
        """Get list of all event names"""
        return list(self._events.keys())

    def has_event(self, event_name: str) -> bool:
        """Check if an event exists"""
        return event_name in self._events

    def emit(self, event_name: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """
        Publish an event by name.

        Synchronous for the ``memory`` backend (dispatches to local listeners
        immediately and returns stats, preserving the original contract).
        For networked backends (``redis``/``persistent``/``record``) use
        :meth:`emit_async` instead — calling ``emit`` there raises a clear
        error, since those require an event loop.

        Args:
            event_name: Name of the event to trigger
            *args: Positional arguments to pass to listeners
            **kwargs: Keyword arguments to pass to listeners

        Returns:
            Dictionary with delivery statistics (memory backend)
        """
        if self._backend != "memory":
            raise RuntimeError(
                f"emit() is synchronous only for backend='memory', got "
                f"{self._backend!r}. Use 'await emitter.emit_async(...)'."
            )
        return self.event(event_name).trigger(*args, **kwargs)

    async def emit_async(
        self, event_name: str, *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Async publish, valid for every backend.

        For ``memory`` it awaits the local dispatch (coroutine listeners are
        awaited).  For networked backends it publishes through the transport;
        remote instances receive via their subscriber/worker loops.

        Args:
            event_name: Name of the event to trigger.
            *args: Positional arguments forwarded to listeners.
            **kwargs: Keyword arguments forwarded to listeners.

        Returns:
            ``{"event_id": <uuid4>, "backend": <backend name>}``.  Note this is
            *not* the listener execution stats — for those, the ``memory``
            backend's synchronous :meth:`emit` returns them directly.
        """
        envelope = serialize_payload(args, kwargs)
        await self._transport.publish(event_name, envelope)
        return {"event_id": envelope["event_id"], "backend": self._backend}

    def emit_sync(self, event_name: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Alias for :meth:`emit` (memory backend, synchronous)."""
        return self.emit(event_name, *args, **kwargs)

    def on(
        self,
        event_name: str,
        func: Optional[Callable[..., Any]] = None,
        *,
        priority: EventPriority = EventPriority.NORMAL,
        weak_ref: bool = False,
    ) -> Callable[..., Any]:
        """
        Decorator or function to register a listener for an event.

        Args:
            event_name: Name of the event
            func: Listener function
            priority: Listener priority
            weak_ref: Use weak reference to the listener

        Returns:
            The decorated function or decorator
        """

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            self.event(event_name).listen(f, priority=priority, weak_ref=weak_ref)
            self._subscribe(event_name)
            return f

        if func is None:
            return decorator
        return decorator(func)

    def once(
        self,
        event_name: str,
        func: Optional[Callable[..., Any]] = None,
        *,
        priority: EventPriority = EventPriority.NORMAL,
        weak_ref: bool = False,
    ) -> Callable[..., Any]:
        """
        Decorator or function to register a one-time listener for an event.

        Args:
            event_name: Name of the event
            func: Listener function
            priority: Listener priority
            weak_ref: Use weak reference to the listener

        Returns:
            The decorated function or decorator
        """

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            self.event(event_name).once(f, priority=priority, weak_ref=weak_ref)
            self._subscribe(event_name)
            return f

        if func is None:
            return decorator
        return decorator(func)

    def remove_listener(self, event_name: str, listener: Callable[..., Any]):
        """
        Remove a listener from an event.

        Args:
            event_name: Name of the event
            listener: Listener function to remove
        """
        self.event(event_name).remove_listener(listener)

    def remove_all_listeners(self, event_name: Optional[str] = None):
        """
        Remove all listeners from an event or all events.

        Args:
            event_name: Name of the event (None for all events)
        """
        if event_name is None:
            for event in self._events.values():
                event.remove_all_listeners()
        else:
            self.event(event_name).remove_all_listeners()


class EventNamespace:
    """
    Namespace for organizing events hierarchically.

    A thin wrapper that prefixes every event name with ``"<namespace>:"`` so
    you can group related events (``ui:button.click``, ``ui:modal.open``)
    without repeating the prefix.  Created via
    :meth:`EventEmitter.namespace` / :meth:`EventNamespace.namespace` (nested).

    Example:
        >>> ui = emitter.namespace("ui")
        >>> @ui.on("button.click")
        ... async def on_click(btn): ...
        >>> ui.emit("button.click", "submit")   # -> emitter.emit("ui:button.click", ...)
    """

    def __init__(self, emitter: EventEmitter, namespace: str):
        self._emitter = emitter
        self._namespace = namespace

    def __getitem__(self, event_name: str) -> Event:
        """Get an event within this namespace"""
        return self.event(event_name)

    def event(self, event_name: str) -> Event:
        """
        Get or create an event within this namespace.

        Args:
            event_name: Name of the event (relative to namespace)

        Returns:
            Event instance
        """
        full_name = f"{self._namespace}{self._emitter._namespace_separator}{event_name}"
        return self._emitter.event(full_name)

    def namespace(self, sub_namespace: str) -> "EventNamespace":
        """
        Get a sub-namespace within this namespace.

        Args:
            sub_namespace: Sub-namespace name

        Returns:
            EventNamespace instance
        """
        return EventNamespace(
            self._emitter,
            f"{self._namespace}{self._emitter._namespace_separator}{sub_namespace}",
        )

    def emit(self, event_name: str, *args: Any, **kwargs: Any) -> Any:
        """Publish an event within this namespace (sync, memory backend)."""
        return self._emitter.emit(self._full(event_name), *args, **kwargs)

    def emit_async(self, event_name: str, *args: Any, **kwargs: Any) -> Any:
        """Async publish within this namespace (all backends)."""
        return self._emitter.emit_async(self._full(event_name), *args, **kwargs)

    def on(
        self,
        event_name: str,
        func: Optional[Callable[..., Any]] = None,
        *,
        priority: EventPriority = EventPriority.NORMAL,
        weak_ref: bool = False,
    ) -> Callable[..., Any]:
        """Register a listener for an event in this namespace."""

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            self._emitter.on(
                self._full(event_name), f, priority=priority, weak_ref=weak_ref
            )
            return f

        if func is None:
            return decorator
        return decorator(func)

    def once(
        self,
        event_name: str,
        func: Optional[Callable[..., Any]] = None,
        *,
        priority: EventPriority = EventPriority.NORMAL,
        weak_ref: bool = False,
    ) -> Callable[..., Any]:
        """Register a one-time listener for an event in this namespace."""

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            self._emitter.once(
                self._full(event_name), f, priority=priority, weak_ref=weak_ref
            )
            return f

        if func is None:
            return decorator
        return decorator(func)

    def _full(self, event_name: str) -> str:
        return f"{self._namespace}{self._emitter._namespace_separator}{event_name}"


class AsyncEventEmitter(EventEmitter):
    """
    .. deprecated:: 0.1.0

        EventEmitter now supports async listeners natively via
        :meth:`EventEmitter.emit_async` and coroutine ``on``/``once`` handlers,
        so this subclass (which ran synchronous ``emit`` in a thread pool) is
        redundant.  Use :class:`EventEmitter` instead.
    """

    def __init__(self, max_workers: Optional[int] = None):
        warnings.warn(
            "AsyncEventEmitter is deprecated and will be removed in a future version. "
            "Use EventEmitter instead, which supports async listeners natively.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    async def emit_async(
        self, event_name: str, *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Asynchronously trigger an event by name.

        Args:
            event_name: Name of the event to trigger
            *args: Positional arguments to pass to listeners
            **kwargs: Keyword arguments to pass to listeners

        Returns:
            Dictionary with execution statistics
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, lambda: self.emit(event_name, *args, **kwargs)
        )

    def schedule_emit(
        self, event_name: str, *args: Any, **kwargs: Any
    ) -> asyncio.Future:
        """
        Schedule an event to be triggered asynchronously.

        Args:
            event_name: Name of the event to trigger
            *args: Positional arguments to pass to listeners
            **kwargs: Keyword arguments to pass to listeners

        Returns:
            Future representing the eventual execution
        """
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(
            self._executor, lambda: self.emit(event_name, *args, **kwargs)
        )

    def shutdown(self):
        """Clean up resources"""
        self._executor.shutdown()
