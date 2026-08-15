---
title: Filtering with Q and F
description: "Queries beyond keyword arguments: Q objects for OR and negation, F for column references, Case/When for conditionals, Subquery, and raw SQL fragments."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Filtering with Q and F in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: Q objects, F expressions, Case/When, Subquery and RawSQL.
---

```python
from tortoise.expressions import Q, F, Case, When, Subquery, RawSQL
```

Keyword arguments to `filter()` are AND-ed. Everything else needs these.

## `Q`: OR, AND and negation

```python
await Post.filter(Q(status="published") | Q(status="featured"))
await Post.filter(Q(status="published") & Q(author_id=7))
await Post.filter(~Q(status="archived"))
```

| Operator | Meaning |
| --- | --- |
| `\|` | OR |
| `&` | AND |
| `~` | NOT |

A `Q` takes the same lookups as `filter`:

```python
Q(title__icontains="async")
Q(created_at__gte=cutoff)
Q(author__name="Ada")
```

### Mixing with keywords

Positional `Q` arguments come first, keywords after, and the two are AND-ed:

```python
await Post.filter(
    Q(title__icontains="async") | Q(body__icontains="async"),
    status="published",
)
```

That is "(title or body mentions async) **and** status is published", which is
almost always what you meant. Putting the keyword inside the `Q` chain instead
would OR it in and quietly return every published post.

### Grouping

Parentheses work as they do in Python, because these are real operators:

```python
await Post.filter(
    (Q(status="published") | Q(status="featured"))
    & Q(created_at__gte=cutoff)
)
```

### Building one up

`Q` objects are values, so a filter can be assembled conditionally:

```python
query = Q()
if term:
    query &= Q(title__icontains=term) | Q(body__icontains=term)
if author_id:
    query &= Q(author_id=author_id)
if not include_archived:
    query &= ~Q(status="archived")

posts = await Post.filter(query).order_by("-created_at")
```

An empty `Q()` matches everything, which is what makes it a safe starting
point. This is the shape for a search endpoint with optional parameters. Much
easier to read than branching over queryset variables.

### A search helper

```python
def search(term: str, *fields: str) -> Q:
    query = Q()
    for field in fields:
        query |= Q(**{f"{field}__icontains": term})
    return query


await Post.filter(search("async", "title", "body", "author__name"))
```

## `F`: referring to a column

```python
from tortoise.expressions import F

await Post.filter(id=1).update(views=F("views") + 1)
```

`F` names a column, so the arithmetic happens **in the database**. The
alternative loses concurrent updates:

```python
post = await Post.get(id=1)
post.views += 1              # read
await post.save()            # write — another request's increment is gone
```

Two requests both read `100`, both write `101`. With `F` the statement is
`SET views = views + 1` and the database serialises them.

Comparing two columns:

```python
await Invoice.filter(paid_amount__lt=F("total_amount"))
await Post.filter(updated_at__gt=F("created_at"))
```

Which cannot be expressed with keyword arguments at all, the right-hand side of
a lookup is always a value.

Arithmetic across columns:

```python
await Product.annotate(margin=F("price") - F("cost")).filter(margin__lt=0)
```

## `Case` / `When`: conditionals in SQL

```python
from tortoise.expressions import Case, When

await Post.annotate(
    weight=Case(
        When(status="featured", then=3),
        When(status="published", then=2),
        default=1,
    )
).order_by("-weight", "-created_at")
```

`When` conditions are evaluated in order; `default` applies when none matches.

This is how you sort by something that is not a column (a priority order over a
status, a bucket over a numeric range) without loading every row and sorting in
Python.

Also useful for conditional aggregation:

```python
from tortoise.functions import Count, Sum

await Author.annotate(
    published=Sum(Case(When(posts__status="published", then=1), default=0)),
    total=Count("posts"),
)
```

One query for both numbers, instead of two.

## `Subquery`

```python
from tortoise.expressions import Subquery

recent_authors = Post.filter(created_at__gte=cutoff).values_list("author_id", flat=True)
await Author.filter(id__in=Subquery(recent_authors))
```

The subquery is evaluated by the database, so the ids never travel to Python.
The alternative (awaiting the inner query and passing a list) round-trips
potentially thousands of ids and then sends them all back in an `IN` clause.

A correlated subquery in an annotation:

```python
await Author.annotate(
    latest_post=Subquery(
        Post.filter(author_id=F("id")).order_by("-created_at").limit(1).values("title")
    )
)
```

Correlated subqueries run once per outer row. For a handful of rows that is
fine; for a large result set, a join or a
[prefetch](/orm/eager-loading/) is usually faster. Check with
[`explain()`](/orm/queries/#explain).

## `RawSQL`

```python
from tortoise.expressions import RawSQL

await Post.annotate(
    rank=RawSQL("ts_rank(search_vector, plainto_tsquery('english', 'async'))")
).order_by("-rank")
```

For expressions the ORM cannot build: a full-text rank, a PostGIS distance, a
window function.

:::danger[Never interpolate user input]
```python
RawSQL(f"ts_rank(search_vector, plainto_tsquery('{term}'))")   # SQL injection
```

`RawSQL` is a string pasted into the query. There is no parameterisation, so
anything a user supplies has to stay out of it.

Where the value has to vary, keep the varying part in an ordinary filter and
the fixed expression in `RawSQL`, or drop to a
[parameterised raw query](/orm/raw-sql/) where you can bind properly.
:::

`RawSQL` also ties the query to one backend's dialect. Fine when you have one;
worth a comment saying so.

## Choosing

| You need | Use |
| --- | --- |
| AND of simple conditions | keyword arguments |
| OR, or negation of a group | `Q` |
| Compare or update using a column | `F` |
| A conditional value | `Case` / `When` |
| A set from another query | `Subquery` |
| An expression the ORM lacks | `RawSQL` |
| A whole query the ORM lacks | [raw SQL](/orm/raw-sql/) |

Reach down the list only when the row above cannot express it. Each step costs
some portability and some readability, and the ones at the bottom cost the
safety of parameterisation.

## See also

- [Lookups](/orm/lookups/): everything after `__`
- [Aggregation](/orm/aggregation/): `annotate`, `Count`, `Sum`
- [Raw SQL](/orm/raw-sql/)
