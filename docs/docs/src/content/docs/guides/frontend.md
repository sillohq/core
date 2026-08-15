---
title: Frontend (SPA)
description: sillo makes it easy to serve single-page applications (SPAs) like React, Vue, or Svelte with automatic fallback routing for client-side navigation.
head:
- tag: meta
  attrs:
    property: og:title
    content: Frontend (SPA)
- tag: meta
  attrs:
    property: og:description
    content: sillo makes it easy to serve single-page applications (SPAs) like React, Vue, or Svelte with automatic fallback routing for client-side navigation.
---

#  Frontend (SPA)

sillo provides built-in support for serving single-page applications (SPAs)
like React, Vue, Svelte, or any other frontend framework. The `FrontendApp`
class serves your built static files and automatically falls back to a
configurable HTML file for unknown paths, so client-side routing works
seamlessly.

##  How It Works

1. You build your frontend (e.g. `npm run build`), which produces a directory of static files (typically `dist/`).
2. sillo serves those files directly when the path matches an existing file.
3. For any other path (like `/dashboard` or `/settings`), sillo falls back to your `index.html` (or a custom fallback), letting your JavaScript router handle the routing.

##  Quick Start

The simplest way to serve a frontend is via the `app.frontend()` convenience method:

```python
from sillo import SilloApp

app = SilloApp()

# API routes registered FIRST take precedence
@app.get("/api/health")
async def health(request, response):
    return response.json({"status": "ok"})

# Serve the SPA — unknown paths fall back to index.html
app.frontend("/", directory="./dist")
```

With this setup:
- `/api/health` → returns JSON (API route matched first)
- `/js/app.js` → serves the file from `dist/js/app.js`
- `/dashboard` → serves `dist/index.html` (SPA fallback)
- `/settings/profile` → also serves `dist/index.html`

##  Using `FrontendApp` Directly

For more control, you can instantiate `FrontendApp` directly and mount it as a route:

```python
from sillo import SilloApp
from sillo.frontend import FrontendApp
from sillo.core.routing import Group

app = SilloApp()

spa = FrontendApp(
    directory="./dist",
    fallback="auto",
    cache_control="public, max-age=3600",
)

# Mount at root
app.add_route(Group(path="/", app=spa))
```

##  Fallback Behaviour

The `fallback` parameter controls what happens when a requested file is not found in the directory:

| Value | Behaviour |
|---|---|
| `"auto"` (default) | Tries `404.html` first, then `index.html` |
| `"app.html"` | Falls back to the specified file (e.g. `app.html`) |
| `None` or `False` | No fallback: returns a 404 JSON response |

###  `"auto"` Mode

```python
spa = FrontendApp(directory="./dist", fallback="auto")
```

sillo looks for a fallback file in this order:
1. `404.html`: if present, serves this for unknown routes
2. `index.html`: otherwise, serves this as the SPA entry point

This is useful if you want a distinct error page for invalid routes without overriding the main app shell.

###  Custom Fallback File

```python
spa = FrontendApp(directory="./dist", fallback="app.html")
```

All unknown paths will serve `dist/app.html`.

###  Disable Fallback

```python
spa = FrontendApp(directory="./dist", fallback=None)
```

Unknown paths return a 404 JSON response instead.

##  Route Precedence

**API routes registered before `frontend()` take precedence.** This is
critical. It ensures your backend endpoints are always reachable and not
intercepted by the SPA fallback:

```python
from sillo import SilloApp

app = SilloApp()

# 1. API routes are registered first
@app.get("/api/health")
async def health(request, response):
    return response.json({"status": "ok"})

@app.get("/api/users")
async def get_users(request, response):
    return response.json([{"id": 1, "name": "Alice"}])

# 2. Frontend catches everything else
app.frontend("/", directory="./dist")
```

If you reverse the order, the frontend fallback would catch all paths before the API routes get a chance to match.

##  Cache Control

Set a `Cache-Control` header on all served files (both direct file hits and fallback responses):

```python
spa = FrontendApp(
    directory="./dist",
    fallback="auto",
    cache_control="public, max-age=86400",  # 24 hours
)
```

##  Mounting at a Sub-path

You can serve the frontend from a sub-path instead of the root:

```python
# All frontend files are served under /app/
app.frontend("/app", directory="./dist")
```

Now your SPA is accessible at `/app/`, and files are served from `/app/js/...`, `/app/css/...`, etc. Unknown paths under `/app/` still fall back to the configured HTML file.

Using `FrontendApp` directly:

```python
spa = FrontendApp(directory="./dist", fallback="auto")
app.add_route(Group(path="/app", app=spa))
```

##  Security

`FrontendApp` includes a path traversal protection that resolves all requested paths and ensures they stay within the configured directory. Requests attempting to use `../` or symlinks to escape the directory will receive a 404 response.

Only `GET` requests are allowed: `POST`, `PUT`, `DELETE`, and other methods
return `405 Method Not Allowed`.

##  Reference

###  `FrontendApp`

```text
class FrontendApp(
    directory: Union[str, Path],
    fallback: Optional[Union[str, bool]] = "auto",
    cache_control: Optional[str] = None,
)
```

###  `SilloApp.frontend()`

```text
def app.frontend(
    path: str = "/",
    directory: Union[str, Path] = "dist",
    fallback: Optional[Union[str, bool]] = "auto",
    name: Optional[str] = None,
    cache_control: Optional[str] = None,
) -> None
```

###  `BaseRouter.frontend()`

Router and sub-applications also expose `frontend()` with the same signature, so you can mount a frontend on a sub-router if needed.
