---
title: Permissions
description: sillo's full permission system — define, assign, revoke, check, and organize permissions. Covers direct user permissions, group-inherited permissions, the PermissionMixin, caching, batch operations, queries, and startup seeding.
head:
- tag: meta
  attrs:
    property: og:title
    content: Permissions in sillo
- tag: meta
  attrs:
    property: og:description
    content: Full sillo permission system — direct assignments, group inheritance, PermissionMixin, caching, queries, and seeding.
---

# Permissions

`sillo.permissions` is a DB-backed permission system that ships as an optional but fully integrated module. It gives you:

- **Named permissions** — any string like `"posts:create"` or `"view_dashboard"`.
- **Direct user assignment** — grant and revoke individual permissions to users.
- **Group inheritance** — assign permissions to a group, and every member gets them automatically.
- **One-call cache** — `load_permissions()` loads direct + inherited permissions into a `set`, then `has_permission(…)` is a pure Python lookup.
- **Auto-wired login** — `UserBaseModel.load_user` and `verify_credentials` already call `load_permissions()` when the mixin is present.

---

## Quick start

```python
from sillo.permissions import PermissionMixin, Permission
from sillo.users import UserBaseModel

# 1. Mixin FIRST (before UserBaseModel)
class Account(PermissionMixin, UserBaseModel):
    class Meta:
        table = "accounts"

# 2. Define permissions (idempotent — safe to run on every startup)
await Permission.define("posts:create")
await Permission.define("posts:edit")
await Permission.define("posts:delete")

# 3. Grant to users
await Permission.assign(user, "posts:create")
await Permission.assign(admin, "posts:create", "posts:edit", "posts:delete")

# 4. Check
await user.load_permissions()
user.has_permission("posts:create")   # True
user.has_permission("posts:delete")   # False
```

---

## Permission model

A `Permission` is just a named row in the `permissions` table. There is no dotted-convention requirement — any string is valid.

### Define

```python
# Idempotent — returns existing or creates new
perm = await Permission.define("users:read", "Can read user profiles")
```

`define` is safe to call on every app startup. It creates only rows that don't already exist.

### Look up

```python
perm = await Permission.get_or_none(name="users:read")
all_perms = await Permission.all()
```

---

## Direct user permissions

### Assign

```python
# Single
await Permission.assign(user, "posts:create")

# Batch — multiple names at once
await Permission.assign(user, "posts:create", "posts:edit", "posts:delete")
```

Each unknown permission name is auto-defined, so callers can `assign` without a separate `define` step.

The `user` argument accepts:

- A model instance with `.identity` (any `UserBaseModel` / `UserProtocol` subclass).
- A raw identity string.

### Revoke

```python
# Single
await Permission.revoke(user, "posts:create")

# Batch
await Permission.revoke(user, "posts:edit", "posts:delete")

# Revoking a nonexistent permission is a no-op
await Permission.revoke(user, "nobody_has_this")
```

### Check (DB query, no cache)

```python
await Permission.has(user, "posts:create")   # True / False
```

### Enumerate

```python
names = await Permission.of(user)            # ["posts:create", "posts:edit"]
```

### Find holders

```python
identities = await Permission.holders("posts:delete")   # ["1", "3", "7"]
```

---

## Groups

Groups bundle permissions so every member inherits them. A user can belong to any number of groups, and groups can have any number of members.

### Create

```python
from sillo.permissions import Group

admins = await Group.get_or_create("admins", "System administrators")
editors = await Group.get_or_create("editors")
```

`Group.get_or_create` is idempotent — it returns the existing group if one with that name already exists.

### Membership

```python
await admins.add_user(user)
await admins.remove_user(other_user)
await admins.has_user(user)            # True / False
await admins.get_members()             # ["1", "2"] identity strings
await admins.get_member_count()        # 2
```

The `user` argument accepts a model instance or a raw identity string — same as `Permission.assign`.

### Group permissions

```python
# Assign — auto-defines the permission if needed
await editors.add_permissions("posts:create", "posts:edit")

# Revoke
await editors.remove_permissions("posts:delete")

# Query
await editors.get_permissions()        # ["posts:create", "posts:edit"]
await editors.has_permission("posts:create")   # True
```

### Queries

```python
# Groups a user belongs to
groups = await Group.of_user(user)          # [Group, Group, …]
names  = await Group.names_of_user(user)    # ["admins", "editors"]

# Permissions assigned to a group (via Permission model)
from sillo.permissions import Permission
perms  = await Permission.of_group(editors)  # ["posts:create", "posts:edit"]
```

---

## PermissionMixin

`PermissionMixin` is the bridge between the DB permission tables and the user model. It resolves **two sources** into a single cache:

1. **Direct** — from `UserPermission` rows (set via `Permission.assign`).
2. **Inherited** — from `GroupPermission` rows for every group the user belongs to.

### Usage

```python
from sillo.permissions import PermissionMixin
from sillo.users import UserBaseModel

class Account(PermissionMixin, UserBaseModel):
    ...
```

**MRO requirement.** `PermissionMixin` **must** come before `UserBaseModel` in the class bases:

| Inheritance | Result |
|---|---|
| `class Account(PermissionMixin, UserBaseModel)` | ✅ Mixin takes precedence |
| `class Account(UserBaseModel, PermissionMixin)` | ❌ Base class shadows mixin |

### Methods

