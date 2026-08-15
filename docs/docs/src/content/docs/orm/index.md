---
title: ORM & Admin
description: "sillo.record and the admin panel. What the ORM adds on top of Tortoise, how the two fit together, and a map of this section."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo ORM and Admin
  - tag: meta
    attrs:
      property: og:description
      content: The Record ORM, migrations, and the admin panel, documented end to end.
---

Two things live here: **Record**, Sillo's ORM, and the **admin panel** built on
top of it.

```python
from sillo.record import Model
from tortoise import fields


class Post(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=200)
    body = fields.TextField()
```

```python
post = await Post.create(title="Hello", body="…")
recent = await Post.active().order_by("-created_at").limit(10)
print(post.to_dict())
```

## Record is Tortoise, plus a layer

`sillo.record` is a convenience layer over
[Tortoise ORM](https://tortoise.github.io/). It does not fork Tortoise, wrap
its query compiler, or replace its connection handling.

Every Tortoise feature (fields, querysets, `Q` objects, relations, prefetching,
aggregation, raw SQL) behaves exactly as the Tortoise documentation describes,
because it **is** Tortoise underneath.

You should not need to go and read that documentation. This section covers the
whole surface: [fields](/orm/field-reference/),
[relationships](/orm/relationships/), the [queryset API](/orm/queryset/), the
[lookups](/orm/lookups/), [aggregation](/orm/aggregation/), [eager
loading](/orm/eager-loading/) and [raw SQL](/orm/raw-sql/), as Sillo exposes
it, with the Record layer in place rather than described separately.

What Record adds is the layer Django and Laravel developers reach for on day
one:

| | |
| --- | --- |
| [A base model](/orm/models/) | Timestamps and soft deletes already wired |
| [Mass-assignment control](/orm/mass-assignment/) | `fillable` and `guarded` |
| [Casting](/orm/casting/) | Attributes converted on the way in and out |
| [Scopes](/orm/scopes/) | Reusable query fragments, local and global |
| [Events](/orm/events/) | Lifecycle hooks and observers |
| [Collections](/orm/collections/) | Chainable operations on a result set |
| [Factories](/orm/factories/) | Test data without fixtures |
| [Transactions](/orm/transactions/) | A context manager, with savepoints |
| [Migrations](/orm/migrations/) | Generated, reviewable, and applied by the CLI |

## The section

### Getting a database

- [Setup](/orm/setup/): `setup_record`, and the connection lifecycle
- [Configuration](/orm/configuration/): `DatabaseConfig`, URLs, backends,
  pooling

### Models

- [Models](/orm/models/): the base class, serialisation, fetch shortcuts
- [Field reference](/orm/field-reference/): every field type and its arguments
- [Record's own fields](/orm/fields/): `PasswordField`, `SlugField`,
  `ULIDField`
- [Relationships](/orm/relationships/): foreign keys, one-to-one, many-to-many
- [Meta, indexes & constraints](/orm/meta/): table options and the schema
- [Mass assignment](/orm/mass-assignment/): `fillable`, `guarded`,
  `update_from_dict`
- [Mixins](/orm/mixins/): composable behaviours, including soft deletes
- [Casting](/orm/casting/): `_casts` and the cast registry
- [Scopes](/orm/scopes/): local and global query scopes
- [Events](/orm/events/): lifecycle hooks and observers

### Querying

- [The QuerySet API](/orm/queryset/): every method, and when the query runs
- [Field lookups](/orm/lookups/): everything you can put after `__`
- [Filtering with Q and F](/orm/filtering/): OR, negation, column references
- [Aggregation](/orm/aggregation/): `annotate`, counting, grouping
- [Eager loading](/orm/eager-loading/): `select_related`, `prefetch_related`
- [Values & projections](/orm/values/): fetching less than a whole row
- [Raw SQL](/orm/raw-sql/): when the ORM cannot express it

### Reading and writing

- [Queries](/orm/queries/): the helpers Record adds around a queryset
- [Collections](/orm/collections/): working with a result set
- [Pagination](/orm/pagination/): pages, and the framework's paginators
- [Bulk operations](/orm/bulk/): `bulk_create`, `upsert`, `bulk_upsert`
- [Transactions](/orm/transactions/): atomicity and savepoints
- [Connections](/orm/connections/): replicas, routing and pooling

### Testing and schemas

- [Factories](/orm/factories/): building instances for tests
- [Seeding and fixtures](/orm/seeding/): `Seeder` and `FixtureLoader`
- [Pydantic](/orm/pydantic/): generating schemas from models
- [Exception handlers](/orm/exceptions/): database errors as HTTP responses

### Migrations

- [Migrations](/orm/migrations/): what they are, and how they are generated
- [Applying them](/orm/migrations-applying/): the deployment shape
- [Programmatically](/orm/migrations-programmatic/): without the CLI

### The admin panel

- [Overview](/orm/admin/): mounting it
- [Registering models](/orm/admin-registering/): `ModelAdmin`
- [Customising](/orm/admin-customising/): lists, filters, search, forms
- [Permissions and auth](/orm/admin-permissions/): who gets in, and to what

## Honesty about maturity

Some parts of this package are thinner than a first read suggests, and you are
better served knowing which up front than finding out during an incident. Where
that is true, the page says so plainly. See for example the [`encrypted`
cast](/orm/casting/#the-encrypted-cast-is-not-encryption).
