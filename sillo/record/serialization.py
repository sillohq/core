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
    max_depth: int = 3,
) -> dict[str, Any]:
    """Serialize *instance* to a dict.

    ``datetime`` values become ISO 8601 strings. A value that has its own
    ``to_dict`` is expanded while ``max_depth`` allows, receiving one less.
    """
    data: dict[str, Any] = {}
    for field_name in instance._meta.fields:
        if exclude and field_name in exclude:
            continue
        if include and field_name not in include:
            continue
        value = getattr(instance, field_name, None)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif max_depth > 0 and hasattr(value, "to_dict"):
            value = value.to_dict(max_depth=max_depth - 1)
        data[field_name] = value
    return data
