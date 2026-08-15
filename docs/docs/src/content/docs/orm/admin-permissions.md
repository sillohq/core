---
title: Admin Permissions & Auth
description: "Who gets into the admin and what they may do. The is_staff gate, the four permission hooks, non-superuser access, auth backends, and the activity log."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Admin Permissions and Authentication
  - tag: meta
    attrs:
      property: og:description
      content: The is_staff gate, has_*_permission hooks, custom auth backends and the audit log.
---

Two separate questions: **who may enter the admin at all**, and **what they may
do once inside**.

## Getting in

```bash
sillo user:admin you@example.com
```

Signing in is not enough. When the admin shares your application's user model
(the ordinary arrangement) every registered account holds a session, and
admitting anyone with a session would hand the whole database to whoever last
filled in the sign-up form.

The gate is:

```python
user.is_active and (user.is_staff or user.is_superuser)
```

An inactive account is refused regardless of its flags. That is what makes
`sillo user:active someone@example.com --off` an effective off switch for admin
access as well as for sign-in.

```bash
sillo user:staff someone@example.com            # grant
sillo user:staff someone@example.com --revoke   # revoke
```

The check runs on **every request**, from the current row, not from something
stamped into the session at sign-in. So revoking access takes effect on the
next click, without waiting for a session to expire.

## What they may do

Four hooks on every `ModelAdmin`:

```python
@staticmethod
def has_view_permission(request) -> bool
@staticmethod
def has_add_permission(request) -> bool
@staticmethod
def has_change_permission(request, obj=None) -> bool
@staticmethod
def has_delete_permission(request, obj=None) -> bool
```

All return `True` by default: any staff user may do anything to any registered
model. Override them to narrow it.

`obj` is the row for change and delete, and `None` when the question is about
the model in general, rendering the "Add" button, say.

### Non-superuser access

This is the common requirement: staff can work, but only a superuser can
destroy.

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    @staticmethod
    def has_delete_permission(request, obj=None):
        return bool(getattr(request.user, "is_superuser", False))
```

Read-only for most, editable for a few:

```python
@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    @staticmethod
    def has_add_permission(request):
        return False

    @staticmethod
    def has_change_permission(request, obj=None):
        return bool(getattr(request.user, "is_superuser", False))

    @staticmethod
    def has_delete_permission(request, obj=None):
        return False
```

Hiding a model from non-superusers entirely:

```python
@staticmethod
def has_view_permission(request):
    return bool(getattr(request.user, "is_superuser", False))
```

### Using the permissions system

For anything more granular than a superuser flag, wire the hooks to
[Sillo's permissions](/guides/permissions/):

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    @staticmethod
    def has_change_permission(request, obj=None):
        return request.user.has_permission("posts.edit")

    @staticmethod
    def has_delete_permission(request, obj=None):
        return request.user.has_permission("posts.delete")
```

Permissions have to be loaded before `has_permission` can answer: see
[Permissions](/guides/permissions/). Loading them in middleware, once per
request, keeps these hooks free.

### Per-object rules

`obj` is what makes ownership checks possible:

```python
@staticmethod
def has_change_permission(request, obj=None):
    if getattr(request.user, "is_superuser", False):
        return True
    if obj is None:
        return True                       # may reach the list
    return obj.author_id == request.user.id
```

:::caution[Per-object checks do not filter the list]
The hooks control **actions**, not visibility of rows. Returning `False` for
someone else's post stops them editing it; the row is still listed, and its
detail page still renders.

[`get_queryset`](/orm/admin-registering/#get_queryset) is what filters rows,
and it does not receive the request, so it cannot filter by user.

The honest conclusion: **the admin is not built for per-user data isolation.**
If different staff must see different rows, build that screen in your
application, where the request is available throughout.
:::

## What the hooks affect

`has_*_permission` is checked in two places: before the action runs, and when
rendering. A user without `has_add_permission` does not see the Add button and
cannot reach the create route by typing the URL.

Not covered by the per-model hooks:

- **The dashboard**: any staff user sees it.
- **The query console** at `/admin/query/`, which is checked as a view
  permission on the model being queried, not per user.
- **Exports**, which follow `has_view_permission`.

## The query console

`/admin/query/` runs SQL against your database. Anyone who reaches it can read
every row, and can write them if your database user is allowed to.

There is no separate permission for it. If that is not acceptable, do not mount
the admin where it is reachable:

```python
if config.admin_enabled:
    admin = setup_admin(app, title="Acme Admin", user_model=User)
```

```bash
ADMIN_ENABLED=false
```

## Authentication backends

The default is `SessionAuth`, over
[Sillo's session middleware](/guides/sessions/). Sign-in verifies the password
against the user model and stores the id in the session.

Replace it wholesale by subclassing `AuthBackend`:

```python
from sillo.admin.auth import AuthBackend


class SsoAuth(AuthBackend):
    async def authenticate(self, request): ...
    async def get_user(self, request): ...
    async def login(self, request, username, password): ...
    async def logout(self, request): ...

    @property
    def middleware(self):
        return self._middleware


admin = setup_admin(app, auth_backend=SsoAuth())
```

`middleware` is what enforces sign-in across the prefix. The backend supplies
it, so an SSO backend can redirect to an identity provider rather than to a
form.

:::note[`auth_backend` overrides `user_model`]
Passing both means `user_model` is ignored. Build the backend with the model
instead:

```python
from sillo.admin.auth import SessionAuth

admin = setup_admin(app, auth_backend=SessionAuth(user_model=User))
```
:::

## The activity log

Every create, update, delete and export is written to `AdminActivity`:

| Column | |
| --- | --- |
| `user_email` | Who |
| `action` | What |
| `model_name`, `object_id` | To what |
| `detail` | Extra context. An export's format and row count |
| `ip_address`, `user_agent` | From where |

Recent entries appear on the dashboard.

Two limits worth stating. It records what the **admin** did. Nothing else
writing to your database appears in it. And it is an ordinary table, so someone
with the query console can read it and, given the right grants, change it. It
is a record for you, not evidence against a determined insider.

## A checklist

- Grant `is_staff` deliberately, and audit it. `sillo user:list --staff`.
- Reserve deletion for superusers on anything you cannot recreate.
- Turn the admin off in environments where nobody needs it.
- Put it behind whatever network controls you already have: the admin is a full
  database client with a web interface.
- Watch the activity log for exports.
