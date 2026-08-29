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
whole surface: [fields](/v0.x/orm/field-reference/),
[relationships](/v0.x/orm/relationships/), the [queryset API](/v0.x/orm/queryset/), the
[lookups](/v0.x/orm/lookups/), [aggregation](/v0.x/orm/aggregation/), [eager
loading](/v0.x/orm/eager-loading/) and [raw SQL](/v0.x/orm/raw-sql/), as Sillo exposes
it, with the Record layer in place rather than described separately.

What Record adds is the layer Django and Laravel developers reach for on day
one:

| | |
| --- | --- |
| [A base model](/v0.x/orm/models/) | Timestamps and soft deletes already wired |
| [Mass-assignment control](/v0.x/orm/mass-assignment/) | `fillable` and `guarded` |
| [Casting](/v0.x/orm/casting/) | Attributes converted on the way in and out |
| [Scopes](/v0.x/orm/scopes/) | Reusable query fragments, local and global |
| [Events](/v0.x/orm/events/) | Lifecycle hooks and observers |
| [Collections](/v0.x/orm/collections/) | Chainable operations on a result set |
| [Factories](/v0.x/orm/factories/) | Test data without fixtures |
| [Transactions](/v0.x/orm/transactions/) | A context manager, with savepoints |
| [Migrations](/v0.x/orm/migrations/) | Generated, reviewable, and applied by the CLI |

## The section

### Getting a database

- [Setup](/v0.x/orm/setup/): `setup_record`, and the connection lifecycle
- [Configuration](/v0.x/orm/configuration/): `DatabaseConfig`, URLs, backends,
  pooling

### Models

- [Models](/v0.x/orm/models/): the base class, serialisation, fetch shortcuts
- [Field reference](/v0.x/orm/field-reference/): every field type and its arguments
- [Record's own fields](/v0.x/orm/fields/): `PasswordField`, `SlugField`,
  `ULIDField`
- [Relationships](/v0.x/orm/relationships/): foreign keys, one-to-one, many-to-many
- [Meta, indexes & constraints](/v0.x/orm/meta/): table options and the schema
- [Mass assignment](/v0.x/orm/mass-assignment/): `fillable`, `guarded`,
  `update_from_dict`
- [Mixins](/v0.x/orm/mixins/): composable behaviours, including soft deletes
- [Casting](/v0.x/orm/casting/): `_casts` and the cast registry
- [Scopes](/v0.x/orm/scopes/): local and global query scopes
- [Events](/v0.x/orm/events/): lifecycle hooks and observers

### Querying

- [The QuerySet API](/v0.x/orm/queryset/): every method, and when the query runs
- [Field lookups](/v0.x/orm/lookups/): everything you can put after `__`
- [Filtering with Q and F](/v0.x/orm/filtering/): OR, negation, column references
- [Aggregation](/v0.x/orm/aggregation/): `annotate`, counting, grouping
- [Eager loading](/v0.x/orm/eager-loading/): `select_related`, `prefetch_related`
- [Values & projections](/v0.x/orm/values/): fetching less than a whole row
- [Raw SQL](/v0.x/orm/raw-sql/): when the ORM cannot express it

### Reading and writing

- [Queries](/v0.x/orm/queries/): the helpers Record adds around a queryset
- [Collections](/v0.x/orm/collections/): working with a result set
- [Pagination](/v0.x/orm/pagination/): pages, and the framework's paginators
- [Bulk operations](/v0.x/orm/bulk/): `bulk_create`, `upsert`, `bulk_upsert`
- [Transactions](/v0.x/orm/transactions/): atomicity and savepoints
- [Connections](/v0.x/orm/connections/): replicas, routing and pooling

### Testing and schemas

- [Factories](/v0.x/orm/factories/): building instances for tests
- [Seeding and fixtures](/v0.x/orm/seeding/): `Seeder` and `FixtureLoader`
- [Pydantic](/v0.x/orm/pydantic/): generating schemas from models
- [Exception handlers](/v0.x/orm/exceptions/): database errors as HTTP responses

### Migrations

- [Migrations](/v0.x/orm/migrations/): what they are, and how they are generated
- [Applying them](/v0.x/orm/migrations-applying/): the deployment shape
- [Programmatically](/v0.x/orm/migrations-programmatic/): without the CLI

### The admin panel

- [Overview](/v0.x/orm/admin/): mounting it
- [Registering models](/v0.x/orm/admin-registering/): `ModelAdmin`
- [Customising](/v0.x/orm/admin-customising/): lists, filters, search, forms
- [Permissions and auth](/v0.x/orm/admin-permissions/): who gets in, and to what

## Honesty about maturity

Some parts of this package are thinner than a first read suggests, and you are
better served knowing which up front than finding out during an incident. Where
that is true, the page says so plainly, including what a helper needs before it
will do what its name says. See for example the [`encrypted`
cast](/v0.x/orm/casting/#the-encrypted-cast).
