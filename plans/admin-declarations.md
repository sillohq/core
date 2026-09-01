# `sillo-admin`: a declaration system, an Inertia UI, and an auth model

**Status:** proposal · **Replaces:** the `ModelAdmin` class-attribute style and
the Jinja-rendered UI · **Ships as:** `sillo-admin`, importable as `sillo.admin`

---

## 1. The rule this is built on

> **A type annotation in Sillo describes a type. It never selects behaviour.**

Nothing here reads `__annotations__`, and nothing changes because a parameter is
spelled one way rather than another. Every behaviour is asked for in an argument
you can see. Where a value must be injected it arrives as a **default value** —
the way `db=Depend(get_db)` already works — because a default is a value and an
annotation is not.

### Where this rule is currently broken

`sillo-graphql` selects which resolver parameters to inject by reading their
annotations: `ctx: HttpContext` is injected, `limit: int` becomes a schema
argument. That is the pattern this document forbids. A `ctx=Ctx()` default
marker does the same job as a value. Out of scope here, same decision, worth
making once — and worth making before that API has users.

---

## 2. What this is coupled to, and what that means

**The admin is a `sillo.record` product.** It reads `_meta.fields_map`, builds
querysets, follows `ForeignKeyField` and `ManyToManyField`, and writes through
model saves. There is no abstraction layer over the ORM and there should not be
one: an admin that could drive any data source would be able to express only
what every data source has in common, which is roughly nothing.

That coupling decides the package boundary:

```
sillo-admin
├── depends on  sillo-framework[record]   the ORM, hard
├── depends on  sillo-inertia             the UI transport
└── optional    sillo-framework auth, permissions, users
```

The optional line is the point of §7: the admin brings its own user model and
its own login, and **hands both over to yours the moment you say so**.

What is *not* coupled: the declaration values in §4 are plain objects that know
nothing about rendering, and the resolver in §11 is the only place that touches
the ORM. A future non-record backend is a second resolver, not a rewrite.

---

## 3. What is wrong with the current style

```python
@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["id", "title", "author"]
    list_display_links = ["title"]
    search_fields = ["title", "body"]
    actions = ["publish"]
```

**A namespace of magic names.** Fifteen class attributes whose meaning you
cannot derive from anything — `list_display_links` is a subset of
`list_display`, `fields` and `exclude` are mutually exclusive, `actions` holds
method names.

**Stringly-typed with no validation.** `"titel"` renders an empty column at
request time. Nothing checks it at startup.

**Not buildable.** Forty models with the same three columns is forty
near-identical class bodies.

**Not composable.** A class attribute cannot be extended except by subclassing,
which merges by MRO rather than by intent.

**Three of its promises are not kept.** Verified by reading the package:

| | |
|---|---|
| `actions = ["publish"]` | Rendered into the toolbar at `routes.py:1066`; `bulk_view` only handles `delete_selected`. Selecting it does nothing |
| Computed columns | Cells resolve from `_meta.fields_map`, then `getattr` on the model. A `ModelAdmin` method is never consulted; a model *method* renders as `<bound method …>` |
| List queries | No `select_related` or `prefetch_related` anywhere. 25 rows × 2 FK columns is 51 queries |

Fixing those three inside the current shape means three more magic attributes.

---

## 4. The declaration system

### Principles

1. **A declaration is a value** — nameable, storable, generatable, reusable. No
   metaclass, no import-time registration.
2. **Explicit over inferred** — nothing derived from a name, an annotation, or
   a position in a class body.
3. **Fail at mount, not at request** — every reference resolved once, against
   the model, when the admin is mounted.
4. **Immutable, with `.with_()`** — extending returns a new declaration, so a
   shared base cannot be edited from a distance.
5. **Handlers look like handlers** — `ctx` first, then what the declaration
   says it passes.
6. **Usable outside the admin** — a `List` describes a table; the admin is one
   place to render one.

### The types

| | |
|---|---|
| `Admin` | The site. Resources, pages, auth; `.mount(app)` |
| `Resource` | One model's surface: list, detail, form, access, scope |
| `List` / `Detail` / `Form` | The three screens |
| `Column` / `Field` / `Filter` | A list column / a form input / a list filter |
| `Action` | Something a user can do to rows |
| `Section` / `Panel` | Grouping inside a form / a detail page |
| `Access` / `Gate` / `Scope` | Who may do what, and to which rows |
| `Order` / `Format` / `Widget` | Sorting / display / editing |
| `Page` / `Widget.card` | A custom page / a dashboard tile |

