"""
sillo.record.collection — Query result collection with chainable methods.

A ``Collection`` wraps a list of model instances and provides functional
methods: ``map``, ``filter``, ``pluck``, ``group_by``, ``key_by``,
``sort_by``, ``chunk``, ``sum``, ``avg``, ``min``, ``max``, ``count``,
``first``, ``last``, ``to_dict``, ``to_json``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any, TypeVar

T = TypeVar("T")


class Collection:
    """Immutable-like chainable collection of model instances.

    Every method returns a **new** Collection — the original is never mutated.

    Usage::

        users = await User.active().all()
        collection = Collection(users)
        emails = collection.pluck("email")
        active_vip = collection.filter(lambda u: u.plan == "vip")
        by_role = collection.group_by("role")
        total = collection.sum("balance")
    """

    def __init__(self, items: list[Any] | None = None):
        """Init"""
        self._items: list[Any] = items or []

    def map(self, callback: Callable[[Any], Any]) -> Collection:
        """Map"""
        return Collection([callback(item) for item in self._items])

    def filter(self, callback: Callable[[Any], bool]) -> Collection:
        """Filter"""
        return Collection([item for item in self._items if callback(item)])

    def reject(self, callback: Callable[[Any], bool]) -> Collection:
        """Reject"""
        return Collection([item for item in self._items if not callback(item)])

    def pluck(self, key: str) -> Collection:
        """Pluck"""
        return Collection([getattr(item, key, None) for item in self._items])

    def group_by(self, key: str) -> dict[Any, Collection]:
        """Group By"""
        result: dict[Any, list] = {}
        for item in self._items:
            val = getattr(item, key, None)
            result.setdefault(val, []).append(item)
        return {k: Collection(v) for k, v in result.items()}

    def key_by(self, key: str) -> dict[Any, Any]:
        """Key By"""
        result: dict[Any, Any] = {}
        for item in self._items:
            result[getattr(item, key, None)] = item
        return result

    def sort_by(self, key: str, *, descending: bool = False) -> Collection:
        """Sort By"""
        return Collection(
            sorted(
                self._items,
                key=lambda x: getattr(x, key, None) or 0,
                reverse=descending,
            )
        )

    def chunk(self, size: int) -> Iterator[Collection]:
        """Chunk"""
        for i in range(0, len(self._items), size):
            yield Collection(self._items[i : i + size])

    def first(self, default=None) -> Any:
        """First"""
        return self._items[0] if self._items else default

    def last(self, default=None) -> Any:
        """Last"""
        return self._items[-1] if self._items else default

    def take(self, count: int) -> Collection:
        """Take"""
        return Collection(self._items[:count])

    def skip(self, count: int) -> Collection:
        """Skip"""
        return Collection(self._items[count:])

    def sum(self, key: str | None = None) -> float:
        """Sum"""
        if key:
            return sum(getattr(item, key, 0) or 0 for item in self._items)
        return sum(self._items)

    def avg(self, key: str | None = None) -> float:
        """Avg"""
        values = (
            [getattr(item, key, 0) or 0 for item in self._items] if key else self._items
        )
        return sum(values) / len(values) if values else 0.0

    def min(self, key: str | None = None):
        """Min"""
        if key:
            return min(getattr(item, key, float("inf")) for item in self._items)
        return min(self._items)

    def max(self, key: str | None = None):
        """Max"""
        if key:
            return max(getattr(item, key, float("-inf")) for item in self._items)
        return max(self._items)

    def count(self) -> int:
        """Count"""
        return len(self._items)

    def is_empty(self) -> bool:
        """Is Empty"""
        return len(self._items) == 0

    def is_not_empty(self) -> bool:
        """Is Not Empty"""
        return not self.is_empty()

    def contains(self, callback: Callable[[Any], bool]) -> bool:
        """Contains"""
        return any(callback(item) for item in self._items)

    def unique(self, key: str | None = None) -> Collection:
        """Unique"""
        if key:
            seen = set()
            result = []
            for item in self._items:
                val = getattr(item, key, None)
                if val not in seen:
                    seen.add(val)
                    result.append(item)
            return Collection(result)
        return Collection(list(set(self._items)))

    def to_list(self) -> list[Any]:
        """To List"""
        return list(self._items)

    def to_dict(self) -> list[Any]:
        """To Dict"""
        return [
            item.to_dict() if hasattr(item, "to_dict") else str(item)
            for item in self._items
        ]

    def to_json(self, indent: int | None = None) -> str:
        """To Json"""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def __iter__(self):
        """Iter"""
        return iter(self._items)

    def __len__(self):
        """Len"""
        return len(self._items)

    def __getitem__(self, index):
        """Getitem"""
        return self._items[index]

    def __repr__(self):
        """Repr"""
        return f"Collection({len(self._items)} items)"
