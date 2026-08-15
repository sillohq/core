---
title: Collections
description: "The Collection class: chainable map, filter, pluck, group_by, sort_by, chunk and the aggregate helpers for working with a result set in Python."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Collections
  - tag: meta
    attrs:
      property: og:description
      content: Chainable operations over a list of model instances.
---

A `Collection` wraps a list of rows you already have, and gives it chainable
operations.

```python
from sillo.record import Collection

posts = Collection(await Post.filter(status="published"))

titles = (
    posts
    .filter(lambda p: p.views > 100)
    .sort_by("views", descending=True)
    .take(5)
    .pluck("title")
)
```

## Where this belongs

**In memory, after the query.** Every method here operates on a Python list.
Nothing generates SQL.

So the rule is simple: if the database can do it, let it.

```python
# wrong — loads every post to keep five
Collection(await Post.all()).sort_by("views", descending=True).take(5)

# right
await Post.all().order_by("-views").limit(5)
```

Collections earn their place when the work cannot be expressed in SQL, or when
you already have the rows and need three different views of them without three
more round trips.

## Transforming

```python
collection.map(lambda p: p.title.upper())
collection.filter(lambda p: p.views > 100)
collection.reject(lambda p: p.is_draft)
collection.unique()
collection.unique("author_id")
```

Each returns a new `Collection`, so they chain. Nothing mutates in place.

## Reshaping

```python
collection.pluck("title")          # ["Hello", "World"]
collection.group_by("status")      # {"draft": Collection, "published": Collection}
collection.key_by("id")            # {3: post, 7: post}
collection.chunk(100)              # [Collection, Collection, …]
```

`key_by` is the one that saves you most often. It is how you avoid a lookup
loop after a [`find_by_ids`](/orm/queries/#find_by_ids):

```python
authors = Collection(await User.filter(id__in=author_ids)).key_by("id")
for post in posts:
    post.author_name = authors[post.author_id].name
```

`chunk` is for batching work: a `Collection` of `Collection`s, each of at most
that size.

## Ordering and slicing

```python
collection.sort_by("created_at")
collection.sort_by("views", descending=True)
collection.take(10)
collection.skip(20)
collection.first()
collection.last()
collection.first(default=None)
```

`first()` and `last()` return `None` on an empty collection unless you pass a
default, so they never raise.

## Aggregates

```python
collection.count()
collection.sum("views")
collection.avg("views")
collection.min("created_at")
collection.max("views")
```

With no key, `sum` and `avg` operate on the items themselves, useful when the
collection holds numbers rather than models:

```python
Collection([1, 2, 3]).sum()      # 6
```

Again: `await Post.all().count()` asks the database and is what you want for a
count of everything. `collection.count()` counts what you already loaded.

## Predicates

```python
collection.is_empty()
collection.is_not_empty()
collection.contains(lambda p: p.status == "draft")
```

## Getting out

```python
collection.to_list()
collection.to_dict()
collection.to_json(indent=2)
```

`to_dict()` calls `to_dict()` on each item, so it works on model instances and
gives you a list of dicts. The same caution as [model
serialisation](/orm/models/#serialisation) applies. It includes every field.

## It is not a queryset

`Collection` and a Tortoise queryset both chain and read similarly, which is
the trap:

| | Queryset | Collection |
| --- | --- | --- |
| Where it runs | The database | Python |
| When | On `await` | Immediately |
| Cost of `.filter()` | A `WHERE` clause | A full scan of the list |
| Memory | One page | Every row you loaded |

A `Collection` built from `await Post.all()` on a large table has already lost.
Filter in the query; refine in the collection.
