"""
sillo.record.pydantic — Bridge between Tortoise models and Pydantic schemas.

Provides helpers to create Pydantic models from Tortoise model fields,
enabling request validation that directly maps to your database models.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from pydantic import BaseModel, Field, create_model
from tortoise import fields as f
from typing_extensions import Doc


def pydantic_model_from_tortoise(
    model_class: type,
    *,
    name: Annotated[str, Doc("Name for the generated Pydantic model.")] = "",
    exclude: Annotated[list[str] | None, Doc("Field names to exclude.")] = None,
    include: Annotated[
        list[str] | None, Doc("If set, ONLY include these fields.")
    ] = None,
    optional_fields: Annotated[
        list[str] | None, Doc("Fields to mark as Optional.")
    ] = None,
) -> type[BaseModel]:
    """Generate a Pydantic model from a Tortoise model's fields.

    Usage::

        UserCreate = pydantic_model_from_tortoise(
            User, name="UserCreate", exclude=["id", "created_at"], optional_fields=["bio"],
        )
        @app.post("/users", request_model=UserCreate)
        async def create_user(request, response):
            user = await User.create(**request.validated_data.model_dump())
    """
    exclude = exclude or []
    include = include or []
    optional_fields = optional_fields or []
    meta = model_class._meta  # ty: ignore[unresolved-attribute]
    fields: dict[str, Any] = {}

    for field_name, field_obj in meta.fields_map.items():
        if exclude and field_name in exclude:
            continue
        if include and field_name not in include:
            continue

        py_type = _tortoise_to_python_type(field_obj)

        # A field the caller may leave out entirely: one they named in
        # *optional_fields*, one the column allows to be null, or the primary
        # key — which the database supplies, so a create schema that demands
        # it is asking the caller to invent a row id.
        #
        # Both the annotation and the default follow from this single answer.
        # They used to be decided separately, and disagreed: `optional_fields`
        # widened the type to Optional but still passed `Field(...)`, so the
        # field stayed required and could only be satisfied by passing None
        # explicitly. The primary key had the opposite failure — it was
        # correctly identified as not required and then given a default of
        # ``...``, which is pydantic's marker for "required".
        optional = (
            field_name in optional_fields or field_obj.null or field_obj.pk
        )

        if optional:
            fields[field_name] = (
                Optional[py_type],  # ty: ignore[invalid-type-form]
                Field(default=None),
            )
        else:
            fields[field_name] = (py_type, Field(...))

    return create_model(
        name or f"{model_class.__name__}Schema", __base__=BaseModel, **fields
    )


def _tortoise_to_python_type(field_obj) -> type:
    """Map a Tortoise ORM field type to the corresponding Python type.

    Looks up the field instance against a hardcoded mapping of common
    Tortoise field classes (IntField, CharField, BooleanField, etc.)
    and returns the Python type used for Pydantic model generation.

    Args:
        field_obj: A Tortoise field instance (e.g. ``fields.IntField()``).

    Returns:
        The corresponding Python type (``int``, ``str``, ``bool``,
        ``float``, ``dict``) or ``str`` as a fallback for unrecognised
        field types.
    """
    mapping = {
        f.IntField: int,
        f.SmallIntField: int,
        f.BigIntField: int,
        f.FloatField: float,
        f.DecimalField: float,
        f.BooleanField: bool,
        f.CharField: str,
        f.TextField: str,
        f.DatetimeField: str,
        f.DateField: str,
        f.TimeDeltaField: float,
        f.JSONField: dict,
    }
    for tf, pt in mapping.items():
        if isinstance(field_obj, tf):
            return pt
    return str
