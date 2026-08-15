---
title: Aggregation
description: "Counting, summing and averaging in the database — annotate and the aggregate functions, grouping, filtering on an aggregate, and the join-inflation trap."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Aggregation
  - tag: meta
    attrs:
      property: og:description
      content: annotate, Count, Sum, Avg, Min, Max, grouping and HAVING.
---

```python
from tortoise.functions import Count, Sum, Avg, Min, Max
```

## `annotate`

Adds a computed column to each row:

```python
authors = await Author.annotate(post_count=Count("posts"))

for author in authors:
    print(author.name, author.post_count)
```

The name you choose becomes an attribute on the instance, and can be used in
`order_by` and `filter`:

```python
await Author.annotate(post_count=Count("posts")).order_by("-post_count").limit(10)
```

That is one query. The Python equivalent — loading every author, fetching their
posts, counting in a loop — is one query per author and moves every row across
the wire to be thrown away.

## The functions

| Function | Returns |
| --- | --- |
| `Count(field)` | Number of rows |
| `Sum(field)` | Total |
| `Avg(field)` | Mean |
| `Min(field)` | Smallest |
| `Max(field)` | Largest |

```python
await Order.annotate(
    line_count=Count("lines"),
    total=Sum("lines__amount"),
    largest=Max("lines__amount"),
)
```

Also available, operating on a value rather than aggregating:

`Coalesce`, `Concat`, `Length`, `Lower`, `Upper`, `Trim`.

```python
from tortoise.functions import Coalesce, Lower, Length

await Post.annotate(sort_key=Lower("title")).order_by("sort_key")
await Post.annotate(size=Length("body")).filter(size__gt=5000)
await Author.annotate(display=Coalesce("nickname", "name"))
```

`Coalesce` is the useful one for optional columns — the first non-null value,
so a fallback happens in SQL rather than in a comprehension afterwards.

## Grouping

```python
rows = await (
    Post.all()
    .annotate(count=Count("id"))
    .group_by("status")
    .values("status", "count")
)
# [{"status": "draft", "count": 12}, {"status": "published", "count": 130}]
```

Three parts: `group_by` names the grouping columns, `annotate` supplies the
aggregates, `values` selects what comes back.

Every column in `values()` must be either grouped or aggregated — that is SQL's
rule, not the ORM's, and the error comes from the database.

For the common case, Record has a shortcut:

```python
from sillo.record.queries import count_by

await count_by(Post.all(), "status")
# {"draft": 12, "published": 130}
```

Grouping by a related column works the same way:

```python
await (
    Post.all()
    .annotate(count=Count("id"))
    .group_by("author__name")
    .values("author__name", "count")
)
```

## Filtering on an aggregate

```python
await (
    Author.annotate(post_count=Count("posts"))
    .filter(post_count__gte=10)
    .order_by("-post_count")
)
```

A filter naming an annotation becomes `HAVING`; a filter naming a column
becomes `WHERE`. That distinction matters when you use both:

```python
await (
    Author.filter(is_active=True)                 # WHERE — before grouping
    .annotate(post_count=Count("posts"))
    .filter(post_count__gte=10)                   # HAVING — after
)
```

Filtering before the aggregate reduces what is aggregated. Filtering after
selects among the results. Getting them the wrong way round gives you the wrong
numbers, not an error.

## The join-inflation trap

The single most common aggregation bug:

```python
await Author.annotate(
    post_count=Count("posts"),
    comment_count=Count("comments"),
)
```

Both numbers are wrong. Each `Count` is over the same joined result set, so an
author with 3 posts and 5 comments produces 15 joined rows — and both counts
report 15.

Three ways out:

**Count distinct**, where supported:

```python
await Author.annotate(post_count=Count("posts", distinct=True))
```

**Separate queries**, and combine in Python. Two queries, both correct, and
easy to read.

**Subqueries:**

```python
from tortoise.expressions import Subquery, F

await Author.annotate(
    post_count=Subquery(
        Post.filter(author_id=F("id")).annotate(n=Count("id")).values("n")
    )
)
```

Whenever a query has two `Count`s over different relations, check the numbers
against a hand-written query before trusting them.

## Aggregating without grouping

For a single number over the whole table, the queryset methods are simpler:

```python
await Post.filter(status="published").count()
```

For a sum, annotate over a group of one, or use raw SQL:

```python
rows = await (
    Order.filter(status="paid")
    .annotate(total=Sum("amount"))
    .group_by("status")
    .values("status", "total")
)
total = rows[0]["total"] if rows else 0
```

Which is clumsy enough that a [raw query](/orm/raw-sql/) is often clearer for a
one-off dashboard number.

## Conditional aggregation

```python
from tortoise.expressions import Case, When

await Author.annotate(
    published=Sum(Case(When(posts__status="published", then=1), default=0)),
    drafts=Sum(Case(When(posts__status="draft", then=1), default=0)),
)
```

Two counts over the same join in one pass, with no inflation — because both are
sums over the same rows rather than counts of them. This is the pattern for a
status breakdown per parent.

## `NULL` in aggregates

- `Count(field)` skips rows where the field is `NULL`. `Count("id")` counts
  rows.
- `Sum`, `Avg`, `Min`, `Max` skip `NULL`s.
- `Sum` over no rows is `NULL`, not `0`.

That last one bites in templates and JSON responses. Wrap it:

```python
await Order.annotate(total=Coalesce(Sum("amount"), 0))
```

## Performance

Aggregation reads every matching row. Two things help:

- **Filter first**, so the aggregate runs over fewer rows.
- **Index the grouping and filter columns** — see
  [Meta and indexes](/orm/meta/#indexes).

For a dashboard where a number is read constantly and changes slowly, the
cheapest query is the one you do not run: cache it, or keep a counter column
updated with [`F`](/orm/filtering/#f--referring-to-a-column) on write.

Check what a query actually does with [`explain()`](/orm/queries/#explain).

## See also

- [Values and projections](/orm/values/#group_by)
- [Filtering with Q and F](/orm/filtering/)
- [Queries](/orm/queries/#count_by) — `count_by`
