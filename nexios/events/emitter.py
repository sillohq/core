import asyncio
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from .core import Event
from .enums import EventPriority


class EventEmitter:
    """
    Advanced event emitter that manages multiple events and provides
    a namespace for event organization.
    """

    def __init__(self):
        self._events: Dict[str, Event] = {}
        self._lock = threading.RLock()
        self._namespace_separator = ":"

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
        Trigger an event by name.

        Args:
            event_name: Name of the event to trigger
            *args: Positional arguments to pass to listeners
            **kwargs: Keyword arguments to pass to listeners

        Returns:
            Dictionary with execution statistics
        """
        return self.event(event_name).trigger(*args, **kwargs)

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
        full_name = (
            f"{self._namespace}{self._emitter._namespace_separator}{event_name}"
        )  # type:ignore
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
            f"{self._namespace}{self._emitter._namespace_separator}{sub_namespace}",  # type: ignore
        )

    def emit(self, event_name: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """
        Trigger an event within this namespace.

        Args:
            event_name: Name of the event (relative to namespace)
            *args: Positional arguments to pass to listeners
            **kwargs: Keyword arguments to pass to listeners

        Returns:
            Dictionary with execution statistics
        """
        return self.event(event_name).trigger(*args, **kwargs)

    def on(
        self,
        event_name: str,
        func: Optional[Callable[..., Any]] = None,
        *,
        priority: EventPriority = EventPriority.NORMAL,
        weak_ref: bool = False,
    ) -> Callable[..., Any]:
        """
        Decorator or function to register a listener for an event in this namespace.

        Args:
            event_name: Name of the event (relative to namespace)
            func: Listener function
            priority: Listener priority
            weak_ref: Use weak reference to the listener

        Returns:
            The decorated function or decorator
        """

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            self.event(event_name).listen(f, priority=priority, weak_ref=weak_ref)
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
        Decorator or function to register a one-time listener for an event in this namespace.

        Args:
            event_name: Name of the event (relative to namespace)
            func: Listener function
            priority: Listener priority
            weak_ref: Use weak reference to the listener

        Returns:
            The decorated function or decorator
        """

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            self.event(event_name).once(f, priority=priority, weak_ref=weak_ref)
            return f

        if func is None:
            return decorator
        return decorator(func)


class AsyncEventEmitter(EventEmitter):
    """
    Event emitter with enhanced support for asynchronous operations.
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
    ) -> asyncio.Future:  # type: ignore
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
