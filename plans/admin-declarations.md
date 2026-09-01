# A declaration system for `sillo.admin`

**Status:** proposal · **Replaces:** the `ModelAdmin` class-attribute style ·
**Compatible:** yes, both work during one release cycle

---

## 1. The rule this is built on

> **A type annotation in Sillo describes a type. It never selects behaviour.**

Nothing in this design reads `__annotations__`, and nothing changes because a
parameter is spelled one way rather than another. Every behaviour is asked for
in an argument you can see.

Where a value must be injected, it is injected the way the framework already
does it — as a **default value**, like `db=Depend(get_db)` — which is a value,
not an annotation.

### One place this rule is currently broken

`sillo-graphql` decides which resolver parameters to inject by reading their
annotations: `ctx: HttpContext` is injected, `limit: int` becomes a GraphQL
argument. That is exactly the pattern this document forbids, and it should be
brought in line — a `ctx=Ctx()` default marker does the same job as a value.
It is out of scope here, but it is the same decision and should be made once.

---

## 2. What is wrong with the current style

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["id", "title", "author"]
    list_display_links = ["title"]
    search_fields = ["title", "body"]
    list_filter = ["status"]
    readonly_fields = ["created_at"]
    actions = ["publish"]
```

**It is a namespace of magic names.** Fifteen class attributes whose meaning
you cannot derive from anything — `list_display_links` is a subset of
`list_display`, `fields` and `exclude` are mutually exclusive, `actions` holds
method names. Nothing tells you that except documentation.

**It is stringly-typed with no validation.** `"titel"` is a typo that renders
an empty column at request time. Nothing checks it at startup.

**It cannot be built.** Registering forty models with the same three columns
means forty near-identical class bodies. There is no way to write the shape
once and apply it.

**It cannot be composed.** A class attribute cannot be extended without
subclassing, and subclassing merges by MRO rather than by intent.

**Three of its promises are not kept.** Verified by reading the package:

| | |
|---|---|
| `actions = ["publish"]` | Renders in the toolbar; `bulk_view` only handles `delete_selected`. Selecting it does nothing |
| Computed columns | Cells resolve from `_meta.fields_map`, then `getattr` on the model. A `ModelAdmin` method is never consulted; a model *method* renders as `<bound method …>` |
| List queries | No `select_related` or `prefetch_related` anywhere. 25 rows × 2 FK columns is 51 queries |

A new declaration system is worth doing partly because fixing those three
inside the current shape means adding three more magic attributes.

---

## 3. Principles

1. **A declaration is a value.** Every part is an object you can name, store,
   pass, generate and reuse. There is no metaclass and no registry scanning.
2. **Explicit over inferred.** Nothing is derived from a name, an annotation,
   or a position in a class body.
3. **Fail at mount, not at request.** Every reference is resolved against the
   model when the admin is mounted. A typo is a startup error naming the
   resource, the field and the nearest match.
4. **Immutable, with `.with_()`.** Declarations never mutate. Extending one
   returns a new one, so a shared base cannot be edited from a distance.
5. **Handlers look like handlers.** `ctx` first, then what the declaration
   says it passes. Same as a route, a consumer, a resolver.
6. **Usable outside the admin.** A `List` is a description of a table. It
   should render in your own page too.

---

## 4. The types

```python
from sillo.admin import Admin, Resource, List, Detail, Form
from sillo.admin import Column, Field, Filter, Action, Section, Panel
from sillo.admin import Access, Order, Widget, Format, Page
```

| | |
|---|---|
| `Admin` | The site. Holds resources and pages; `.mount(app)` |
| `Resource` | One model's surface: its list, detail, form and access |
| `List` / `Detail` / `Form` | The three screens |
| `Column` | One list column |
| `Field` | One form input |
| `Filter` | One list filter |
| `Action` | Something a user can do to rows |
| `Section` / `Panel` | Grouping inside a form / a detail page |
| `Access` | Who may do what |
| `Order` | Sort order |
| `Format` / `Widget` | How a value is displayed / edited |
| `Page` | A custom admin page |

---

## 5. What it reads like

```python
from sillo.admin import (
    Access, Action, Admin, Column, Field, Filter, Form,
    Detail, List, Order, Panel, Resource, Section, Widget, notice,
)

