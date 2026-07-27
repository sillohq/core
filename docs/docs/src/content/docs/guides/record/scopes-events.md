---
title: Scopes & Events
description: Reusable query scopes (local and global), the name-collision trap that silently changes what a scope filters, and why model lifecycle events never fire on their own.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Scopes & Events
  - tag: meta
    attrs:
      property: og:description
      content: Reusable query scopes (local and global), the name-collision trap that silently changes what a scope filters, and why model lifecycle events never fire on their own.
---

#  Scopes & Events

Two features share this page because they are the two ways `sillo.record`
lets you attach behaviour to a model without repeating yourself: scopes
put reusable constraints on queries, and events put callbacks on the
model lifecycle.

They are at very different levels of maturity. Scopes work well and are
worth using, provided you understand one naming rule. Events, as shipped,
are a registration API with nothing calling it — you have to fire them
yourself. Both are covered honestly below.

##  Query scopes

A scope is a named, reusable piece of a query. Instead of scattering
`filter(published=True, deleted_at=None)` across twenty call sites, you
name it once and call the name.

Scopes work because Tortoise querysets are chainable and each method
returns a new queryset. A scope is just a function from queryset to
queryset.

###  Declaring a local scope

Define a classmethod whose name starts with `scope_`. It receives the
queryset as its first argument after `cls`.

```python title="declaring scopes"
from tortoise import fields
from tortoise.expressions import Q
from sillo.record import Model


class Article(Model):
    title = fields.CharField(max_length=200)
    body = fields.TextField()
    published = fields.BooleanField(default=False)
    plan = fields.CharField(max_length=20, default="free")

    @classmethod
    def scope_published(cls, queryset):
        return queryset.filter(published=True)

    @classmethod
    def scope_premium(cls, queryset):
        return queryset.filter(plan__in=["pro", "enterprise"])

    @classmethod
    def scope_recent(cls, queryset, days: int = 7):
        from datetime import datetime, timedelta, timezone
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return queryset.filter(created_at__gte=since)

    @classmethod
    def scope_search(cls, queryset, term: str):
        return queryset.filter(Q(title__icontains=term) | Q(body__icontains=term))
```

Two things then become available, through two separate mechanisms.

`Model.__init_subclass__` scans for `scope_*` methods at class creation
time and installs a same-named classmethod that calls
`getattr(cls.all(), scope_name)(...)`. That gives you
`Article.published()`.

`RecordQuerySet.__getattr__` resolves any unknown attribute against
`model.scope_<name>`, which is what makes scopes chainable onto an
existing queryset. That gives you `Article.all().published()`.

```python title="using scopes"
rows = await Article.published().premium().recent(30)
rows = await Article.all().published().order_by("-created_at").limit(20)
rows = await Article.filter(plan="pro").published()
rows = await Article.published().search("async")
```

Scopes compose with each other and with ordinary queryset methods in any
order, because every step is still a queryset. An unknown name raises
`AttributeError: 'RecordQuerySet' object has no attribute 'nonexistent'`,
which is the normal Python failure and easy to read.

###  The name-collision trap

:::danger[A scope named after an existing model method silently means two different things]
`Model.__init_subclass__` installs the shortcut only if the public name
is not already taken:

```python
public_name = name.removeprefix("scope_")
if hasattr(cls, public_name):
    continue          # shortcut NOT installed
```

`Model` already defines `active`, `deleted`, `filter`, `all`, `get`,
`create`, `save`, `delete`, and `count`. Declaring `scope_active` does
**not** give you `Article.active()` — that name still resolves to the
base model's soft-delete filter. But `RecordQuerySet.__getattr__` has no
such guard, so `Article.all().active()` *does* reach your scope.

Same name, two filters, chosen by how you started the chain:

```python
class User(Model):
    is_active = fields.BooleanField(default=True)

    @classmethod
    def scope_active(cls, queryset):
        return queryset.filter(is_active=True)

await User.active()          # WHERE deleted_at IS NULL   ← base model
await User.all().active()    # WHERE is_active = true     ← your scope
```

Those return genuinely different rows. Never name a scope `active`,
`deleted`, `filter`, `all`, `get`, `create`, `save`, `delete`, or
`count`. Pick a name that reads well and does not collide —
`scope_enabled`, `scope_live`, `scope_visible`.
:::

A defensive habit: after declaring scopes, assert the shortcut exists.

```python title="catching collisions at import time"
for name in ("published", "premium", "recent"):
    assert getattr(Article, name, None) is not None, f"scope {name} collided"
```

###  Global scopes

A global scope is applied to every queryset the model's manager
produces. Multi-tenancy and always-on soft-delete filtering are the two
cases that justify it.

```python title="registering a global scope"
Article.add_global_scope(lambda qs: qs.filter(deleted_at__isnull=True))

await Article.all()                    # WHERE deleted_at IS NULL
await Article.filter(plan="pro")       # WHERE plan = 'pro' AND deleted_at IS NULL
await Article.without_global_scopes()  # no filter
```

