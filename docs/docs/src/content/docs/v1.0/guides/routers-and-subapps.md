---
title: Routers & Sub-Applications
description: "Organize sillo routes into modular Routers and Groups: prefixes, nesting, mounting sub-applications (including external ASGI apps), and per-router middleware and dependencies."
head:
- tag: meta
  attrs:
    property: og:title
    content: Routers & Sub-Applications in sillo
- tag: meta
  attrs:
    property: og:description
    content: Modular routing in sillo with Router prefixes, nested routers, and Group-mounted sub-apps.
---

#  Routers & Sub-Applications

As an app grows, a single flat list of `@app.get(...)` decorators becomes hard
to navigate. sillo lets you group routes into **`Router`** objects with their
own path prefix, mount them under the main app, and nest them arbitrarily. You
can also mount an entire **sub-application** (another `SilloApp`, or any ASGI
app such as a FastAPI service) under a path using a **`Group`**.

The mental model:

- A **`Router`** is a *collection of routes* plus a prefix. It is not itself an app; you mount it onto an app (or another router).
- A **`Group`** is a *mount point*: it places either a sub-app or a set of routes behind a single path prefix, optionally wrapped in middleware.

Both flatten into the app's route table at startup, so nesting adds no per-request overhead.

##  The smallest useful form

```python
from sillo import SilloApp, HttpContext
from sillo.core.routing import Router

app = SilloApp()

v1 = Router(prefix="/v1")

@v1.get("/users")
async def list_users(ctx: HttpContext):
    return {"users": []}

@v1.get("/users/{user_id}")
async def get_user(ctx: HttpContext, user_id):
    return {"user_id": user_id}

app.mount_router(v1)
```

`app.mount_router(v1)` folds the router's routes into the app under `/v1`, so the handlers answer `GET /v1/users` and `GET /v1/users/{user_id}`.

<aside type="tip" title="mount_router takes no prefix">
The prefix lives on the `Router`, not on `mount_router`. You cannot pass a prefix to `app.mount_router(...)`. Set it once with `Router(prefix="/v1")` and reuse the router everywhere.
</aside>

##  Router options

`Router(...)` accepts more than a prefix:

```python
v1 = Router(
    prefix="/v1",
    tags=["v1"],                       # OpenAPI tag applied to all routes
    dependencies=[...],                # Depends applied to every route in the router
    middleware=[...],                  # router-level middleware (see below)
    name="api-v1",                     # name for the router group
)
```

- **`tags`**: groups the router's endpoints under a tag in generated OpenAPI
  docs.
- **`dependencies`**: a list of `Depend(...)` objects resolved for *every*
  route in the router (e.g. a shared auth dependency).
- **`middleware`**: functions applied to requests matching this router's
  routes.
- **`name`**: an identifier for the router (mostly for referencing in
  tooling/URL generation within the router tree).

##  Nesting routers

A router can mount another router, building a deep prefix tree:

```python
from sillo import SilloApp, HttpContext, text
from sillo.core.routing import Router

app = SilloApp()

v1 = Router(prefix="/v1")
users = Router(prefix="/users")

@users.get("/")
async def users_index(ctx: HttpContext):
    return text("User root")

@users.get("/{id}")
async def users_detail(ctx: HttpContext, id):
    return {"user": id}

# nest: /v1/users/*
v1.mount_router(users)
# mount the tree onto the app: /v1/users/*
app.mount_router(v1)
```

Final paths: `/v1/users/` and `/v1/users/{id}`. You can nest as deeply as you
like: `v1.mount_router(users)`, `users.mount_router(posts)`, and so on. sillo
resolves the full prefix by walking the tree at startup.

##  Per-router middleware and dependencies

Middleware and dependencies declared on a router run only for routes under that router. This is how you scope "require auth for everything under `/admin`" without touching each handler:

```python
from sillo import SilloApp, HttpContext, text, Depend
from sillo.core.routing import Router

app = SilloApp()

admin = Router(prefix="/admin", tags=["admin"])

def require_staff(ctx: HttpContext):
    if not ctx.headers.get("X-Staff"):
        from sillo.exceptions import HTTPException
        raise HTTPException(403, "staff only")
    return True

@admin.get("/dashboard")
async def dashboard(ctx: HttpContext, _staff=Depend(require_staff)):
    return text("secret dashboard")

app.mount_router(admin)
```

Here `require_staff` resolves for every route registered on `admin`. (You can also pass `dependencies=[Depend(require_staff)]` to the `Router` constructor to apply it uniformly.)

