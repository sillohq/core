"""
sillo.record.pagination — Tortoise data handlers for sillo's pagination system.

Bridges ``sillo.pagination`` strategies to Tortoise querysets.  No duplicate
pagination logic — just the data-handler layer that connects pagination
strategies to Tortoise's ``.count()``, ``.offset()``, and ``.limit()`` API.
"""

from __future__ import annotations

from typing import Annotated, Any

from typing_extensions import Doc

from sillo.pagination import AsyncDataHandler, SyncDataHandler


class TortoiseDataHandler(AsyncDataHandler):
    """Async data handler wrapping a Tortoise queryset.

    Works with ``sillo.pagination.PageNumberPagination``,
    ``sillo.pagination.LimitOffsetPagination``, and
    ``sillo.pagination.CursorPagination``.
    """

    def __init__(self, queryset: Annotated[Any, Doc("Tortoise queryset.")]):
        """Init"""
        self._qs = queryset

    async def get_total_items(self) -> int:
        """Get Total Items"""
        return await self._qs.count()

    async def get_items(self, offset: int, limit: int) -> list[Any]:
        """Get Items"""
        return await self._qs.offset(offset).limit(limit).all()


class SyncTortoiseDataHandler(SyncDataHandler):
    """Synchronous data handler (rare — for SyncPaginator compat)."""

    def __init__(self, data: list[Any]):
        """Init"""
        self._data = data

    def get_total_items(self) -> int:
        """Get Total Items"""
        return len(self._data)

    def get_items(self, offset: int, limit: int) -> list[Any]:
        """Get Items"""
        return self._data[offset : offset + limit]
