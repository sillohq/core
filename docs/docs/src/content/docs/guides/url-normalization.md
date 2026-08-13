---
title: URL Normalization
description: Keep URLs consistent (trailing slashes, double slashes, and case) with the first-party sillo.normalize middleware.
---

#  URL Normalization

`sillo.normalize` is a first-party module that rewrites inconsistent request paths into a single canonical form before routing runs. It handles three problems:

- **Trailing slashes** — `/users/` vs `/users` should resolve to one form, not both.
- **Double slashes** — `//users//123` is collapsed to `/users/123`.
- **Path case** — optionally lowercased so `/API/Users` and `/api/users` are the same route.

Use it to avoid duplicate content, broken bookmarks, and split analytics, and to keep API clients from guessing which URL shape is "correct."

##  The smallest useful form

```python
from sillo import SilloApp
from sillo.normalize import Normalize, SlashAction

app = SilloApp()

app.use(Normalize(slash_action=SlashAction.REDIRECT_REMOVE))

@app.get("/users")
async def users(request, response):
    return {"users": ["alice", "bob"]}
```

With the default `REDIRECT_REMOVE`, a request to `/users/` is answered with a **`301`** redirect to `/users`; `//users//123` is cleaned to `/users/123` before the redirect target is computed. The handler only ever sees the canonical path.

##  How a request is normalized

`NormalizeMiddleware.process_request` runs this sequence for every request:

1. **Skip** paths that contain `.`, `?`, or `#` (files, queries, fragments) — these are never rewritten.
2. **Collapse double slashes** when `auto_remove_double_slashes=True` (the default).
3. **Lowercase** the path when `normalize_case=True`.
4. **Apply the slash action** — either mutate `request.scope["path"]` in place (silent modes) or return a `301`/`302` redirect (redirect modes).
5. Otherwise call `await call_next()` unchanged.

Because silent modes rewrite `request.scope["path"]`, the router matches the cleaned path with no extra round trip. Redirect modes send the client to the canonical URL and stop there.

##  Slash actions

| Action | Behavior |
| --- | --- |
| `REDIRECT_REMOVE` (default) | `301` redirect that strips the trailing slash |
| `REDIRECT_ADD` | `301` redirect that appends the trailing slash |
| `REMOVE` | Strips the trailing slash silently (no redirect) |
| `ADD` | Appends the trailing slash silently (no redirect) |
| `IGNORE` | Leaves slashes as-is; still collapses double slashes |

##  Configuration

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `slash_action` | `SlashAction` | `REDIRECT_REMOVE` | Trailing-slash policy |
| `auto_remove_double_slashes` | `bool` | `True` | Collapse `//` → `/` |
| `redirect_status_code` | `int` | `301` | Status for redirect modes |
| `normalize_case` | `bool` | `False` | Lowercase the path |

##  Scenarios

**SEO-friendly public site** — pick one form and redirect to it so search engines index a single URL:

```python
app.use(Normalize(slash_action=SlashAction.REDIRECT_REMOVE, redirect_status_code=301))
# /blog/posts/ → 301 → /blog/posts
```

**Internal API that must not redirect** — silent normalization keeps clients from following extra hops:

```python
app.use(Normalize(slash_action=SlashAction.REMOVE, auto_remove_double_slashes=True))
# /api/users/ is handled as /api/users
```

**Case-insensitive legacy routes** — lowercasing the path unifies `/API/Users` and `/api/users`:

```python
app.use(Normalize(slash_action=SlashAction.IGNORE, normalize_case=True))
```

<aside type="caution" title="normalize_case can break routes">
Lowercasing rewrites the path for *every* request. If your routes are case-sensitive (e.g. `/Users/{id}` vs `/users/{id}` are different handlers), `normalize_case=True` will collapse them and route to the wrong handler. Only enable it when all your routes are intentionally lowercase.
</aside>

##  Helper functions

The same logic is available as pure functions for building URLs outside the request lifecycle:

```python
from sillo.normalize import normalize_path, has_trailing_slash, clean_url_path

normalize_path("//a//b//")          # "/a/b/"
has_trailing_slash("/path/")        # True
clean_url_path("https://x.com//a//b")  # "https://x.com/a/b"
```

##  Errors and edge cases

- **Infinite redirect loops** — happen when a redirect mode disagrees with your route definitions. If routes are registered *with* a trailing slash but `slash_action=REDIRECT_REMOVE`, the middleware redirects away from the only matching route. Make the slash action match how routes are defined.
- **Static files and assets** — paths containing a `.` (e.g. `/static/app.js`) are skipped, so asset URLs are never rewritten.
- **Skipped paths** — anything with `?` or `#` is passed through untouched; normalization only touches the path segment.
- **`normalize_case` + mixed-case routes** — as noted above, this silently merges distinct routes.

##  Testing

Use `TestClient` and assert the redirect (or the served path) for redirect vs silent modes:

```python
from sillo import SilloApp
from sillo.normalize import Normalize, SlashAction
from sillo.testclient import TestClient


def test_redirect_remove():
    app = SilloApp()
    app.use(Normalize(slash_action=SlashAction.REDIRECT_REMOVE))

    @app.get("/users")
    async def users(request, response):
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/users/")
    assert resp.status_code == 301
    assert resp.headers["location"].endswith("/users")


def test_silent_remove():
    app = SilloApp()
    app.use(Normalize(slash_action=SlashAction.REMOVE))

    seen = {}

    @app.get("/api/users")
    async def users(request, response):
        seen["path"] = request.url.path
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/api/users/").status_code == 200
    assert seen["path"] == "/api/users"
```

##  Works with

- **Routing** — normalization runs in `process_request`, so the router always sees the canonical path. Place `Normalize` early in the middleware chain.
- **Static files** — asset paths are auto-skipped, so normalization never interferes with `static()` mounts.
- **Security middleware** — run `Normalize` before CSRF/Shield so they evaluate the cleaned path consistently.

##  Production considerations

- **Pick one slash behavior** and apply it everywhere; mixing `REMOVE` and `ADD` across services splits your URL space.
- **Use `301` for permanent policy** (SEO-cached by browsers/CDNs); use `302` only for temporary experiments.
- **Silent modes avoid latency** from redirect round trips, which matters for high-throughput APIs.
- **Monitor redirects** in staging — a loop between the middleware and a route is the most common misconfiguration.

##  Related topics

- [Routing](/guides/routing/) — how the canonical path is matched
- [Static Files](/guides/static-files/) — assets skipped by normalization
- [Middleware](/guides/middleware/) — ordering `Normalize` in the chain