### What it reads like

```python
from sillo.admin import (
    Access, Action, Admin, Column, Detail, Field, Filter, Form,
    List, Order, Panel, Resource, Section, Widget, notice,
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
        Column.compute("Words", lambda row: len(row.body.split()), align="right",
                       sort="word_count"),

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
        Section("Audit", Field.readonly("created_at"), Field.readonly("updated_at"),
                collapsed=True),
    ),

    detail=Detail(
        Panel.fields("Overview", "title", "author", "status"),
        Panel.inline("Sections", PostSection, columns=["heading", "position"],
                     editable=True, extra=1, order=Order.asc("position")),
        Panel.related("Comments", Comment, limit=10, order=Order.desc("created_at")),
    ),

    access=Access(view=True, add="post.add",
                  change=lambda ctx, row: row.author_id == ctx.user.id,
                  delete=False),
))
```

### Notes on the parts

**Columns.** `Column.compute(label, fn, sort=...)` — `fn` is `(row) -> value`.
`sort=` names the database column, because a computed column that cannot be
sorted is a dead column. `Column.relation` is what teaches the list to
`select_related`: declaring the column removes the N+1, rather than a second
attribute you must keep in step with the first.

**Filters.** Every filter compiles to a queryset transformation.
`Filter.custom(label, fn)` takes the same shape, so the escape hatch is not a
special case.

**Actions.** The handler receives a **queryset**, not a list of ids, so an
action over 40,000 rows is one statement. It returns a free builder — `notice`,
`warning`, `download`, `go` — matching `json()` and `text()` elsewhere.

**Buildable.** A declaration is a value, so generating one is a function:

```python
def reference_data(model, *fields):
    return Resource(
        model, group="Reference",
        list=List(*[Column(f) for f in fields], order=Order.asc(fields[0])),
        form=Form(Section("", *[Field(f) for f in fields])),
        access=Access(view=True, add="reference.edit", change="reference.edit",
                      delete=False),
    )

for model in (Tag, Category, Region, Currency):
    admin.add(reference_data(model, "name", "slug"))
```

Composition is `.with_()`, which appends positional parts and overrides
keywords, returning a new object:

```python
BASE = List(Column("id"), Column("name"), per_page=50)

admin.add(Resource(Tag,  list=BASE.with_(Column("slug"))))
admin.add(Resource(Team, list=BASE.with_(Column.relation("owner"))))
```

**Integratable.** A `List` renders in your own route, with your own queryset,
inside your own layout:

```python
ORDERS = List(Column("id"), Column("total"), Column.badge("status"))

@app.get("/team/orders")
async def team_orders(ctx: HttpContext):
    return await admin.render(ctx, ORDERS, Order.filter(team_id=ctx.user.team_id))
```

Packages ship declarations and the application decides whether to mount them —
`admin.add(*billing.resources)` — so nothing is registered by import side
effect.

**Validation.** Resolved once at `mount()`:

```
AdminDeclarationError: Resource(Post).list column 'titel' is not a field of Post.
  Did you mean 'title'?
  Declared at app/admin.py:24
```

Field references exist; `Column.relation` names a real relation and its
`display` exists on the far side; `sort=` names a real column; action handlers
accept `(ctx, rows)`; `Access` strings name registered permissions; a
non-nullable field with no default is not marked readonly, which would make the
form unsubmittable.

---

## 5. The UI: Inertia, React, Tailwind

The admin stops being Jinja templates and becomes an Inertia application.
Python owns the data and the rules; React owns the rendering.

```
browser  ─┐
          │  Inertia page visit
          ▼
sillo.admin route  ──►  resolve Resource  ──►  props  ──►  React page
                            │
                            └─►  sillo.record
```

**Python sends declarations, not HTML.** A resolved `Resource` serialises to
JSON: columns with their types and formats, filters with their options, actions
with their labels and confirmations, the page of rows. The React side is a
generic renderer for that shape — it does not know what a `Post` is.

That is the property that makes the whole thing work. Adding
`Column.badge("status", colors=…)` changes a prop, not a template, so the UI
never needs a rebuild to serve a new resource.

