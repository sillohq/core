---
title: Customising the Admin
description: "Shaping the admin for real work: list columns, search, filters, ordering, page size, form fields, read-only fields, bulk actions and exports."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Customising the Sillo Admin
  - tag: meta
    attrs:
      property: og:description
      content: list_display, search_fields, list_filter, ordering, fields, readonly_fields and actions.
---

## The list

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["id", "title", "author", "status", "published_at"]
    list_display_links = ["title"]
```

Columns are shown in the order given. Each name is a field, a relation, or a
method on the `ModelAdmin` or the model.

Default is `["__str__"]`, one column, the row's string form.

`list_display_links` decides which columns are links to the detail page.
Without it the first column links. Naming `title` is usually better: a linked
`id` is a small target and a meaningless label.

### Computed columns

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "word_count"]

    @staticmethod
    def word_count(post):
        return len(post.body.split())
```

For anything derived. Keep it cheap. It runs once per row, and a method that
queries is an N+1 by construction.

### Relations cost a query each

```python
list_display = ["title", "author"]        # one query per row
```

Fix it in the queryset:

```python
@classmethod
def get_queryset(cls, queryset):
    return queryset.select_related("author")
```

`select_related` for forward foreign keys, `prefetch_related` for reverse and
many-to-many. At 50 rows a page the difference is 51 queries versus 2.

## Search

```python
search_fields = ["title", "body", "author__username"]
```

Adds the search box. Fields are matched case-insensitively and OR-ed together,
so one term searches all of them. `__`-spanning works.

An empty `search_fields` means no search box at all, not a box that finds
nothing.

Search is `LIKE '%term%'`. That cannot use a normal B-tree index, so on a large
table it is a full scan. For anything big, a trigram index (PostgreSQL) or a
real search service is the answer; the admin's box is for tables you can afford
to scan.

## Filters

```python
list_filter = ["status", "is_published", "author"]
```

Each becomes a filter control in the sidebar. Best on low-cardinality fields: a
status, a boolean, a foreign key with a handful of rows.

A filter on a field with thousands of distinct values produces a list with
thousands of entries, and the query to build it is not free. Use search for
those.

## Ordering

```python
ordering = ["-published_at", "id"]
```

The default sort. A leading `-` is descending.

Include a tiebreaker. `-published_at` alone is not a stable order if two rows
share a timestamp, and unstable ordering means rows appear on two pages or on
none. See [Pagination](/v0.x/orm/pagination/#ordering-is-not-optional).

Without `ordering`, the order is the database's, which is to say undefined.

## Page size

```python
list_per_page = 50
```

Defaults to 25. Higher means fewer clicks and slower pages; the cost is
usually the relations, not the row count, so fix
[`get_queryset`](#relations-cost-a-query-each) before lowering this.

## The form

```python
fields = ["title", "slug", "body", "status", "published_at"]
```

Which fields appear, and in what order. Without it, every editable field
appears in model order.

```python
exclude = ["deleted_at", "internal_notes"]
```

The inverse. `fields` wins if both are given. It is a whitelist, and honouring
a blacklist alongside it would be ambiguous.

Prefer `fields`. A column added next year appears in the form automatically
under `exclude`, and does not under `fields`. Same reasoning as
[`fillable` over `guarded`](/v0.x/orm/mass-assignment/#which-to-reach-for).

### Read-only fields

```python
readonly_fields = ["created_at", "updated_at", "slug"]
```

Shown, not editable. For values the system owns.

To let a field be set once and never changed:

```python
@classmethod
def get_readonly_fields(cls, add=False):
    return ["created_at"] if add else ["created_at", "slug"]
```

`add=True` is the create form.

### `save_on_top`

```python
save_on_top = True
```

A second save button above the form. Worth it for models with long forms, where
the only save button is a scroll away.

### Password fields

A [`PasswordField`](/v0.x/orm/fields/#passwordfield) is detected and rendered as a
password widget (reveal toggle, strength meter, confirmation) rather than a
text input, and the stored hash is never rendered back into the form.

## Bulk actions

```python
actions = ["delete_selected", "publish"]
```

Actions appear in a dropdown above the list and apply to the checked rows.
`delete_selected` is the default and the only bundled one.

Define your own as a method taking the queryset of selected rows:

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    actions = ["delete_selected", "publish"]

    @staticmethod
    async def publish(queryset):
        await queryset.update(status="published", published_at=now())
```

:::caution[`QuerySet.update()` skips the model layer]
It is set-based SQL: no [events](/v0.x/orm/events/), no
[casts](/v0.x/orm/casting/), no [validation](/v0.x/orm/mixins/#validatesbeforesavemixin),
and `updated_at` does not move unless you set it.

That is exactly what you want for a thousand rows, and exactly what you do not
want when a hook has to run. Loop and `save()` when it does, and think about
how many rows someone can select before you do.
:::

Deletion goes through the model, so a model with
[`CascadesDeletesMixin`](/v0.x/orm/mixins/#cascadesdeletesmixin) still cascades.

## Exports

Every list has a CSV and JSON export, with no configuration. It carries the
current filters, search and ordering, so it exports what you are looking at
rather than the whole table.

Both are recorded in the [activity log](/v0.x/orm/admin/#the-activity-log) with the
row count. Worth remembering: an export is a copy of production data leaving
the building, and the log is how you find out that it did.

## The dashboard

Shows the registered models and the recent activity. It is not configurable:
for anything bespoke, build a page in your own application, where you have the
full framework rather than the admin's templates.
