---
title: Pages and Props
description: "Writing an Inertia page: render, shared props, deferred work, redirects, and handlers that only gather data."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Inertia Pages and Props
  - tag: meta
    attrs:
      property: og:description
      content: render, shared props, redirects, and handlers that only gather data.
---

#  Pages and Props

##  Adding a page

Write the component:

```tsx
// views/pages/Reports.tsx
import { Head } from '@inertiajs/react'

export default function Reports({ rows }: { rows: Row[] }) {
  return (
    <>
      <Head title="Reports" />
      <ul>{rows.map(r => <li key={r.id}>{r.name}</li>)}</ul>
    </>
  )
}
```

Write the handler:

```python
# routes/web.py
from sillo_inertia import render


from sillo import HttpContext

async def reports(ctx: HttpContext):
    return await render("Reports", {"rows": await Report.all().values()})
```

Register it. Pages are declared as `Route` objects, with
`exclude_from_schema` because they are not an API:

```python
Route("/reports", handler=web.reports, methods=["GET"],
      name="reports", exclude_from_schema=True)
```

No build step, no route file to regenerate, and no client-side router to keep
in step.

##  `render` without the adapter

`render`, `redirect`, `back` and `location` are importable on their own. They
find the adapter through the middleware handling the request, so a routes
module builds Inertia responses without importing the module that owns the
application, and so without the circular import that would otherwise cause.

```python
from sillo_inertia import render


from sillo import HttpContext

async def home(ctx: HttpContext):
    return await render("Home", {"name": "Sillo"})
```

Outside a request (a background job, a test calling a handler directly) pass
one explicitly:

```python
await inertia.render("Home", props, request=ctx)
```

With neither, `render` raises `OutsideRequestError` and names the three ways
to end up there.

##  Props

A prop can be a value, a callable, or a coroutine function. Callables that
want the request take one parameter; those that do not, take none.

```python
{
    "count": 5,                                   # a value
    "total": lambda: Order.count(),               # called per ctx
    "mine": lambda ctx: ctx.user.orders,  # given the ctx
    "stats": fetch_stats,                         # async, awaited
}
```

Anything a prop returns is serialised to JSON and handed to the browser, so a
model instance is the wrong thing to put in one. Return the fields you mean to
publish:

```python
{"user": {"id": user.id, "email": user.email}}    # explicit
{"user": user}                                     # ships every column
```

Listing them by hand is what stops a column added later (a password hash, an
internal note) from quietly starting to reach the client.

##  Shared props

Props every page receives are registered once, at startup:

```python
inertia.share(
    app_name=config.app_name,
    auth=lambda ctx: {"user": current_user(ctx)},
)
```

They are registered once but resolved per request: a callable prop is called
each time a page renders, so `auth` reflects whoever is making *this* request
rather than whoever was making the one during startup.

A page's own props win on a name clash.

##  Handlers that only gather data

When a handler does nothing but collect props, `@inertia.page` takes the rest:

```python
@app.get("/users/{user_id}")
@inertia.page("Users/Show")
async def show(user_id):
    return {"user": await User.get(id=user_id)}
```

The function declares only what it uses. Ask for `request` or `response` by
name and you get them; leave them out and they are not passed. Path
parameters, injected dependencies and validated bodies all arrive as they
would on any handler.

Returning a response instead of a mapping sends that response untouched, so a
handler can still redirect out of a page:

```python
from sillo import HttpContext

@app.post("/users")
@inertia.page("Users/Create")
async def create(ctx: HttpContext):
    await User.create(**await ctx.json())
    return inertia.redirect("/users")
```

##  Redirects

```python
inertia.redirect("/dashboard")   # 303 after POST/PUT/PATCH, 302 after GET
inertia.back()                   # to the Referer
inertia.back(fallback="/posts")  # ...when there is no Referer
```

The 303 is not decoration. On a 302 the browser repeats the POST against the
new URL, so a redirect after a successful create makes a second record.

To send someone out of Inertia entirely (an external URL, a hosted checkout)
use `location`, which asks the client for a full browser visit rather than an
XHR one:

```python
inertia.location("https://billing.example.com/checkout")
```

##  Guarding a page

Check and redirect. Do not reach for `auth=` on the route:

```python
from sillo import HttpContext, redirect

async def dashboard(ctx: HttpContext):
    if not ctx.user.is_authenticated:
        return redirect("/login")

    return await render("Dashboard", {...})
```

`auth=` answers **401**, which is right for a JSON API and wrong here:
Inertia's client surfaces a 401 as an unhandled error modal rather than a
login screen. What the guard should do is application-specific, which is why
it is written out rather than delegated.

##  Partial reloads and `lazy()`

:::caution
**`lazy()` here is narrower than in Inertia's own adapters.** Upstream, a lazy
prop is excluded from every regular visit and included only when asked for by
name. Here it is resolved on a full visit like any other prop, and only
partial reloads filter it out.

Do not rely on it to keep an expensive query off the first page load.
:::

##  Next

- [Forms and Validation](/v1.0/guides/inertia/forms/): returning errors from a
  failed submission
- [Assets and Deployment](/v1.0/guides/inertia/assets/): asset versions and shipping
  it