`RecordManager.get_queryset()` calls `apply_scopes()` on the fresh
queryset, so the filter lands on everything the manager creates —
verified for `.all()` and `.filter()` above.

`without_global_scopes()` returns a plain `RecordQuerySet` with no scopes
applied, and it still chains:

```python
await Article.without_global_scopes().filter(deleted_at__isnull=False)
```

Registration is per class and the registry is created lazily on the class
that calls `add_global_scope`. A subclass that has not registered
anything of its own inherits the parent's registry object — so adding a
scope from the subclass mutates the shared list and affects the parent
too. If a model hierarchy needs different global scopes per level,
register on each concrete class explicitly rather than relying on
inheritance.

###  Multi-tenancy with a global scope

The pattern global scopes exist for. Read the tenant from a contextvar
set by middleware, so the filter follows the request without every
handler remembering it.

```python title="tenant isolation"
from contextvars import ContextVar

current_tenant: ContextVar[int | None] = ContextVar("current_tenant", default=None)


async def tenant_middleware(request, response, call_next):
    token = current_tenant.set(int(request.headers["x-tenant-id"]))
    try:
        return await call_next()
    finally:
        current_tenant.reset(token)


def scope_to_tenant(queryset):
    tenant_id = current_tenant.get()
    if tenant_id is None:
        # Fail closed: no tenant means no rows, never all rows.
        return queryset.filter(id__isnull=True)
    return queryset.filter(tenant_id=tenant_id)


Invoice.add_global_scope(scope_to_tenant)
app.use(tenant_middleware)
```

:::caution[Fail closed, and reset the contextvar]
The `tenant_id is None` branch matters. If an unset tenant returns the
queryset unfiltered, a background job or a missed middleware path leaks
every tenant's data through an endpoint that looks correct in testing.
Return an impossible filter instead.

Resetting the contextvar in a `finally` matters for the same reason.
Without the reset, a worker task reusing the context can carry the
previous request's tenant.

And remember that `without_global_scopes()` bypasses this. Grep for it
before shipping a multi-tenant application, and keep its use confined to
deliberate admin paths.
:::

###  What global scopes do not cover

They apply to querysets built through the model manager. They do not
apply to raw SQL, to `connections.get(...).execute_query(...)`, to
`Model.raw()`, or to relation traversal from an already-loaded parent
object. A global tenant filter on `Invoice` does not filter
`await customer.invoices` — that traversal builds its queryset through
the relation, not the manager. For anything security-critical, the filter
must also exist in the schema or in an explicit `WHERE`.

##  Model lifecycle events

`HasEvents` provides a per-model event dispatcher with ten hook points:
`before_create`, `after_create`, `before_save`, `after_save`,
`before_update`, `after_update`, `before_delete`, `after_delete`,
`before_restore`, `after_restore`.

:::danger[Nothing in `sillo.record` fires these events]
`HasEvents` gives you `on()`, `observe()`, and `fire_event()`. No code
path in `Model.save()`, `create()`, `delete()`, `soft_delete()`, or
`restore()` calls `fire_event()`. A callback registered with
`@User.on("after_create")` is never invoked by creating a user.

This is verifiable in one line: register an `after_create` callback,
create a row, and the callback's side effect never happens.

`HasEvents` is also not part of `Model` — the base class inherits
`HasCasts` and `HasScopes` only. Mixing it in is necessary but not
sufficient.

Treat this as a registration API you must wire up yourself. The pattern
below does that.
:::

###  Wiring events up so they actually fire

Override `save()` and `delete()` on a base class of your own and fire the
events from there. This is roughly thirty lines and gives you the
behaviour the API promises.

```python title="myapp/base.py"
from sillo.record import HasEvents, Model


class EventedModel(HasEvents, Model):
    """Base model that actually dispatches lifecycle events."""

    class Meta:
        abstract = True

    async def save(self, *args, **kwargs):
        creating = not self._saved_in_db

        await self.fire_event("before_save", self)
        await self.fire_event(
            "before_create" if creating else "before_update", self
        )

        result = await super().save(*args, **kwargs)

        await self.fire_event(
            "after_create" if creating else "after_update", self
        )
        await self.fire_event("after_save", self)
        return result

    async def delete(self, *args, **kwargs):
        await self.fire_event("before_delete", self)
        result = await super().delete(*args, **kwargs)
        await self.fire_event("after_delete", self)
        return result
```

Note the mixin order — `HasEvents` before `Model` — for the same MRO
reason described in [Models & Mixins](/guides/record/models/). Then:

```python title="myapp/models.py"
class User(EventedModel):
    email = fields.CharField(max_length=255)


@User.on("before_create")
async def normalise_email(user):
    user.email = user.email.strip().lower()


@User.on("after_create")
async def send_welcome(user):
    await mailer.send_welcome(user.email)
```

Even with this wiring, the events cover `save()` and `delete()` only.
`bulk_create`, `bulk_upsert`, `upsert`, `queryset.update()`, and
`queryset.delete()` do not go through instance methods and will not fire
anything.

