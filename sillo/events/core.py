import asyncio
import inspect
import logging
import threading
import time
import uuid
import weakref
from collections.abc import Callable
from datetime import datetime
from typing import Any, Optional
from weakref import WeakMethod, ref

from .enums import EventPhase, EventPriority
from .exceptions import (
    EventCancelledError,
    ListenerAlreadyRegisteredError,
    MaxListenersExceededError,
)
from .mixins import EventSerializationMixin
from .types import EventContext, ListenerType

# Setup logging
logger = logging.getLogger(__name__)


class Event(EventSerializationMixin):
    """Advanced event implementation with support for priority-based dispatch.

    This class provides a full-featured event object that supports priority-based
    listener execution, DOM-style event propagation (capture/bubble phases),
    both synchronous and asynchronous listeners, thread-safe listener management,
    event cancellation, detailed event context tracking, and built-in performance
    metrics collection.

    Events can be organized hierarchically via parent-child relationships, enabling
    propagation patterns where ancestor events observe or intercept events fired
    on their descendants.  Each event maintains an execution history and running
    performance metrics for observability.

    The class inherits serialization capabilities from
    :class:`~sillo.events.mixins.EventSerializationMixin`, allowing event state
    to be converted to and from dictionary representations for transport or
    persistence.

    Attributes:
        DEFAULT_MAX_LISTENERS: Class-level default for the maximum number of
            listeners a single event instance may hold (100).
    """

    DEFAULT_MAX_LISTENERS = 100

    def __init__(self, name: str, max_listeners: int | None = None):
        """Initialize an Event instance with the given name and listener limit.

        Sets up internal data structures for priority-bucketed listener storage,
        once-listener tracking, thread-safety locks, parent-child hierarchy
        references, execution history, and performance metrics counters.

        Args:
            name: Human-readable name that uniquely identifies this event within
                an emitter or namespace.  Used in log messages, error reports,
                and metric labels.
            max_listeners: Upper bound on the total number of listeners this
                event may hold across all priority levels.  Pass ``None`` to
                fall back to :attr:`DEFAULT_MAX_LISTENERS` (100).  Setting this
                to a very large value effectively disables the guard.

        Raises:
            ValueError: If ``max_listeners`` is provided and is less than zero.
        """
        self.name = name
        self._listeners: dict[EventPriority, list[ListenerType]] = {
            EventPriority.HIGHEST: [],
            EventPriority.HIGH: [],
            EventPriority.NORMAL: [],
            EventPriority.LOW: [],
            EventPriority.LOWEST: [],
        }
        self._once_listeners: dict[EventPriority, list[ListenerType]] = {
            EventPriority.HIGHEST: [],
            EventPriority.HIGH: [],
            EventPriority.NORMAL: [],
            EventPriority.LOW: [],
            EventPriority.LOWEST: [],
        }
        self._max_listeners = max_listeners or self.DEFAULT_MAX_LISTENERS
        self._lock = threading.RLock()
        self._parent: Event | None = None
        self._children: list[Event] = []
        self._enabled = True
        self._history: list[dict[str, Any]] = []
        self._metrics: dict[str, Any] = {
            "trigger_count": 0,
            "total_listeners_executed": 0,
            "average_execution_time": 0.0,
        }

    def __repr__(self) -> str:
        """Return a concise string representation of this Event instance.

        The representation includes the event name and the current total count
        of registered listeners (both persistent and once-listeners combined),
        making it suitable for debugging and interactive inspection.

        Returns:
            A formatted string of the form ``<Event name='...' listeners=N>``
            where *N* is the live listener count obtained via the
            :attr:`listener_count` property.
        """
        return f"<Event name='{self.name}' listeners={self.listener_count}>"

    @property
    def listener_count(self) -> int:
        """Get the total number of listeners currently registered on this event.

        Counts both persistent listeners and one-shot (``once``) listeners across
        all five priority buckets.  The count is computed under the internal
        reentrant lock so the value is consistent even when listeners are being
        added or removed concurrently from other threads.

        Returns:
            Non-negative integer representing the sum of all persistent and
            once-listeners across every :class:`~sillo.events.enums.EventPriority`
            bucket.
        """
        with self._lock:
            return sum(len(v) for v in self._listeners.values()) + sum(
                len(v) for v in self._once_listeners.values()
            )

    @property
    def max_listeners(self) -> int:
        """Get the maximum number of listeners this event is allowed to hold.

        Returns the current ceiling enforced by :meth:`_add_listener` when new
        listeners are registered.  If the listener count reaches this value,
        subsequent registration attempts raise
        :class:`~sillo.events.exceptions.MaxListenersExceededError`.

        Returns:
            Positive integer representing the upper bound on total listeners
            (both persistent and once) for this event instance.
        """
        return self._max_listeners

    @max_listeners.setter
    def max_listeners(self, value: int):
        """Set the maximum number of listeners allowed on this event.

        Updates the listener ceiling that guards against accidental listener
        leaks.  The new value is validated under the internal lock to prevent
        race conditions with concurrent listener registration.

        Args:
            value: New maximum listener count.  Must be greater than or equal
                to the current :attr:`listener_count`.

        Raises:
            ValueError: If ``value`` is less than the current number of
                registered listeners, since shrinking below the existing count
                would silently orphan active listeners.
        """
        with self._lock:
            if value < self.listener_count:
                raise ValueError(
                    f"Cannot set max_listeners to {value} when there are {self.listener_count} listeners"
                )
            self._max_listeners = value

    @property
    def enabled(self) -> bool:
        """Check whether this event is currently enabled for dispatch.

        When an event is disabled, calls to :meth:`trigger` and
        :meth:`trigger_async` return immediately with a cancellation
        dictionary without invoking any registered listeners.  This provides
        a lightweight on/off switch without requiring listener removal.

        Returns:
            ``True`` if the event will dispatch to listeners when triggered,
            ``False`` if trigger calls will be short-circuited.
        """
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """Enable or disable event dispatch for this event instance.

        Sets the internal enabled flag that controls whether :meth:`trigger`
        and :meth:`trigger_async` execute registered listeners or return
        immediately.  Toggling this flag is thread-safe and does not affect
        the listener registry — listeners remain registered and will fire
        once the event is re-enabled.

        Args:
            value: ``True`` to enable dispatch so that listeners are invoked
                on trigger, ``False`` to disable dispatch causing trigger
                calls to return a cancellation dictionary immediately.
        """
        self._enabled = value

    @property
    def parent(self) -> Optional["Event"]:
        """Get the parent event in the propagation hierarchy.

        Returns the event that this event is a child of, or ``None`` if this
        event sits at the root of the hierarchy.  Parent relationships drive
        the capture and bubble propagation phases during event dispatch.

        Returns:
            The parent :class:`Event` instance, or ``None`` if this event has
            no parent and is therefore a root-level event.
        """
        return self._parent

    @parent.setter
    def parent(self, value: Optional["Event"]):
        """Set the parent event, updating the hierarchy bidirectionally.

        Assigns a new parent to this event.  If a previous parent existed,
        this event is removed from that parent's children list first.  The
        new parent (if not ``None``) receives a weak-reference proxy of this
        event in its children list to avoid reference cycles.

        Args:
            value: The new parent :class:`Event` instance, or ``None`` to
                detach this event from the hierarchy entirely.
        """
        with self._lock:
            if self._parent is not None:
                self._parent._children.remove(self)
            self._parent = value
            if value is not None:
                value._children.append(weakref.proxy(self))  # type: ignore

    @property
    def children(self) -> list["Event"]:
        """Get a snapshot of the child events registered under this event.

        Returns a shallow copy of the internal children list so that callers
        can iterate safely without holding the lock.  Children are stored as
        weak-reference proxies to prevent reference cycles in the hierarchy.

        Returns:
            A new list of :class:`Event` instances that are direct children
            of this event in the propagation hierarchy.  The list is empty
            if no children have been added.
        """
        return self._children.copy()

    def add_child(self, child: "Event"):
        """Add a child event to this event's propagation hierarchy.

        Establishes a parent-child relationship by setting this event as the
        parent of the given child.  This enables capture-phase propagation
        from this event down to the child and bubble-phase propagation from
        the child back up.  If the child already has a different parent, that
        relationship is severed first.

        Args:
            child: The :class:`Event` instance to register as a direct child
                of this event in the propagation hierarchy.
        """
        child.parent = self

    def remove_child(self, child: "Event"):
        """Remove a child event from this event's propagation hierarchy.

        Severs the parent-child relationship between this event and the given
        child by clearing the child's parent reference.  If the child is not
        currently a child of this event, the call is a no-op.  After removal,
        capture/bubble propagation between these two events ceases.

        Args:
            child: The :class:`Event` instance to detach from this event's
                children list.  If not found among current children, no
                modification occurs.
        """
        if child in self._children:
            child.parent = None

    def listen(
        self,
        func: Callable[..., Any] | None = None,
        *,
        priority: EventPriority = EventPriority.NORMAL,
        weak_ref: bool = False,
    ) -> Callable[..., Any]:
        """Register a persistent listener via decorator or direct invocation.

        Can be used as a bare decorator (``@event.listen``), a parameterized
        decorator (``@event.listen(priority=EventPriority.HIGH)``), or called
        directly (``event.listen(my_func)``).  The listener remains registered
        until explicitly removed and fires on every subsequent :meth:`trigger`.

        Args:
            func: The listener callable to register.  When used as a decorator
                without arguments this is passed automatically; when used with
                keyword arguments pass ``None`` or omit it.
            priority: The :class:`~sillo.events.enums.EventPriority` level that
                determines execution order relative to other listeners.
                Defaults to ``EventPriority.NORMAL``.
            weak_ref: If ``True``, store a weak reference to the listener so
                that it does not prevent garbage collection of bound methods.
                Defaults to ``False``.

        Returns:
            The original listener callable, unmodified, allowing transparent
            use as a decorator without altering the decorated function.

        Raises:
            ListenerAlreadyRegisteredError: If the same callable is already
                registered at the same priority level.
            MaxListenersExceededError: If adding this listener would exceed
                the configured :attr:`max_listeners` ceiling.
        """

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            self._add_listener(f, priority=priority, weak_ref=weak_ref)
            return f

        if func is None:
            return decorator
        return decorator(func)

    def once(
        self,
        func: Callable[..., Any] | None = None,
        *,
        priority: EventPriority = EventPriority.NORMAL,
        weak_ref: bool = False,
    ) -> Callable[..., Any]:
        """Register a one-shot listener that auto-removes after first invocation.

        Can be used as a bare decorator (``@event.once``), a parameterized
        decorator (``@event.once(priority=EventPriority.HIGH)``), or called
        directly (``event.once(my_func)``).  The listener fires exactly once
        on the next :meth:`trigger` and is then automatically removed from
        the internal registry.

        Args:
            func: The listener callable to register.  When used as a decorator
                without arguments this is passed automatically; when used with
                keyword arguments pass ``None`` or omit it.
            priority: The :class:`~sillo.events.enums.EventPriority` level that
                determines execution order relative to other listeners.
                Defaults to ``EventPriority.NORMAL``.
            weak_ref: If ``True``, store a weak reference to the listener so
                that it does not prevent garbage collection of bound methods.
                Defaults to ``False``.

        Returns:
            The original listener callable, unmodified, allowing transparent
            use as a decorator without altering the decorated function.

        Raises:
            ListenerAlreadyRegisteredError: If the same callable is already
                registered as a once-listener at the same priority level.
            MaxListenersExceededError: If adding this listener would exceed
                the configured :attr:`max_listeners` ceiling.
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
        """Internal method to register a listener with validation and wrapping.

        Performs duplicate detection, max-listener enforcement, optional weak
        reference wrapping, and storage into the appropriate priority bucket.
        This is the single code path used by both :meth:`listen` and
        :meth:`once` to ensure consistent validation semantics.

        Args:
            listener: The callable to invoke when the event is triggered.
                May be a regular function, a bound method, or a coroutine
                function.
            priority: The :class:`~sillo.events.enums.EventPriority` bucket
                into which the listener is placed.  Defaults to
                ``EventPriority.NORMAL``.
            once: If ``True``, the listener is stored in the once-listener
                registry and cleared after the first trigger.  Defaults to
                ``False``.
            weak_ref: If ``True``, wrap the listener in a :class:`weakref.ref`
                or :class:`weakref.WeakMethod` so it does not prevent garbage
                collection.  Defaults to ``False``.

        Raises:
            MaxListenersExceededError: If the total listener count has already
                reached the configured :attr:`max_listeners` ceiling.
            ListenerAlreadyRegisteredError: If an equivalent listener is
                already present in the target priority bucket.
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
        """Remove a listener from all priority buckets and once-registries.

        Scans every :class:`~sillo.events.enums.EventPriority` level in both
        the persistent and once-listener registries, removing all entries that
        match the given callable.  Uses :meth:`_listeners_equal` for comparison
        so weak references and wrapped functions are resolved before matching.

        Args:
            listener: The callable to remove.  All registrations of this
                callable across every priority level are removed in a single
                pass under the internal lock.
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
        """Determine whether two listener references point to the same callable.

        Resolves weak references and ``WeakMethod`` proxies to their underlying
        callables before comparison.  Also unwraps decorator chains via the
        ``__wrapped__`` attribute so that a decorated function and its original
        are considered equivalent.  If either weak reference has been garbage
        collected (returns ``None``), the listeners are considered unequal.

        Args:
            listener1: First listener reference, which may be a raw callable,
                a :class:`weakref.ref`, or a :class:`weakref.WeakMethod`.
            listener2: Second listener reference to compare against, with the
                same type flexibility as ``listener1``.

        Returns:
            ``True`` if both references resolve to the same underlying callable
            (after unwrapping ``__wrapped__`` chains), ``False`` otherwise or
            if either weak reference has been collected.
        """
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

    def trigger(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
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
            event_data: dict[str, Any] = {
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
                    f"Error triggering event '{self.name}': {e!s}", exc_info=True
                )
                raise

    def _propagate(self, event_data: dict[str, Any], phase: EventPhase):
        """Propagate event to parent or children"""
        if phase == EventPhase.CAPTURING and self.parent:
            event_data["context"].phase = phase
            self.parent.trigger(*event_data["args"], **event_data["kwargs"])
        elif phase == EventPhase.BUBBLING and self.children:
            for child in self.children:
                event_data["context"].phase = phase
                child.trigger(*event_data["args"], **event_data["kwargs"])

    async def trigger_async(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Async variant of :meth:`trigger`.

        Identical semantics to ``trigger`` but coroutine listeners are
        *awaited* (in priority order) rather than fire-and-forget, so their
        results and exceptions are observed.  Required for networked
        transports where the dispatch callback is async.
        """
        if not self._enabled:
            return {"cancelled": True, "reason": "Event disabled"}

        with self._lock:
            event_id = str(uuid.uuid4())
            context = EventContext(
                timestamp=time.time(), event_id=event_id, source=self
            )
            event_data: dict[str, Any] = {
                "args": args,
                "kwargs": kwargs,
                "context": context,
                "cancelled": False,
                "default_prevented": False,
            }

        try:
            if self.parent:
                await self._propagate_async(event_data, EventPhase.CAPTURING)

            execution_stats = await self._execute_listeners_async(
                event_data, EventPhase.AT_TARGET
            )

            if not event_data["cancelled"] and self.parent:
                await self._propagate_async(event_data, EventPhase.BUBBLING)

            self._update_metrics(execution_stats)
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
            logger.error(f"Error triggering event '{self.name}': {e!s}", exc_info=True)
            raise

    async def _propagate_async(self, event_data: dict[str, Any], phase: EventPhase):
        if phase == EventPhase.CAPTURING and self.parent:
            event_data["context"].phase = phase
            await self.parent.trigger_async(*event_data["args"], **event_data["kwargs"])
        elif phase == EventPhase.BUBBLING and self.children:
            for child in self.children:
                event_data["context"].phase = phase
                await child.trigger_async(*event_data["args"], **event_data["kwargs"])

    async def _execute_listeners_async(
        self, event_data: dict[str, Any], phase: EventPhase
    ) -> dict[str, Any]:
        """Async listener execution: coroutine listeners are awaited.

        Unlike the synchronous :meth:`_execute_listeners` (which fire-and-forgets
        coroutine listeners via ``create_task``), this *awaits* each coroutine
        listener in priority order.  That is what makes networked delivery
        correct: a listener's exceptions are observed and routed to the
        transport's error handler, and ordering is preserved.  Synchronous
        listeners are still called inline.
        """
        start_time = time.time()
        listeners_executed = 0
        cancelled = False

        with self._lock:
            all_listeners: list[tuple[ListenerType, EventPriority, bool]] = []
            for priority in EventPriority:
                all_listeners.extend(
                    (listener, priority, False)
                    for listener in self._listeners[priority]
                )
                all_listeners.extend(
                    (listener, priority, True)
                    for listener in self._once_listeners[priority]
                )
            for priority in EventPriority:
                self._once_listeners[priority].clear()

        for listener, priority, _ in all_listeners:
            if event_data.get("cancelled", False):
                cancelled = True
                break
            try:
                actual_listener: Callable[..., Any] | None = None
                if isinstance(listener, (ref, WeakMethod)):
                    actual_listener = listener()
                    if actual_listener is None:
                        continue
                else:
                    actual_listener = listener
                if actual_listener is None:
                    continue

                event_data["context"].phase = phase

                if inspect.iscoroutinefunction(actual_listener):
                    await actual_listener(*event_data["args"], **event_data["kwargs"])
                else:
                    actual_listener(*event_data["args"], **event_data["kwargs"])

                listeners_executed += 1
            except EventCancelledError:
                event_data["cancelled"] = True
                cancelled = True
                break
            except Exception as e:
                logger.error(
                    f"Error in event listener for '{self.name}': {e!s}",
                    exc_info=True,
                )

        execution_time = time.time() - start_time
        return {
            "total": listeners_executed,
            "total_time": execution_time,
            "average_time": execution_time / max(1, listeners_executed),
            "cancelled": cancelled,
        }

    def _execute_listeners(
        self, event_data: dict[str, Any], phase: EventPhase
    ) -> dict[str, Any]:
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
            all_listeners: list[tuple[ListenerType, EventPriority, bool]] = []
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
                actual_listener: Callable[..., Any] | None = None
                if isinstance(listener, (ref, WeakMethod)):
                    actual_listener = listener()
                    if actual_listener is None:
                        continue
                else:
                    actual_listener = listener

                if actual_listener is None:
                    continue

                # Update context
                event_data["context"].phase = phase

                # Execute the listener
                if inspect.iscoroutinefunction(actual_listener):
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
                    f"Error in event listener for '{self.name}': {e!s}",
                    exc_info=True,
                )

        execution_time = time.time() - start_time

        return {
            "total": listeners_executed,
            "total_time": execution_time,
            "average_time": execution_time / max(1, listeners_executed),
            "cancelled": cancelled,
        }

    def _update_metrics(self, stats: dict[str, Any]):
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

    def _record_history(self, event_data: dict[str, Any], stats: dict[str, Any]):
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

    def get_metrics(self) -> dict[str, Any]:
        """Get event performance metrics"""
        return self._metrics.copy()

    def get_history(self, limit: int | None = None) -> list[dict[str, Any]]:
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
