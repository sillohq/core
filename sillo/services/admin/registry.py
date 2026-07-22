"""
sillo.services.admin.registry — ModelAdmin registration system.

Handles registration of models with their admin configuration classes.
Each registered model gets a :class:`ModelAdmin` that controls the
admin interface for that model.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type


class ModelAdmin:
    """Configuration for a model's admin interface.

    Attributes that control the admin UI::

        class UserAdmin(ModelAdmin):
            list_display = ["id", "email", "name", "created_at"]
            list_display_links = ["email"]
            search_fields = ["email", "name"]
            list_filter = ["is_active", "plan"]
            ordering = ["-created_at"]
            list_per_page = 25
            fields = ["email", "name", "is_active", "plan"]
            readonly_fields = ["created_at", "updated_at"]
            actions = ["delete_selected"]
            save_on_top = True
    """

    # ── List view configuration ───────────────────────────────────────
    list_display: List[str] = ["__str__"]
    list_display_links: List[str] = []
    list_filter: List[str] = []
    search_fields: List[str] = []
    ordering: List[str] = []
    list_per_page: int = 25
    actions: List[str] = ["delete_selected"]

    # ── Form configuration ────────────────────────────────────────────
    fields: Optional[List[str]] = None
    exclude: Optional[List[str]] = None
    readonly_fields: List[str] = []
    save_on_top: bool = False

    # ── Permissions ───────────────────────────────────────────────────
    @staticmethod
    def has_view_permission(request) -> bool:
        """Has View Permission

            Args:
                request: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return True

    @staticmethod
    def has_add_permission(request) -> bool:
        """Has Add Permission

            Args:
                request: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return True

    @staticmethod
    def has_change_permission(request, obj=None) -> bool:
        """Has Change Permission

            Args:
                request: [description]
                obj: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return True

    @staticmethod
    def has_delete_permission(request, obj=None) -> bool:
        """Has Delete Permission

            Args:
                request: [description]
                obj: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return True

    # ── Display helpers ───────────────────────────────────────────────
    @classmethod
    def get_list_display(cls):
        """Get List Display

            Returns:
                [description]

            Raises:
                [description]
        """
        return cls.list_display

    @classmethod
    def get_search_fields(cls):
        """Get Search Fields

            Returns:
                [description]

            Raises:
                [description]
        """
        return cls.search_fields

    @classmethod
    def get_list_filter(cls):
        """Get List Filter

            Returns:
                [description]

            Raises:
                [description]
        """
        return cls.list_filter

    @classmethod
    def get_ordering(cls):
        """Get Ordering

            Returns:
                [description]

            Raises:
                [description]
        """
        return cls.ordering

    @classmethod
    def get_fields(cls, add: bool = False):
        """Get Fields

            Args:
                add: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return cls.fields

    @classmethod
    def get_readonly_fields(cls, add: bool = False):
        """Get Readonly Fields

            Args:
                add: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return cls.readonly_fields

    @classmethod
    def get_queryset(cls, queryset):
        """Get Queryset

            Args:
                queryset: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return queryset


class Registry:
    """Holds all registered model → ModelAdmin mappings."""

    def __init__(self):
        """Init

            Returns:
                [description]

            Raises:
                [description]
        """
        self._registry: Dict[Type, Type[ModelAdmin]] = {}

    def register(self, model_class: Type, admin_class: Type[ModelAdmin]) -> None:
        """Register

            Args:
                model_class: [description]
                admin_class: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        if model_class in self._registry:
            raise ValueError(f"Model {model_class.__name__} is already registered")
        self._registry[model_class] = admin_class

    def get(self, model_class: Type) -> Optional[Type[ModelAdmin]]:
        """Get

            Args:
                model_class: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return self._registry.get(model_class)

    @property
    def models(self) -> List[Type]:
        """Models

            Returns:
                [description]

            Raises:
                [description]
        """
        return list(self._registry.keys())

    @property
    def admins(self) -> List[Type[ModelAdmin]]:
        """Admins

            Returns:
                [description]

            Raises:
                [description]
        """
        return list(self._registry.values())

    def __iter__(self):
        """Iter

            Returns:
                [description]

            Raises:
                [description]
        """
        return iter(self._registry.items())

    def __contains__(self, model_class: Type) -> bool:
        """Contains

            Args:
                model_class: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return model_class in self._registry
