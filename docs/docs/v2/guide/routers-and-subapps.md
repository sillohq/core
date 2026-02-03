---
title: Routers and Sub-Applications
description: Nexios provides a powerful routing system that allows you to create modular and nested routing structures. Here's an example of how you can use routers and sub-applications in your application
head:
  - - meta
    - property: og:title
      content: Routers and Sub-Applications
  - - meta
    - property: og:description
      content: Nexios provides a powerful routing system that allows you to create modular and nested routing structures. Here's an example of how you can use routers and sub-applications in your application
---
# Routers and Sub-Applications
Nexios provides a powerful routing system that allows you to create modular and nested routing structures. Here's an example of how you can use routers and sub-applications in your application.
## Creating a Router and Mounting it to the Main Application
```python
from nexios import NexiosApp
from nexios.routing import Router

app = NexiosApp()

v1_router = Router(prefix="/v1")

@v1_router.get("/users")
async def list_users(req, res):
    return res.json({"message": "List of users"})

@v1_router.get("/users/{user_id}")
async def get_user(req, res, user_id):
    return res.json({"user_id": user_id})

app.mount_router(v1_router)

```

Using a Different Prefix
If you want the router mounted under a different prefix, set it on the router itself.
```py
v1_router = Router(prefix="/api/v1")
app.mount_router(v1_router)
```
:::tip Tip
`app.mount_router` does not take a prefix argument. Use `Router(prefix="/...")`.
:::

This example creates a router with two routes, one for listing users and another for getting a specific user. The router is then mounted to the main application using the `mount_router` method.

This matches `/v1/users` and `/v1/users/{user_id}`

::: warning ⚠️ Bug Alert
Ensure to use `mount_router` after all routes have been defined.
:::

##  What is Router?

A Router is a container for routes and sub-applications. It allows you to create a modular and nested routing structure in your application.



::: warning ⚠️ Bug Alert
Ensure all mounted sub application or sub-routers have unique prefixes
:::

Routers can contain other routers. This is useful when you want even finer modularization, e.g., versioned APIs with internal domains.
```python

app = NexiosApp()

v1_router = Router(prefix="/v1")
user_router = Router(prefix="/users")

@user_router.get("/")
async def index(req, res):
    return res.text("User root")

@user_router.get("/{id}")
async def detail(req, res, id):
    return res.json({"user": id})

# Mount user_router inside v1_router
v1_router.mount_router(user_router)

# Mount v1_router into the app
app.mount_router(v1_router)

```
Now, the final paths are:

- `/v1/users/`

- `/v1/users/{id}`

You can nest as deeply as you want. Internally, Nexios flattens the route tree during app startup for performance.

The `Router` class also have similar routing methods as `NexiosApp` class


## Sub-Applications = Routers

NexiosApp is an ASGI application. To mount a sub-app under a path, use `register`.

```py
main_app = NexiosApp()
admin_app = NexiosApp()

@admin_app.get("/dashboard")
async def dashboard(req, res):
    return res.text("Welcome to the admin panel")

main_app.register(admin_app, "/admin")

```

Now you can access /admin/dashboard.

This makes it trivial to build modular applications where teams can work on separate parts (e.g., auth, billing, analytics) in isolation and plug them into a larger system


## Groups 

Nexios also supports groups, which is a way to group routes together and share them between multiple apps.

Sometimes you want to group routes or apps under a shared path or with middleware applied collectively — that’s where Group comes in.

```py

from nexios.routing import Router,Group,Route
from nexios import NexiosApp

users = Router()

async def list_users(req, res):
    return res.json(["John", "Jane"])


async def get_user(req, res, id):
    return res.json({"user": id})

group = Group(
    path="/users",
    routes=[
        Route(path="/", methods=["GET"], handler=list_users),
        Route(path="/{id}", methods=["GET"], handler=get_user),
    ],
)

app = NexiosApp()
app.add_route(group)

```

Now you can access `/users` and `/users/{id}`


## Grouping Sub-Applications

Nexios supports grouping sub-applications under a shared path or with middleware applied collectively.

```py

from nexios import NexiosApp
from nexios.grouping import Group

admin_app = NexiosApp()

@admin_app.get("/dashboard")
async def dashboard(req, res):
    return res.text("Welcome to the admin panel")

group = Group(path="/admin", app=admin_app)

main_app = NexiosApp()
main_app.register(group)

```

Now you can access /admin/dashboard

## External ASGI Apps

Nexios `.register` method allows you to mount other asgi application on the `NexiosApp` Instnce or `Router` class

```py
app = NexiosApp()

def external_app(scope, receive , send):
    ...

app.register(external_app, "/mount_path")
```

You can also mount  a `fastapi` or `starlatte` app

```py
from nexios import NexiosApp
from fastapi import FastApi

app = NexiosApp()

fast_app = FastApi()

app.register(fast_app,"/service2")
```

