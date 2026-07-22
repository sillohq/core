"""sillo.record.mixins — Composable model behaviors inspired by Laravel Eloquent."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    import ulid
except ImportError:
    ulid = None  # type: ignore[assignment]


class SoftDeletesMixin:
    """Adds soft-delete capability to any model.

    Provides ``soft_delete()``, ``restore()``, ``force_delete()``,
    and scoped queries ``active()`` / ``deleted()`` / ``with_trashed()``.
    Requires the model to have a ``deleted_at`` datetime field (nullable).
    """

    async def soft_delete(self) -> None:
        """Soft Delete

        Returns:
            [description]

        Raises:
            [description]
        """
        self.deleted_at = datetime.now(timezone.utc)
        await self.save(update_fields=["deleted_at"])

    async def restore(self) -> None:
        """Restore

        Returns:
            [description]

        Raises:
            [description]
        """
        self.deleted_at = None
        await self.save(update_fields=["deleted_at"])

    async def force_delete(self) -> None:
        """Force Delete

        Returns:
            [description]

        Raises:
            [description]
        """
        await self.delete()

    @classmethod
    def active(cls):
        """Active

        Returns:
            [description]

        Raises:
            [description]
        """
        return cls.filter(deleted_at__isnull=True)

    @classmethod
    def only_trashed(cls):
        """Only Trashed

        Returns:
            [description]

        Raises:
            [description]
        """
        return cls.filter(deleted_at__isnull=False)

    @classmethod
    def with_trashed(cls):
        """With Trashed

        Returns:
            [description]

        Raises:
            [description]
        """
        return cls.all()

    @property
    def is_trashed(self) -> bool:
        """Is Trashed

        Returns:
            [description]

        Raises:
            [description]
        """
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
        await self.save(update_fields=["updated_at"])

    def set_created_at(self) -> None:
        """Set Created At

        Returns:
            [description]

        Raises:
            [description]
        """
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc)


class HasUlidMixin:
    """Generates a ULID primary key before creation."""

    def generate_ulid(self) -> str:
        """Generate Ulid

        Returns:
            [description]

        Raises:
            [description]
        """
        return str(ulid.new())


class SerializesToDictMixin:
    """Adds ``to_dict()`` / ``to_json()`` with field exclusion/inclusion."""

    def to_dict(
        self,
        *,
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
        max_depth: int = 3,
    ) -> Dict:
        """To Dict

        Returns:
            [description]

        Raises:
            [description]
        """
        data = {}
        for field_name in self._meta.fields:
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

    def to_json(self, *, indent: Optional[int] = None, **kwargs) -> str:
        """To Json

        Returns:
            [description]

        Raises:
            [description]
        """
        return json.dumps(self.to_dict(**kwargs), indent=indent, default=str)


class ValidatesBeforeSaveMixin:
    """Runs ``self.validate()`` before every ``save()`` call.

    Override ``validate()`` in your model to add custom validation logic.
    Raises ``ValidationError`` if validation fails.
    """

    async def validate(self) -> None:
        """Override in your model. Raise ValueError or return None."""
        pass

    async def save(self, *args, **kwargs):
        """Save

        Returns:
            [description]

        Raises:
            [description]
        """
        await self.validate()
        return await super().save(*args, **kwargs)


class CascadesDeletesMixin:
    """Cascading deletes for related models.

    Define ``_cascade_deletes: List[str]`` with related field names.
    When ``delete()`` is called, related models are deleted first.
    """

    _cascade_deletes: List[str] = []

    async def delete(self):
        """Delete

        Returns:
            [description]

        Raises:
            [description]
        """
        for relation in self._cascade_deletes:
            related = getattr(self, relation, None)
            if related is not None:
                if hasattr(related, "delete"):
                    await related.delete()
        return await super().delete()
