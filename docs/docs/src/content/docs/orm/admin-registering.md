---
title: Registering Models
description: "Putting a model in the admin: the register decorator, the ModelAdmin class, its full attribute set, and where registration should live."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Registering Models in the Sillo Admin
  - tag: meta
    attrs:
      property: og:description
      content: The register decorator, ModelAdmin, and its attributes.
---

```python
from sillo.admin import ModelAdmin


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["id", "title", "status", "created_at"]
```

Or without a decorator:

```python
admin.register(Post, PostAdmin)
```

Both forms exist because a decorator reads better next to a class and the
direct call is what you need when the pair is built dynamically.

## The minimum

```python
@admin.register(Tag)
class TagAdmin(ModelAdmin):
    pass
```

Every default applies: rows shown by `__str__`, no search, no filters, 25 per
page, delete as the only bulk action.

Which is worth doing for reference tables, and worth spending five more lines
on for anything you will actually work in.

:::tip[Give the model a `__str__`]
Without one, every row reads `Post object (4)`. `__str__` is what the list
shows by default, what a foreign key renders as in a form, and what the
activity log names.
:::

## The attributes

| Attribute | Default | Controls |
| --- | --- | --- |
| `verbose_name` | class name | The label in the sidebar |
| `list_display` | `["__str__"]` | Columns in the list |
| `list_display_links` | `[]` | Which columns link to the detail page |
| `list_filter` | `[]` | Fields offered as filters |
| `search_fields` | `[]` | Fields the search box looks in |
| `ordering` | `[]` | Default sort |
| `list_per_page` | `25` | Rows per page |
| `actions` | `["delete_selected"]` | Bulk actions |
| `fields` | `None` | Fields on the form, in order |
| `exclude` | `None` | Fields kept off the form |
| `readonly_fields` | `[]` | Shown but not editable |
| `save_on_top` | `False` | A second save button above the form |

A realistic one:

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    verbose_name = "Posts"
    list_display = ["id", "title", "author", "status", "published_at"]
    list_display_links = ["title"]
    list_filter = ["status", "author"]
    search_fields = ["title", "body"]
    ordering = ["-published_at"]
    list_per_page = 50
    readonly_fields = ["created_at", "updated_at"]
    exclude = ["deleted_at"]
```

Each is covered in [Customising](/orm/admin-customising/).

## Overriding the getters

Every attribute has a classmethod behind it, so anything that has to be
computed can be:

```python
@classmethod
def get_list_display(cls): ...
@classmethod
def get_search_fields(cls): ...
@classmethod
def get_list_filter(cls): ...
@classmethod
def get_ordering(cls): ...
@classmethod
def get_fields(cls, add=False): ...
@classmethod
def get_readonly_fields(cls, add=False): ...
@classmethod
def get_queryset(cls, queryset): ...
```

`get_fields` and `get_readonly_fields` take `add` (`True` on the create form,
`False` on edit) which is how a field is settable once and read-only
afterwards:

```python
@classmethod
def get_readonly_fields(cls, add=False):
    return [] if add else ["slug"]
```

### `get_queryset`

The one you will reach for most. It filters what the admin can see at all:

```python
@classmethod
def get_queryset(cls, queryset):
    return queryset.filter(deleted_at__isnull=True)
```

```python
@classmethod
def get_queryset(cls, queryset):
    return queryset.select_related("author").prefetch_related("tags")
```

That second form is worth doing whenever `list_display` names a relation.
Without it the list issues one query per row to render the author column, the
classic N+1, and very visible at 50 rows a page.

:::caution[`get_queryset` takes no request]
It is a classmethod over the queryset alone, so it cannot filter by the signed-
in user. Per-user scoping is not something this hook can express.

The permission methods *do* receive the request. See
[Permissions](/orm/admin-permissions/). Use those to decide whether someone may
see a model at all, and keep genuinely per-user data out of the admin.
:::

## Where registration lives

The routes are built **on startup**, so every registration has to have run by
then. The reliable place is a module imported during application assembly:

```python
# app/admin.py
from sillo.admin import ModelAdmin
from app.bootstrap import admin
from database.models import Post, Tag, User


@admin.register(Post)
class PostAdmin(ModelAdmin):
    ...
```

```python
# app/bootstrap.py
def create_app():
    app = SilloApp()
    ...
    admin = setup_admin(app, title="Acme Admin", user_model=User)
    import app.admin  # noqa: F401 — registers the models
    return app
```

The starter does this for you. Registering after startup silently does nothing:
the model is in the registry, and no routes exist for it.

## What is registered for you

- **The user model**, always: the site cannot authenticate without one, and
  browsing who can sign in is something every admin needs.
- **`AdminActivity`**, the log.

`AdminRole` is not, since it only applies if you use the admin's own user
model. Register it yourself if you do.

To replace the auto-registered user admin, register your own. Yours is what the
registry ends up holding:

```python
@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ["id", "email", "username", "is_staff", "is_active"]
    search_fields = ["email", "username"]
    list_filter = ["is_staff", "is_active"]
    readonly_fields = ["password", "created_at"]
```
