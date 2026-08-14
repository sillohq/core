---
title: Pagination
description: "Paginating model queries — the Record helper, the framework's pagination strategies over a Tortoise queryset, and choosing between page numbers, limit/offset and cursors."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Pagination
  - tag: meta
    attrs:
      property: og:description
      content: PaginatedResult, TortoiseDataHandler, and the three pagination strategies.
---

Two layers, for two different jobs.

| | Use it for |
| --- | --- |
| [`paginate()`](#the-record-helper) | A page of rows inside your own code |
| [The pagination system](#the-framework-system) | An HTTP endpoint: query parameters, envelope, links |

## The Record helper

```python
from sillo.record.queries import paginate

result = await paginate(
    Post.filter(status="published"),
    page=2,
    page_size=20,
    ordering="-created_at",
)
```

```python
result.items       # the rows
result.total       # matching rows in total
result.page        # 2
result.page_size   # 20
result.pages       # total pages
result.has_next    # bool
result.has_prev    # bool
result.to_dict()   # all of the above, serialisable
```

Two queries: a `COUNT`, and the page itself.

## The framework system

For an endpoint, the [pagination system](/guides/pagination/) handles the parts
`paginate()` does not — reading and validating the query parameters, capping
the page size, and building a consistent response envelope.

Record supplies the adapter that lets it read a Tortoise queryset:

```python
from sillo.pagination import PageNumberPagination
from sillo.record.pagination import TortoiseDataHandler


@app.get("/posts")
async def list_posts(request, response):
    handler = TortoiseDataHandler(Post.filter(status="published").order_by("-id"))
    paginator = PageNumberPagination(handler, page_size=20)
    page = await paginator.paginate(request)
    return response.json(page)
```

`TortoiseDataHandler` implements two methods — `get_total_items()` and
`get_items(offset, limit)` — which is the whole contract. The strategy above it
decides what the parameters mean.

`SyncTortoiseDataHandler` exists for the synchronous paginator and takes a list
you already have. You will not normally want it.

## The three strategies

### Page number

```
/posts?page=3&page_size=20
```

What people expect, and what a numbered pager needs. Requires the `COUNT`,
which on a large table is the expensive part of the request.

### Limit / offset

```
/posts?limit=20&offset=40
```

The same mechanics, phrased for an API client. Both share the deep-page
problem: `OFFSET 100000` makes the database walk and discard a hundred thousand
rows.

### Cursor

```
/posts?cursor=eyJpZCI6MTIzfQ&limit=20
```

Carries the position of the last row rather than a count of rows to skip, so
the query becomes `WHERE id < :last` — an index seek, at the same cost on page
one and page ten thousand. No `COUNT` at all.

The trade is that you cannot jump to page 47, and there is no total. For an
infinite scroll, a feed, or an export, that is not a loss.

**Use a cursor** for anything unbounded or hot. **Use page numbers** when a
human needs to see "page 3 of 12" and the table is small enough for the
`COUNT`.

## Ordering is not optional

```python
Post.filter(status="published").order_by("-created_at", "id")
```

`LIMIT`/`OFFSET` over an unordered query has no defined row order. In practice
that means a row can appear on two consecutive pages while nothing changes, and
another can be skipped entirely.

Order by something that breaks ties. `-created_at` alone does not if two rows
can share a timestamp — append the primary key.

For cursor pagination this is stronger still: the ordering **is** the cursor.
It must be stable and unique, or the cursor cannot express a position.

## Counting is the expensive half

`total` costs a `COUNT(*)` over the filtered set. PostgreSQL cannot answer that
from an index alone, so on a large table it is a scan — often more expensive
than fetching the page.

Options, in order of preference:

1. **Drop the total.** Cursor pagination, or a "next" link with no count.
2. **Approximate it.** `reltuples` on PostgreSQL is free and close enough for
   "about 40,000 results".
3. **Cache it.** A count that is a minute stale is usually fine.

## In the admin

The [admin panel](/orm/admin-customising/) paginates its own lists;
`list_per_page` on the `ModelAdmin` sets the size, defaulting to 25.

## See also

- [Pagination](/guides/pagination/) — the strategies, parameters and envelope
  in full.
- [Queries](/orm/queries/#iter_all) — `iter_all`, for walking everything rather
  than showing a page.
