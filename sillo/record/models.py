"""
sillo.record.models — Enhanced Tortoise base model.

Features:
- Auto ``created_at`` / ``updated_at`` / ``deleted_at`` (soft-delete)
- ``to_dict()`` / ``to_json()`` serialization
- ``update_from_dict()`` for Pydantic-compatible partial updates
- ``get_or_none`` / ``get_or_create`` / ``bulk_create`` shortcuts
- ``active()`` / ``deleted()`` queryset filters
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any, ClassVar, Dict, List, Optional, Type, TypeVar

from tortoise import Model as _TortoiseModel
from tortoise import fields
from typing_extensions import Doc

from .fields import CreatedAtField, SoftDeleteField, UpdatedAtField

T = TypeVar("T", bound="Model")


class Model(_TortoiseModel):
    """Enhanced Tortoise base model.

    Usage::

        class User(sillo.record.Model):
            id = fields.IntField(pk=True)
            email = fields.CharField(max_length=255, unique=True)
            name = fields.CharField(max_length=100)

        user = await User.create(email="a@b.com", name="Alice")
        users = await User.filter(name__icontains="ali").all()
        print(user.to_dict())
    """

    created_at: ClassVar[CreatedAtField] = CreatedAtField()
    updated_at: ClassVar[UpdatedAtField] = UpdatedAtField()
    deleted_at: ClassVar[SoftDeleteField] = SoftDeleteField()

    class Meta:
        abstract = True

    def to_dict(
        self,
        *,
        exclude: Annotated[Optional[List[str]], Doc("Field names to omit.")] = None,
        include: Annotated[
            Optional[List[str]], Doc("If set, ONLY include these fields.")
        ] = None,
    ) -> Dict[str, Any]:
        """Serialize the model to a plain dict."""
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

    async def update_from_dict(
        self,
        data: Annotated[
            Dict[str, Any], Doc("Dict to apply, e.g. from pydantic model_dump().")
        ],
    ) -> None:
        """Apply a dict of field updates and save."""
        for key, value in data.items():
            if key in self._meta.fields:
                setattr(self, key, value)
        await self.save()

    async def soft_delete(self) -> None:
        """Mark as deleted without removing the row."""
        self.deleted_at = datetime.now(timezone.utc)
        await self.save(update_fields=["deleted_at"])

    async def restore(self) -> None:
        """Clear deleted_at to undelete."""
        self.deleted_at = None
        await self.save(update_fields=["deleted_at"])

    @classmethod
    def active(cls):
        """Queryset excluding soft-deleted rows."""
        return cls.filter(deleted_at__isnull=True)

    @classmethod
    def deleted(cls):
        """Queryset of only soft-deleted rows."""
        return cls.filter(deleted_at__isnull=False)

    @classmethod
    async def get_or_none(cls: Type[T], **kwargs) -> Optional[T]:
        """Return the first matching row, or None."""
        try:
            return await cls.get(**kwargs)
        except Exception:
            return None

    @classmethod
    async def get_or_create(
        cls: Type[T],
        defaults: Annotated[
            Optional[Dict[str, Any]], Doc("Values to use when creating.")
        ] = None,
        **kwargs,
    ) -> tuple[T, bool]:
        """Return existing or create new. Returns (instance, created)."""
        instance = await cls.get_or_none(**kwargs)
        if instance:
            return instance, False
        return await cls.create(**{**kwargs, **(defaults or {})}), True

    @classmethod
    async def bulk_create(
        cls: Type[T],
        items: Annotated[List[Dict[str, Any]], Doc("List of field dicts.")],
        batch_size: Annotated[int, Doc("Insert this many per query.")] = 100,
    ) -> List[T]:
        """Insert multiple rows efficiently."""
        instances = [cls(**item) for item in items]
        for i in range(0, len(instances), batch_size):
            await cls.bulk_create(instances[i : i + batch_size])
        return instances

    @classmethod
    async def count_active(cls) -> int:
        """Count non-deleted rows."""
        return await cls.active().count()
