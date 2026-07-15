"""
sillo.record.pagination — Tortoise data handlers for sillo's pagination system.

Bridges ``sillo.pagination`` strategies to Tortoise querysets.  No duplicate
pagination logic — just the data-handler layer that connects pagination
strategies to Tortoise's ``.count()``, ``.offset()``, and ``.limit()`` API.
"""

from __future__ import annotations

from typing import Annotated, Any, List

from sillo.pagination import AsyncDataHandler, SyncDataHandler
from typing_extensions import Doc


class TortoiseDataHandler(AsyncDataHandler):
    """Async data handler wrapping a Tortoise queryset.

    Works with ``sillo.pagination.PageNumberPagination``,
    ``sillo.pagination.LimitOffsetPagination``, and
    ``sillo.pagination.CursorPagination``.
    """

    def __init__(self, queryset: Annotated[Any, Doc("Tortoise queryset.")]):
        self._qs = queryset

    async def get_total_items(self) -> int:
        return await self._qs.count()

    async def get_items(self, offset: int, limit: int) -> List[Any]:
        return await self._qs.offset(offset).limit(limit).all()


class SyncTortoiseDataHandler(SyncDataHandler):
    """Synchronous data handler (rare — for SyncPaginator compat)."""

    def __init__(self, data: List[Any]):
        self._data = data

    def get_total_items(self) -> int: return len(self._data)

    def get_items(self, offset: int, limit: int) -> List[Any]:
        return self._data[offset : offset + limit]