###  Observers

An observer groups related callbacks into one class. Any of the ten hook
names it defines is called; the rest are ignored.

```python title="an observer"
from sillo.record import ModelObserver


class UserObserver(ModelObserver):
    async def before_create(self, user):
        user.email = user.email.strip().lower()

    async def after_create(self, user):
        await audit_log(f"user {user.id} created")
        await search_index.add(user)

    async def after_delete(self, user):
        await search_index.remove(user.id)


User.observe(UserObserver())
```

Callbacks registered with `on()` fire before observers, and multiple
observers fire in registration order.

###  Exceptions in callbacks are swallowed

`EventDispatcher.fire` wraps each callback in `try/except Exception` and
logs with `logger.exception`. A `before_create` callback that raises does
**not** abort the save.

```python title="what actually happens"
@User.on("before_delete")
async def prevent_admin_deletion(user):
    if user.role == "admin":
        raise RuntimeError("cannot delete admins")   # logged, then ignored
```

That user is deleted. If you need a hook that can veto an operation, use
`ValidatesBeforeSaveMixin` (whose exception genuinely propagates) or
raise from your overridden `save()` outside the dispatcher.

The upside of the swallow is that a failing analytics callback cannot
take down a write path. The downside is that it is impossible to tell
from the caller whether every hook succeeded. Log aggressively inside
callbacks and alert on `sillo.record.events` error records.

###  Unknown event names are ignored

`EventDispatcher.on` checks `if event in self._listeners` before
appending. Registering `@User.on("after_creation")` — a typo — silently
does nothing. There is no error, no warning, and no way to notice except
that the callback never runs. Copy names from the table rather than
typing them.

###  Dispatchers are shared down an inheritance chain

`_events` is created lazily on the class where `on()` or `observe()` is
first called. A model subclassing another model that already has a
dispatcher shares it, so a callback registered on the parent also fires
for the child, and one registered on the child fires for the parent. If
you need per-class isolation, call `Model._ensure_events()` on each
concrete class before registering anything.

##  What not to do

**Do not name a scope after an existing model method.** `scope_active`
produces two different filters depending on how the chain starts.

**Do not let a global scope fail open.** An unresolved tenant must
produce zero rows, not all rows.

**Do not rely on global scopes for authorisation.** They cover manager
querysets only — not raw SQL, not relation traversal.

**Do not assume lifecycle events fire.** They do not, until you wire them
up.

**Do not use a `before_*` event to veto an operation.** Exceptions are
caught and logged.

**Do not put a slow call in a `before_save` hook.** It runs inside the
write path and, once you have wired dispatch into `save()`, inside any
transaction that save belongs to.

**Do not expect events from bulk operations.** `bulk_create`, `upsert`,
and `queryset.update()` bypass instance methods entirely.

##  Performance notes

Scopes cost nothing at runtime — a scope call is a Python function
returning a queryset, and the SQL is compiled once when the queryset is
awaited. Chaining ten scopes produces one query.

Global scopes run on every `get_queryset()`. Keep the callable cheap: a
contextvar read and a `filter()` is fine, a database lookup inside a
global scope means an extra query on every query.

Event dispatch is a dict lookup plus a loop over the registered
callbacks, all awaited sequentially. Ten callbacks each awaiting a
network call add their latency to the write. Push slow work onto a
background queue rather than doing it in an `after_save`.

##  API reference

| Name | Signature | Notes |
|---|---|---|
| `scope_<name>` | `(cls, queryset, *args, **kwargs) -> QuerySet` | Convention; classmethod |
| `Model.<name>()` | installed by `__init_subclass__` | Skipped if the name already exists |
| `add_global_scope` | `(scope: Callable) -> None` | Applies to every manager queryset |
| `without_global_scopes` | `() -> RecordQuerySet` | Bypasses all global scopes |
| `apply_scopes` | `(queryset) -> QuerySet` | Called by `RecordManager.get_queryset` |
| `ScopeRegistry.add` / `.remove` | `(scope) -> None` / `-> bool` | `remove` returns `False` if absent |
| `HasEvents.on` | `(event: str) -> decorator` | Unknown names silently ignored |
| `HasEvents.observe` | `(observer: ModelObserver) -> None` | Fires after `on()` callbacks |
| `HasEvents.fire_event` | `(event: str, instance) -> None` | You must call this yourself |

##  Related

- [Models & Mixins](/guides/record/models/) — mixin ordering, and `ValidatesBeforeSaveMixin` for hooks that can veto
- [Record Overview](/guides/record/) — setup and connection lifecycle
- [Casting & Collections](/guides/record/casting-collections/) — transforming values on read and write
- [Transactions & Factories](/guides/record/transactions-factories/) — wrapping multi-model writes
- [Events](/guides/events/) — sillo's application-level event emitter, which does fire on its own
- [Middleware](/guides/middleware/) — where tenant context gets established