| Method | Returns | Description |
|---|---|---|
| `load_permissions()` | `set[str]` | Fetches direct + group-inherited permissions from DB, caches internally |
| `has_permission(perm)` | `bool` | Cache check. `False` if inactive, `True` if superuser |
| `has_perm(perm)` | `bool` | Alias — delegates to `has_permission` |
| `get_groups()` | `list[str]` | Names of all groups this user belongs to |
| `is_in_group(name)` | `bool` | Check group membership by name |
| `get_group_permissions()` | `set[str]` | Permission names inherited through groups (excludes direct) |

### Permission resolution rules

```
has_permission("x") →
    if not is_active       → False
    if is_superuser        → True
    if "x" in _perm_cache  → True
    else                   → False
```

Where `_perm_cache` = `direct_permissions | group_inherited_permissions`.

### Cache lifecycle

`load_permissions()` is called automatically when:

- `UserBaseModel.load_user(identity)` resolves a user (login via middleware).
- `UserBaseModel.verify_credentials(…)` authenticates credentials.

You can also call it manually to refresh after changing assignments:

```python
await Permission.assign(user, "new_role")
await user.load_permissions()          # refresh cache
user.has_permission("new_role")        # True
```

---

## Startup seeding

A typical app defines permissions and seeds groups once at startup:

```python
# app/startup.py or a lifespan hook
from sillo.permissions import Permission, Group

async def seed_permissions():
    # 1. Define all possible permissions
    await Permission.define("posts:create")
    await Permission.define("posts:edit")
    await Permission.define("posts:delete")
    await Permission.define("posts:publish")
    await Permission.define("users:read")
    await Permission.define("users:write")
    await Permission.define("settings:read")
    await Permission.define("settings:write")

    # 2. Create groups and bundle permissions
    admins = await Group.get_or_create("admins", "Full system access")
    await admins.add_permissions(
        "posts:create", "posts:edit", "posts:delete", "posts:publish",
        "users:read", "users:write",
        "settings:read", "settings:write",
    )

    editors = await Group.get_or_create("editors", "Content editors")
    await editors.add_permissions("posts:create", "posts:edit", "posts:publish")

    viewers = await Group.get_or_create("viewers", "Read-only access")
    await viewers.add_permissions("posts:read")
```

Then in your user registration or admin flow, assign users to groups:

```python
await admins.add_user(new_admin)
```

---

## Using with useAuth

Permissions integrate with route-level gating through `useAuth`:

```python
from sillo.auth import useAuth

@app.get("/posts", auth=useAuth(permissions=["posts:read"]))
async def list_posts(request, response):
    ...

@app.delete("/posts/{id}", auth=useAuth(permissions=["posts:delete"]))
async def delete_post(request, response, id: int):
    ...
```

`useAuth(permissions=[…])` calls `user.has_permission(perm)` for every string in the list. They all must pass. If any fails the route raises `403 PermissionDenied`.

---

## Complete example

```python
from sillo.permissions import PermissionMixin, Permission, Group
from sillo.users import UserBaseModel, UserManager
from sillo.users.password import make_password

class Account(PermissionMixin, UserBaseModel):
    objects = UserManager()

    class Meta:
        table = "accounts"

# ── Startup ──────────────────────────────────────────────────────
await Permission.define("files:upload")
await Permission.define("files:delete")

premium = await Group.get_or_create("premium")
await premium.add_permissions("files:upload", "files:delete")

# ── Registration ─────────────────────────────────────────────────
alice = await Account.create(
    email="alice@x.com",
    username="alice",
    password=make_password("secret"),
)

# Give Alice a bonus permission directly
await Permission.assign(alice, "files:upload")
await premium.add_user(alice)

# ── On login ─────────────────────────────────────────────────────
loaded = await Account.load_user(str(alice.id))
# load_permissions() was called automatically by load_user

loaded.has_permission("files:upload")    # True — direct
loaded.has_permission("files:delete")    # True — inherited from premium
loaded.has_permission("files:share")     # False
loaded.is_in_group("premium")            # True
```

---

## Reference

### Import paths

```python
from sillo.permissions import (
    Permission,          # Model: define, assign, revoke, of, has, holders, of_group
    UserPermission,      # Join table (user ↔ permission), not typically used directly
    Group,               # Model: get_or_create, add_user, add_permissions, etc.
    UserGroup,           # Join table (user ↔ group), not typically used directly
    GroupPermission,     # Join table (group ↔ permission), not typically used directly
    PermissionMixin,     # Mixin: load_permissions, has_permission, has_perm, get_groups, is_in_group, get_group_permissions
)
```

### Batch operations

| Operation | Syntax |
|---|---|
| Define | `Permission.define(name)` |
| Assign (user) | `Permission.assign(user, *names)` |
| Revoke (user) | `Permission.revoke(user, *names)` |
| Check (user) | `Permission.has(user, name)` |
| Enumerate (user) | `Permission.of(user)` |
| Holders | `Permission.holders(name)` |
| Create group | `Group.get_or_create(name, description=None)` |
| Group add user | `group.add_user(user)` |
| Group remove user | `group.remove_user(user)` |
| Group assign perms | `group.add_permissions(*names)` |
| Group revoke perms | `group.remove_permissions(*names)` |
| Group permissions | `group.get_permissions()` / `group.has_permission(name)` |
| Group members | `group.get_members()` / `group.has_user(user)` / `group.get_member_count()` |
| User's groups | `Group.of_user(user)` / `Group.names_of_user(user)` |
| Group perms (Permission) | `Permission.of_group(group)` |

### Related

- [Protecting Routes](/guides/protecting-routes/) — route-level gating with `useAuth`
- [Users & User Models](/guides/users/) — user base model, custom user classes
- [Authentication](/guides/authentication/) — middleware + backend model
