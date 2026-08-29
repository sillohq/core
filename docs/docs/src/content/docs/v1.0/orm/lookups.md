---
title: Field Lookups
description: "Every lookup you can put after __ in a Sillo filter (comparison, membership, text matching, null checks, date parts and the JSON-specific set) with the SQL each produces."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Field Lookups
  - tag: meta
    attrs:
      property: og:description
      content: "The complete lookup reference: comparison, text, null, ranges, date parts and JSON."
---

```python
await Post.filter(views__gte=100)
await Post.filter(title__icontains="async")
await Post.filter(status__in=["published", "featured"])
```

Everything after `__` is either a lookup or a
[relation to traverse](/v1.0/orm/relationships/#spanning-relations-in-queries). With
no lookup, the comparison is equality.

## Comparison

| Lookup | SQL |
| --- | --- |
| *(none)* | `= ?` |
| `not` | `<> ?` |
| `gt` | `> ?` |
| `gte` | `>= ?` |
| `lt` | `< ?` |
| `lte` | `<= ?` |

```python
await Post.filter(views__gt=100)
await Post.filter(created_at__gte=cutoff)
await Post.filter(status__not="archived")
```

`status__not="archived"` and `.exclude(status="archived")` differ on `NULL`:
`<> 'archived'` is `NULL` (and therefore not true) for a row whose status is
`NULL`, so neither returns it, but only `exclude` reads as intent. Prefer
`exclude` for negation and keep `not` for a single inline condition.

## Membership

| Lookup | SQL |
| --- | --- |
| `in` | `IN (…)` |
| `not_in` | `NOT IN (…)` |

```python
await Post.filter(id__in=[1, 2, 3])
await Post.filter(status__not_in=["archived", "deleted"])
```

An empty list is `IN ()` (always false) which is usually right but worth
knowing when the list comes from user input.

Large `IN` lists get slow; past a few thousand ids, a join against a temporary
table or a subquery is faster.

## Ranges

```python
await Post.filter(created_at__range=(start, end))
```

`BETWEEN`, and **inclusive at both ends**. For dates that is often not what you
want. `range=(jan_1, feb_1)` includes February the 1st at midnight. Use two
bounds when the upper one should be exclusive:

```python
await Post.filter(created_at__gte=jan_1, created_at__lt=feb_1)
```

## Null

| Lookup | SQL |
| --- | --- |
| `isnull=True` | `IS NULL` |
| `isnull=False` | `IS NOT NULL` |
| `not_isnull=True` | `IS NOT NULL` |

```python
await Post.filter(published_at__isnull=True)
await Post.filter(deleted_at__isnull=True)      # the soft-delete filter
```

`= None` is not the same thing. SQL's `= NULL` is never true; `IS NULL` is the
only way to ask.

## Text matching

| Lookup | Matches | Case |
| --- | --- | --- |
| `contains` | anywhere | sensitive |
| `icontains` | anywhere | insensitive |
| `startswith` | at the start | sensitive |
| `istartswith` | at the start | insensitive |
| `endswith` | at the end | sensitive |
| `iendswith` | at the end | insensitive |
| `iexact` | whole value | insensitive |
| `search` | full-text | backend-dependent |

```python
await Post.filter(title__icontains="async")
await Post.filter(slug__startswith="2026-")
await Post.filter(email__iexact="ADA@example.com")
```

:::caution[`contains` cannot use an index]
`icontains` compiles to `LIKE '%term%'`. A leading wildcard means a B-tree
index is unusable, so this is a full scan on every query.

`startswith` **can** use an index (no leading wildcard) which is why a prefix
search is cheap and a substring search is not.

For real search on a large table: a trigram index (`pg_trgm`) on PostgreSQL, a
full-text index, or a search service. The admin's
[search box](/v1.0/orm/admin-customising/#search) is `icontains`, and is meant for
tables you can afford to scan.
:::

`search` maps to the backend's full-text support where there is one and
degrades elsewhere. Check what it compiles to on your database with
[`.sql()`](/v1.0/orm/queryset/#inspecting) before relying on it.

## Regular expressions

| Lookup | Case |
| --- | --- |
| `posix_regex` | sensitive |
| `iposix_regex` | insensitive |

```python
await Post.filter(slug__posix_regex=r"^\d{4}-\d{2}-")
```

POSIX regular expressions, so PostgreSQL and MySQL. Not supported on SQLite
without a registered function. Never indexable.

## Date parts

Available on datetime and date columns:

`year`, `quarter`, `month`, `week`, `day`, `hour`, `minute`, `second`,
`microsecond`.

```python
await Post.filter(created_at__year=2026)
await Post.filter(created_at__month=8)
await Post.filter(created_at__year=2026, created_at__quarter=3)
```

:::note[Date parts are computed per row]
`WHERE EXTRACT(year FROM created_at) = 2026` cannot use an index on
`created_at`, because the index stores the timestamp and the query asks about a
function of it.

The indexable form is a range:

```python
await Post.filter(created_at__gte=jan_1_2026, created_at__lt=jan_1_2027)
```

Same rows, and it uses the index. Worth the extra line on any table big enough
to care.
:::

## JSON fields

[`JSONField`](/v1.0/orm/field-reference/#json) has its own set, not the ones above:

| Lookup | Meaning |
| --- | --- |
| `filter` | Match by key path |
| `contains` | The document contains this structure |
| `contained_by` | The document is contained by this structure |
| `isnull` / `not_isnull` | The column is null |

```python
await Post.filter(metadata__filter={"theme": "dark"})
await Post.filter(metadata__contains={"tags": ["python"]})
```

Support varies sharply by backend. `JSONB` on PostgreSQL is fully queryable,
SQLite stores JSON as text and can do much less. Test against the database you
deploy on.

If you find yourself filtering the same key repeatedly, that key wants to be a
column.

## Across relations

Lookups compose with traversal, to any depth:

```python
await Post.filter(author__name__icontains="ada")
await Post.filter(author__profile__country__in=["GB", "IE"])
await Comment.filter(post__created_at__gte=cutoff)
```

Each `__` before the final lookup is a join.

### Many-to-many produces duplicates

```python
await Post.filter(tags__name__in=["python", "async"])          # duplicates
await Post.filter(tags__name__in=["python", "async"]).distinct()
```

A join across a many-to-many yields one row per match, so a post with both tags
appears twice. [`distinct()`](/v1.0/orm/values/#distinct) collapses them.

## Filtering on an annotation

```python
from tortoise.functions import Count

await (
    Post.annotate(comment_count=Count("comments"))
    .filter(comment_count__gte=10)
)
```

A filter on an annotated name becomes `HAVING` rather than `WHERE`, which is
what lets it see the aggregate. See [Aggregation](/v1.0/orm/aggregation/).

## Case sensitivity

The `i`-prefixed lookups are explicit. Everything else depends on your
database's collation:

- **PostgreSQL** is case-sensitive by default. `iexact` and friends use
  `LOWER()` or `ILIKE`.
- **MySQL** is usually case-**in**sensitive by default (`utf8mb4_general_ci`),
  so `exact` and `iexact` behave identically, and the same code behaves
  differently on PostgreSQL.
- **SQLite** is case-sensitive except for ASCII with `NOCASE`.

If your development database and your production database differ here, write
the `i` lookup explicitly wherever you mean it. The bug is otherwise invisible
until deployment.

## See also

- [Filtering with Q and F](/v1.0/orm/filtering/): OR, negation, column references
- [The QuerySet API](/v1.0/orm/queryset/)
- [Relationships](/v1.0/orm/relationships/)
