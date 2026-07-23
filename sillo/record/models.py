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
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated, Any, ClassVar, Dict, Iterable, List, Optional, Type, TypeVar

from tortoise import Model as _TortoiseModel
from tortoise import fields
from tortoise.exceptions import ConfigurationError, OperationalError
from typing_extensions import Doc

from .casting import HasCasts
from .fields import CreatedAtField, SoftDeleteField, UpdatedAtField
from .scopes import HasScopes, RecordManager

T = TypeVar("T", bound="Model")


class Model(_TortoiseModel, HasCasts, HasScopes):
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
        """Meta

        Returns:
            [description]

        Raises:
            [description]
        """

        abstract = True
        manager = RecordManager()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "_meta"):
            cls._meta.manager = RecordManager(cls)
        for name in dir(cls):
            if not name.startswith("scope_"):
                continue
            public_name = name.removeprefix("scope_")
            if hasattr(cls, public_name):
                continue

            def scope_method(scope_name):
                @classmethod
                def call_scope(model_cls, *args, **kwargs):
                    return getattr(model_cls.all(), scope_name)(*args, **kwargs)

                return call_scope

            setattr(cls, public_name, scope_method(public_name))

    def _set_kwargs(self, kwargs: dict) -> set[str]:
        meta = self._meta
        passed_fields = {*kwargs.keys()} | meta.fetch_fields
        casts = getattr(type(self), "_casts", {})

        for key, value in kwargs.items():
            if key in meta.fk_fields or key in meta.o2o_fields:
                if value and not value._saved_in_db:
                    raise OperationalError(
                        f"You should first call .save() on {value} before referring to it"
                    )
                setattr(self, key, value)
                passed_fields.add(meta.fields_map[key].source_field)
            elif key in meta.fields_db_projection:
                field_object = meta.fields_map[key]
                if field_object.pk and field_object.generated:
                    self._custom_generated_pk = True
                if value is None and not field_object.null:
                    raise ValueError(f"{key} is non nullable field, but null was passed")
                if key not in casts:
                    value = field_object.to_python_value(value)
                setattr(self, key, value)
            elif key in meta.backward_fk_fields:
                raise ConfigurationError(
                    "You can't set backward relations through init, change related model instead"
                )
            elif key in meta.backward_o2o_fields:
                raise ConfigurationError(
                    "You can't set backward one to one relations through init,"
                    " change related model instead"
                )
            elif key in meta.m2m_fields:
                raise ConfigurationError(
                    "You can't set m2m relations through init, use m2m_manager instead"
                )

        return passed_fields

    @classmethod
    def _init_from_db(cls: Type[T], **kwargs: Any) -> T:
        self = cls.__new__(cls)
        object.__setattr__(self, "_partial", False)
        object.__setattr__(self, "_saved_in_db", True)
        object.__setattr__(
            self,
            "_custom_generated_pk",
            self._meta.db_pk_column not in self._meta.generated_db_fields,
        )
        object.__setattr__(self, "_await_when_save", {})
        object.__setattr__(self, "_record_loading", True)

        meta = self._meta
        inited_keys: set[str] = set()
        try:
            for key, model_field, field in meta.db_native_fields:
                object.__setattr__(self, model_field, kwargs[key])
                inited_keys.add(key)
            for key, model_field, field in meta.db_default_fields:
                value = kwargs[key]
                if value is not None:
                    value = field.field_type(value)
                object.__setattr__(self, model_field, value)
                inited_keys.add(key)
            for key, model_field, field in meta.db_complex_fields:
                object.__setattr__(self, model_field, field.to_python_value(kwargs[key]))
                inited_keys.add(key)
        except KeyError:
            object.__setattr__(self, "_partial", True)
            native_fields = [f for *_, f in meta.db_native_fields]
            default_fields = complex_fields = None
            for key, value in kwargs.items():
                if key in inited_keys or key not in meta.fields_map:
                    continue
                field = meta.fields_map[key]
                if field not in native_fields:
                    if default_fields is None:
                        default_fields = [f for *_, f in meta.db_default_fields]
                    if field in default_fields:
                        if value is not None:
                            value = field.field_type(value)
                    else:
                        if complex_fields is None:
                            complex_fields = [f for *_, f in meta.db_complex_fields]
                        if field in complex_fields:
                            value = field.to_python_value(value)
                object.__setattr__(self, key, value)

        object.__setattr__(self, "_record_loading", False)
        return self

    def __setattr__(self, key, value) -> None:
        if not key.startswith("_") and not getattr(self, "_record_loading", False):
            mutator = getattr(type(self), f"set_{key}_attribute", None)
            if mutator is not None:
                value = mutator(self, value)
        super().__setattr__(key, value)

    def __getattribute__(self, key: str):
        value = super().__getattribute__(key)
        if key.startswith("_"):
            return value
        if getattr(self, "_record_encoding", False):
            return value
        try:
            meta = super().__getattribute__("_meta")
        except AttributeError:
            return value
        if key not in meta.fields:
            return value
        raw_value = value
        if key in getattr(type(self), "_casts", {}):
            raw_value = HasCasts.cast_get(self, key, raw_value)
        accessor = getattr(type(self), f"get_{key}_attribute", None)
        if accessor is not None:
            return accessor(self, raw_value)
        return raw_value

    @contextmanager
    def _encoded_cast_values(self):
        casts = getattr(type(self), "_casts", {})
        if not casts:
            yield
            return
        originals: Dict[str, Any] = {}
        object.__setattr__(self, "_record_encoding", True)
        for field_name in casts:
            if field_name not in self._meta.fields:
                continue
            try:
                raw_value = object.__getattribute__(self, field_name)
            except AttributeError:
                continue
            encoded = HasCasts.cast_set(self, field_name, raw_value)
            originals[field_name] = raw_value
            object.__setattr__(self, field_name, encoded)
        try:
            yield
        finally:
            for field_name, value in originals.items():
                object.__setattr__(self, field_name, value)
            object.__setattr__(self, "_record_encoding", False)

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

    async def save(self, *args, **kwargs) -> None:
        with self._encoded_cast_values():
            return await super().save(*args, **kwargs)

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
        items: Annotated[Iterable[Dict[str, Any] | T], Doc("Field dicts or instances.")],
        batch_size: Annotated[int, Doc("Insert this many per query.")] = 100,
        *,
        ignore_conflicts: bool = False,
        update_fields: Optional[Iterable[str]] = None,
        on_conflict: Optional[Iterable[str]] = None,
        using_db=None,
    ) -> List[T]:
        """Insert multiple rows efficiently."""
        instances = [item if isinstance(item, cls) else cls(**item) for item in items]
        for i in range(0, len(instances), batch_size):
            batch = instances[i : i + batch_size]
            with cls._encoded_instances(batch):
                await super().bulk_create(
                    batch,
                    batch_size=batch_size,
                    ignore_conflicts=ignore_conflicts,
                    update_fields=update_fields,
                    on_conflict=on_conflict,
                    using_db=using_db,
                )
        return instances

    @classmethod
    @contextmanager
    def _encoded_instances(cls, instances: Iterable[T]):
        contexts = [instance._encoded_cast_values() for instance in instances]
        for ctx in contexts:
            ctx.__enter__()
        try:
            yield
        finally:
            for ctx in reversed(contexts):
                ctx.__exit__(None, None, None)

    @classmethod
    async def bulk_upsert(
        cls: Type[T],
        items: Iterable[Dict[str, Any] | T],
        *,
        conflict_fields: Iterable[str],
        update_fields: Optional[Iterable[str]] = None,
        batch_size: int = 100,
        using_db=None,
    ) -> List[T]:
        """Insert rows or update them using database-native conflict handling."""
        instances = [item if isinstance(item, cls) else cls(**item) for item in items]
        conflict_fields = tuple(conflict_fields)
        if update_fields is None:
            update_fields = tuple(
                field
                for field in cls._meta.fields
                if field not in conflict_fields and field != cls._meta.pk_attr
            )
        await cls.bulk_create(
            instances,
            batch_size=batch_size,
            update_fields=tuple(update_fields),
            on_conflict=conflict_fields,
            using_db=using_db,
        )
        return instances

    @classmethod
    async def upsert(
        cls: Type[T],
        values: Optional[Dict[str, Any]] = None,
        *,
        conflict_fields: Iterable[str],
        update_fields: Optional[Iterable[str]] = None,
        using_db=None,
        **kwargs,
    ) -> T:
        """Upsert one row using native ``ON CONFLICT``/equivalent support."""
        payload = {**(values or {}), **kwargs}
        conflict_fields = tuple(conflict_fields)
        await cls.bulk_upsert(
            [payload],
            conflict_fields=conflict_fields,
            update_fields=update_fields,
            using_db=using_db,
        )
        lookup = {field: payload[field] for field in conflict_fields}
        return await cls.without_global_scopes().get(**lookup)

    @classmethod
    async def count_active(cls) -> int:
        """Count non-deleted rows."""
        return await cls.active().count()
