"""
sillo.work.queue.listener — Advanced event listener with wildcards and filtering.

Extends the basic event dispatcher with:
* Wildcard pattern matching (e.g. ``order.*`` matches ``order.shipped``)
* Listener priority groups
* Conditional listeners (only fire if a guard returns True)
* Once-listeners (auto-unsubscribe after first fire)
* Async listener registry for DI integration
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from typing import Annotated, Any, Awaitable, Callable, Dict, List, Optional, Set, Type

from typing_extensions import Doc

from .events import Event, EventDispatcher, ListenerCallback

logger = logging.getLogger("sillo.work.queue.listener")


class WildcardListener:
    """Matches events by glob pattern (e.g. ``"user.*"``)."""

    def __init__(
        self,
        pattern: Annotated[str, Doc("Glob pattern — e.g. 'order.shipped' or 'order.*'.")],
        callback: Annotated[ListenerCallback, Doc("Async callable.")],
        *,
        priority: Annotated[int, Doc("Higher = earlier.")] = 0,
        once: Annotated[bool, Doc("Auto-unsubscribe after first fire.")] = False,
        guard: Annotated[Optional[Callable[[Event], bool]], Doc("Only fire if this returns True.")] = None,
    ):
        self.pattern = pattern
        self.callback = callback
        self.priority = priority
        self.once = once
        self.guard = guard
        self._fired = False

    def matches(self, event_name: str) -> bool:
        return fnmatch.fnmatch(event_name, self.pattern)

    async def handle(self, event: Event) -> None:
        if self.once and self._fired:
            return
        if self.guard and not self.guard(event):
            return
        await self.callback(event)
        self._fired = True


class ListenerRegistry:
    """Manages typed and wildcard listeners for an :class:`EventDispatcher`.

    Usage::

        registry = ListenerRegistry(dispatcher)
        registry.on("order.*", handle_order_events, priority=10)
        registry.once("user.registered", send_welcome_email)
    """

    def __init__(self, dispatcher: EventDispatcher):
        self.dispatcher = dispatcher
        self._wildcards: List[WildcardListener] = []
        self._typed: Dict[Type[Event], List[ListenerCallback]] = {}

    def on(
        self,
        event: Annotated[Any, Doc("Event type or glob string.")],
        callback: Annotated[ListenerCallback, Doc("Async callable.")],
        *,
        priority: Annotated[int, Doc("Higher = earlier.")] = 0,
    ) -> None:
        """Register a persistent listener."""
        if isinstance(event, str):
            self._wildcards.append(WildcardListener(event, callback, priority=priority))
            self._wildcards.sort(key=lambda w: -w.priority)
        else:
            self.dispatcher.register(event, callback, priority=priority)

    def once(
        self,
        event: Annotated[Any, Doc("Event type or glob string.")],
        callback: Annotated[ListenerCallback, Doc("Async callable.")],
    ) -> None:
        """Register a listener that auto-unsubscribes after first fire."""
        if isinstance(event, str):
            self._wildcards.append(WildcardListener(event, callback, once=True))
        else:
            async def _once(evt):
                self.dispatcher.forget(event, callback)
                await callback(evt)
            self.dispatcher.register(event, _once)

    async def dispatch_wildcards(self, event: Event) -> None:
        """Fire matching wildcard listeners for an event."""
        event_name = type(event).__name__
        remaining = []
        for wl in self._wildcards:
            if wl.matches(event_name):
                await wl.handle(event)
                if not wl.once:
                    remaining.append(wl)
            else:
                remaining.append(wl)
        self._wildcards = remaining

    def clear(self) -> None:
        """Remove all registered listeners."""
        self._wildcards.clear()
        self._typed.clear()
        self.dispatcher.clear()


class EventListener:
    """High-level listener that bridges the event system with the queue.

    Usage::

        listener = EventListener(dispatcher)
        listener.listen(UserRegistered, send_welcome_email)
        listener.listen("order.*", log_all_order_events)
    """

    def __init__(self, dispatcher: EventDispatcher):
        self.registry = ListenerRegistry(dispatcher)
        self.dispatcher = dispatcher

    def listen(
        self,
        event: Annotated[Any, Doc("Event type or glob pattern.")],
        callback: Annotated[ListenerCallback, Doc("Async callable.")],
        *,
        priority: Annotated[int, Doc("Higher = earlier.")] = 0,
    ) -> None:
        """Register a listener for *event*."""
        self.registry.on(event, callback, priority=priority)
