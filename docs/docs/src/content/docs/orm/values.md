---
title: Values & Projections
description: "Fetching less than a whole row — values, values_list, only, distinct, in_bulk and group_by — and when a dict beats a model instance."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Values and Projections
  - tag: meta
    attrs:
      property: og:description
      content: values, values_list, only, distinct, in_bulk and group_by.
---

A model instance is not always what you want. These return less.

## `values`

```python
rows = await Post.all().values("id", "title")
# [{"id": 1, "title": "Hello"}, …]
```

Dicts, not instances. Only the named columns are selected.

With no arguments it returns every column:

```python
await Post.all().values()
```

Rename in flight with keywords:

```python
await Post.all().values("id", headline="title")
# [{"id": 1, "headline": "Hello"}, …]
```

Traversal works, and the joined column keeps its full path as the key:

```python
await Post.all().values("title", "author__name")
# [{"title": "Hello", "author__name": "Ada"}, …]
```

That is the neat trick here: one query, one join, a flat dict, and no relation
to fetch afterwards.

## `values_list`

```python
await Post.all().values_list("id", "title")
# [(1, "Hello"), (2, "World"), …]

await Post.all().values_list("id", flat=True)
# [1, 2, 3, …]
```

`flat=True` takes exactly one field and unwraps the tuples. It is the shortest
way to get a list of ids for a subsequent query — though a
[`Subquery`](/orm/filtering/#subquery) is better still, since it never brings
the ids into Python at all.

## When to project

An instance carries every column, the field machinery, and a place for
relations. For a dropdown of five hundred titles that is a lot of object
construction for two strings.

Rough guidance:

- **A list to render, or to serialise:** `values()`.
- **One column:** `values_list(flat=True)`.
- **Rows you will modify or call methods on:** instances.
- **Instances, but the row is wide:** [`only()`](#only).

The saving is not only Python objects. A `TextField` you did not ask for is a
column the database still reads and sends over the wire.

## What you give up

`values()` and `values_list()` return plain data:

- no `to_dict()`, no [casts](/orm/casting/), no model methods;
- no `save()` — you cannot write these back;
- no [property or computed attributes](/orm/models/).

A [cast](/orm/casting/) field fetched with `values()` gives you the **encoded**
column value — the JSON string, not the dict. Decoding happens on the instance,
and there is no instance.

## `only`

```python
posts = await Post.all().only("id", "title")
```

Real instances, with only those columns loaded. You get the model's methods,
`save()` works, and the wide columns are left in the database.

The catch is that touching an unloaded field triggers a second query per
instance — the same N+1 shape as an unfetched relation, from a different
direction. Only project what the code path genuinely does not use.

The primary key is always included, whether or not you name it.

## `distinct`

```python
await Post.filter(tags__name__in=["python", "async"]).distinct()
await Post.all().values_list("status", flat=True).distinct()
```

`SELECT DISTINCT`. Two common needs:

**Collapsing join duplicates.** A join across a
[many-to-many](/orm/relationships/#filtering-across-it) produces one row per
match, so a post with two matching tags appears twice.

**Getting the distinct values of a column**, as in the second example — the
list of statuses actually in use, for a filter dropdown.

`DISTINCT` deduplicates the **whole selected row**, so adding a column can
change the answer. `values_list("status", flat=True).distinct()` gives distinct
statuses; `.distinct().values_list("status", flat=True)` on full rows does not,
because the rows differ by id.

For "the newest row per group", `DISTINCT` is the wrong tool — that is a window
function in [raw SQL](/orm/raw-sql/), or a
[`Subquery`](/orm/filtering/#subquery).

## `in_bulk`

```python
posts = await Post.all().in_bulk([1, 2, 3], field_name="id")
# {1: <Post>, 2: <Post>, 3: <Post>}
```

One query, keyed by the field you asked for. This is the fix for the lookup
loop:

```python
# N queries
for row in rows:
    row.post = await Post.get(id=row.post_id)

# one query
posts = await Post.all().in_bulk([r.post_id for r in rows], field_name="id")
for row in rows:
    row.post = posts.get(row.post_id)
```

Missing ids are simply absent from the dict — use `.get()` rather than `[]`
unless you have already established they all exist.

`field_name` need not be the primary key; any unique column works.

## `group_by`

```python
from tortoise.functions import Count

rows = await (
    Post.all()
    .annotate(count=Count("id"))
    .group_by("status")
    .values("status", "count")
)
# [{"status": "draft", "count": 12}, {"status": "published", "count": 130}]
```

`group_by` names the grouping columns; `annotate` supplies the aggregates;
`values` selects what comes back.

For the common case Record has a shortcut:

```python
from sillo.record.queries import count_by

await count_by(Post.all(), "status")
# {"draft": 12, "published": 130}
```

See [Aggregation](/orm/aggregation/) for the fuller treatment.

## Combining

These compose with everything else:

```python
await (
    Post.filter(status="published")
    .select_related("author")
    .order_by("-created_at")
    .limit(50)
    .values("id", "title", "author__name")
)
```

Two rules worth knowing:

- `values()` and `values_list()` are **terminal** in shape — you cannot chain
  `filter()` after them and get a queryset back.
- `only()` is not terminal; it returns a queryset like any other.