admin = Admin(title="Acme Ops", prefix="/admin")


async def publish(ctx, rows):
    published = await rows.filter(status="draft").update(status="live")
    return notice(f"Published {published} posts")


admin.add(Resource(
    Post,
    label="Post", plural="Posts", icon="file-text", group="Content",

    list=List(
        Column("title", link=True),
        Column.relation("author", display="email", link=True),
        Column.badge("status", colors={"live": "green", "draft": "zinc"}),
        Column.date("published_at", label="Published", format="relative"),
        Column.compute("Words", lambda row: len(row.body.split()), align="right"),

        filters=[
            Filter.text("title"),
            Filter.choice("status", STATUSES),
            Filter.date_range("published_at", presets=["7d", "30d", "quarter"]),
            Filter.custom("Long reads", lambda rows: rows.filter(word_count__gte=2000)),
        ],
        actions=[
            Action("Publish", publish, icon="upload", confirm="Publish {count} posts?"),
            Action.delete(),
        ],
        order=Order.desc("published_at"),
        select_related=["author"],
        per_page=25,
        empty="No posts yet.",
    ),

    form=Form(
        Section("Content",
            Field("title", placeholder="A short, specific title"),
            Field("body", widget=Widget.markdown(height=400)),
        ),
        Section("Publishing",
            Field("status"),
            Field("published_at", help="Leave empty to publish immediately."),
            Field("tags", widget=Widget.tags()),
        ),
        Section("Audit",
            Field.readonly("created_at"),
            Field.readonly("updated_at"),
            collapsed=True,
        ),
    ),

    detail=Detail(
        Panel.fields("Overview", "title", "author", "status"),
        Panel.inline("Sections", PostSection, columns=["heading", "position"],
                     editable=True, extra=1, order=Order.asc("position")),
        Panel.related("Comments", Comment, limit=10, order=Order.desc("created_at")),
    ),

    access=Access(
        view=True,
        add="posts.create",
        change=lambda ctx, row: row.author_id == ctx.user.id or ctx.user.is_staff,
        delete=False,
    ),
))
```

Every line says what it does. There is no attribute whose meaning depends on
another attribute, and nothing is inferred from a name.

---

## 6. Design notes

### Columns

```python
Column("title", label=None, sortable=True, link=False, align="left", width=None)
Column.compute(label, fn, sort=None, align="left")
Column.relation("author", display="email", link=True)
Column.badge("status", colors={...})
Column.bool("is_active")
Column.money("total_cents", currency="USD", scale=100)
Column.date("created_at", format="relative")
Column.custom(label, render)
```

`fn` is `(row) -> value`. `sort=` names the database column a computed column
sorts by — **a computed column that cannot be sorted is a dead column**, which
is why the argument exists rather than being optional-by-omission.

`Column.relation` is what teaches the list to `select_related`; declaring the
column is what removes the N+1, rather than a second attribute you must
remember to keep in step.

### Filters

```python
Filter.text("title")
Filter.choice("status", options, multiple=False)
Filter.bool("published")
Filter.date_range("created_at", presets=["today", "7d", "30d"])
Filter.number_range("total_cents")
Filter.relation("author", search=True)
Filter.custom(label, fn)          # fn: (rows) -> rows
```

Every filter compiles to a queryset transformation. `Filter.custom` is the
escape hatch and takes the same shape, so nothing is special-cased.

### Actions

```python
Action(label, handler, *, icon=None, confirm=None, destructive=False,
       access=None, scope="bulk")
