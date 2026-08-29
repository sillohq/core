---
title: The Admin Panel
description: "Mounting Sillo's admin panel: setup_admin, the routes it registers, what it auto-registers for you, and the first sign-in."
head:
  - tag: meta
    attrs:
      property: og:title
      content: The Sillo Admin Panel
  - tag: meta
    attrs:
      property: og:description
      content: Mounting the admin, the routes it adds, and signing in for the first time.
---

A browsable interface over your models: list, search, filter, create, edit,
delete, export.

```python
from sillo import SilloApp
from sillo.admin import ModelAdmin, setup_admin

app = SilloApp()
admin = setup_admin(app, title="Acme Admin")


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["id", "title", "status", "created_at"]
    search_fields = ["title", "body"]
    list_filter = ["status"]
```

Then `/admin/`.

## Setting it up

```python
setup_admin(
    app,
    title="Recorder Admin",
    prefix="/admin",
    auth_backend=None,
    user_model=None,
)
```

| Parameter | Meaning |
| --- | --- |
| `title` | Shown in the header and the browser tab |
| `prefix` | URL prefix for every admin route |
| `user_model` | The model people sign in as. Defaults to the admin's own `AdminUser`. |
| `auth_backend` | A full [auth backend](/v1.0/orm/admin-permissions/#authentication-backends). Overrides `user_model`. |

Returns the `AdminSite`, which is what you register models on.

### It needs a database

The admin reads and writes through the ORM, so [`setup_record`](/v1.0/orm/setup/)
has to have run, and `sillo.admin.models` must be in `model_modules`:

```python
setup_record(
    app,
    DatabaseConfig.from_env(),
    model_modules=["database.models", "sillo.admin.models"],
)
```

That module holds `AdminActivity`, the log every admin site writes to. Leave it
out and the first admin action fails on a missing table.

### Use your own user model

Almost always what you want: the people who administer a site are usually
people who use it, and one user model is one place to add a field, one password
policy, one set of rows:

```python
from database.models import User

admin = setup_admin(app, title="Acme Admin", user_model=User)
```

Any [`UserBaseModel`](/v1.0/guides/users/) subclass works.

## Mounting, step by step

`setup_admin` calls `AdminSite.mount`, which:

1. **Auto-registers the user model**, so you can always browse who can sign in.
2. **Registers the activity log**, `AdminActivity`.
3. **Adds the auth middleware**, which enforces sign-in on the whole prefix.
4. **Mounts the static files.** The admin's own CSS and JS.
5. **Builds the routes on startup**, not at mount time.

That last point matters: routes are built **on startup**, so every
`@admin.register` that runs during import is included. Registering a model
after startup has no effect.

`AdminRole` is deliberately *not* auto-registered. It only exists if you use
the admin's own user model, and most projects do not. Register it yourself if
you do.

## The routes

Per site:

| Path | Purpose |
| --- | --- |
| `/admin/login/` | Sign in |
| `/admin/logout/` | Sign out |
| `/admin/` | Dashboard, with recent activity |
| `/admin/query/` | The SQL query console |

And per registered model, where `post` is the lowercased class name:

| Path | Methods | Purpose |
| --- | --- | --- |
| `/admin/post/` | GET | List |
| `/admin/post/create/` | GET, POST | Create |
| `/admin/post/export/` | GET | Export as CSV or JSON |
| `/admin/post/{id}/` | GET | Detail |
| `/admin/post/{id}/update/` | GET, POST | Edit |
| `/admin/post/{id}/delete/` | GET, POST | Delete |
| `/admin/post/bulk/` | POST | Bulk actions |

Each is named (`admin-post-list`, `admin-post-detail`) so `url_for` works.

:::caution[The slug is the class name]
Two models with the same class name in different modules produce the same path,
and the second registration wins. Rename one.
:::

## Signing in

Create an administrator from the CLI:

```bash
sillo user:admin you@example.com
```

That sets `is_staff`, which is the flag the admin checks. Being signed in is
not enough. See [Permissions](/v1.0/orm/admin-permissions/).

## Exports

Every list has an export, and it carries the filters, search and ordering you
are currently looking at. So "export what I am looking at" does that, rather
than exporting the whole table.

CSV and JSON. Both are recorded in the activity log with the row count.

## The query console

`/admin/query/` runs SQL against the application's database.

It is powerful and it is exactly as dangerous as that sounds: anyone who can
reach it can read every row in your database, and depending on your database
user's grants, write them too. Restrict who can get in
([Permissions](/v1.0/orm/admin-permissions/)), and consider disabling the admin
entirely in production if nobody needs it there:

```python
if config.admin_enabled:
    admin = setup_admin(app, title="Acme Admin", user_model=User)
```

## The activity log

Every create, update, delete and export is recorded in `AdminActivity`, with
the user's email, the model, the object id, the IP address and the user agent.
The dashboard shows the recent entries.

It records what the **admin** did. It is not a general audit log. Nothing
outside the admin writes to it.

## Next

- [Registering models](/v1.0/orm/admin-registering/): `ModelAdmin` and what it
  controls.
- [Customising](/v1.0/orm/admin-customising/): lists, search, filters, forms.
- [Permissions and auth](/v1.0/orm/admin-permissions/): who gets in, and to what.
