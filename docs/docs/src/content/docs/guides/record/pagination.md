---
title: Pagination
description: Page-number, limit-offset, and cursor pagination via Tortoise data handlers — integrated with sillo.pagination strategies.
---

# Pagination

`sillo.record.pagination` does NOT implement its own pagination
strategies.  It uses the existing `sillo.pagination` module
(which provides `PageNumberPagination`, `LimitOffsetPagination`,
and `CursorPagination`) and adds a Tortoise-specific data handler
layer.  This keeps pagination logic in one place while letting
Tortoise querysets participate in the same pagination pipeline
as lists and other data sources.

## Architecture

The pagination system has three layers:

1. **Strategy** (`sillo.pagination`) — pure pagination logic: parse
   query params, calculate offsets, generate HATEOAS links.
2. **Data Handler** (`sillo.record.pagination`) — bridge between
   the strategy and a specific data source (Tortoise queryset).
3. **Paginator** (`sillo.pagination`) — ties strategy + handler
   together and produces the paginated result.

This separation means you can paginate ANY data source by writing
a new data handler, without touching the strategy layer.

### TortoiseDataHandler

Implements `AsyncDataHandler`:

```python
from sillo.record.pagination import TortoiseDataHandler

class TortoiseDataHandler(AsyncDataHandler):
    def __init__(self, queryset):
        self._qs = queryset

    async def get_total_items(self) -> int:
        return await self._qs.count()

    async def get_items(self, offset: int, limit: int) -> list:
        return await self._qs.offset(offset).limit(limit).all()
```

Two methods — `count()` and `offset().limit().all()` — are all
Tortoise needs to participate in any pagination strategy.

## Page-Number Pagination

```python
from sillo.pagination import PageNumberPagination, AsyncPaginator
from sillo.record.pagination import TortoiseDataHandler

qs = User.active().order_by("-created_at")
handler = TortoiseDataHandler(qs)
strategy = PageNumberPagination(
    page_param="page",
    page_size_param="page_size",
    default_page=1,
    default_page_size=20,
    max_page_size=100,
)
paginator = AsyncPaginator(
    handler, strategy,
    str(request.url),
    dict(request.query_params),
)

result = await paginator.paginate()
# {
#   "items": [<User>, ...],
#   "pagination": {
#     "total_items": 150,
#     "total_pages": 8,
#     "page": 1,
#     "page_size": 20,
#     "links": {
#       "next": "/users?page=2&page_size=20",
#       "prev": null,
#       "first": "/users?page=1&page_size=20",
#       "last": "/users?page=8&page_size=20"
#     }
#   }
# }
```

## Limit-Offset Pagination

```python
from sillo.pagination import LimitOffsetPagination

strategy = LimitOffsetPagination(
    limit_param="limit",
    offset_param="offset",
    default_limit=20,
    max_limit=100,
)
paginator = AsyncPaginator(handler, strategy, str(request.url), dict(request.query_params))
result = await paginator.paginate()
```

## Cursor Pagination

```python
from sillo.pagination import CursorPagination

strategy = CursorPagination(
    cursor_param="cursor",
    page_size_param="page_size",
    default_page_size=20,
    max_page_size=100,
    sort_field="id",
)
paginator = AsyncPaginator(handler, strategy, str(request.url), dict(request.query_params))
result = await paginator.paginate()
```

## In a Handler

```python
@app.get("/users")
async def list_users(request, response):
    qs = User.active()
    handler = TortoiseDataHandler(qs)
    strategy = PageNumberPagination(default_page_size=20)
    paginator = AsyncPaginator(handler, strategy, str(request.url), dict(request.query_params))
    return response.json(await paginator.paginate())
```

## Override Query Parameters

`paginate(**kwargs)` accepts overrides:

```python
result = await paginator.paginate(page=3, page_size=50)
```

For the full strategy API (LinkBuilder, validation, error types), see
the `sillo.pagination` module documentation.  The `sillo.record.pagination`
module only provides the Tortoise data handler layer.
