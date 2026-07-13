"""
sillo.work.queue.events — Laravel-style event dispatcher and subscriber system.

Events are simple dataclass instances.  Listeners are async callables
registered to handle specific event types.  Supports wildcard matching
and priority ordering.

Usage::

    from sillo.work.queue.events import Event, listen, EventDispatcher

    class OrderShipped(Event):
        order_id: str
        tracking: str

    @listen(OrderShipped)
    async def notify_customer(event: OrderShipped):
        await send_email(...)

    dispatcher = EventDispatcher()
    dispatcher.register(OrderShipped, notify_customer)
    await dispatcher.dispatch(OrderShipped(order_id="42", tracking="1Z999"))
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Annotated, Any, Awaitable, Callable, Dict, List, Optional, Type, TypeVar

from typing_extensions import Doc

logger = logging.getLogger("sillo.work.queue.events")

E = TypeVar("E", bound="Event")


@dataclass
class Event:
    """Base class for all events. Subclass and add fields."""

    _fired_at: float = field(default_factory=time.time, init=False)
    _propagation_stopped: bool = field(default=False, init=False)

    def stop_propagation(self) -> None:
        """Prevent remaining listeners from receiving this event."""
        self._propagation_stopped = True


ListenerCallback = Callable[[Event], Awaitable[None]]


def listen(*events: Type[Event], priority: int = 0) -> Callable:
    """Decorator that registers a function as a listener for given event types.

    Usage::

        @listen(OrderShipped, PaymentReceived)
        async def handle(event):
            ...
    """
    def decorator(func: ListenerCallback) -> ListenerCallback:
        func._listens_to = events
        func._listener_priority = priority
        return func
    return decorator


@dataclass
class ListenerRegistration:
    """Internal registration entry for a listener."""

    callback: ListenerCallback
    event_type: Type[Event]
    priority: int = 0
    name: str = ""


class EventDispatcher:
    """Central event dispatcher — register listeners and fire events.

    Listeners are called in priority order (higher = earlier).  If a
    listener raises, the exception is logged and remaining listeners
    are still invoked (fail-open).

    Usage::

        dispatcher = EventDispatcher()
        dispatcher.register(OrderShipped, notify_customer, priority=10)
        await dispatcher.dispatch(OrderShipped(order_id="42"))
        dispatcher.forget(OrderShipped, notify_customer)
    """

    def __init__(self):
        self._listeners: Dict[Type[Event], List[ListenerRegistration]] = {}
        self._wildcards: List[ListenerRegistration] = []

    def register(
        self,
        event_type: Annotated[Type[Event], Doc("Event class to listen for.")],
        callback: Annotated[ListenerCallback, Doc("Async callable receiving the event instance.")],
        *,
        priority: Annotated[int, Doc("Higher values fire first.")] = 0,
        name: Annotated[str, Doc("Optional label for debugging.")] = "",
    ) -> None:
        """Register a listener for *event_type*."""
        reg = ListenerRegistration(callback=callback, event_type=event_type, priority=priority, name=name or callback.__name__)
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(reg)
        self._listeners[event_type].sort(key=lambda r: -r.priority)

    def register_wildcard(
        self,
        callback: Annotated[ListenerCallback, Doc("Async callable.")],
        *,
        priority: Annotated[int, Doc("Higher = earlier.")] = 0,
    ) -> None:
        """Register a listener that receives ALL events (wildcard)."""
        self._wildcards.append(ListenerRegistration(callback=callback, event_type=Event, priority=priority, name=callback.__name__))
        self._wildcards.sort(key=lambda r: -r.priority)

    def forget(
        self,
        event_type: Annotated[Type[Event], Doc("Event class.")],
        callback: Annotated[ListenerCallback, Doc("Callback to remove.")],
    ) -> bool:
        """Remove a specific listener. Returns True if found."""
        if event_type not in self._listeners:
            return False
        before = len(self._listeners[event_type])
        self._listeners[event_type] = [r for r in self._listeners[event_type] if r.callback is not callback]
        return len(self._listeners[event_type]) < before

    def has_listeners(self, event_type: Type[Event]) -> bool:
        """Check if any listeners are registered for *event_type*."""
        return bool(self._listeners.get(event_type)) or bool(self._wildcards)

    async def dispatch(self, event: Annotated[E, Doc("Event instance to dispatch.")]) -> E:
        """Fire *event* to all matching listeners.

        Listeners are called sequentially (not concurrently) to enable
        ``stop_propagation()`` semantics.  If you need parallel dispatch,
        spawn tasks within your listeners.
        """
        event_type = type(event)

        # Wildcard listeners (all events)
        for reg in self._wildcards:
            if event._propagation_stopped:
                break
            await self._call_listener(reg, event)

        # Exact-match listeners
        for reg in self._listeners.get(event_type, []):
            if event._propagation_stopped:
                break
            await self._call_listener(reg, event)

        return event

    async def _call_listener(self, reg: ListenerRegistration, event: Event) -> None:
        try:
            await reg.callback(event)
        except Exception:
            logger.exception(f"Listener '{reg.name}' for {reg.event_type.__name__} raised")

    def clear(self) -> None:
        """Remove all registered listeners."""
        self._listeners.clear()
        self._wildcards.clear()
