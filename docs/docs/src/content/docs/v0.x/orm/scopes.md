---
title: Query Scopes
description: "Reusable query fragments: local scope_ methods that become chainable, global scopes applied to every query, and how to escape them when you need everything."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Query Scopes
  - tag: meta
    attrs:
      property: og:description
      content: Local scopes, global scopes, RecordQuerySet and without_global_scopes.
---

A scope is a named piece of a query you would otherwise repeat.

```python
class Post(Model):
    status = fields.CharField(max_length=20)
    published_at = fields.DatetimeField(null=True)

    @classmethod
    def scope_published(cls, queryset):
        return queryset.filter(status="published", published_at__isnull=False)

    @classmethod
    def scope_by_author(cls, queryset, author_id):
        return queryset.filter(author_id=author_id)
```

```python
await Post.published()
await Post.published().by_author(7).order_by("-published_at").limit(10)
```

## Local scopes

Any classmethod named `scope_<name>` becomes available two ways:

- **On the model**, as `Model.<name>(...)`: starting a new query.
- **On a queryset**, as `.<name>(...)`: continuing one.

The chaining is what makes them worth having. A scope returns a queryset, so it
composes with `filter`, `order_by`, `limit`, other scopes, and everything else
Tortoise offers.

```python
@classmethod
def scope_search(cls, queryset, term):
    return queryset.filter(
        Q(title__icontains=term) | Q(body__icontains=term)
    )
```

```python
await Post.published().search("async").limit(20)
```

The first argument after `cls` is always the queryset. Everything after it is
yours.

:::note[An existing attribute wins]
The model-level shortcut is only created when the name is free. A scope called
`scope_filter` would not overwrite `filter`. The queryset method still works,
but `Post.filter()` remains Tortoise's.

Name scopes after the intent (`published`, `overdue`, `for_tenant`) rather than
after query verbs, and this never comes up.
:::

## Global scopes

A global scope applies to **every** query on the model.

```python
Post.add_global_scope(lambda qs: qs.filter(deleted_at__isnull=True))
```

```python
await Post.all()                          # excludes soft-deleted rows
await Post.filter(author_id=7)            # also excludes them
await Post.without_global_scopes().all()  # everything
```

This is the idiomatic way to make [soft deletes](/v0.x/orm/mixins/#softdeletesmixin)
the default, which the base model deliberately does not do on its own. See the
caution in [Models](/v0.x/orm/models/#soft-deletes).

### Multi-tenancy

The other common use, and the one to be careful with:

```python
Invoice.add_global_scope(lambda qs: qs.filter(tenant_id=current_tenant()))
```

It works, and it is genuinely useful for defence in depth. It is not a security
boundary on its own:

- `without_global_scopes()` bypasses it, and one call site eventually will;
- raw SQL bypasses it;
- a related-model traversal from an unfiltered model can reach the rows anyway;
- `current_tenant()` has to be correct in every context the model is used from,
  including console commands and background jobs where no request set it.

Enforce tenancy in the query you write and treat the global scope as the safety
net, not the other way round.

### Registering them

Global scopes are usually added once, where the models are imported:

```python
# database/models/__init__.py
from .post import Post
from .invoice import Invoice

Post.add_global_scope(lambda qs: qs.filter(deleted_at__isnull=True))
```

`add_global_scope` on a base class applies to its subclasses, which is how you
would make soft deletes default across a whole project.

To remove one you need the same callable object:

```python
active_only = lambda qs: qs.filter(deleted_at__isnull=True)
Post.add_global_scope(active_only)
Post._scope_registry.remove(active_only)
```

Which is a reason to define them as named functions rather than inline lambdas
if you ever expect to remove one.

## Escaping them

```python
Post.without_global_scopes()          # a queryset with none applied
```

Necessary for an admin view that has to show trashed rows, a repair script, or
a report over everything. The framework uses it itself. [`upsert`](/v0.x/orm/bulk/)
Re-fetches the row through `without_global_scopes()` so that upserting a
soft-deleted row still returns it.

## How it fits together

| Piece | Role |
| --- | --- |
| `HasScopes` | The mixin on the base model, providing `add_global_scope` and `without_global_scopes` |
| `ScopeRegistry` | Holds the global scopes for a model, and applies them |
| `RecordQuerySet` | Tortoise's `QuerySet` with the `scope_*` methods attached |
| `RecordManager` | The default manager, which applies global scopes to every queryset |

The manager is the load-bearing one. It is set on
[`Model.Meta`](/v0.x/orm/models/#meta), so replacing `manager` with something that
does not subclass `RecordManager` silently switches global scopes off:

```python
class Meta:
    manager = MyManager()   # must subclass RecordManager
```

## Scopes versus managers versus properties

- **A scope** when the result is a queryset that should keep chaining. Most
  cases.
- **A classmethod** returning a value when it is a terminal question:
  `await Post.published_count()`.
- **A property** when it is about one loaded instance and needs no query:
  `post.is_published`.

The mistake to avoid is a "scope" that awaits internally and returns a list. It
looks like a scope at the call site and then refuses to chain.