**Why Inertia rather than an API plus a SPA.** No second auth story, no client
router to keep in step with the Python routes, no OpenAPI surface to maintain
for screens nobody else consumes. A page visit is a request; the server decides
what is on it. Redirects, flash messages, validation errors and form
round-trips work the way they do in any server-rendered app.

**Component inventory** — small, because the declaration does the work:

```
DataTable      columns, sorting, selection, pagination, empty state
FilterBar      one control per Filter kind
ActionMenu     bulk + row, confirmation dialogs
FormRenderer   Section → Field → Widget
DetailView     Panel: fields | inline | related | custom
Shell          nav from resource groups, command palette, breadcrumbs, flash
Dashboard      card | chart | table tiles
```

**Prerequisite, and it blocks everything.** `sillo-inertia` 0.0.1a4 is entirely
on the 0.x API — zero occurrences of `HttpContext` or `ctx`, `Request` and
`Response` throughout. It has to be ported to the context-handler API before
any of this can be built. That is phase 0 and it is not optional.

---

## 6. Distribution: bundled, no Node

**`pip install sillo-admin` must not require Node, a build step, or a network
call.** Someone installing an admin panel is not signing up to run Vite.

### What ships

```
sillo_admin/
├── declare/          the values in §4
├── resolve/          model binding and validation
├── routes/           the Inertia endpoints
├── auth/             §7
└── static/           BUILT ASSETS — shipped in the wheel
    ├── admin.[hash].js
    ├── admin.[hash].css
    └── manifest.json
```

### What does not

```
ui/                   React sources, Tailwind config, Vite config
├── src/
├── package.json
└── vite.config.ts
```

`ui/` lives in the repository and is excluded from the wheel. A consumer gets
`static/` and nothing else — no `node_modules`, no `package.json`, no
`postinstall`.

```toml
[tool.hatch.build.targets.wheel]
packages = ["sillo_admin"]
exclude = ["ui", "ui/**"]

[tool.hatch.build.targets.wheel.hooks.custom]
# Runs `npm ci && npm run build` in ui/ and copies dist/ into
# sillo_admin/static/ before packaging. Fails the build if the manifest is
# missing, so a wheel can never ship without its assets.
path = "build_ui.py"

[tool.hatch.build.targets.sdist]
# The sdist carries ui/ so the wheel is reproducible from source.
include = ["sillo_admin", "ui", "build_ui.py"]
```

### Serving them

Assets are served by the framework's own static layer under the admin prefix,
with content-hashed filenames and immutable cache headers. No CDN, no external
request — so the admin works on an air-gapped network and under a
Content-Security-Policy that forbids third-party script, which is the same
decision `sillo-graphql`'s bundled explorer makes.

### Customising without ejecting

Three levels, in increasing order of commitment:

1. **Tokens.** `Admin(theme=Theme(accent="#4f46e5", radius="md", density="compact"))`
   writes CSS custom properties into the shell. No rebuild.
2. **Slots.** `admin.slot("list.toolbar", "acme/ExportButton")` mounts your own
   component into a named region, loaded from your app's Vite build. Needs your
   build, not ours.
3. **Eject.** `sillo admin eject ./admin-ui` copies `ui/` into your project and
   points the admin at your build output. Supported, documented, and the last
   resort — you now own the upgrades.

---

## 7. Style

Four directions. All four are Tailwind, all four ship dark and light, all four
are driven by the same token set — so this is a choice about defaults, not
about architecture.

### A — Console *(recommended)*

Dense, quiet, keyboard-first. Near-black and near-white rather than pure, a
single restrained accent, hairline borders instead of shadows, tabular numerals
everywhere, monospace for ids and timestamps. Rows are 36px. The command
palette is the primary navigation, not a bonus.

```
bg   #fbfbfa / #101114     ink  #16181d / #e8e8ea
line #e4e4e7 / #26282e     dim  #6b7280 / #9095a1
accent  one hue, used for focus and primary actions only
radius  6px      row 36px      text 13px      mono for ids, money, dates
```

Right because an admin is a tool for people who use it all day. It reads as
infrastructure rather than as a product, it gets out of the way, and it is the
one direction that does not fight a dense table. It is also the visual language
the rest of Sillo's surfaces already use.

