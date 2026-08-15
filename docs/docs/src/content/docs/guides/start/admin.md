---
title: The Admin Panel
description: Registering models, who is allowed in, the activity log, and why the admin uses your user model rather than one of its own.
head:
  - tag: meta
    attrs:
      property: og:title
      content: The Sillo Admin Panel
  - tag: meta
    attrs:
      property: og:description
      content: Registering models, who is allowed in, and why the admin uses your user model.
---

#  The Admin Panel

At `/admin/`. Note the trailing slash, the routes need it.

```bash
sillo user:admin ada@example.com ada
sillo serve --reload
```

Then sign in at <http://localhost:8000/admin/> with that email and
password.

##  One user model

There is no separate administrator account. Sign-in is checked against
your project's `User`, so people use their normal account, and adding a
field to `User` adds it everywhere.

That works because the admin's own default user model and yours both extend
`sillo.users.UserBaseModel`, the same `set_password`, `check_password` and
`verify_credentials`. Passing yours replaces the other outright rather than
adapting to it:

```python
admin = AdminSite(
    title="Myapp Admin",
    prefix=config.admin_prefix,
    user_model=User,
)
```

`database/config.py` therefore registers `sillo.admin.models` (the activity
log) but **not** `sillo.admin.default_user`:

```python
MODEL_MODULES = ["database.models", "sillo.admin.models"]
```

That second module holds `AdminUser` and `AdminRole`. Registering it would
create `admin_users` and `admin_roles` beside your `users`: a second set
of accounts to keep in step, or to forget about, that nothing would ever
write a row to.

