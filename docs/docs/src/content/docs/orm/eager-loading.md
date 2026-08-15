---
title: Eager Loading
description: "Avoiding the N+1 — select_related, prefetch_related, the Prefetch object, fetch_related, and how to tell which one a relation needs."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Eager Loading
  - tag: meta
    attrs:
      property: og:description
      content: select_related, prefetch_related, Prefetch and diagnosing the N+1.
---

## The problem

```python
posts = await Post.all().limit(50)
for post in posts:
    print(post.author.name)      # raises — the relation was never fetched
```

Sillo raises rather than quietly issuing a query. That is deliberate: an
implicit query inside a loop is the N+1, and it is invisible until the table
grows. Being made to ask for the relation is what makes the cost visible.

The fix is to say so in the query:

```python
posts = await Post.all().limit(50).select_related("author")
for post in posts:
    print(post.author.name)      # already loaded
```

Two queries instead of fifty-one — and one of them was going to happen anyway.

## `select_related`

```python
await Post.all().select_related("author")
await Post.all().select_related("author", "category")
await Post.all().select_related("author__profile")
```

A **join**. The related row comes back in the same query, in the same result
set.

Use it for **forward** relations — the ones where this table holds the foreign
key:

- [`ForeignKeyField`](/orm/relationships/#foreign-keys)
- [`OneToOneField`](/orm/relationships/#one-to-one)

It cannot be used for reverse relations or many-to-many, because those are
one-to-many: a join would multiply the rows rather than widen them.

## `prefetch_related`

```python
await Post.all().prefetch_related("tags")
await Author.all().prefetch_related("posts")
await Post.all().prefetch_related("tags", "comments")
```

A **second query** per relation, matched up in Python.

Use it for the one-to-many directions:

- reverse foreign keys (`author.posts`)
- [many-to-many](/orm/relationships/#many-to-many) (`post.tags`)

It works on forward relations too, at the cost of an extra query rather than a
join — which is occasionally what you want when the joined row is wide and
repeated.

## Choosing

| Relation | Use |
| --- | --- |
| Forward FK — `post.author` | `select_related` |
| One-to-one — `user.profile` | `select_related` |
| Reverse FK — `author.posts` | `prefetch_related` |
| Many-to-many — `post.tags` | `prefetch_related` |

The rule underneath: **one row on the other side, join; many rows, prefetch.**

They compose:

```python
await (
    Post.all()
    .select_related("author")        # one query, joined
    .prefetch_related("tags")        # a second query
)
```

## `Prefetch` — filtering what is prefetched

```python
from tortoise.query_utils import Prefetch

authors = await Author.all().prefetch_related(
    Prefetch(
        "posts",
        queryset=Post.filter(status="published").order_by("-created_at"),
    )
)
```

Each author's `posts` now holds only their published posts, newest first.

Without this, prefetching loads **every** related row. For an author with ten
thousand posts, `prefetch_related("posts")` fetches all ten thousand to render
a list of five.

`to_attr` puts the result somewhere else, so the unfiltered relation stays
available:

```python
Prefetch(
    "posts",
    queryset=Post.filter(status="published"),
    to_attr="published_posts",
)
```

```python
author.published_posts      # the filtered list
```

:::caution[Limiting inside a Prefetch limits the total]
A `LIMIT` in a prefetch queryset applies to the single combined query, not per
parent. `Prefetch("posts", queryset=Post.all().limit(5))` gives you five posts
across *all* authors, not five each.

"The five most recent per author" is a window function — see
[raw SQL](/orm/raw-sql/).
:::

## `fetch_related`

On an instance you already have:

```python
post = await Post.get(id=1)
await post.fetch_related("author", "tags")
```

Fine for one object. Inside a loop it **is** the N+1 — that is the same
sequence of queries, written out. If you are calling it in a loop, the fix is
`prefetch_related` on the query that produced the loop.

## Nested

```python
await Post.all().prefetch_related("comments__author")
await Author.all().prefetch_related("posts__tags")
await Comment.all().select_related("post__author")
```

Depth is fine. Breadth is what gets expensive — each prefetched relation is
another query, and each joined relation widens every row.

## Diagnosing an N+1

**The exception.** Touching an unfetched relation raises, which catches most of
these during development.

**The query count.** Log statements while you exercise a page:

```bash
DB_ECHO=true
```

A list page issuing 50-odd near-identical queries is the signature.

**The plan.** [`explain()`](/orm/queries/#explain) for one query at a time.

**In the admin.** A `list_display` naming a relation is one query per row.
Fix it in [`get_queryset`](/orm/admin-registering/#get_queryset):

```python
@classmethod
def get_queryset(cls, queryset):
    return queryset.select_related("author").prefetch_related("tags")
```

## When not to eager load

Eager loading trades queries for data transferred. Both have a cost.

- **A relation you might not use** — behind a conditional — is better fetched
  when the condition is true.
- **A join that multiplies rows.** Two `prefetch_related` calls are two clean
  queries; two joins over one-to-many relations would be a cross product.
- **Deep chains on a large result set.** Fifty posts × their comments × each
  comment's author is a lot of objects for a page showing titles.

The honest check is [`explain()`](/orm/queries/#explain) and the query count,
not intuition.

## Projections instead

Sometimes the relation is wanted for one column, and a
[projection](/orm/values/) is cheaper than loading the object at all:

```python
await Post.all().values("title", "author__name")
# [{"title": "Hello", "author__name": "Ada"}, …]
```

One query, one join, a flat dict, and no related instances constructed. For a
list you are about to serialise, this is often the best answer.