### B — Paper

Light, generous, editorial. Serif headings, 15px body, 48px rows, real
whitespace, cards with soft shadows. Reads beautifully and shows about half as
much per screen.

Right when the admin is a content tool used occasionally by non-technical
people — a CMS, an editorial workflow.

### C — Grid

Spreadsheet-first. Ruled cells, frozen header and first column, 28px rows,
inline editing as the default rather than a feature, no card chrome at all.

Right when the job is bulk data work — reconciliation, imports, moderation
queues — and wrong for anything with long-form fields.

### D — Native

No opinion. Consumes the host application's CSS custom properties and matches
whatever design system is already there.

Right when the admin is a tab inside an existing product rather than a separate
place you go.

**Recommendation: ship A as the default, D as a documented option, and B and C
as themes** — because A and D are the two that need no maintenance, and B and C
are token sets plus a density setting rather than separate codebases.

---

## 8. Authentication and permissions

The admin brings its own login and its own user model, and hands both to yours
the moment you say so. Nothing here is a second authorisation system: it
compiles onto `sillo.permissions`, which already ships `Permission`, `Group`,
`UserPermission`, `UserGroup` and `GroupPermission`, and onto the
`PermissionMixin` your user model may already carry.

### The declaration

```python
from sillo.admin import Admin, Audit, Auth, Gate, Impersonation, Login, MFA, Session

admin = Admin(
    title="Acme Ops",
    auth=Auth(
        users=User,                       # your model; omit for the bundled one
        backend=SessionAuth(),            # or the application's own backend
        gate=Gate.staff(),                # who may enter at all
        permissions=Auth.RECORDS,         # resolve against sillo.permissions
        session=Session(idle="30m", absolute="12h", concurrent=1),
        login=Login(throttle="5/15m", remember=True,
                    providers=[OAuth("google", domain="acme.com")]),
        mfa=MFA.totp(required=Gate.role("owner"), recovery_codes=10),
        impersonation=Impersonation(gate=Gate.permission("users.impersonate"),
                                    banner=True, max="1h"),
        audit=Audit(retain="1y", redact=["password", "token", "secret"]),
    ),
)
```

Omit `auth=` and you get the current behaviour: the bundled `AdminUser`, a
session backend, and `is_staff` as the gate.

### Four questions, four layers

**1. May you enter at all?** `Gate`.

```python
Gate.staff()                             # is_staff or is_superuser, and active
Gate.permission("admin.access")
Gate.role("support")
Gate.any(Gate.role("owner"), Gate.permission("admin.access"))
Gate.custom(lambda ctx: ctx.user.email.endswith("@acme.com"))
```

This is the gate that already exists as `SessionAuth.may_enter`, made
declarable. It matters more than it looks: when the admin shares the
application's user model — the ordinary arrangement — every registered account
holds a session, and admitting anyone with one hands over the database.

**2. May you do this to this model?** `Access`, per resource.

```python
Access(view=True, add="post.add", change="post.change", delete=False)
```

Registering a `Resource` **declares** four permissions —
`<label>.view|add|change|delete` — and `sillo admin permissions sync` writes
any that are missing into the `Permission` table. So the permissions a
deployment can grant are derived from what is registered rather than typed
twice.

Roles group them:

```python
admin.roles(
    Role("support", grants=["order.view", "customer.view"]),
    Role("editor", grants=Role.crud(Post, Tag), inherits=["support"]),
    Role("owner", grants="*"),
)
```

A `Role` compiles to a `Group` with `GroupPermission` rows, so roles are data
after the first sync and can be edited in the admin itself.

**3. May you do it to *this row*?** A callable in `Access`, plus `Scope` for
the queryset.

```python
Resource(
    Order,
    access=Access(change=lambda ctx, row: row.team_id == ctx.user.team_id),
    scope=Scope.by(lambda ctx: {"team_id": ctx.user.team_id}),
)
```

`Access` decides whether a button is shown and whether a write is allowed;
`Scope` decides what is in the list at all. **Both are needed** — access
without scope leaks row existence through pagination counts and search results,
and scope without access leaves a writable object reachable by id.

`Scope.owner("author_id")` and `Scope.tenant("team_id")` are the two common
cases written out.

