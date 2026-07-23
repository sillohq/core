"""
sillo.record.scopes — Query scopes (local and global) inspired by Laravel Eloquent.

Local scopes are methods prefixed with ``scope_``.  Global scopes are
automatically applied to every query on a model.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from tortoise.manager import Manager
from tortoise.queryset import QuerySet


class ScopeRegistry:
    """Registry of global scopes applied to every query."""

    def __init__(self):
        """Init

        Returns:
            [description]

        Raises:
            [description]
        """
        self._global_scopes: List[Callable] = []

    def add(self, scope: Callable) -> None:
        """Register a global scope. ``scope(queryset) -> queryset``."""
        self._global_scopes.append(scope)

    def remove(self, scope: Callable) -> bool:
        """Remove a global scope. Returns True if found."""
        try:
            self._global_scopes.remove(scope)
            return True
        except ValueError:
            return False

    def apply(self, queryset):
        """Apply all registered scopes to *queryset*."""
        for scope in self._global_scopes:
            queryset = scope(queryset)
        return queryset

    def without_global_scopes(self, queryset):
        """Return the queryset without applying any global scopes."""
        return queryset


class HasScopes:
    """Mixin that adds scope support to a model class.

    Usage::

        class User(Model, HasScopes):
            @classmethod
            def scope_active(cls, queryset):
                return queryset.filter(is_active=True)

            @classmethod
            def scope_vip(cls, queryset):
                return queryset.filter(plan="vip")

        active_vip = await User.active().vip().all()
    """

    _scope_registry: Optional[ScopeRegistry] = None

    @classmethod
    def add_global_scope(cls, scope: Callable) -> None:
        """Register a global scope applied to ALL queries on this model."""
        if cls._scope_registry is None:
            cls._scope_registry = ScopeRegistry()
        cls._scope_registry.add(scope)

    @classmethod
    def without_global_scopes(cls):
        """Return a queryset without global scopes applied."""
        return cls._meta.manager.without_global_scopes()

    @classmethod
    def apply_scopes(cls, queryset):
        """Apply Scopes

        Args:
            queryset: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if cls._scope_registry is not None:
            return cls._scope_registry.apply(queryset)
        return queryset


class RecordQuerySet(QuerySet):
    """Tortoise QuerySet with chainable ``scope_*`` model methods."""

    def __getattr__(self, name: str):
        scope = getattr(self.model, f"scope_{name}", None)
        if scope is None:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )

        def apply_local_scope(*args, **kwargs):
            return scope(self, *args, **kwargs)

        return apply_local_scope

    def without_global_scopes(self):
        """Return this queryset rebuilt without model-level global scopes."""
        queryset = self.__class__(self.model)
        queryset._db = self._db
        return queryset


class RecordManager(Manager):
    """Default manager that applies model global scopes."""

    def get_queryset(self) -> RecordQuerySet:
        queryset = RecordQuerySet(self._model)
        apply_scopes = getattr(self._model, "apply_scopes", None)
        if apply_scopes is not None:
            return apply_scopes(queryset)
        return queryset

    def without_global_scopes(self) -> RecordQuerySet:
        return RecordQuerySet(self._model)
