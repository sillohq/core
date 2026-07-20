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
        """Run local listeners for a received/triggered event.

        This is the dispatch callback bound to the transport.  It looks up the
        in-process :class:`~sillo.events.core.Event` for *channel*, decodes the
        envelope's ``args``/``kwargs``, and runs them via
        :meth:`~sillo.events.core.Event.trigger_async` (so coroutine listeners
        are awaited and their errors observed).
        """
        event = self._events.get(channel)
        if event is None:
            return
        args = tuple(envelope.get("args", ()))
        kwargs = envelope.get("kwargs", {})
        await event.trigger_async(*args, **kwargs)

    async def _default_error_handler(self, exc, channel, envelope) -> None:
        logger = __import__("logging").getLogger("sillo.events")
        logger.error("Listener error on %r: %s", channel, exc)

    async def start(self) -> None:
        """Start the underlying transport (subscriber/worker loops)."""
        await self._transport.start()

    async def stop(self) -> None:
        """Stop the transport and release resources."""
        await self._transport.stop()

    @property
    def transport(self) -> BaseTransport:
        return self._transport

    def _subscribe(self, event_name: str) -> None:
        """Subscribe the transport to a channel when a listener is added.

        Only transports that implement ``subscribe`` (redis pub/sub) react;
        memory/persistent/record ignore it.
        """
        subscribe = getattr(self._transport, "subscribe", None)
        if subscribe is not None:
            try:
                subscribe(event_name)
            except RuntimeError:
                # Loop not running yet — start() will subscribe on first emit.
                pass

    def __contains__(self, event_name: str) -> bool:
        """Check if event exists"""
        return event_name in self._events

    def __getitem__(self, event_name: str) -> Event:
        """Get an event by name"""
        return self.event(event_name)

    def event(self, event_name: str) -> Event:
        """
        Get or create an event by name.

        Args:
            event_name: Name of the event (can include namespaces)

        Returns:
            Event instance
        """
        with self._lock:
            if event_name not in self._events:
                self._events[event_name] = Event(event_name)
            return self._events[event_name]

    def namespace(self, namespace: str) -> "EventNamespace":
        """
        Get a namespace for organizing events.

        Args:
            namespace: Namespace prefix

        Returns:
            EventNamespace instance
        """
        return EventNamespace(self, namespace)

    def remove_event(self, event_name: str):
        """
        Remove an event and all its listeners.

        Args:
            event_name: Name of the event to remove
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
