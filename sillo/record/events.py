"""
sillo.record.events — Model lifecycle events (Observer pattern).

Provides hooks that fire at specific points in a model's lifecycle:
``before_create``, ``after_create``, ``before_save``, ``after_save``,
``before_delete``, ``after_delete``, ``before_update``, ``after_update``.

Register callbacks per model class or globally.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List

logger = logging.getLogger("sillo.record.events")


class ModelObserver:
    """Observer that listens to multiple model events.

    Usage::

        class UserObserver(ModelObserver):
            async def before_create(self, instance):
                instance.email = instance.email.lower()

            async def after_create(self, instance):
                await audit_log(f"User {instance.id} created")

        User.observe(UserObserver())
    """

    async def before_create(self, instance):
        """Before Create

        Args:
            instance: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def after_create(self, instance):
        """After Create

        Args:
            instance: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def before_save(self, instance):
        """Before Save

        Args:
            instance: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def after_save(self, instance):
        """After Save

        Args:
            instance: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def before_update(self, instance):
        """Before Update

        Args:
            instance: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def after_update(self, instance):
        """After Update

        Args:
            instance: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def before_delete(self, instance):
        """Before Delete

        Args:
            instance: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass

    async def after_delete(self, instance):
        """After Delete

        Args:
            instance: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        pass


class EventDispatcher:
    """Dispatches model lifecycle events to registered callbacks."""

    def __init__(self):
        """Init

        Returns:
            [description]

        Raises:
            [description]
        """
        self._listeners: Dict[str, List[Callable[..., Awaitable[None]]]] = {
            "before_create": [],
            "after_create": [],
            "before_save": [],
            "after_save": [],
            "before_update": [],
            "after_update": [],
            "before_delete": [],
            "after_delete": [],
            "before_restore": [],
            "after_restore": [],
        }
        self._observers: List[ModelObserver] = []

    def on(self, event: str, callback: Callable[..., Awaitable[None]]) -> None:
        """Register a callback for a lifecycle event."""
        if event in self._listeners:
            self._listeners[event].append(callback)

    def observe(self, observer: ModelObserver) -> None:
        """Register an observer instance."""
        self._observers.append(observer)

    async def fire(self, event: str, instance) -> None:
        """Fire all callbacks registered for *event*."""
        for cb in self._listeners.get(event, []):
            try:
                await cb(instance)
            except Exception:
                logger.exception(f"Event callback {event} failed")

        for observer in self._observers:
            handler = getattr(observer, event, None)
            if handler:
                try:
                    await handler(instance)
                except Exception:
                    logger.exception(
                        f"Observer {type(observer).__name__}.{event} failed"
                    )


class HasEvents:
    """Mixin that adds lifecycle events to a model.

    Usage::

        class User(Model, HasEvents):
            ...

        @User.on("after_create")
        async def log_creation(instance):
            print(f"User {instance.id} created")

        User.observe(UserObserver())
    """

    _events: Optional[EventDispatcher] = None

    @classmethod
    def _ensure_events(cls):
        """Ensure Events

        Returns:
            [description]

        Raises:
            [description]
        """
        if cls._events is None:
            cls._events = EventDispatcher()

    @classmethod
    def on(cls, event: str):
        """Decorator: register a callback for a lifecycle event."""
        cls._ensure_events()

        def decorator(func):
            """Decorator

            Args:
                func: [description]

            Returns:
                [description]

            Raises:
                [description]
            """
            cls._events.on(event, func)
            return func

        return decorator

    @classmethod
    def observe(cls, observer: ModelObserver) -> None:
        """Register an observer."""
        cls._ensure_events()
        cls._events.observe(observer)

    @classmethod
    async def fire_event(cls, event: str, instance) -> None:
        """Fire Event

        Args:
            event: [description]
            instance: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if cls._events:
            await cls._events.fire(event, instance)
