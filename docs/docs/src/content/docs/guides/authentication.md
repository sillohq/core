---
title: Authentication
description: How authentication works in sillo — the AuthenticationMiddleware + backend model, the useAuth route gate, and the three built-in backends (JWT, session, API key).
head:
- tag: meta
  attrs:
    property: og:title
    content: Authentication in sillo
- tag: meta
  attrs:
    property: og:description
    content: sillo authentication model — middleware, backends, useAuth, and JWT/session/API-key strategies.
---

# Authentication

sillo authentication has two moving parts:

1. **`AuthenticationMiddleware`** runs once per request and resolves *who* the caller is, attaching a user object to `request.user`.
2. **`useAuth`** is a per-route gate that decides *whether* the resolved user is allowed to call that specific handler.

The middleware is backend-driven: each backend knows how to read one credential type (a JWT, a session cookie, an API key). You compose backends to support multiple auth strategies in the same app.

## The smallest useful form

A single JWT backend protecting the whole app:

```python
from sillo import silloApp
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.jwt_auth import JWTAuthBackend
from sillo.users import User

app = silloApp()

app.use(AuthenticationMiddleware(
    user_model=User,
    backend=JWTAuthBackend(secret_key="change-me", identifier="sub"),
))

@app.get("/me", auth=useAuth())
async def me(request, response):
    return {"id": request.user.identity, "email": request.user.email}
```

Two things to internalize from this snippet:

- `identifier="sub"` is **required** for the built-in `TokenForUser` — it writes the user id into the JWT `sub` claim, and the backend reads the claim named by `identifier`. The default `identifier` is `"id"`, which will not match and silently yields an unauthenticated user.
- `useAuth()` with no arguments means "any authenticated user." Without it the handler runs even for anonymous callers.

## How a request is authenticated

For each request the middleware walks its backends in order and stops at the first that succeeds:

```
request
  → backend 1 (e.g. JWT)  → success? use it
  → backend 2 (e.g. session) → success? use it
  → ...
  → none succeed → request.user = UnauthenticatedUser
```

On success the backend returns an `AuthResult(identity, scope)`. The middleware then calls `user_model.load_user(identity)` to produce the full user object and stores it on `request.scope["user"]`, plus the backend's `scope` string (e.g. `"jwt"`, `"session"`, `"apikey"`) on `request.scope["auth"]`.

Scope strings are what `useAuth(scopes=[...])` later checks against. They let you accept "any logged-in user" or restrict a route to one method.

## Combining backends

Pass a list to accept more than one credential type. Order matters — JWT is tried before session below:

```python
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=[
        JWTAuthBackend(secret_key=JWT_SECRET, identifier="sub"),
        SessionAuthBackend(),
    ],
))
```

A request carrying a valid bearer token authenticates as `"jwt"`; one with only a session cookie authenticates as `"session"`; a request with neither gets `UnauthenticatedUser` and `request.scope["auth"]` is `None`.

## The route gate

`useAuth` runs *after* the middleware, right before your handler. It inspects `request.user` and the auth scope:

```python
# any authenticated user
@app.get("/me", auth=useAuth())

# only JWT-authenticated callers
@app.get("/api", auth=useAuth(scopes=["jwt"]))

# requires a specific permission on the user object
@app.get("/users", auth=useAuth(permissions=["read:users"]))

# runs either way; check request.user.is_authenticated inside
@app.get("/feed", auth=useAuth(required=False))
```

On failure it raises `AuthenticationFailed` (401) or `PermissionDenied` (403). See [Protecting Routes](/guides/protecting-routes/) for the full gate reference.

## Choosing a strategy

| Strategy | Credential | Best for |
| --- | --- | --- |
| JWT | `Authorization: Bearer <token>` | SPAs, mobile, stateless APIs |
| Session | signed cookie (via `SessionMiddleware`) | server-rendered web apps |
| API key | `X-API-Key` header | server-to-server, programmatic access |

You are not limited to one — combining JWT + session (as above) is common for an app that serves both a browser UI and a JSON API. Each strategy has its own page:

- [JWT Authentication](/guides/jwt-auth/)
- [Session Authentication](/guides/session-auth/)
- [API Keys](/guides/api-keys/)

## What a user object looks like

Every `user_model` must satisfy the `AbstractBaseUser` contract: `is_authenticated`, `identity`, `display_name`, `has_perm`/`has_permission`, and a `load_user(identity)` classmethod. sillo ships a ready `User` model (Record/Tortoise-backed) and a lightweight `SimpleUser` for tests. See [Users & User Models](/guides/users/) for building custom users and password hashing.

<aside type="caution" title="The middleware sets the user, the gate enforces it">
`AuthenticationMiddleware` only *resolves* the user. It never rejects a request — an anonymous caller still reaches your handler with `request.user.is_authenticated == False`. Rejecting unauthorized callers is the job of `useAuth`. Always put `auth=useAuth()` (or a more specific variant) on protected routes rather than checking `request.user` by hand inside the handler.
</aside>

## Error handling

Both auth failures surface as HTTP exceptions you can catch and reformat like any other:

```python
from sillo.auth.exceptions import AuthenticationFailed, PermissionDenied

@app.add_exception_handler(AuthenticationFailed)
async def on_401(request, response, exc):
    return response.json({"error": "unauthorized"}, status_code=401)
```

`AuthenticationFailed` → 401, `PermissionDenied` → 403.

## Next steps

- [Protecting Routes](/guides/protecting-routes/) — every `useAuth` option, scopes, permissions, subclassing
- [Users & User Models](/guides/users/) — `User`, `AbstractBaseUser`, `SimpleUser`, passwords
- [JWT Authentication](/guides/jwt-auth/) — issuing and verifying tokens
- [Session Authentication](/guides/session-auth/) — `SessionGuard` and cookie login
- [API Keys](/guides/api-keys/) — scoped, hashed keys