Action.row(label, handler, ...)      # one row
Action.delete()                      # the built-in, still declared explicitly
```

```python
async def ship(ctx, rows):
    ...
    return notice("Shipped")
```

The handler receives a **queryset**, not a list of ids, so an action over
40,000 rows is one statement. Return one of the free builders — `notice`,
`warning`, `download`, `go` — matching `json()` and `text()` elsewhere.

`confirm=` renders the interstitial. `access=` reuses `Access`'s vocabulary.

### Access

```python
Access(
    view=True,                                   # bool
    add="posts.create",                          # a permission name
    change=lambda ctx, row: row.owner_id == ctx.user.id,   # a callable
    delete=False,
)
```

Callables receive `(ctx, row)` — `row` is `None` for list-level questions —
and may be async. Strings go through `sillo.permissions`, so the admin does
not grow a second authorisation model.

### Widgets and formats

`Widget` is how a value is **edited**; `Format` is how it is **displayed**.
Keeping them apart is why a read-only money column and an editable money field
do not need the same object.

```python
Widget.text() / .textarea() / .markdown() / .select() / .tags() /
      .date() / .color() / .file() / .json() / .relation(search=True)

Format.date(...) / .money(...) / .badge(...) / .bytes() / .relative()
```

---

## 7. Buildable

Because a declaration is a value, generating one is a function.

```python
def reference_data(model, *fields, label=None):
    """The list/form pair every lookup table wants."""
    return Resource(
        model,
        label=label,
        group="Reference",
        list=List(*[Column(f) for f in fields], order=Order.asc(fields[0])),
        form=Form(Section("", *[Field(f) for f in fields])),
        access=Access(view=True, add="reference.edit", change="reference.edit",
                      delete=False),
    )


for model in (Tag, Category, Region, Currency):
    admin.add(reference_data(model, "name", "slug"))
```

Composition is `.with_()`, which returns a new declaration:

```python
BASE = List(Column("id"), Column("name"), per_page=50)

admin.add(Resource(Tag,  list=BASE.with_(Column("slug"))))
admin.add(Resource(Team, list=BASE.with_(Column.relation("owner"),
                                         filters=[Filter.bool("archived")])))
```

`.with_()` appends positional parts and overrides keywords. It never mutates,
so `BASE` cannot be changed from a distance by whoever registers last.

---

## 8. Integratable

**Into your own pages.** A `List` describes a table; the admin is one place to
render one.

```python
ORDERS = List(Column("id"), Column("total"), Column.badge("status"),
              filters=[Filter.date_range("created_at")])

@app.get("/team/orders")
async def team_orders(ctx: HttpContext):
    return await admin.render(ctx, ORDERS, Order.filter(team_id=ctx.user.team_id))
```

Same filters, same sorting, same pagination — inside your own layout, with your
own queryset, and without the admin's chrome or its auth.

**From other packages.** A package ships declarations and the application
decides whether to mount them:

```python
from sillo_billing.admin import resources as billing

admin.add(*billing)
```

Nothing is registered by import side effect, which is what makes that
decision the application's.

**Custom pages.**

```python
@admin.page("/reports/revenue", title="Revenue", icon="chart", group="Reports")
async def revenue(ctx: HttpContext):
    return admin.template("reports/revenue.html", rows=await monthly())
```

**Dashboard.**

```python
admin.dashboard(
    Widget.card("Revenue this month", monthly_revenue, format=Format.money()),
    Widget.chart("Signups", signups_by_day, kind="line"),
    Widget.table("Needs attention", stuck_orders, link=Order),
)
```

---

## 9. Validation

Every declaration is resolved against the model at `mount()`, once.

```
AdminDeclarationError: Resource(Post).list column 'titel' is not a field of Post.
  Did you mean 'title'?
  Declared at app/admin.py:24
