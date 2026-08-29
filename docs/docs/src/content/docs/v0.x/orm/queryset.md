---
title: The QuerySet API
description: "Every method on a Sillo queryset (building, narrowing, ordering, slicing, fetching one, counting, updating and deleting) and when each one hits the database."
head:
  - tag: meta
    attrs:
      property: og:title
      content: The Sillo Record QuerySet API
  - tag: meta
    attrs:
      property: og:description
      content: Every queryset method, what it returns, and when the query runs.
---

A queryset is a query being built. Nothing runs until you await it.

```python
query = Post.filter(status="published")     # no query yet
query = query.order_by("-created_at")       # still none
posts = await query.limit(10)               # now
```

That laziness is what lets a query be assembled across several functions, and
why a scope can return one and the caller keep chaining.

## Building

| Method | Returns |
| --- | --- |
| `Model.all()` | Everything |
| `Model.filter(**kw)` | Rows matching |
| `Model.exclude(**kw)` | Rows not matching |
| `.filter()` / `.exclude()` | Narrows further |

```python
await Post.all()
await Post.filter(status="published")
await Post.filter(status="published", author_id=7)
await Post.exclude(status="archived")
await Post.filter(status="published").exclude(author_id=7)
```

Several keywords in one `filter` are AND-ed. Chained `filter` calls are also
AND-ed, so `filter(a=1).filter(b=2)` and `filter(a=1, b=2)` are the same query.

For OR, negation, or anything more structured, use
[`Q` objects](/v0.x/orm/filtering/).

Everything after `__` is a [lookup](/v0.x/orm/lookups/) or a relation to traverse:

```python
await Post.filter(title__icontains="async")
await Post.filter(created_at__gte=cutoff)
await Post.filter(author__name="Ada")
```

## Ordering

```python
await Post.all().order_by("-created_at")
await Post.all().order_by("status", "-created_at")
await Post.all().order_by("author__name")
```

