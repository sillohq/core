"""
sillo.db.models — Enhanced Tortoise Model base class.

Features beyond standard Tortoise:
- Auto ``created_at`` / ``updated_at``
- Soft-delete support
- ``to_dict()`` / ``to_json()`` serialization
- ``update_from_dict()`` for Pydantic-compatible partial updates
- Query shortcuts: ``get_or_none``, ``get_or_create``, ``bulk_create``
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional, Type, TypeVar

from tortoise import Model as _TortoiseModel
from tortoise import fields

from .fields import CreatedAtField, SoftDeleteField, UpdatedAtField

T = TypeVar("T", bound="Model")


class QuerySet(
    _TortoiseModel._meta.default_connection.__class__.QuerySet if False else Any
):
    """Enhanced queryset — placeholder for actual Tortoise QuerySet integration."""

    pass


class Model(_TortoiseModel):
    """Enhanced Tortoise base model.

    Usage::

        class User(sillo.db.Model):
            id = fields.IntField(pk=True)
            email = fields.CharField(max_length=255, unique=True)
            name = fields.CharField(max_length=100)

        user = await User.create(email="a@b.com", name="Alice")
        users = await User.filter(name__icontains="ali").all()
    """

    created_at: ClassVar[CreatedAtField] = CreatedAtField()
    updated_at: ClassVar[UpdatedAtField] = UpdatedAtField()
    deleted_at: ClassVar[SoftDeleteField] = SoftDeleteField()

    class Meta:
        abstract = True

    # ── serialization ──────────────────────────────────────────────────────

    def to_dict(
        self,
        *,
        exclude: Optional[List[str]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Serialize the model to a plain dict.

        Args:
            exclude: Field names to omit.
            include: If set, ONLY include these fields.
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
            elif isinstance(value, Model):
                value = value.to_dict()
            data[field_name] = value
        return data

    def to_json(self, *, indent: Optional[int] = None, **kwargs) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(**kwargs), indent=indent, default=str)

    # ── mutation helpers ───────────────────────────────────────────────────

    async def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Apply a dict of field updates and save.

        This works well with Pydantic model dumps::

            user.update_from_dict(form.model_dump(exclude_unset=True))
        """
        meta = self._meta
        for key, value in data.items():
            if key in meta.fields:
                setattr(self, key, value)
        await self.save()

    # ── soft-delete ────────────────────────────────────────────────────────

    async def soft_delete(self) -> None:
        """Set ``deleted_at`` to now without removing the row."""
        self.deleted_at = datetime.now(timezone.utc)
        await self.save(update_fields=["deleted_at"])

    async def restore(self) -> None:
        """Clear ``deleted_at`` to un-delete a soft-deleted row."""
        self.deleted_at = None
        await self.save(update_fields=["deleted_at"])

    @classmethod
    def active(cls):
        """Return a queryset excluding soft-deleted rows."""
        return cls.filter(deleted_at__isnull=True)

    @classmethod
    def deleted(cls):
        """Return a queryset of ONLY soft-deleted rows."""
        return cls.filter(deleted_at__isnull=False)

    # ── query shortcuts ────────────────────────────────────────────────────

    @classmethod
    async def get_or_none(cls: Type[T], **kwargs) -> Optional[T]:
        """Return the first matching row, or None."""
        try:
            return await cls.get(**kwargs)
        except Exception:
            return None

    @classmethod
    async def get_or_create(
        cls: Type[T], defaults: Optional[Dict[str, Any]] = None, **kwargs
    ) -> tuple[T, bool]:
        """Return the existing row or create a new one.

        Returns (instance, created_bool).
        """
        instance = await cls.get_or_none(**kwargs)
        if instance:
            return instance, False
        params = {**kwargs, **(defaults or {})}
        return await cls.create(**params), True

    @classmethod
    async def bulk_create(
        cls: Type[T], items: List[Dict[str, Any]], batch_size: int = 100
    ) -> List[T]:
        """Insert multiple rows efficiently.

        Args:
            items: List of field dicts.
            batch_size: Insert this many per query.
        """
        instances = [cls(**item) for item in items]
        created = []
        for i in range(0, len(instances), batch_size):
            batch = instances[i : i + batch_size]
            await cls.bulk_create(batch)
            created.extend(batch)
        return instances

    @classmethod
    async def count_active(cls) -> int:
        """Count non-deleted rows."""
        return await cls.active().count()

    # ── validation ─────────────────────────────────────────────────────────

    async def validate(self) -> None:
        """Hook called before save. Override in subclasses."""
        pass

    async def save(self, *args, **kwargs):
        await self.validate()
        return await super().save(*args, **kwargs)