```

Checked at mount:

- every field reference exists on the model, with a nearest-match suggestion;
- `Column.relation` names an actual relation, and its `display` exists on the
  far side;
- `sort=` on a computed column names a real database column;
- an action handler is callable and accepts `(ctx, rows)`;
- `Access` strings name registered permissions;
- a `Field` for a non-nullable column without a default is not `readonly`,
  which would make the form unsubmittable.

This is the payoff for keeping references as strings rather than inventing a
reference object: strings stay readable, and the check happens before the
application serves anything.

---

## 10. Coexistence and migration

`ModelAdmin` keeps working. Internally it is **compiled** to a `Resource`, so
there is one rendering path rather than two:

```python
Resource.from_model_admin(PostAdmin)   # what the registry does for you
```

Which also means the three broken promises in §2 are fixed for existing
`ModelAdmin` users without them changing anything: the compiler emits real
actions, real computed columns, and `select_related` derived from the relation
columns it finds.

| `ModelAdmin` | `Resource` |
|---|---|
| `list_display = ["title"]` | `List(Column("title"))` |
| `list_display_links = ["title"]` | `Column("title", link=True)` |
| `search_fields = [...]` | `Filter.text(...)` |
| `list_filter = ["status"]` | `Filter.choice("status", ...)` |
| `ordering = ["-created_at"]` | `Order.desc("created_at")` |
| `fields` / `exclude` | `Form(Section(...))` |
| `readonly_fields = [...]` | `Field.readonly(...)` |
| `actions = ["publish"]` | `Action("Publish", publish)` |
| `has_*_permission` | `Access(...)` |
| `get_queryset` | `Resource(queryset=...)` |

Deprecation warning in the release after this lands; removal one release later.

---

## 11. Implementation

Each phase is shippable on its own and leaves the admin working.

### Phase 0 — the values

`sillo/admin/declare/` — `resource.py`, `screens.py`, `columns.py`,
`fields.py`, `filters.py`, `actions.py`, `access.py`, `widgets.py`,
`errors.py`. Frozen dataclasses, `.with_()`, no rendering, no ORM.

Tests: construction, immutability, `.with_()` semantics, every constructor.

### Phase 1 — resolution

`declare/resolve.py`: bind a `Resource` to a model, validate every reference,
emit `AdminDeclarationError` with suggestions. `Resource.from_model_admin`.

Tests: every validation rule, one bad declaration per rule, suggestion quality.

### Phase 2 — the list

`routes.list_view` reads a resolved `Resource`. Delivers computed columns,
`select_related` from relation columns, declared filters, declared ordering.

Tests: query counts (the N+1 assertion), computed cells, each filter kind.

### Phase 3 — actions

Real dispatch, queryset-scoped, `confirm=` interstitial, free builders,
per-action access, audit log entries.

Tests: bulk over a filtered selection, a refused action, a downloading action.

### Phase 4 — form and detail

`Section`, `Field`, `Widget`, `Panel.inline` (editable), `Panel.related`.

### Phase 5 — pages, dashboard, embedding

`@admin.page`, `admin.dashboard(...)`, `admin.render(ctx, list, queryset)`.

### Phase 6 — docs and deprecation

Rewrite `/v1.0/orm/admin-*`, add a migration table, warn on `ModelAdmin`.

---

## 12. Open questions

1. **`Admin` or `AdminSite`?** The current class is `AdminSite`. `Admin` is
   shorter and reads better beside `Graph` and `Hub`; keeping `AdminSite` is
   one less rename. Leaning `Admin`, with `AdminSite` as an alias.
2. **Should `Filter.text` be `Search`?** It is the thing `search_fields` did.
   `Filter.text` is consistent; `Search` is what people will look for.
3. **Inline editing in the list** (`list_editable`) — a separate feature, or
   a `Column(editable=True)` flag? Leaning separate: inline editing needs a
   save endpoint and optimistic UI that a column flag hides.
4. **Does `admin.render` belong in the admin package** or in a shared
   `sillo.tables` that the admin also uses? The second is cleaner and larger.