##  Groups: mounting a sub-application

When the thing you want to mount is itself an app (a separate `SilloApp`, or
any ASGI app) use `Group`. A `Group` takes either `app=` (an ASGI app) or
`routes=` (a list of `Route` objects), plus a `path` prefix.

###  Mounting another SilloApp

```python
from sillo import SilloApp, HttpContext, text
from sillo.core.routing import Group

main_app = SilloApp()
admin_app = SilloApp()

@admin_app.get("/dashboard")
async def dashboard(ctx: HttpContext):
    return text("Welcome to the admin panel")

admin_group = Group(path="/admin", app=admin_app)
main_app.add_route(admin_group)
```

Now `/admin/dashboard` is served by `admin_app`. The sub-app keeps its own
routes, handlers, and (if you add them) its own middleware, useful when
different teams own different parts of a system.

###  Mounting a list of routes

```python
from sillo.core.routing import Router, Group, Route
from sillo import SilloApp, HttpContext

users = Router()

async def list_users(ctx: HttpContext):
    return ["John", "Jane"]

async def get_user(ctx: HttpContext, id):
    return {"user": id}

group = Group(
    path="/users",
    routes=[
        Route(path="/", methods=["GET"], handler=list_users),
        Route(path="/{id}", methods=["GET"], handler=get_user),
    ],
)
app = SilloApp()
app.add_route(group)
```

This answers `/users` and `/users/{id}`. `Group` with `routes=` is essentially a prefix wrapper around a set of `Route` objects; `Group` with `app=` mounts a whole app.

##  Mounting external ASGI apps

Because a `Group` accepts any ASGI app, you can mount a FastAPI (or Starlette, Quart, …) service under a path without rewriting it:

```python
from sillo import SilloApp
from sillo.core.routing import Group
from fastapi import FastAPI

app = SilloApp()
fast_app = FastAPI()

@fast_app.get("/ping")
def ping():
    return {"ping": "pong"}

fast_group = Group(path="/service2", app=fast_app)
app.add_route(fast_group)
```

Requests to `/service2/ping` are delegated to `fast_app`, whose own routing and middleware run normally. This is the migration-friendly escape hatch: keep a legacy service running while new routes live in sillo.

<aside type="caution" title="Prefix hygiene">
A `Group`'s `path` should start with `/`. If it doesn't, sillo warns and prepends one. Consistent leading slashes keep nested prefixes from collapsing (`/v1` + `/users` → `/v1/users`, not `/v1users`).
</aside>

##  Route names and URL generation

Routes (and routers) accept a `name=` used with `url_for` to build URLs without hard-coding paths:

```python
from sillo import HttpContext

@v1.get("/users/{user_id}", name="get-user")
async def get_user(ctx: HttpContext, user_id):
    return {"user_id": user_id}

@app.get("/home")
async def home(ctx: HttpContext):
    url = ctx.url_for("get-user", user_id=42)   # -> /v1/users/42
    return {"link": str(url)}
```

When a route lives under a router prefix, `url_for` includes that prefix automatically. Name routes once and generate links everywhere.

##  Putting it together: a modular app

```python
from sillo import SilloApp, HttpContext, Depend
from sillo.core.routing import Router, Group

app = SilloApp()

# public API v1
api = Router(prefix="/api/v1", tags=["api"])

@api.get("/health")
async def health(ctx: HttpContext):
    return {"status": "ok"}

# admin sub-app
admin = SilloApp()

@admin.get("/stats")
async def stats(ctx: HttpContext):
    return {"requests": 0}

# compose
app.mount_router(api)
app.add_route(Group(path="/admin", app=admin))
```

This gives you `/api/v1/health` and `/admin/stats` from two independently-defined pieces.

##  Works with

- [Routing](/v1.0/guides/routing/): path syntax, converters, `name=`, and all route
  options
- [Handlers](/v1.0/guides/handlers/): the handler contract used inside routers
- [Middleware](/v1.0/guides/middleware/): router-scoped and global middleware
- [Handlers](/v1.0/guides/handlers/): define function handlers for router endpoints
- [Dependency Injection](/v1.0/guides/dependency-injection/): router-level
  `dependencies=`

##  Related topics

- [Startup & Shutdown](/v1.0/guides/startups-and-shutdowns/): run setup when the
  composed app boots
- [Error Handling](/v1.0/guides/error-handling/): exception handlers registered per
  app vs. globally
- [Events](/v1.0/guides/events/): router-level event hooks
