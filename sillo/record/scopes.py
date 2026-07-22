"""
sillo.record.scopes — Query scopes (local and global) inspired by Laravel Eloquent.

Local scopes are methods prefixed with ``scope_``.  Global scopes are
automatically applied to every query on a model.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


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
        queryset = cls.all()
        return queryset

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
