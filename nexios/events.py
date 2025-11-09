# type:ignore
import asyncio
import inspect
import json
import logging
import threading
import time
import uuid
import weakref
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
from weakref import ReferenceType, WeakMethod, ref

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound="Event")


class EventPriority(Enum):
    """Priority levels for event listeners"""

    HIGHEST = auto()
    HIGH = auto()
    NORMAL = auto()
    LOW = auto()
    LOWEST = auto()


class EventPhase(Enum):
    """Event propagation phases"""

    CAPTURING = auto()
    BUBBLING = auto()
    AT_TARGET = auto()


@dataclass
class EventContext:
    """Context information about the event"""

    timestamp: float
    event_id: str
    source: Any
    phase: EventPhase = EventPhase.AT_TARGET


class EventError(Exception):
    """Base exception for event-related errors"""

    pass


class ListenerAlreadyRegisteredError(EventError):
    """Raised when a listener is already registered"""

    pass


class MaxListenersExceededError(EventError):
    """Raised when maximum number of listeners is exceeded"""

    pass


class EventCancelledError(EventError):
    """Raised when an event is cancelled"""

    pass


ListenerType = Union[
    Callable[..., Any],
    ReferenceType[Callable[..., Any]],
    WeakMethod[Callable[..., Any]],
]


class EventProtocol(Protocol):
    """Protocol for event listeners"""

    name: ...
    listener_count: ...
    max_listeners: ...
    enabled: ...
    get_metrics: ...

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


