"""
sillo.record.factories — Model factories for testing (Laravel-style).

Define factory classes that generate test data with sensible defaults.

Usage::

    class UserFactory(Factory):
        model = User
        definition = lambda: {"email": f"user{uuid4().hex[:8]}@test.com", "name": "Test User"}

    user = await UserFactory.create()
    users = await UserFactory.create_many(5)
    unsaved = UserFactory.make()
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from typing_extensions import Doc


class Factory:
    """Base factory for generating model instances.

    Define ``model`` (the model class) and ``definition`` (a callable
    returning a dict of default attributes).
    """

    model: type | None = None
    definition: Callable[[], dict[str, Any]] = dict

    @classmethod
    def make(
        cls,
        overrides: Annotated[
            dict[str, Any] | None, Doc("Attributes to override.")
        ] = None,
    ) -> Any:
        """Create an unsaved model instance."""
        data = {**cls.definition(), **(overrides or {})}
        return cls.model(**data)  # ty: ignore[call-non-callable]

    @classmethod
    async def create(
        cls,
        overrides: Annotated[
            dict[str, Any] | None, Doc("Attributes to override.")
        ] = None,
    ) -> Any:
        """Create and persist a model instance."""
        instance = cls.make(overrides)
        await instance.save()
        return instance

    @classmethod
    async def create_many(
        cls,
        count: Annotated[int, Doc("Number of instances.")],
        overrides: Annotated[
            dict[str, Any] | None, Doc("Attributes applied to all.")
        ] = None,
    ) -> list[Any]:
        """Create and persist *count* instances."""
        instances = []
        for _ in range(count):
            instance = await cls.create(overrides)
            instances.append(instance)
        return instances

    @classmethod
    def state(cls, **kwargs) -> Callable:
        """Return a modifier that overrides definition attributes."""

        def modifier():
            """Modifier"""
            return {**cls.definition(), **kwargs}

        return modifier


class FactoryBuilder:
    """Registry-builder pattern for defining factories."""

    def __init__(self):
        """Init"""
        self._factories: dict[str, type[Factory]] = {}

    def register(self, name: str, factory: type[Factory]) -> None:
        """Register"""
        self._factories[name] = factory

    def get(self, name: str) -> type[Factory]:
        """Get"""
        if name not in self._factories:
            raise KeyError(f"Factory '{name}' not registered")
        return self._factories[name]
