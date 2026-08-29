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
whole surface: [fields](/v1.0/orm/field-reference/),
[relationships](/v1.0/orm/relationships/), the [queryset API](/v1.0/orm/queryset/), the
[lookups](/v1.0/orm/lookups/), [aggregation](/v1.0/orm/aggregation/), [eager
loading](/v1.0/orm/eager-loading/) and [raw SQL](/v1.0/orm/raw-sql/), as Sillo exposes
it, with the Record layer in place rather than described separately.

What Record adds is the layer Django and Laravel developers reach for on day
one:

| | |
| --- | --- |
| [A base model](/v1.0/orm/models/) | Timestamps and soft deletes already wired |
| [Mass-assignment control](/v1.0/orm/mass-assignment/) | `fillable` and `guarded` |
| [Casting](/v1.0/orm/casting/) | Attributes converted on the way in and out |
| [Scopes](/v1.0/orm/scopes/) | Reusable query fragments, local and global |
| [Events](/v1.0/orm/events/) | Lifecycle hooks and observers |
| [Collections](/v1.0/orm/collections/) | Chainable operations on a result set |
| [Factories](/v1.0/orm/factories/) | Test data without fixtures |
| [Transactions](/v1.0/orm/transactions/) | A context manager, with savepoints |
| [Migrations](/v1.0/orm/migrations/) | Generated, reviewable, and applied by the CLI |

## The section

### Getting a database

- [Setup](/v1.0/orm/setup/): `setup_record`, and the connection lifecycle
- [Configuration](/v1.0/orm/configuration/): `DatabaseConfig`, URLs, backends,
  pooling

### Models

- [Models](/v1.0/orm/models/): the base class, serialisation, fetch shortcuts
- [Field reference](/v1.0/orm/field-reference/): every field type and its arguments
- [Record's own fields](/v1.0/orm/fields/): `PasswordField`, `SlugField`,
  `ULIDField`
- [Relationships](/v1.0/orm/relationships/): foreign keys, one-to-one, many-to-many
- [Meta, indexes & constraints](/v1.0/orm/meta/): table options and the schema
- [Mass assignment](/v1.0/orm/mass-assignment/): `fillable`, `guarded`,
  `update_from_dict`
- [Mixins](/v1.0/orm/mixins/): composable behaviours, including soft deletes
- [Casting](/v1.0/orm/casting/): `_casts` and the cast registry
- [Scopes](/v1.0/orm/scopes/): local and global query scopes
- [Events](/v1.0/orm/events/): lifecycle hooks and observers

### Querying

- [The QuerySet API](/v1.0/orm/queryset/): every method, and when the query runs
- [Field lookups](/v1.0/orm/lookups/): everything you can put after `__`
- [Filtering with Q and F](/v1.0/orm/filtering/): OR, negation, column references
- [Aggregation](/v1.0/orm/aggregation/): `annotate`, counting, grouping
- [Eager loading](/v1.0/orm/eager-loading/): `select_related`, `prefetch_related`
- [Values & projections](/v1.0/orm/values/): fetching less than a whole row
- [Raw SQL](/v1.0/orm/raw-sql/): when the ORM cannot express it

### Reading and writing

- [Queries](/v1.0/orm/queries/): the helpers Record adds around a queryset
- [Collections](/v1.0/orm/collections/): working with a result set
- [Pagination](/v1.0/orm/pagination/): pages, and the framework's paginators
- [Bulk operations](/v1.0/orm/bulk/): `bulk_create`, `upsert`, `bulk_upsert`
- [Transactions](/v1.0/orm/transactions/): atomicity and savepoints
- [Connections](/v1.0/orm/connections/): replicas, routing and pooling

### Testing and schemas

- [Factories](/v1.0/orm/factories/): building instances for tests
- [Seeding and fixtures](/v1.0/orm/seeding/): `Seeder` and `FixtureLoader`
- [Pydantic](/v1.0/orm/pydantic/): generating schemas from models
- [Exception handlers](/v1.0/orm/exceptions/): database errors as HTTP responses

### Migrations

- [Migrations](/v1.0/orm/migrations/): what they are, and how they are generated
- [Applying them](/v1.0/orm/migrations-applying/): the deployment shape
- [Programmatically](/v1.0/orm/migrations-programmatic/): without the CLI

### The admin panel

- [Overview](/v1.0/orm/admin/): mounting it
- [Registering models](/v1.0/orm/admin-registering/): `ModelAdmin`
- [Customising](/v1.0/orm/admin-customising/): lists, filters, search, forms
- [Permissions and auth](/v1.0/orm/admin-permissions/): who gets in, and to what

## Honesty about maturity

Some parts of this package are thinner than a first read suggests, and you are
better served knowing which up front than finding out during an incident. Where
that is true, the page says so plainly, including what a helper needs before it
will do what its name says. See for example the [`encrypted`
cast](/v1.0/orm/casting/#the-encrypted-cast).
