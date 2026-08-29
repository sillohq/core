---
title: Queries
description: "The query helpers around a Tortoise queryset (paginate, iter_all, explain, find_by_ids and count_by) and where plain Tortoise is the answer."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Queries
  - tag: meta
    attrs:
      property: og:description
      content: paginate, iter_all, explain, find_by_ids and count_by.
---

The querying surface itself (`filter`, `order_by`, `limit`, `annotate`,
`values`, `Q`, `select_related`) is documented across [The QuerySet
API](/v0.x/orm/queryset/), [Lookups](/v0.x/orm/lookups/), [Filtering](/v0.x/orm/filtering/),
[Aggregation](/v0.x/orm/aggregation/), [Eager loading](/v0.x/orm/eager-loading/) and
[Values](/v0.x/orm/values/).

```python
posts = await Post.filter(status="published").order_by("-created_at").limit(10)
count = await Post.filter(author_id=7).count()
exists = await Post.filter(slug="hello").exists()
```

This page covers the five helpers `sillo.record.queries` adds on top, for the
things that come up repeatedly and are awkward to write each time.

```python
from sillo.record.queries import (
    paginate, iter_all, explain, find_by_ids, count_by,
)
```

## `paginate`

```python
result = await paginate(Post.filter(status="published"), page=2, page_size=20)

result.items         # the rows
result.total         # total matching rows
result.page          # 2
result.page_size     # 20
result.pages         # total pages
result.has_next      # bool
result.has_prev      # bool
result.to_dict()
```

One `COUNT` and one page query. `ordering` applies an order without building it
into the queryset first:

```python
await paginate(Post.all(), page=1, ordering="-created_at")
```

A leading `-` is descending, as everywhere else.

:::caution[Order the query, or the pages are not stable]
An unordered `LIMIT/OFFSET` has no defined row order. Two requests for page 1
can legitimately return different rows, and a row can appear on both page 1 and
page 2 while nothing changes.

Always order by something unique, or unique enough. `-created_at` alone is not
if two rows can share a timestamp. `["-created_at", "id"]` is.
:::

For an HTTP endpoint, the [pagination system](/v0.x/orm/pagination/) is usually the
better entry point: it handles the query parameters and the response envelope
as well.

## `iter_all`

```python
async for post in iter_all(Post.all(), batch_size=500):
    await reindex(post)
```

Walks a whole table in batches, holding one batch in memory rather than the
table. For a migration script, a backfill, or a report over everything.

The rule is the same as pagination's: **order the queryset**, or batches can
overlap and skip. And a batched walk is not a snapshot, rows inserted while it
runs may or may not be seen. Where that matters, walk by primary key range
rather than offset, or do the whole thing in a
[transaction](/v0.x/orm/transactions/) if your database and your patience allow.

## `explain`

```python
plan = await explain(Post.filter(author_id=7).order_by("-created_at"))
print(plan)
```

The database's own query plan. This is how you find out whether an index is
being used, rather than inferring it from a timing.

The output format is the database's, and differs between SQLite, PostgreSQL and
MySQL. Read the plan for the database you deploy on. A SQLite plan tells you
almost nothing about how PostgreSQL will execute the same query.

Related: [`DB_ECHO`](/v0.x/orm/configuration/#echo) logs every statement, which is
the blunter tool for spotting an N+1.

## `find_by_ids`

```python
posts = await find_by_ids(Post.all(), [3, 7, 11])
```

One query, `WHERE id IN (…)`. The point is that it replaces a loop of `get`
calls. The classic N+1 that looks harmless with three ids and is not with three
hundred.

The result is not ordered to match the ids you passed. Reorder in Python if it
matters:

```python
by_id = {post.id: post for post in posts}
ordered = [by_id[i] for i in ids if i in by_id]
```

## `count_by`

```python
counts = await count_by(Post.all(), "status")
# {"draft": 12, "published": 130, "archived": 4}
```

A `GROUP BY` with counts, as a dict. For a dashboard tile or a facet list.

One query, whatever the number of groups, which is the difference from a
`count()` per value in a loop.

## The rest of the query surface

Covered in full elsewhere in this section, the highlights:

```python
from tortoise.expressions import Q, F
from tortoise.functions import Count, Sum

# OR, and negation
await Post.filter(Q(status="published") | Q(author_id=7))
await Post.filter(~Q(status="archived"))

# atomic increment — no read, no race
await Post.filter(id=4).update(views=F("views") + 1)

# aggregates
await Post.annotate(comment_count=Count("comments")).order_by("-comment_count")

# eager loading
await Post.all().prefetch_related("comments").select_related("author")
```

`select_related` (a join, for forward foreign keys) and `prefetch_related` (a
second query, for reverse and many-to-many) are the two to reach for the moment
a template or serialiser touches a relation inside a loop. See [Eager
loading](/v0.x/orm/eager-loading/).

## Raw SQL

When none of the above can express it, [drop to SQL](/v0.x/orm/raw-sql/):

```python
from tortoise import connections

conn = connections.get("default")
rows = await conn.execute_query_dict(
    "SELECT status, COUNT(*) AS n FROM posts GROUP BY status"
)
```

Always parameterise, and note that the placeholder style is the driver's: `$1`
on PostgreSQL, `%s` on MySQL, `?` on SQLite.

Raw SQL bypasses [global scopes](/v0.x/orm/scopes/), [casts](/v0.x/orm/casting/) and
[events](/v0.x/orm/events/). That is the whole point of it, and the reason to keep
it to the queries the ORM genuinely cannot express.