**4. May you see *this field*?** `Access` on a `Field` or `Column`.

```python
Field("salary", access=Access(view="hr.salary.view", change="hr.salary.change"))
Column("email", access=Access(view="pii.read"))
```

A field you may not view is absent from the props, not hidden with CSS — so it
never reaches the browser. A field you may view but not change renders
readonly, and a write to it is rejected server-side rather than trusted.

### What else it carries

| | |
|---|---|
| **Session policy** | Idle and absolute lifetimes, concurrent-session cap, revoke-all on password change, a visible list of your own sessions |
| **Login** | Throttling per identity and per address, `remember me`, optional OAuth providers with a domain restriction, generic failure messages |
| **MFA** | TOTP with recovery codes, required by `Gate` so it can be demanded of owners and not of everyone; step-up before destructive actions |
| **Impersonation** | Gated, banner-marked, time-boxed, fully audited, and unable to escalate — you cannot impersonate someone with permissions you lack |
| **Audit** | Every mutating action with actor, object, field-level diff, address and request id; redaction list; retention. Built on the existing activity log |
| **Password** | Delegated to `sillo.hashing`, never reimplemented |

### Hooking into what you already have

The whole of §8 is optional. Three arrangements, all supported:

1. **Standalone** — bundled `AdminUser`, admin-only login. For an internal tool
   with no public user model.
2. **Shared model, admin login** — `users=User`, `gate=Gate.staff()`. Your
   people, your accounts, a separate sign-in page for the admin.
3. **Shared model, shared session** — `backend=` the application's own
   authentication middleware. Someone signed into the product is signed into
   the admin, subject to the gate.

The third is what most applications want and the one the current code half
supports.

---

## 9. Coexistence and migration

`ModelAdmin` keeps working. Internally it **compiles** to a `Resource`, so
there is one rendering path rather than two — which means the three broken
promises in §3 are fixed for existing users without them changing a line: the
compiler emits real actions, real computed columns, and `select_related`
derived from the relation columns it finds.

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
| `get_queryset` | `Scope` / `Resource(queryset=...)` |

Deprecation warning one release after this lands; removal one release later.

---

## 10. Implementation

Each phase ships on its own and leaves the admin working.

| Phase | What | Blocks on |
|---|---|---|
| **0** | Port `sillo-inertia` to the context API | — |
| **1** | `declare/` — the values, frozen, `.with_()`, no ORM, no rendering | — |
| **2** | `resolve/` — bind to a model, validate, `Resource.from_model_admin` | 1 |
| **3** | `ui/` — Vite, Tailwind, the seven components, the build hook and bundled wheel | 0 |
| **4** | The list: computed columns, `select_related`, declared filters and ordering | 2, 3 |
| **5** | Actions: real dispatch, queryset-scoped, confirmations, free builders | 4 |
| **6** | Form and detail: `Section`, `Widget`, editable inlines, related panels | 4 |
| **7** | Auth: `Gate`, `Access`, `Scope`, roles, permission sync, audit | 2 |
| **8** | MFA, impersonation, session policy | 7 |
| **9** | Pages, dashboard widgets, `admin.render` embedding, theme tokens | 6 |
| **10** | Extract to `sillo-admin`, docs, deprecate `ModelAdmin` | all |

Tests per phase, with two that are not obvious: **query counts** on the list
view — the N+1 assertion, which is the regression most likely to come back —
and **a permission matrix**, one test per (role × resource × action) cell,
generated from the declarations rather than written out.

---

## 11. Open questions

1. **`Admin` or `AdminSite`?** `Admin` reads better beside `Graph` and `Hub`;
   `AdminSite` is one less rename. Leaning `Admin`, with an alias.
2. **Does `admin.render` belong here** or in a shared `sillo.tables` the admin
   also uses? The second is cleaner and considerably larger.
3. **Inline list editing** — its own feature, or `Column(editable=True)`?
   Leaning separate: it needs a save endpoint and optimistic UI that a flag
   would hide.
4. **Does `Scope` belong to the admin at all**, or to `sillo.record` as a
   general row-level security feature? It is more useful there and harder.
5. **Bundled asset size.** React plus a table plus a date picker is not small.
   Worth measuring in phase 3 and worth a `Admin(assets="lean")` that drops the
   chart and markdown widgets if it is over budget.
