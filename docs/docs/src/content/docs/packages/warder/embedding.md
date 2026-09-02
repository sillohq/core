---
title: Embedding and customising
description: A List in your own route, named slots, theme tokens, and the eject you should not need.
---

## A List in your own route

The declarations are usable outside the admin. A `List` describes a table; the
admin is one place that happens to draw one.

```python
HONOURS = List(
    Column.relation("student", display="last_name"),
    Column.compute("Total", lambda row: row.total, sort=False, align="right"),
    sort=Sort.desc("exam"),
    per_page=20,
    selectable=False,
)


@app.get("/honours")
async def honours(ctx: HttpContext):
    return await admin.render(
        ctx, HONOURS, Result.filter(published=True, exam__gte=50), title="Honour roll"
    )
```

Drawn over the queryset you hand it, in your route's own URL space. No resource,
no registration, and **no admin permission consulted** — because it is your route
and you have already decided who may be on it.

## Three rungs of customisation

In increasing order of commitment.

### 1. Theme tokens — no rebuild

```python
Admin(theme=Theme.console(accent="#0f766e", density="compact", radius="4px"))
```

Python writes CSS custom properties into the document. See
[Theming](/packages/warder/theming/).

### 2. Slots — your build, not ours

```python
admin.slot("list.toolbar", "acme/ExportButton")
```

Mounts one of your own components into a named region of the shell, loaded from
your application's own Vite build. `Panel.custom` and `Page(component=…)` are the
same idea for a whole panel or a whole page.

Until the component exists, the props render as a readable table rather than an
apology — the data is there, and it proves the route, the gate and the loader all
worked.

### 3. Eject — you own the upgrades

```bash
warder eject ./admin-ui
```

Copies `ui/` into your project and points the admin at your build output.
Supported, documented, and the last resort.

## How the interface ships

Built assets live in `warder/static/` **inside the wheel**; the React sources
live in `ui/` in the repository and are excluded from it. `pip install warder`
needs no Node, no build step and no network call — somebody installing an admin
panel is not signing up to run Vite.

It is one JavaScript file and one stylesheet on purpose. The admin is served
under a prefix *you* choose, and code-splitting would have to resolve chunk URLs
against a base it cannot know until runtime. Inlining every dynamic import
removes the question, and one request that warms the cache beats six that split
it for a screen people open once and use all day.

Assets are content-hashed and served by the framework's own static layer under
the admin's prefix, with immutable cache headers. The manifest's hash is also the
Inertia asset version: when a deploy changes the bundle, an open tab is told to
reload rather than handed new props to render with old JavaScript.

## Working on Warder itself

```bash
cd ui && npm install && npm run build     # → warder/static/
warder check app:admin
```

The build hook refuses to package a wheel whose interface failed to build,
because that one installs cleanly and renders a blank page.