class EventSerializationMixin(EventProtocol):
    """
    Mixin for event serialization capabilities.
    """

    def to_json(self) -> str:
        """Serialize event configuration to JSON"""
        return json.dumps(
            {
                "name": self.name,
                "listener_count": self.listener_count,
                "max_listeners": self.max_listeners,
                "enabled": self.enabled,
                "metrics": self.get_metrics(),
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> _T:  # type:ignore
        """Deserialize event configuration from JSON"""

        cls = cast(Type[_T], cls)
        data = json.loads(json_str)
        event = cls(data["name"])
        event.max_listeners = data["max_listeners"]
        event.enabled = data["enabled"]
        return event


class Event(EventSerializationMixin):
    """
    Advanced event implementation with support for:
    - Priority-based listener execution
    - Event propagation (capture/bubble phases)
    - Asynchronous listeners
    - Thread safety
    - Listener management
    - Event cancellation
    - Detailed event context
    - Performance metrics
    """

    DEFAULT_MAX_LISTENERS = 100

    def __init__(self, name: str, max_listeners: Optional[int] = None):
        """
        Initialize an event.

        Args:
            name: Name of the event
            max_listeners: Maximum number of listeners allowed (None for no limit)
        """
        self.name = name
        self._listeners: Dict[EventPriority, List[ListenerType]] = {
            EventPriority.HIGHEST: [],
            EventPriority.HIGH: [],
            EventPriority.NORMAL: [],
            EventPriority.LOW: [],
            EventPriority.LOWEST: [],
        }
        self._once_listeners: Dict[EventPriority, List[ListenerType]] = {
            EventPriority.HIGHEST: [],
            EventPriority.HIGH: [],
            EventPriority.NORMAL: [],
            EventPriority.LOW: [],
            EventPriority.LOWEST: [],
        }
        self._max_listeners = max_listeners or self.DEFAULT_MAX_LISTENERS
        self._lock = threading.RLock()
        self._parent: Optional["Event"] = None
        self._children: List["Event"] = []
        self._enabled = True
        self._history: List[Dict[str, Any]] = []
        self._metrics: Dict[str, Any] = {
            "trigger_count": 0,
            "total_listeners_executed": 0,
            "average_execution_time": 0.0,
        }

    def __repr__(self) -> str:
        return f"<Event name='{self.name}' listeners={self.listener_count}>"

    @property
    def listener_count(self) -> int:
        """Get total number of listeners"""
        with self._lock:
            return sum(len(v) for v in self._listeners.values()) + sum(
                len(v) for v in self._once_listeners.values()
            )

    @property
    def max_listeners(self) -> int:
        """Get maximum number of listeners allowed"""
        return self._max_listeners

    @max_listeners.setter
    def max_listeners(self, value: int):
        """Set maximum number of listeners allowed"""
        with self._lock:
            if value < self.listener_count:
                raise ValueError(
                    f"Cannot set max_listeners to {value} when there are {self.listener_count} listeners"
                )
            self._max_listeners = value

    @property
    def enabled(self) -> bool:
        """Check if event is enabled"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """Enable or disable the event"""
        self._enabled = value

    @property
    def parent(self) -> Optional["Event"]:
        """Get parent event"""
        return self._parent

    @parent.setter
    def parent(self, value: Optional["Event"]):
        """Set parent event"""
        with self._lock:
            if self._parent is not None:
                self._parent._children.remove(self)
            self._parent = value
            if value is not None:
                value._children.append(weakref.proxy(self))  # type:ignore

    @property
    def children(self) -> List["Event"]:
        """Get child events"""
        return self._children.copy()

    def add_child(self, child: "Event"):
        """Add a child event"""
        child.parent = self

    def remove_child(self, child: "Event"):
        """Remove a child event"""
        if child in self._children:
            child.parent = None

    def listen(
        self,
        func: Optional[Callable[..., Any]] = None,
        *,
        priority: EventPriority = EventPriority.NORMAL,
        weak_ref: bool = False,
    ) -> Callable[..., Any]:
        """
        Decorator or function to register a listener.

        Args:
            func: Listener function
            priority: Listener priority
            weak_ref: Use weak reference to the listener

        Returns:
            The decorated function or decorator
        """

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            self._add_listener(f, priority=priority, weak_ref=weak_ref)
            return f

        if func is None:
            return decorator
        return decorator(func)

    def once(
        self,
        func: Optional[Callable[..., Any]] = None,
        *,
        priority: EventPriority = EventPriority.NORMAL,
        weak_ref: bool = False,
    ) -> Callable[..., Any]:
        """
        Decorator or function to register a one-time listener.

        Args:
            func: Listener function
            priority: Listener priority
            weak_ref: Use weak reference to the listener

        Returns:
            The decorated function or decorator
        """

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            self._add_listener(f, priority=priority, once=True, weak_ref=weak_ref)
            return f

        if func is None:
            return decorator
        return decorator(func)

    def _add_listener(
        self,
        listener: Callable[..., Any],
        *,
        priority: EventPriority = EventPriority.NORMAL,
        once: bool = False,
        weak_ref: bool = False,
    ):
        """
        Internal method to add a listener.

        Args:
            listener: Listener function
            priority: Listener priority
            once: Whether to remove after first trigger
            weak_ref: Use weak reference to the listener

        Raises:
            ListenerAlreadyRegisteredError: If listener is already registered
            MaxListenersExceededError: If max listeners would be exceeded
        """
        with self._lock:
            if self.listener_count >= self._max_listeners:
                raise MaxListenersExceededError(
                    f"Max listeners ({self._max_listeners}) exceeded for event '{self.name}'"
                )

            # Check if listener is already registered
            container = self._once_listeners if once else self._listeners
            for existing in container[priority]:
                if self._listeners_equal(existing, listener):
                    raise ListenerAlreadyRegisteredError(
                        f"Listener already registered for event '{self.name}'"
                    )

            # Apply weak reference if requested
            wrapped_listener: ListenerType
            if weak_ref:
                if inspect.ismethod(listener):
                    wrapped_listener = WeakMethod(listener)
                else:
                    wrapped_listener = ref(listener)
            else:
                wrapped_listener = listener

            # Store the listener
            container[priority].append(wrapped_listener)

    def remove_listener(self, listener: Callable[..., Any]):
        """
        Remove a listener from all priorities.

        Args:
            listener: Listener function to remove
        """
        with self._lock:
            for priority in EventPriority:
                self._listeners[priority] = [
                    registered_listener
                    for registered_listener in self._listeners[priority]
                    if not self._listeners_equal(registered_listener, listener)
                ]

                self._once_listeners[priority] = [
                    registered_listener
                    for registered_listener in self._once_listeners[priority]
                    if not self._listeners_equal(registered_listener, listener)
                ]

    def _listeners_equal(
        self, listener1: Callable[..., Any], listener2: Callable[..., Any]
    ) -> bool:
        """Check if two listeners are effectively the same"""
        if listener1 == listener2:
            return True

        l1 = listener1() if isinstance(listener1, (ref, WeakMethod)) else listener1
        l2 = listener2() if isinstance(listener2, (ref, WeakMethod)) else listener2

        if l1 is None or l2 is None:
            return False

        # Check if one wraps the other
        if hasattr(l1, "__wrapped__"):
            l1 = l1.__wrapped__
        if hasattr(l2, "__wrapped__"):
            l2 = l2.__wrapped__

        return l1 == l2

    def remove_all_listeners(self):
        """Remove all listeners"""
        with self._lock:
            for priority in EventPriority:
                self._listeners[priority].clear()
                self._once_listeners[priority].clear()

    def has_listener(self, listener: Callable[..., Any]) -> bool:
        """Check if a listener is registered"""
        with self._lock:
            for priority in EventPriority:
                if any(
                    self._listeners_equal(_, listener)
                    for _ in self._listeners[priority]
                ):
                    return True
                if any(
                    self._listeners_equal(_, listener)
                    for _ in self._once_listeners[priority]
                ):
                    return True
            return False

    def trigger(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """
        Trigger the event and notify all listeners.

        Args:
            *args: Positional arguments to pass to listeners
            **kwargs: Keyword arguments to pass to listeners

        Returns:
            Dictionary with execution statistics

        Raises:
            EventCancelledError: If event is cancelled during propagation
        """
        if not self._enabled:
            return {"cancelled": True, "reason": "Event disabled"}

        with self._lock:
            event_id = str(uuid.uuid4())
            context = EventContext(
                timestamp=time.time(), event_id=event_id, source=self
            )

            # Prepare event data
            event_data: Dict[str, Any] = {
                "args": args,
                "kwargs": kwargs,
                "context": context,
                "cancelled": False,
                "default_prevented": False,
            }

            # Execute in phases: capture (parent to child), target, bubble (child to parent)
            try:
                # Capture phase (parent to child)
                if self.parent:
                    self._propagate(event_data, EventPhase.CAPTURING)

                # Target phase
                execution_stats = self._execute_listeners(
                    event_data, EventPhase.AT_TARGET
                )

                # Bubble phase (child to parent) if not cancelled
                if not event_data["cancelled"] and self.parent:
                    self._propagate(event_data, EventPhase.BUBBLING)

                # Update metrics
                self._update_metrics(execution_stats)

                # Record history
                self._record_history(event_data, execution_stats)

                if event_data["cancelled"]:
                    raise EventCancelledError("Event was cancelled during propagation")

                return {
                    "event_id": event_id,
                    "listeners_executed": execution_stats["total"],
                    "execution_time": execution_stats["total_time"],
                    "cancelled": event_data["cancelled"],
                }
            except Exception as e:
                logger.error(
                    f"Error triggering event '{self.name}': {str(e)}", exc_info=True
                )
                raise

    def _propagate(self, event_data: Dict[str, Any], phase: EventPhase):
        """Propagate event to parent or children"""
        if phase == EventPhase.CAPTURING and self.parent:
            event_data["context"].phase = phase
            self.parent.trigger(*event_data["args"], **event_data["kwargs"])
        elif phase == EventPhase.BUBBLING and self.children:
            for child in self.children:
                event_data["context"].phase = phase
                child.trigger(*event_data["args"], **event_data["kwargs"])

    def _execute_listeners(
        self, event_data: Dict[str, Any], phase: EventPhase
    ) -> Dict[str, Any]:
        """
        Execute all appropriate listeners.

        Args:
            event_data: Event data dictionary
            phase: Current event phase

        Returns:
            Execution statistics
        """
        start_time = time.time()
        listeners_executed = 0
        cancelled = False

        # Collect listeners to execute
        with self._lock:
            all_listeners: List[Tuple[ListenerType, EventPriority, bool]] = []
            for priority in EventPriority:
                all_listeners.extend(
                    (listener, priority, False)
                    for listener in self._listeners[priority]
                )
                all_listeners.extend(
                    (listener, priority, True)
                    for listener in self._once_listeners[priority]
                )

            # Clear once listeners
            for priority in EventPriority:
                self._once_listeners[priority].clear()

        # Execute listeners in priority order
        for listener, priority, _ in all_listeners:
            if event_data.get("cancelled", False):
                cancelled = True
                break

            try:
                # Resolve weak references
                actual_listener: Optional[Callable[..., Any]] = None
                if isinstance(listener, (ref, WeakMethod)):
                    actual_listener = listener()  # type:ignore
                    if actual_listener is None:
                        continue
                else:
                    actual_listener = listener

                if actual_listener is None:
                    continue

                # Update context
                event_data["context"].phase = phase

                # Execute the listener
                if asyncio.iscoroutinefunction(actual_listener):
                    asyncio.create_task(
                        actual_listener(*event_data["args"], **event_data["kwargs"])
                    )
                else:
                    actual_listener(*event_data["args"], **event_data["kwargs"])

                listeners_executed += 1
            except EventCancelledError:
                event_data["cancelled"] = True
                cancelled = True
                break
            except Exception as e:
                logger.error(
                    f"Error in event listener for '{self.name}': {str(e)}",
                    exc_info=True,
                )

        execution_time = time.time() - start_time

        return {
            "total": listeners_executed,
            "total_time": execution_time,
            "average_time": execution_time / max(1, listeners_executed),
            "cancelled": cancelled,
        }

    def _update_metrics(self, stats: Dict[str, Any]):
        """Update performance metrics"""
        with self._lock:
            self._metrics["trigger_count"] += 1
            self._metrics["total_listeners_executed"] += stats["total"]

            # Update average execution time using moving average
            old_avg = self._metrics["average_execution_time"]
            new_count = self._metrics["trigger_count"]
            self._metrics["average_execution_time"] = (
                old_avg * (new_count - 1) + stats["average_time"]
            ) / new_count

    def _record_history(self, event_data: Dict[str, Any], stats: Dict[str, Any]):
        """Record event trigger in history"""
        with self._lock:
            self._history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "event_id": event_data["context"].event_id,
                    "args": str(event_data["args"]),
                    "kwargs": str(event_data["kwargs"]),
                    "listeners_executed": stats["total"],
                    "execution_time": stats["total_time"],
                    "cancelled": event_data["cancelled"],
                }
            )

            # Keep history size manageable
            if len(self._history) > 100:
                self._history.pop(0)

    def get_metrics(self) -> Dict[str, Any]:
        """Get event performance metrics"""
        return self._metrics.copy()

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get event trigger history"""
        with self._lock:
            if limit is None:
                return self._history.copy()
            return self._history[-limit:] if limit else []

    def cancel(self):
        """Cancel the current event propagation"""
        raise EventCancelledError("Event propagation cancelled")

    def prevent_default(self):
        """Prevent default behavior (meaning depends on event)"""
        event_data = inspect.currentframe().f_back.f_locals.get("event_data")  # type: ignore
        if event_data:
            event_data["default_prevented"] = True


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
        full_name = f"{self._namespace}{self._emitter._namespace_separator}{event_name}"  # type:ignore
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


class EventBenchmark:
    """
    Utility for benchmarking event performance.
    """

    @staticmethod
    def benchmark(
        emitter: EventEmitter, event_name: str, iterations: int = 1000
    ) -> Dict[str, Any]:
        """
        Benchmark event triggering performance.

        Args:
            emitter: Event emitter instance
            event_name: Name of the event to benchmark
            iterations: Number of iterations to run

        Returns:
            Dictionary with benchmark results
        """

        # Add a simple listener
        def dummy_listener(*args: Any, **kwargs: Any) -> None:
            pass

        emitter.on(event_name)(dummy_listener)

        # Run benchmark
        start_time = time.time()
        for _ in range(iterations):
            emitter.emit(event_name)
        total_time = time.time() - start_time

        # Clean up
        emitter.remove_listener(event_name, dummy_listener)

        return {
            "iterations": iterations,
            "total_time": total_time,
            "average_time": total_time / iterations,
            "events_per_second": iterations / total_time,
        }
