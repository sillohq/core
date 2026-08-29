---
title: Raw SQL
description: "Dropping to SQL when the ORM cannot express a query: Model.raw, the connection API, parameterisation, and the placeholder style each backend expects."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Raw SQL in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: Model.raw, execute_query, parameterisation and per-backend placeholders.
---

Some queries the ORM cannot build: window functions, recursive CTEs, `LATERAL`
joins, a full-text rank. Write those in SQL.

## `Model.raw`: rows as instances

```python
posts = await Post.raw(
    "SELECT * FROM posts WHERE status = 'published' ORDER BY created_at DESC"
)
```

Returns model instances. The query must select enough columns to build one, the
primary key at minimum, and any field you intend to touch.

Use it when the *filtering* is the hard part but you still want model objects
back.

## The connection API: rows as data

```python
from tortoise import connections

conn = connections.get("default")

count, rows = await conn.execute_query(
    "SELECT status, COUNT(*) AS n FROM posts GROUP BY status"
)
```

| Method | Returns |
| --- | --- |
| `execute_query(sql, values)` | `(affected, rows)` |
| `execute_query_dict(sql, values)` | rows as dicts |
| `execute_insert(sql, values)` | the inserted id |
| `execute_many(sql, values)` | nothing; runs once per parameter set |
| `execute_script(sql)` | nothing; multiple statements, **no parameters** |

`execute_query_dict` is the one to reach for:

```python
rows = await conn.execute_query_dict(
    "SELECT status, COUNT(*) AS n FROM posts GROUP BY status"
)
# [{"status": "draft", "n": 12}, {"status": "published", "n": 130}]
```

## Parameterise. Always.

```python
# WRONG — SQL injection
rows = await conn.execute_query_dict(
    f"SELECT * FROM posts WHERE slug = '{slug}'"
)

# RIGHT
rows = await conn.execute_query_dict(
    "SELECT * FROM posts WHERE slug = $1", [slug]
)
```

There is no safe amount of interpolation. A slug that looks harmless today
comes from a URL, and the string `'; DROP TABLE posts; --` is a valid URL
segment.

:::caution[The placeholder differs by backend]
| Backend | Placeholder |
| --- | --- |
| PostgreSQL (asyncpg) | `$1`, `$2` |
| MySQL (asyncmy) | `%s` |
| SQLite (aiosqlite) | `?` |

This is the driver's syntax, not Tortoise's, so a raw query is tied to the
database you wrote it for. It is the main reason a project that develops on
SQLite and deploys on PostgreSQL should keep raw SQL to a minimum, or run its
tests against the real backend.
:::

**Identifiers cannot be parameterised.** A table or column name has to be part
of the string, so when one is dynamic, validate it against a fixed allow-list
rather than passing it through:

```python
if column not in {"created_at", "views", "title"}:
    raise ValueError(f"cannot sort by {column!r}")

rows = await conn.execute_query_dict(f"SELECT * FROM posts ORDER BY {column} DESC")
```

## What raw SQL bypasses

Everything the model layer does:

- [global scopes](/v1.0/orm/scopes/#global-scopes): including a soft-delete filter;
- [casts](/v1.0/orm/casting/): you get the raw column value;
- [model events](/v1.0/orm/events/) and
  [validation](/v1.0/orm/mixins/#validatesbeforesavemixin);
- `updated_at`.

That is the point of it, and the reason to keep it to the queries that need it.
A raw `DELETE` on a soft-deleted model really deletes.

## Where it is worth it

**Window functions**, "the newest post per author", which the ORM cannot
express:

```sql
SELECT * FROM (
  SELECT p.*, ROW_NUMBER() OVER (PARTITION BY author_id ORDER BY created_at DESC) AS rn
  FROM posts p
) ranked
WHERE rn = 1
```

**Recursive CTEs**, a category tree in one query rather than one per level:

```sql
WITH RECURSIVE tree AS (
  SELECT id, parent_id, name FROM categories WHERE id = $1
  UNION ALL
  SELECT c.id, c.parent_id, c.name
  FROM categories c JOIN tree t ON c.parent_id = t.id
)
SELECT * FROM tree
```

**Bulk operations with SQL-side logic**, an `UPDATE … FROM`, an `INSERT …
SELECT`.

**Reports** that join five tables and group three ways. A dashboard query is
often clearer as SQL than as a chain of `annotate` calls, and it is the form
you can paste into a console to debug.

## Where it is not

If the ORM can express it, let it. You keep parameterisation, portability,
scopes, casts and the ability to compose with a [scope](/v1.0/orm/scopes/).

Before dropping down, check whether one of these covers it:

| Need | Tool |
| --- | --- |
| OR, negation | [`Q`](/v1.0/orm/filtering/#q-or-and-and-negation) |
| Column arithmetic | [`F`](/v1.0/orm/filtering/#f-referring-to-a-column) |
| A conditional value | [`Case`/`When`](/v1.0/orm/filtering/#case--when-conditionals-in-sql) |
| A set from another query | [`Subquery`](/v1.0/orm/filtering/#subquery) |
| One expression the ORM lacks | [`RawSQL`](/v1.0/orm/filtering/#rawsql) in an annotation |

[`RawSQL`](/v1.0/orm/filtering/#rawsql) in particular is the middle ground: one raw
expression inside a query that is otherwise built normally.

## Transactions

Raw queries participate in the ambient transaction:

```python
from sillo.record.transactions import transaction

async with transaction():
    await conn.execute_query("UPDATE posts SET views = views + 1 WHERE id = $1", [1])
    await post.save()
```

Both roll back together, because both use the same connection.

Take the connection **inside** the block, not before it. See
[Connections](/v1.0/orm/connections/).

## Migrations

A migration can run SQL directly, which is how you add a check constraint, a
partial index, or a `CREATE INDEX CONCURRENTLY`:

```python
ops.RunSQL(
    "CREATE UNIQUE INDEX one_active_per_author ON posts (author_id) WHERE status = 'active'",
    reverse_sql="DROP INDEX one_active_per_author",
)
```

Always supply `reverse_sql`. A migration with no way back is a migration you
cannot roll back past.

## Keeping it honest

- **Put raw queries in one module**, not scattered through handlers. They are
  the backend-specific part of your codebase and benefit from being visible.
- **Name the backend in a comment** when the SQL is dialect-specific.
- **Test them against the real database.** A raw query is precisely the code a
  SQLite test suite will not exercise correctly.