A leading `-` is descending. `order_by()` **replaces** any
[`Meta.ordering`](/v0.x/orm/meta/#ordering) rather than adding to it.

```python
await Post.all().earliest("created_at")
await Post.all().latest("created_at")
```

`earliest` and `latest` order and take one, returning `None` if there are no
rows.

## Slicing

```python
await Post.all().limit(10)
await Post.all().offset(20).limit(10)
```

Python slicing works too, and compiles to the same thing:

```python
await Post.all()[20:30]
```

:::caution[Always order a limited query]
`LIMIT` without `ORDER BY` has no defined row order. Two identical requests can
return different rows, and a row can appear on two consecutive pages while
nothing changes.

Order by something unique, or unique enough, `["-created_at", "id"]`.
:::

## Fetching one

```python
post = await Post.get(id=1)             # raises DoesNotExist, or MultipleObjectsReturned
post = await Post.get_or_none(id=1)     # None if absent
post = await Post.filter(...).first()   # None if empty
post = await Post.filter(...).last()    # None if empty
```

`get()` raising is useful in a handler, with the [exception
handlers](/v0.x/orm/exceptions/) registered, `DoesNotExist` becomes a 404 and you
write no branch at all.

`get_or_none()` is right when absence is an expected answer rather than an
error.

`get()` also raises `MultipleObjectsReturned` when the filter is not unique.
That is a real signal: it means the lookup you thought identified one row does
not.

## Existence and counting

```python
await Post.filter(status="published").exists()     # bool — SELECT 1 … LIMIT 1
await Post.filter(status="published").count()      # int — COUNT(*)
```

Use `exists()` when you only want to know. `count() > 0` counts every matching
row to answer a yes/no question, and on a large table that difference is
substantial.

`COUNT(*)` is not free either. PostgreSQL cannot answer it from an index alone.
See [Pagination](/v0.x/orm/pagination/#counting-is-the-expensive-half).

## Writing

```python
post = await Post.create(title="Hello", body="…")

post.title = "Hello again"
await post.save()
await post.save(update_fields=["title"])

await post.delete()
```

`update_fields` writes only those columns. Worth it on a wide row, and worth it
to avoid clobbering a column another process changed since you loaded it.

### Set-based writes

```python
await Post.filter(status="draft").update(status="published")
await Post.filter(created_at__lt=cutoff).delete()
```

One statement, any number of rows. They return the number affected.

:::caution[These skip the model layer]
`QuerySet.update()` and `QuerySet.delete()` are SQL. No instances are built, so:

- no [model events](/v0.x/orm/events/);
- no [validation](/v0.x/orm/mixins/#validatesbeforesavemixin);
- no [casts](/v0.x/orm/casting/): a cast field gets the raw Python value;
- `updated_at` does not move unless you set it;
- [`SoftDeletesMixin`](/v0.x/orm/mixins/) does not apply: `delete()` here is a real
  delete.

That is exactly what you want for a million rows and exactly what you do not
want when a hook has to run. Loop and `save()` when it does.
:::

```python
await Post.filter(status="draft").update(
    status="published", updated_at=datetime.now(timezone.utc),
)
```

### Atomic updates

```python
from tortoise.expressions import F

await Post.filter(id=1).update(views=F("views") + 1)
```

`F` refers to the column's current value, so the increment happens in the
database. The read-modify-write version loses concurrent increments.

## Bulk

```python
await Post.bulk_create([Post(title="a"), Post(title="b")])
await Post.bulk_update(posts, fields=["title"], batch_size=100)
```

Record adds [`bulk_upsert` and `upsert`](/v0.x/orm/bulk/) on top of these.

## Shaping the result

```python
await Post.all().values("id", "title")               # list of dicts
await Post.all().values_list("id", "title")          # list of tuples
await Post.all().values_list("id", flat=True)        # list of ids
await Post.all().only("id", "title")                 # instances, fewer columns
await Post.all().distinct()
await Post.all().in_bulk([1, 2, 3], field_name="id") # {id: instance}
```

See [Values and projections](/v0.x/orm/values/).

## Relations

```python
await Post.all().select_related("author")       # a join
await Post.all().prefetch_related("tags")       # a second query
```

See [Eager loading](/v0.x/orm/eager-loading/).

## Aggregation

```python
from tortoise.functions import Count

await Post.annotate(comments=Count("comments")).order_by("-comments")
```

See [Aggregation](/v0.x/orm/aggregation/).

## Locking

```python
async with transaction():
    post = await Post.select_for_update().get(id=1)
    post.views += 1
    await post.save()
```

`SELECT … FOR UPDATE`, takes a row lock until the transaction ends, so a
concurrent transaction reading the same row waits.

```python
await Post.select_for_update(nowait=True).get(id=1)      # raise instead of waiting
await Post.select_for_update(skip_locked=True).all()     # skip locked rows
```

`skip_locked` is the idiom for a queue-in-a-table: several workers each take
rows nobody else has.

Only meaningful inside a [transaction](/v0.x/orm/transactions/). Outside one the
lock is released immediately, and the whole thing is a no-op.

## Index hints

```python
await Post.all().use_index("idx_posts_status")
await Post.all().force_index("idx_posts_status")
```

MySQL only. A last resort for when the planner picks badly, and worth
revisiting after any schema change, since a hint that was right once becomes a
hint that is wrong later.

## Inspecting

```python
print(Post.filter(status="published").sql())
print(await Post.filter(status="published").explain())
```

`sql()` returns the statement without running it. `explain()` asks the database
for its plan. Both are how you find out what a chain of scopes actually
compiled to.

`sql(params_inline=True)` inlines the parameters, which makes it copy-pasteable
into a console, and unsafe to log, since it contains the values.

## Connections

```python
await Post.all().using_db(replica)
```

See [Connections](/v0.x/orm/connections/).

## Reuse and mutation

A queryset method returns a **new** queryset:

```python
base = Post.filter(status="published")
recent = base.order_by("-created_at").limit(10)
popular = base.order_by("-views").limit(10)
```

`base` is unchanged, so both branches are safe. This is what makes
[scopes](/v0.x/orm/scopes/) composable.

Awaiting the same queryset twice runs the query twice. There is no result
cache. Await once and keep the list:

```python
posts = await Post.filter(status="published")
print(len(posts))
for post in posts:
    ...
```

## Iterating

```python
for post in await Post.filter(status="published"):
    ...
```

Note the `await` *before* the loop: awaiting gives you a list, and the loop is
over that list. For a table too large to hold, use
[`iter_all`](/v0.x/orm/queries/#iter_all), which walks in batches.
