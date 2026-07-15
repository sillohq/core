"""
sillo.record.fields — Custom Tortoise field types.

- CreatedAtField / UpdatedAtField / SoftDeleteField
- SlugField — auto-generated URL-safe slug
- ULIDField — sortable primary key
"""

from __future__ import annotations

from typing import Optional

from tortoise import fields as _fields


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
    """Nullable datetime for soft-deletion. None = active."""

    def __init__(self, **kwargs):
        kwargs.setdefault("null", True)
        kwargs.setdefault("default", None)
        super().__init__(**kwargs)


class SlugField(_fields.CharField):
    """URL-safe slug, optionally auto-generated from a source field."""

    def __init__(
        self, max_length: int = 200, source_field: Optional[str] = None, **kwargs
    ):
        kwargs.setdefault("max_length", max_length)
        super().__init__(**kwargs)
        self._source_field = source_field


class ULIDField(_fields.CharField):
    """ULID primary key (26-char sortable identifier)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 26)
        kwargs.setdefault("pk", True)
        super().__init__(**kwargs)
