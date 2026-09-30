"""sillo.record.serialization — turn a model instance into a plain dict.

``Model.to_dict`` and ``SerializesToDictMixin.to_dict`` share this one walk, so
what a model serializes to cannot drift between them.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any


def model_to_dict(
    instance: Any,
    *,
    exclude: Sequence[str] | None = None,
    include: Sequence[str] | None = None,
    relations: bool | Sequence[str] = False,
    max_depth: int = 3,
) -> dict[str, Any]:
    """Serialize *instance* to a dict.

    ``datetime`` values become ISO 8601 strings. A value that has its own
    ``to_dict`` is expanded while ``max_depth`` allows, receiving one less.

    Relations (foreign keys, one-to-one, reverse and many-to-many) are left
    out by default. On an instance that has not fetched them they are lazy
    query handles that no encoder can serialize, and a foreign key's
    ``<name>_id`` column is already in the result.

    Pass ``relations=True``, or the names of relations, to include them. Only
    relations that were already fetched (``fetch_related`` /
    ``prefetch_related``) are included: serializing never queries, and a
    relation that was not fetched is skipped rather than guessed at. ``True``
    carries on into the related models, bounded by ``max_depth``; names apply
    to this model only.
    """
    relation_fields = instance._meta.fetch_fields
    wanted: set[str] = set()
    if relations is True:
        wanted = set(relation_fields)
    elif relations:
        wanted = set(relations)
        unknown = wanted - relation_fields
        if unknown:
            raise ValueError(
                f"{type(instance).__name__} has no relation named "
                + ", ".join(repr(name) for name in sorted(unknown))
            )
    follow = relations if relations is True else False

    data: dict[str, Any] = {}
    for field_name in instance._meta.fields:
        if field_name in relation_fields:
            if field_name in wanted and max_depth > 0:
                found, value = _fetched(
                    getattr(instance, field_name, None), follow, max_depth - 1
                )
                if found and _wanted(field_name, exclude, include):
                    data[field_name] = value
            continue
        if not _wanted(field_name, exclude, include):
            continue
        value = getattr(instance, field_name, None)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif max_depth > 0 and hasattr(value, "to_dict"):
            value = value.to_dict(max_depth=max_depth - 1)
        data[field_name] = value
    return data


def _wanted(
    name: str, exclude: Sequence[str] | None, include: Sequence[str] | None
) -> bool:
    if exclude and name in exclude:
        return False
    return not (include and name not in include)


def _fetched(value: Any, follow: bool, max_depth: int) -> tuple[bool, Any]:
    """``(True, serialized)`` for a relation that was fetched, else ``(False, None)``."""
    if value is None:
        return True, None
    if hasattr(value, "to_dict"):
        return True, value.to_dict(relations=follow, max_depth=max_depth)
    # Reverse and many-to-many relations keep what they loaded once fetched.
    if getattr(value, "_fetched", False):
        return True, [
            item.to_dict(relations=follow, max_depth=max_depth) for item in value
        ]
    return False, None
