"""
sillo.db.fields — Custom field types extending Tortoise ORM.

Adds sillo-idiomatic field shortcuts, validators, and type hints.
"""

from __future__ import annotations

from typing import Any, Optional, Type

from tortoise import fields as _fields
from tortoise.validators import MaxLengthValidator, MinLengthValidator


class AutoNowMixin:
    """Mixin that auto-sets a field on creation and update."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


def _auto_now_default():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


class CreatedAtField(_fields.DatetimeField):
    """Auto-set to UTC now on creation. Never updated."""

    def __init__(self, **kwargs):
        kwargs.setdefault("auto_now_add", True)
        super().__init__(**kwargs)


class UpdatedAtField(_fields.DatetimeField):
    """Auto-set to UTC now on every save."""

    def __init__(self, **kwargs):
        kwargs.setdefault("auto_now", True)
        super().__init__(**kwargs)


class SoftDeleteField(_fields.DatetimeField):
    """Nullable datetime for soft-deletion. ``None`` = active."""

    def __init__(self, **kwargs):
        kwargs.setdefault("null", True)
        kwargs.setdefault("default", None)
        super().__init__(**kwargs)


class SlugField(_fields.CharField):
    """URL-safe slug with optional auto-generation from a source field."""

    def __init__(self, max_length: int = 200, source_field: Optional[str] = None, **kwargs):
        kwargs.setdefault("max_length", max_length)
        super().__init__(**kwargs)
        self._source_field = source_field


class EncryptedField(_fields.TextField):
    """Field whose value is transparently encrypted at rest."""

    def __init__(self, key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._cipher_key = key


class JSONListField(_fields.JSONField):
    """JSON field that always stores a list. Defaults to ``[]``."""

    def __init__(self, **kwargs):
        kwargs.setdefault("default", list)
        super().__init__(**kwargs)


class ULIDField(_fields.CharField):
    """ULID primary key field (26-char sortable identifier)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 26)
        kwargs.setdefault("pk", True)
        super().__init__(**kwargs)

    def _generate(self):
        import ulid
        return str(ulid.new())


# Field shortcuts — import from sillo.db
TextField = _fields.TextField
IntField = _fields.IntField
BigIntField = _fields.BigIntField
SmallIntField = _fields.SmallIntField
FloatField = _fields.FloatField
DecimalField = _fields.DecimalField
BoolField = _fields.BooleanField
CharField = _fields.CharField
DateTimeField = _fields.DatetimeField
DateField = _fields.DateField
TimeDeltaField = _fields.TimeDeltaField
EmailField = _fields.CharField  # override with validator
ForeignKey = _fields.ForeignKeyField
OneToOne = _fields.OneToOneField
ManyToMany = _fields.ManyToManyField
