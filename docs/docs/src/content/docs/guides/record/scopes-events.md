---
title: Scopes & Events
description: Local/global query scopes, model lifecycle events, and observers — deep production reference.
---

# Scopes & Events

## Query Scopes

Query scopes let you define reusable query constraints that can be
chained on querysets.  This is inspired by Laravel's query scopes.

Scopes work because Tortoise querysets are immutable and chainable —
every `.filter()` or `.order_by()` call returns a new queryset.
Scopes are simply class methods that receive a queryset and return
a modified one.

### Local Scopes

Define methods with any name (convention: `scope_` prefix) that take
a queryset as the first argument:

```python
from sillo.record import Model, HasScopes
from tortoise import fields

class User(Model, HasScopes):
    email = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    plan = fields.CharField(max_length=50, default="free")
    created_at = fields.DatetimeField(auto_now_add=True)

    @classmethod
    def scope_active(cls, queryset):
        return queryset.filter(is_active=True)

    @classmethod
    def scope_vip(cls, queryset):
        return queryset.filter(plan__in=["pro", "enterprise"])

    @classmethod
    def scope_recent(cls, queryset, days: int = 7):
        from datetime import datetime, timedelta, timezone
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return queryset.filter(created_at__gte=since)

    @classmethod
    def scope_search(cls, queryset, query: str):
        return queryset.filter(
            Q(email__icontains=query) | Q(name__icontains=query)
        )

# Chain scopes:
users = await User.active().vip().recent(30).all()
# SQL: SELECT * FROM users WHERE is_active=true AND plan IN ('pro','enterprise')
#      AND created_at >= NOW() - INTERVAL '30 days'
```

### Global Scopes

Global scopes are automatically applied to EVERY query on a model.
Use them for multi-tenancy, soft-deletes, or audit trails:

```python
class TenantModel(Model, HasScopes):
    tenant_id = fields.IntField()

    @classmethod
    def scope_current_tenant(cls, queryset):
        # Assume current_tenant_id is set in middleware/DI
        from sillo.context import get_current_tenant_id
        tenant_id = get_current_tenant_id()
        return queryset.filter(tenant_id=tenant_id)

# Apply globally:
TenantModel.add_global_scope(TenantModel.scope_current_tenant)

# Every query now auto-filters:
users = await TenantModel.all()  # WHERE tenant_id = ?

# Bypass when needed (admin panel):
users = await TenantModel.without_global_scopes().all()
```

`without_global_scopes()` returns a normal queryset, so you can keep chaining:

```python
users = await TenantModel.without_global_scopes().filter(tenant_id=42)
```

## Model Events

Lifecycle events let you hook into specific moments in a model's
lifecycle.  They are Python-side callbacks — they do NOT use
database triggers.

### Available Events

| Event | Fires |
|---|---|
| `before_create` | Before INSERT |
| `after_create` | After INSERT |
| `before_save` | Before INSERT or UPDATE |
| `after_save` | After INSERT or UPDATE |
| `before_update` | Before UPDATE |
| `after_update` | After UPDATE |
| `before_delete` | Before DELETE |
| `after_delete` | After DELETE |
| `before_restore` | Before clearing deleted_at |
| `after_restore` | After clearing deleted_at |

### Event Callbacks

```python
from sillo.record import Model, HasEvents

class User(Model, HasEvents):
    email = fields.CharField(max_length=255)

@User.on("before_create")
async def normalize_email(instance):
    instance.email = instance.email.lower().strip()

@User.on("after_create")
async def send_welcome_email(instance):
    await email_service.send_welcome(instance.email)

@User.on("before_delete")
async def prevent_admin_deletion(instance):
    if instance.role == "admin":
        raise RuntimeError("Cannot delete admin users")
```

### Observers

Group related handlers into a single class:

```python
from sillo.record import ModelObserver

class UserObserver(ModelObserver):
    async def before_create(self, user):
        user.email = user.email.lower()

    async def after_create(self, user):
        await audit_log(f"Created user {user.id}")
        await search_index.index(user)

    async def before_delete(self, user):
        await user.posts.all().delete()
        await search_index.remove(user.id)

User.observe(UserObserver())
```

Observers are registered per-model class.  Multiple observers can be
registered on the same model — they fire in registration order.
