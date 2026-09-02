---
title: Resources
description: One model's whole surface — and what you get from naming nothing but the model.
---

A `Resource` is one model and everything the admin does with it.

```python
admin.add(Resource(
    Post,
    label="Post", plural="Posts", icon="file-text", group="Content",
    list=List(...), form=Form(...), detail=Detail(...),
    access=Access(view=True, add="post.add", delete=False),
    scope=Scope.tenant("team_id"),
))
```

## Everything is optional but the model

```python
admin.add(Resource(Post))
```

That is a working list, form and detail page, derived at mount from the model's
own columns. It is the difference between an admin you can point at a new model
in ten seconds and one you configure before you can look at anything.

What is derived:

| | |
|---|---|
| **Label and plural** | `BlogPost` → "Blog post" / "Blog posts". English regulars plus the common irregulars; `plural=` for anything else |
| **Slug** | `/admin/blog-post` |
| **Permissions** | `blog-post.view`, `.add`, `.change`, `.delete` |
| **List** | identity first, then state, then time — capped at seven columns |
| **Filters** | a search box over the text columns, a chip per state column, one date range |
| **Ordering** | newest first when there is a timestamp, else the key descending |
| **Form** | every writable column, with the timestamps in a collapsed *Audit* group |
| **Detail** | the form's fields, plus a window onto each child table |

Every one of those is replaced by naming it, and nothing fights a declaration
that exists.

## Naming things

```python
Resource(
    ClassRoom,
    label="Class",
    plural="Classes",
    # Without these the slug is `class-room`, and so is every permission.
    slug="class",
    stem="class",
)
```

`slug` is the URL segment; `stem` is what the four permissions are named after.
They are separate because a URL and a permission name change for different
reasons.

## Flags versus access

```python
Resource(Payment, creatable=False, editable=False)
```

A flag is a statement about the **model** — a row created by a job and never by
hand — and it holds however the permissions are set. `Access` is a statement
about a **person**. Both are applied, and the flag wins:

```python
Resource(Post, creatable=False, access=Access(add="post.add"))
# → nobody may add, whatever permissions they hold
```

## A queryset of its own

`queryset=` is the resource's own idea of what it manages; `scope=` is this
person's slice of it. Both are applied, in that order, before anything reads a
row.

```python
Resource(
    Order,
    queryset=lambda ctx, rows: rows.filter(archived=False),
    scope=Scope.tenant("team_id"),
)
```

Skipping either is a leak. See [Permissions](/packages/warder/permissions/).

## crud(), for the shape most reference tables want

```python
from warder import crud

for model in (Tag, Category, Region):
    admin.add(crud(model, "name", "slug", group="Reference"))
```

A convenience, not a layer: it returns an ordinary `Resource` you can take
apart with `.with_()`.
