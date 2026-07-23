---
title: Class-Based Views
description: Group related HTTP endpoints in a single class with sillo's APIView — method dispatch, class-level middleware, and per-view error handlers.
head:
- tag: meta
  attrs:
    property: og:title
    content: Class-Based Views in sillo
- tag: meta
  attrs:
    property: og:description
    content: Group related HTTP endpoints in a single class with sillo's APIView — method dispatch, class-level middleware, and per-view error handlers.
---

# Class-Based Views

`APIView` (from `sillo.views`) groups related HTTP endpoints in one class. Each HTTP method you implement — `get`, `post`, `put`, `delete`, `patch` — becomes a handler for that method at the view's path. It also supports class-level `middleware` and `error_handlers`, so cross-cutting logic lives in one place instead of being repeated on every route.

## The smallest useful form

```python
from sillo import silloApp
from sillo.views import APIView

app = silloApp()

class UserView(APIView):
    async def get(self, request, response):
        return response.json({"method": "GET"})

    async def post(self, request, response):
        data = await request.json
        return response.json({"received": data}, status=201)

app.add_route(UserView.as_route("/users"))
```

`UserView.as_route("/users")` returns a `Route` covering every method the class defines. Register it with `app.add_route(...)`, the same call you'd use for a plain route.

## Method dispatch

Implement a method named after the HTTP verb you want to handle. The framework dispatches the incoming request to the matching method; an unimplemented method returns `405 Method Not Allowed`.

```python
class ItemView(APIView):
    async def get(self, request, response):
        item_id = request.path_params["id"]
        return response.json({"id": item_id})

    async def delete(self, request, response):
        item_id = request.path_params["id"]
        return response.json({"deleted": item_id})

app.add_route(ItemView.as_route("/items/{id}"))
```

Limit which methods are served with the `methods` argument:

```python
# Only GET and POST, even if other methods are defined
app.add_route(ItemView.as_route("/items/{id}", methods=["GET", "POST"]))
```

`as_route` also accepts any `Route` option as a keyword — `name=`, `tags=`, `summary=`, `description=`, and so on — for OpenAPI and URL generation.

## Class-level middleware

Set a `middleware` class attribute (a list) to run functions before the method handler. Middleware runs in order; a middleware can short-circuit the request by returning a response directly.

```python
from sillo.views import APIView

def require_auth(request, response, call_next):
    if not request.headers.get("Authorization"):
        return response.json({"error": "unauthorized"}, status=401)
    return call_next()

class ProtectedView(APIView):
    middleware = [require_auth]

    async def get(self, request, response):
        return response.json({"secret": "ok"})

app.add_route(ProtectedView.as_route("/protected"))
```

## Per-view error handlers

Set `error_handlers` to a dict mapping exception types to async handlers `(request, response, exc) -> Response`. Raised exceptions of those types are caught and turned into responses without leaving the view.

```python
from pydantic import ValidationError
from sillo.views import APIView

async def handle_validation(request, response, exc):
    return response.json({"error": exc.errors()}, status=422)

class SignupView(APIView):
    error_handlers = {ValidationError: handle_validation}

    async def post(self, request, response):
        payload = await request.json
        user = UserSchema(**payload)        # raises ValidationError on bad input
        return response.json({"user": user.model_dump()}, status=201)

app.add_route(SignupView.as_route("/signup"))
```

## How dispatch works

When a request hits the view's path, sillo looks for a method on the class whose name matches the HTTP verb (lower-cased): `get`, `post`, `put`, `delete`, `patch`, `head`, `options`. If the method exists (and is allowed by `methods=`, if given), it is called with `(self, request, response)`. If no matching method exists, the view answers `405 Method Not Allowed` — so you only implement the verbs your resource supports.

The class instance is created per request, which means you can safely stash request-scoped state on `self` inside one method (e.g. `self.current_user = ...`) and read it from a helper called later in the same request.

## `as_route` options

`as_route(path, methods=None, **kwargs)` returns a `Route`. Beyond `path` and `methods`, any keyword accepted by `Route` is forwarded — use these for documentation and URL generation:

```python
app.add_route(
    UserView.as_route(
        "/users",
        name="user-collection",   # for url_for("user-collection")
        tags=["users"],           # OpenAPI tag
        summary="List and create users",
        description="Endpoints for the user collection.",
    )
)
```

## Middleware and error handling together

Class-level `middleware` runs *before* the method; `error_handlers` runs *after* a method raises. They compose naturally: auth in middleware, validation errors in `error_handlers`.