:::note
**If you *want* the standalone admin user model** (an admin panel for a system
whose users are not the application's users) register that module and let
`AdminSite` use its default:

```python
MODEL_MODULES = ["database.models", "sillo.admin.models", "sillo.admin.default_user"]
```

```python
admin = AdminSite(title="Myapp Admin", prefix=config.admin_prefix)
```

Then run `sillo db:sillo user:admin users --apply`. You now maintain two sets of
accounts, deliberately.
:::

##  Registering models

In `app/admin.py`, inside `register_admin`:

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    verbose_name = "Posts"
    list_display = ["id", "title", "author_id", "published_at"]
    search_fields = ["title", "body"]
    list_filter = ["published_at"]
    readonly_fields = ["created_at"]
    ordering = ["-id"]
```

| Attribute | |
| --- | --- |
| `verbose_name` | What the sidebar calls it |
| `list_display` | Columns on the list page |
| `search_fields` | What the search box searches |
| `list_filter` | Fields offered as filters |
| `readonly_fields` | Shown but not editable |
| `ordering` | Default sort, `-` for descending |

:::caution
**Register before `admin.mount()`.** Mounting registers the user model
with a default presentation if nothing has claimed it yet, so registering
your `UserAdmin` first is what lets your columns and filters take effect.
:::

##  What the admin gives you per model

For every registered model, mounted under the admin's prefix:

| Route | |
| --- | --- |
| `/admin/<model>/` | List, with search, filters and pagination |
| `/admin/<model>/create/` | Create form |
| `/admin/<model>/<id>/` | Detail |
| `/admin/<model>/<id>/update/` | Edit form |
| `/admin/<model>/<id>/delete/` | Delete, with confirmation |
| `/admin/<model>/export/` | Export the current list |
| `/admin/<model>/bulk/` | Bulk actions |

`<model>` is the class name lowercased. `Post` becomes `/admin/post/`.

Password fields get a dedicated widget with a strength meter and a
confirmation field named `password__confirm`. Submitting the form without
the confirmation returns the form with "Passwords do not match" rather
than creating an account with an unverified password.

##  Who may enter

An account needs `is_staff`. `sillo user:admin` sets it, along with
`is_superuser`.

The rule is **active, and staff or superuser**, and it is checked at
sign-in *and* on every request:

```python
@staticmethod
def may_enter(user) -> bool:
    if not getattr(user, "is_active", True):
        return False
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
```

:::danger
**Why the flag is load-bearing.** With one shared user model, every
account that ever signed up holds a session. If a session alone were
enough to reach `/admin/`, the sign-up form would be the way in:

```text
POST /api/auth/register  ->  201
POST /api/auth/login     ->  200
GET  /admin/             ->  200      # read and write on every model
```

Anonymous requests were always redirected. It was specifically *any
signed-up account* that walked in.
:::

The account is read on each request rather than trusted from the session,
which carries only an identity and a display name. So clearing `is_staff`
or `is_active` takes effect on that person's **next request**, not at
their next sign-in.

###  Promoting and revoking

```python
from sillo.users.commands import find_user, set_staff

user = await find_user("ada@example.com", model=User)
await set_staff(user, True, model=User)     # let them in
await set_staff(user, False, model=User)    # and out again
```

Or edit the `is_staff` checkbox on the user's own admin page, which is why
`User` is registered in the admin at all.

##  The activity log

`sillo.admin.models` provides `AdminActivity`: who did what, to which
model, and when. It is registered by default and appears in the sidebar as
**Activity Log**.

```text
user_email                action    model_name   object_id
ada@example.com           login     User         —
ada@example.com           create    Users        7
ada@example.com           export    Users        —
```

Writes to it are best-effort (a failure to record must not fail the action
being recorded) so a missing table means the log is simply empty rather than
that the admin breaks.

###  Turning it off

Remove it from `MODEL_MODULES` and migrate:

```python
MODEL_MODULES = ["database.models"]
```

```bash
sillo db:make drop activity log --apply
```

The sidebar entry disappears with the table. That is deliberate: the admin
registers the log without knowing whether your application wanted it, so a
registered model with no table is a real case, and a nav link that leads
to a 500 is worse than no link.

:::note
**How the admin decides.** Whether a model is usable is asked **per request**,
by resolving a connection the way a query would, not at startup.

It cannot be asked at startup. `AdminSite.mount()` is called before
`setup_record` in a conventional application factory, because mounting
attaches auth middleware and middleware ordering forces it first. So the
admin's startup hook runs while the ORM is still uninitialised, and the
honest answer at that moment is always "no".

This is worth knowing if you write anything that hooks the admin's
startup.
:::

##  Permissions

`ModelAdmin` exposes three hooks, called per request:

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    def has_add_permission(self, request) -> bool:
        return request.user.is_superuser

    def has_change_permission(self, request) -> bool:
        return True

    def has_delete_permission(self, request) -> bool:
        return request.user.is_superuser
```

They control the buttons on the dashboard and the list page. Anything enforcing
a rule that matters should also be enforced in the model or the route. An admin
that hides a button has hidden a button.

The **query console** at `/admin/query/` is superuser-only regardless: it
grants read and write on every table, so being signed in is not enough.

##  Customising the site

```python
admin = AdminSite(
    title="Myapp Admin",          # header and browser tab
    prefix="/admin",              # from config.admin_prefix
    user_model=User,
    auth_backend=None,            # bring your own — see below
)
```

For authentication that is not sessions (SSO, LDAP, a proxy header) subclass
`AuthBackend`:

```python
from sillo.admin.auth import AuthBackend


class HeaderAuth(AuthBackend):
    async def authenticate(self, request) -> bool:
        return request.headers.get("X-Forwarded-Email") in ALLOWED

    async def get_user(self, request):
        return {"id": request.headers.get("X-Forwarded-Email"), "display_name": "SSO"}


admin = AdminSite(title="Myapp Admin", auth_backend=HeaderAuth())
```

A backend with no `user_model` is left alone by the checks that assume
one.

##  Disabling the admin

```bash
ADMIN_ENABLED=false
```

`app/bootstrap.py` reads `config.admin_enabled` and skips registration
entirely. Nothing is mounted, no middleware is added, and `/admin/` is a
404.

Useful for an API-only deployment of the same codebase.

##  Things that will bite you

1. **Trailing slashes.** `/admin/login/`, not `/admin/login`.

2. **The login field is named `email`.** It accepts an email or a
   username as the value, but a form posting `username=` fails silently.

3. **Register models before `admin.mount()`**, or the default
   presentation wins.

4. **The session middleware must stay**, even if the rest of the
   application moves to JWT. The admin authenticates through it.

5. **Registering the admin after the middleware block** makes every admin
   page 500 with "No Session Middleware Installed" while the session
   middleware is demonstrably installed. See
   [Project Structure](/guides/start/structure/#appbootstrappy).

##  Related

- [Users & Authentication](/guides/start/authentication/): the model the admin
  signs in
- [Database & Migrations](/guides/start/database/): what `MODEL_MODULES`
  decides
- [Project Structure](/guides/start/structure/): where `app/admin.py` sits
- [Middleware](/guides/middleware/): why registration order matters
