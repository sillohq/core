"""
sillo.record.queries — Query helpers.

Provides pagination, async iteration over large datasets, explain plans,
bulk find-by-ids, and field-level count aggregation.
"""

from __future__ import annotations

from typing import Annotated, Any, AsyncIterator, List, Optional, Type, TypeVar

from typing_extensions import Doc

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
        return max(1, (self.total + self.page_size - 1) // self.page_size)

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
    page: Annotated[int, Doc("1-based page number.")] = 1,
    page_size: Annotated[int, Doc("Items per page.")] = 20,
    *,
    ordering: Annotated[
        Optional[str], Doc("Field name with optional '-' prefix for descending.")
    ] = None,
) -> PaginatedResult:
    """Paginate any Tortoise queryset."""
    if ordering:
        queryset = queryset.order_by(ordering)
    total = await queryset.count()
    offset = (page - 1) * page_size
    items = await queryset.offset(offset).limit(page_size).all()
    return PaginatedResult(items=items, total=total, page=page, page_size=page_size)


async def iter_all(
    queryset,
    batch_size: Annotated[int, Doc("Fetch this many rows per query.")] = 500,
) -> AsyncIterator[Any]:
    """Memory-efficient iteration over all results."""
    offset = 0
    while True:
        batch = await queryset.offset(offset).limit(batch_size).all()
        if not batch:
            break
        for item in batch:
            yield item
        offset += batch_size


async def explain(queryset) -> str:
    """Return the SQL EXPLAIN plan for a queryset."""
    try:
        sql, params = queryset.sql()
        from tortoise import connections

        conn = connections.get("default")
        result = await conn.execute_query(f"EXPLAIN {sql}", params)
        return str(result)
    except Exception as e:
        return f"EXPLAIN unavailable: {e}"


async def find_by_ids(queryset, ids: List[Any]) -> List[Any]:
    """Fetch multiple rows by primary key."""
    pk = queryset.model._meta.pk_attr
    return await queryset.filter(**{f"{pk}__in": ids}).all()


async def count_by(queryset, field: str) -> dict:
    """Group by field and return counts."""
    results = {}
    async for row in queryset.all():
        val = getattr(row, field, None)
        results[str(val)] = results.get(str(val), 0) + 1
    return results
