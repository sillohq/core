"""
sillo.record.collection — Query result collection with chainable methods.

A ``Collection`` wraps a list of model instances and provides functional
methods: ``map``, ``filter``, ``pluck``, ``group_by``, ``key_by``,
``sort_by``, ``chunk``, ``sum``, ``avg``, ``min``, ``max``, ``count``,
``first``, ``last``, ``to_dict``, ``to_json``.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterator, List, Optional, TypeVar

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

    def __init__(self, items: Optional[List[Any]] = None):
        """Init

        Args:
            items: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._items: List[Any] = items or []

    def map(self, callback: Callable[[Any], Any]) -> "Collection":
        """Map

        Args:
            callback: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return Collection([callback(item) for item in self._items])

    def filter(self, callback: Callable[[Any], bool]) -> "Collection":
        """Filter

        Args:
            callback: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return Collection([item for item in self._items if callback(item)])

    def reject(self, callback: Callable[[Any], bool]) -> "Collection":
        """Reject

        Args:
            callback: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return Collection([item for item in self._items if not callback(item)])

    def pluck(self, key: str) -> "Collection":
        """Pluck

        Args:
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return Collection([getattr(item, key, None) for item in self._items])

    def group_by(self, key: str) -> Dict[Any, "Collection"]:
        """Group By

        Args:
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        result: Dict[Any, List] = {}
        for item in self._items:
            val = getattr(item, key, None)
            result.setdefault(val, []).append(item)
        return {k: Collection(v) for k, v in result.items()}

    def key_by(self, key: str) -> Dict[Any, Any]:
        """Key By

        Args:
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        result: Dict[Any, Any] = {}
        for item in self._items:
            result[getattr(item, key, None)] = item
        return result

    def sort_by(self, key: str, *, descending: bool = False) -> "Collection":
        """Sort By

        Args:
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return Collection(
            sorted(
                self._items,
                key=lambda x: getattr(x, key, None) or 0,
                reverse=descending,
            )
        )

    def chunk(self, size: int) -> Iterator["Collection"]:
        """Chunk

        Args:
            size: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        for i in range(0, len(self._items), size):
            yield Collection(self._items[i : i + size])

    def first(self, default=None) -> Any:
        """First

        Args:
            default: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return self._items[0] if self._items else default

    def last(self, default=None) -> Any:
        """Last

        Args:
            default: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return self._items[-1] if self._items else default

    def take(self, count: int) -> "Collection":
        """Take

        Args:
            count: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return Collection(self._items[:count])

    def skip(self, count: int) -> "Collection":
        """Skip

        Args:
            count: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return Collection(self._items[count:])

    def sum(self, key: Optional[str] = None) -> float:
        """Sum

        Args:
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if key:
            return sum(getattr(item, key, 0) or 0 for item in self._items)
        return sum(self._items)

    def avg(self, key: Optional[str] = None) -> float:
        """Avg

        Args:
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        values = (
            [getattr(item, key, 0) or 0 for item in self._items] if key else self._items
        )
        return sum(values) / len(values) if values else 0.0

    def min(self, key: Optional[str] = None):
        """Min

        Args:
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if key:
            return min(getattr(item, key, float("inf")) for item in self._items)
        return min(self._items)

    def max(self, key: Optional[str] = None):
        """Max

        Args:
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if key:
            return max(getattr(item, key, float("-inf")) for item in self._items)
        return max(self._items)

    def count(self) -> int:
        """Count

        Returns:
            [description]

        Raises:
            [description]
        """
        return len(self._items)

    def is_empty(self) -> bool:
        """Is Empty

        Returns:
            [description]

        Raises:
            [description]
        """
        return len(self._items) == 0

    def is_not_empty(self) -> bool:
        """Is Not Empty

        Returns:
            [description]

        Raises:
            [description]
        """
        return not self.is_empty()

    def contains(self, callback: Callable[[Any], bool]) -> bool:
        """Contains

        Args:
            callback: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return any(callback(item) for item in self._items)

    def unique(self, key: Optional[str] = None) -> "Collection":
        """Unique

        Args:
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
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

    def to_list(self) -> List[Any]:
        """To List

        Returns:
            [description]

        Raises:
            [description]
        """
        return list(self._items)

    def to_dict(self) -> List[Dict[str, Any]]:
        """To Dict

        Returns:
            [description]

        Raises:
            [description]
        """
        return [
            item.to_dict() if hasattr(item, "to_dict") else str(item)
            for item in self._items
        ]

    def to_json(self, indent: Optional[int] = None) -> str:
        """To Json

        Args:
            indent: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def __iter__(self):
        """Iter

        Returns:
            [description]

        Raises:
            [description]
        """
        return iter(self._items)

    def __len__(self):
        """Len

        Returns:
            [description]

        Raises:
            [description]
        """
        return len(self._items)

    def __getitem__(self, index):
        """Getitem

        Args:
            index: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return self._items[index]

    def __repr__(self):
        """Repr

        Returns:
            [description]

        Raises:
            [description]
        """
        return f"Collection({len(self._items)} items)"
