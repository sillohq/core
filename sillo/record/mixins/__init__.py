"""sillo.record.mixins — Composable model behaviors inspired by Laravel Eloquent."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import ClassVar, Dict, List, Optional

try:  # pragma: no cover - depends on whether an optional extra is installed
    import ulid
except ImportError:  # pragma: no cover
    ulid = None  # ty: ignore[invalid-assignment]


class SoftDeletesMixin:
    """Adds soft-delete capability to any model.

    Provides ``soft_delete()``, ``restore()``, ``force_delete()``,
    and scoped queries ``active()`` / ``deleted()`` / ``with_trashed()``.
    Requires the model to have a ``deleted_at`` datetime field (nullable).
    """

    async def soft_delete(self) -> None:
        """Soft Delete"""
        self.deleted_at = datetime.now(timezone.utc)
        await self.save(update_fields=["deleted_at"])  # ty: ignore[unresolved-attribute]

    async def restore(self) -> None:
        """Restore"""
        self.deleted_at = None
        await self.save(update_fields=["deleted_at"])  # ty: ignore[unresolved-attribute]

    async def force_delete(self) -> None:
        """Force Delete"""
        await self.delete()  # ty: ignore[unresolved-attribute]

    @classmethod
    def active(cls):
        """Active"""
        return cls.filter(deleted_at__isnull=True)  # ty: ignore[unresolved-attribute]

    @classmethod
    def only_trashed(cls):
        """Only Trashed"""
        return cls.filter(deleted_at__isnull=False)  # ty: ignore[unresolved-attribute]

    @classmethod
    def with_trashed(cls):
        """With Trashed"""
        return cls.all()  # ty: ignore[unresolved-attribute]

    @property
    def is_trashed(self) -> bool:
        """Is Trashed"""
        return self.deleted_at is not None


class TimestampsMixin:
    """Adds ``created_at`` / ``updated_at`` auto-management.

    Requires the model to have ``created_at`` and ``updated_at`` datetime fields.
    If the underlying Tortoise field uses ``auto_now_add`` / ``auto_now``, Tortoise
    handles it automatically. This mixin provides explicit methods for manual control.
    """

    async def touch(self) -> None:
        """Update ``updated_at`` to now and save."""
        self.updated_at = datetime.now(timezone.utc)
        await self.save(update_fields=["updated_at"])  # ty: ignore[unresolved-attribute]

    def set_created_at(self) -> None:
        """Set Created At"""
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc)


class HasUlidMixin:
    """Generates a ULID primary key before creation."""

    def generate_ulid(self) -> str:
        """Return a new 26-character ULID.

        ``ulid.new()`` is the API of ``ulid-py``, a different distribution to
        the ``python-ulid`` this package declares — so this raised
        ``AttributeError`` on every supported install. ``python-ulid`` spells
        it ``ULID()``.
        """
        if ulid is None:
            raise RuntimeError(
                "HasUlidMixin needs the python-ulid package.\n\n"
                "    uv add python-ulid\n\n"
                "or install the framework's full feature set with "
                '`uv add "sillo-framework[all]"`.'
            )

        return str(ulid.ULID())


class SerializesToDictMixin:
    """Adds ``to_dict()`` / ``to_json()`` with field exclusion/inclusion."""

    def to_dict(
        self,
        *,
        exclude: list[str] | None = None,
        include: list[str] | None = None,
        max_depth: int = 3,
    ) -> dict:
        """To Dict"""
        data = {}
        for field_name in self._meta.fields:  # ty: ignore[unresolved-attribute]
            if exclude and field_name in exclude:
                continue
            if include and field_name not in include:
                continue
            value = getattr(self, field_name, None)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif max_depth > 0 and hasattr(value, "to_dict"):
                value = value.to_dict(max_depth=max_depth - 1)
            data[field_name] = value
        return data

    def to_json(self, *, indent: int | None = None, **kwargs) -> str:
        """To Json"""
        return json.dumps(self.to_dict(**kwargs), indent=indent, default=str)


class ValidatesBeforeSaveMixin:
    """Runs ``self.validate()`` before every ``save()`` call.

    Override ``validate()`` in your model to add custom validation logic.
    Raises ``ValidationError`` if validation fails.
    """

    async def validate(self) -> None:
        """Override in your model. Raise ValueError or return None."""

    async def save(self, *args, **kwargs):
        """Save"""
        await self.validate()
        return await super().save(*args, **kwargs)  # ty: ignore[unresolved-attribute]


class CascadesDeletesMixin:
    """Cascading deletes for related models.

    Define ``_cascade_deletes: List[str]`` with related field names.
    When ``delete()`` is called, related models are deleted first.
    """

    _cascade_deletes: ClassVar[list[str]] = []

    async def delete(self):
        """Delete"""
        for relation in self._cascade_deletes:
            related = getattr(self, relation, None)
            if related is not None and hasattr(related, "delete"):
                await related.delete()
        return await super().delete()  # ty: ignore[unresolved-attribute]
