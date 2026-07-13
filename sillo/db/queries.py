"""
sillo.db.queries — Enhanced query interface.

Thin wrappers around Tortoise QuerySet that provide sillo-idiomatic
patterns: pagination, async iteration, explain plans, and bulk operations.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, List, Optional, Type, TypeVar

T = TypeVar("T")


class PaginatedResult:
    """Holds a page of results plus pagination metadata."""

    def __init__(self, items: List[Any], total: int, page: int, page_size: int):
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size

    @property
    def pages(self) -> int:
        return (
            max(1, (self.total + self.page_size - 1) // self.page_size)
            if self.total
            else 1
        )

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def to_dict(self) -> dict:
        return {
            "items": [
                item.to_dict() if hasattr(item, "to_dict") else str(item)
                for item in self.items
            ],
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "pages": self.pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


async def paginate(
    queryset,
    page: int = 1,
    page_size: int = 20,
    *,
    ordering: Optional[str] = None,
) -> PaginatedResult:
    """Paginate any Tortoise queryset.

    Args:
        queryset: A Tortoise QuerySet (after ``.filter()`` or ``.all()``).
        page: 1-based page number.
        page_size: Items per page.
        ordering: Optional field name with ``-`` prefix for descending.

    Returns:
        :class:`PaginatedResult` with items and metadata.
    """
    if ordering:
        queryset = queryset.order_by(ordering)

    total = await queryset.count()
    offset = (page - 1) * page_size
    items = await queryset.offset(offset).limit(page_size)

    return PaginatedResult(items=items, total=total, page=page, page_size=page_size)


async def exists(queryset) -> bool:
    """Check if a queryset returns any results."""
    return await queryset.exists()


async def explain(queryset) -> str:
    """Return the SQL EXPLAIN plan for a queryset."""
    try:
        sql, params = queryset.sql()
        from tortoise import connections

        conn = connections.get("default")
        if hasattr(conn, "execute_query"):
            result = await conn.execute_query(f"EXPLAIN {sql}", params)
            return str(result)
        return str(sql)
    except Exception as e:
        return f"EXPLAIN unavailable: {e}"


async def iter_all(queryset, batch_size: int = 500) -> AsyncIterator[Any]:
    """Iterate over all results in batches (memory-efficient for large datasets).

    Usage::

        async for user in iter_all(User.filter(is_active=True)):
            await process(user)
    """
    offset = 0
    while True:
        batch = await queryset.offset(offset).limit(batch_size)
        if not batch:
            break
        for item in batch:
            yield item
        offset += batch_size
        if len(batch) < batch_size:
            break


async def find_by_ids(queryset, ids: List[Any]) -> List[Any]:
    """Fetch multiple rows by primary key efficiently."""
    pk_field = queryset.model._meta.pk_attr
    return await queryset.filter(**{f"{pk_field}__in": ids})


async def count_by(queryset, field: str) -> dict:
    """Group by *field* and return count per value.

    Returns:
        Dict mapping field values to counts.
    """
    results = {}
    async for row in queryset.all():
        val = getattr(row, field, None)
        results[str(val)] = results.get(str(val), 0) + 1
    return results
