"""
sillo.admin.registry — ModelAdmin registration system.

Handles registration of models with their admin configuration classes.
Each registered model gets a :class:`ModelAdmin` that controls the
admin interface for that model.
"""

from __future__ import annotations

from typing import ClassVar


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

    # ── Display ────────────────────────────────────────────────────────
    verbose_name: str | None = (
        None  # sidebar/header label; defaults to the model's class name
    )

    # ── List view configuration ───────────────────────────────────────
    list_display: ClassVar[list[str]] = ["__str__"]
    list_display_links: ClassVar[list[str]] = []
    list_filter: ClassVar[list[str]] = []
    search_fields: ClassVar[list[str]] = []
    ordering: ClassVar[list[str]] = []
    list_per_page: int = 25
    actions: ClassVar[list[str]] = ["delete_selected"]

    # ── Form configuration ────────────────────────────────────────────
    fields: list[str] | None = None
    exclude: list[str] | None = None
    readonly_fields: ClassVar[list[str]] = []
    save_on_top: bool = False

    # ── Permissions ───────────────────────────────────────────────────
    @staticmethod
    def has_view_permission(request) -> bool:
        """Has View Permission"""
        return True

    @staticmethod
    def has_add_permission(request) -> bool:
        """Has Add Permission"""
        return True

    @staticmethod
    def has_change_permission(request, obj=None) -> bool:
        """Has Change Permission"""
        return True

    @staticmethod
    def has_delete_permission(request, obj=None) -> bool:
        """Has Delete Permission"""
        return True

    # ── Display helpers ───────────────────────────────────────────────
    @classmethod
    def get_list_display(cls):
        """Get List Display"""
        return cls.list_display

    @classmethod
    def get_search_fields(cls):
        """Get Search Fields"""
        return cls.search_fields

    @classmethod
    def get_list_filter(cls):
        """Get List Filter"""
        return cls.list_filter

    @classmethod
    def get_ordering(cls):
        """Get Ordering"""
        return cls.ordering

    @classmethod
    def get_fields(cls, add: bool = False):
        """Get Fields"""
        return cls.fields

    @classmethod
    def get_readonly_fields(cls, add: bool = False):
        """Get Readonly Fields"""
        return cls.readonly_fields

    @classmethod
    def get_queryset(cls, queryset):
        """Get Queryset"""
        return queryset


class Registry:
    """Holds all registered model → ModelAdmin mappings."""

    def __init__(self):
        """Init"""
        self._registry: dict[type, type[ModelAdmin]] = {}

    def register(self, model_class: type, admin_class: type[ModelAdmin]) -> None:
        """Register"""
        if model_class in self._registry:
            raise ValueError(f"Model {model_class.__name__} is already registered")
        self._registry[model_class] = admin_class

    def get(self, model_class: type) -> type[ModelAdmin] | None:
        """Get"""
        return self._registry.get(model_class)

    @property
    def models(self) -> list[type]:
        """Models"""
        return list(self._registry.keys())

    @property
    def admins(self) -> list[type[ModelAdmin]]:
        """Admins"""
        return list(self._registry.values())

    def __iter__(self):
        """Iter"""
        return iter(self._registry.items())

    def __contains__(self, model_class: type) -> bool:
        """Contains"""
        return model_class in self._registry
