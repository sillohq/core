---
title: URL Normalization
description: URL normalization middleware for trailing slashes, double slashes, and case normalization in sillo.
---

# URL Normalization

The `sillo.normalize` module provides URL normalization middleware and helper utilities. It handles trailing slashes, double slashes, case normalization, and path cleaning.

## Installation

`sillo.normalize` is a first-party module included with sillo. No extra install required.

## Quick Start

```python
from sillo import silloApp
from sillo.normalize import Normalize, SlashAction

app = silloApp()

app.use(Normalize(
    slash_action=SlashAction.REDIRECT_REMOVE,
    redirect_status_code=301,
))

@app.get("/users")
async def users(request, response):
    return {"users": ["alice", "bob"]}
```

Requests to `/users/` redirect to `/users`. Double slashes like `//users//123` are cleaned to `/users/123`.

## Slash Actions

| Action | Behavior |
|---|---|
| `REDIRECT_REMOVE` | 301 redirect to remove trailing slash |
| `REDIRECT_ADD` | 301 redirect to add trailing slash |
| `REMOVE` | Remove trailing slash silently |
| `ADD` | Add trailing slash silently |
| `IGNORE` | Leave slashes as-is |

## Configuration Options

| Option | Type | Default | Description |
|---|---|---|---|
| `slash_action` | `SlashAction` | `REDIRECT_REMOVE` | Trailing slash policy |
| `auto_remove_double_slashes` | `bool` | `True` | Clean `//` → `/` |
| `redirect_status_code` | `int` | `301` | Redirect HTTP status |
| `normalize_case` | `bool` | `False` | Lowercase path |

## Examples

### SEO-Friendly Redirects

```python
app.use(Normalize(slash_action=SlashAction.REDIRECT_REMOVE))
# /blog/posts/ → 301 → /blog/posts
```

### Silent Normalization (no redirects)

```python
app.use(Normalize(
    slash_action=SlashAction.REMOVE,
    auto_remove_double_slashes=True,
))
# /api/users/ → silently treated as /api/users
```

### Case-Insensitive Paths

```python
app.use(Normalize(
    slash_action=SlashAction.IGNORE,
    normalize_case=True,
))
# /API/Users → /api/users
```

## Helper Functions

```python
from sillo.normalize import normalize_path, has_trailing_slash, clean_url_path

normalize_path("//a//b//")       # "/a/b/"
has_trailing_slash("/path/")     # True
clean_url_path("https://x.com//a//b")  # "https://x.com/a/b"
```

Built with ❤️ by [@sillo-labs](https://github.com/sillo-labs).
