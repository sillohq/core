---
title: Inertia
description: "Build a React or Vue frontend against Sillo routes with sillo-inertia: server-side routing, no API layer, and no client-side router to keep in sync."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Inertia with Sillo
  - tag: meta
    attrs:
      property: og:description
      content: "Build a React or Vue frontend against Sillo routes with sillo-inertia: server-side routing and no API layer."
---

#  Inertia

[Inertia.js](https://inertiajs.com) lets you write a React or Vue frontend
without building an API for it. Routes stay on the server, handlers return a
component name and its props, and the client swaps the page without a full
reload.

It is the middle path between [Templating](/guides/templating/) and
[Frontend (SPA)](/guides/frontend/): you get a real component-based frontend,
but routing, authorisation and data loading stay in Python, where the rest of
your application already is.

Support lives in a separate package, [`sillo-inertia`](https://github.com/sillohq/inertia),
so nothing here is carried by applications that do not use it.

```bash
pip install sillo-inertia
```

##  A page

```python
from sillo import SilloApp
from sillo.core.http import Request, Response
from sillo_inertia import Inertia, vite_react

app = SilloApp()
inertia = Inertia(
    app,
    root_view="resources/views/app.html",
    version="1",
    vite=vite_react(dev=True),
)


@app.get("/")
async def home(request: Request, response: Response):
    return await inertia.render("Home", {"name": "Sillo"})
```

`render` returns a response. Whether that response is a full HTML document or
a JSON page object is decided by the request, not by you: the first visit is a
plain browser navigation and gets the document, and every navigation after that
carries `X-Inertia: true` and gets JSON.

Passing `app` installs the middleware. That middleware is what makes
`render("Home", ...)` work without being handed a request — it records the
request being answered, so the adapter can read it back.

##  The root view

`resources/views/app.html` needs two placeholders:

```html
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    {{ inertia_head }}
  </head>
  <body>
    <div id="{{ root_id }}"></div>
    {{ inertia }}
  </body>
</html>
```

`{{ inertia_head }}` renders the Vite tags. `{{ inertia }}` renders the page
object as a `<script type="application/json" data-page="app">` element, which
is where Inertia 2.x and later read it from.

:::caution
**Do not put the page object on the root `<div>` as `data-page`.** That was the
Inertia 1.x convention. Current clients never look there, so the page boots
with a null page object and throws
`Cannot read properties of null (reading 'component')` from inside
`createInertiaApp`.
:::

##  Handlers that only produce props

When a handler does nothing but gather data, `@inertia.page` takes the rest:

```python
@app.get("/users/{user_id}")
@inertia.page("Users/Show")
async def show(user_id):
    return {"user": await User.get(id=user_id)}
```

The function declares only what it uses. Ask for `request` or `response` by
name and you get them; leave them out and they are not passed. Path parameters,
injected dependencies and validated bodies all arrive as they would on any
handler.

Returning a response instead of a mapping sends that response untouched, so a
handler can still redirect out of a page:

```python
@app.post("/users")
@inertia.page("Users/Create")
async def create(request: Request):
    await User.create(**await request.json())
    return inertia.redirect("/users")
```

##  Props

A prop can be a value, a callable, or a coroutine function. Callables that want
the request take one parameter; those that do not, take none.

```python
{
    "count": 5,                                   # a value
    "total": lambda: Order.count(),               # called per request
    "mine": lambda request: request.user.orders,  # given the request
    "stats": fetch_stats,                         # async, awaited
}
```

Props shared by every page are set once, at startup:

```python
inertia.share(app_name="MyApp", auth={"user": None})
```

A page's own props win on a name clash.

##  Redirects

```python
inertia.redirect("/dashboard")   # 303 after POST/PUT/PATCH, 302 after GET
inertia.back()                   # to the Referer
inertia.back(fallback="/posts")  # ...when there is no Referer
```

The 303 is not decoration. On a 302 the browser repeats the POST against the
new URL, so a redirect after a successful create makes a second record.

To send someone out of Inertia entirely — an external URL, a hosted checkout —
use `location`, which asks the client for a full browser visit rather than an
XHR one:

```python
inertia.location("https://billing.example.com/checkout")
```

##  Without the adapter in scope

`render`, `redirect`, `back` and `location` are importable on their own. They
find the adapter through the same middleware, so a routes module can build
Inertia responses without importing the module that owns the application — and
so without the circular import that would otherwise cause.

```python
from sillo_inertia import render


@app.get("/")
async def home(request: Request, response: Response):
    return await render("Home", {"name": "Sillo"})
```

Outside a request — a background job, a test calling a handler directly — pass
one explicitly:

```python
await inertia.render("Home", props, request=request)
```

With neither, `render` raises `OutsideRequestError` and names the three ways to
end up there.

##  Asset versions

When the client's `X-Inertia-Version` does not match the current one, the
middleware answers with a 409 and `X-Inertia-Location` before the handler runs.
The client does a full visit and comes back on the current build — which is
what stops a stale bundle rendering a new page object against components that
no longer match it.

```python
Inertia(app, root_view=..., version="1.0.0")           # a fixed string
Inertia(app, root_view=..., version=read_manifest_hash)  # re-read per request
```

A `version` of `None` disables the check.

##  Things worth knowing

1. **`lazy()` here is narrower than in Inertia's own adapters.** Upstream, a
   lazy prop is excluded from every regular visit and included only when asked
   for by name. Here it is resolved on a full visit like any other prop, and
   only partial reloads filter it out. Do not rely on it to keep an expensive
   query off the first page load.

2. **`render` no longer takes `request` and `response`.** It did before
   `0.0.1a3`. The old call raises a `TypeError` naming the new form.

3. **Vite in production reads a manifest.** `vite_react(dev=False)` resolves
   entries through `dist/.vite/manifest.json`, so the frontend must be built
   before the application starts serving.

##  Related

- [Frontend (SPA)](/guides/frontend/) — serving a built SPA with client-side routing
- [Templating](/guides/templating/) — server-rendered Jinja pages
- [Static Files](/guides/static-files/) — serving assets
- [`sillo-inertia` on GitHub](https://github.com/sillohq/inertia) — full reference