```python
from pydantic import BaseModel, ValidationError
from sillo.views import APIView

class CreateComment(BaseModel):
    body: str

def require_auth(request, response, call_next):
    if not request.headers.get("Authorization"):
        return response.json({"error": "unauthorized"}, status=401)
    return call_next()

async def handle_validation(request, response, exc: ValidationError):
    return response.json({"error": "invalid", "details": exc.errors()}, status=422)

class CommentView(APIView):
    middleware = [require_auth]
    error_handlers = {ValidationError: handle_validation}

    async def get(self, request, response):
        return response.json({"comments": []})

    async def post(self, request, response):
        payload = await request.json
        comment = CreateComment(**payload)      # raises ValidationError -> 422
        return response.json({"created": comment.model_dump()}, status=201)

app.add_route(CommentView.as_route("/comments"))
```

## A full CRUD view

Combining path params, methods, middleware, validation, and OpenAPI metadata into one cohesive resource:

```python
from pydantic import BaseModel
from sillo import silloApp
from sillo.views import APIView
from sillo.http.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_404_NOT_FOUND
from sillo.exceptions import HTTPException

app = silloApp()

# in-memory store for the example
_POSTS = {}

class PostIn(BaseModel):
    title: str
    body: str

def require_auth(request, response, call_next):
    if not request.headers.get("Authorization"):
        return response.json({"error": "unauthorized"}, status=401)
    return call_next()

class PostView(APIView):
    middleware = [require_auth]
    tags = ["posts"]

    async def get(self, request, response, id: int):
        post = _POSTS.get(id)
        if post is None:
            raise HTTPException(HTTP_404_NOT_FOUND, "post not found")
        return response.json(post, status=HTTP_200_OK)

    async def put(self, request, response, id: int):
        post = _POSTS.get(id)
        if post is None:
            raise HTTPException(HTTP_404_NOT_FOUND, "post not found")
        data = PostIn(**await request.json)
        post.update(data.model_dump())
        return response.json(post)

    async def delete(self, request, response, id: int):
        _POSTS.pop(id, None)
        return response.json({"deleted": id})

class PostCollection(APIView):
    middleware = [require_auth]
    tags = ["posts"]

    async def get(self, request, response):
        return response.json(list(_POSTS.values()))

    async def post(self, request, response):
        data = PostIn(**await request.json)
        new_id = len(_POSTS) + 1
        _POSTS[new_id] = {"id": new_id, **data.model_dump()}
        return response.json(_POSTS[new_id], status=HTTP_201_CREATED)

app.add_route(PostCollection.as_route("/posts", name="post-collection"))
app.add_route(PostView.as_route("/posts/{id:int}", name="post-detail"))
```

This exposes `GET/POST /posts` and `GET/PUT/DELETE /posts/{id}` with shared auth, shared tags, and clean status codes — the kind of resource that would otherwise be four separate decorated functions.

## Using views inside a Router

`as_route` returns an ordinary `Route`, so you can add it to a `Router` exactly like any other route:

```python
from sillo.routing import Router

api = Router(prefix="/api")
api.add_route(PostCollection.as_route("/posts", name="post-collection"))
api.add_route(PostView.as_route("/posts/{id:int}", name="post-detail"))
app.mount_router(api)
```

## When to use class-based views

- A single resource has several HTTP methods that share middleware, error handling, or helper methods.
- You want to colocate related endpoints and avoid repeating `require_auth`/`error_handlers` on each function.
- You prefer object-oriented organization over flat decorators.

For a one-off endpoint, a plain `@app.get(...)` handler (see [Handlers](/guides/handlers/)) is simpler. Views earn their keep when the resource is rich.

## Testing a view

Because a view is just routes, test it through `TestClient` like any endpoint:

```python
from sillo.testclient import TestClient

resp = TestClient(app).get("/posts", headers={"Authorization": "Bearer x"})
assert resp.status_code == 200

bad = TestClient(app).post(
    "/posts",
    json={"title": "Hi"},                 # missing "body" -> 422 via error_handlers
    headers={"Authorization": "Bearer x"},
)
assert bad.status_code == 422
```

## Works with

- [Handlers](/guides/handlers/) — function-based handlers and the `request`/`response` contract
- [Routing](/guides/routing/) — path syntax, `name=`, and route options
- [Middleware](/guides/middleware/) — app- and router-level middleware
- [Error Handling](/guides/error-handling/) — app-wide exception handlers
- [Dependency Injection](/guides/dependency-injection/) — shared logic as `Depend(...)` instead of class methods
