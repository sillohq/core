---
title: Authentication
description: How authentication works in sillo — the two-layer model (AuthenticationMiddleware resolves who, useAuth enforces policy), backends, the identity-to-user flow, composing strategies, custom backends, and error handling. Starts with the smallest working integration.
head:
- tag: meta
  attrs:
    property: og:title
    content: Authentication in sillo
- tag: meta
  attrs:
    property: og:description
    content: sillo authentication model — middleware, backends, useAuth, identity flow, and JWT/session/API-key strategies.
---

# Authentication

sillo authentication has a clean two-layer shape:

1. **`AuthenticationMiddleware`** runs once per request and answers *who is this caller?* It attaches a user object to `request.user`. It never rejects a request.
2. **`useAuth`** is a per-route gate that answers *is this user allowed to call this handler?* It runs just before your handler and raises 401/403 on failure.

The middleware is **backend-driven**: each backend knows how to read exactly one credential type — a JWT, a session cookie, or an API key. You compose backends to support several auth strategies in one app.

## The smallest working integration

This is the whole thing: a JWT backend that resolves `request.user`, and a protected `/me` route.

```python
# app.py
from sillo import silloApp
from sillo.record import setup_record, DatabaseConfig
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.jwt_auth import JWTAuthBackend
from sillo.users import User

app = silloApp()

# database (creates the "users" table)
db = setup_record(app, DatabaseConfig.sqlite("app.db"), model_modules=["myapp.models"])

# resolve request.user from a bearer token
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=JWTAuthBackend(secret_key="change-me", identifier="sub"),
))

@app.get("/me", auth=useAuth())
async def me(request, response):
    return {"id": request.user.identity, "email": request.user.email}
```

```python
# myapp/models.py
from sillo.users import User

# create a user once, then issue a token for it
user = await User.objects.create_user(
    email="alice@example.com", username="alice", password="StrongP@ss1",
)
token = TokenForUser(user, secret="change-me").token_pair()["access_token"]
# GET /me  with  Authorization: Bearer <token>  →  request.user is alice
```

Two things to internalize from this snippet:

- **`identifier="sub"` is required** for sillo-issued tokens. `TokenForUser` writes the user id into the JWT `sub` claim, and the backend reads the claim named by `identifier`. The backend defaults to `identifier="id"`, which won't match — leaving you with an empty identity and an unauthenticated user. Always pin `identifier="sub"` unless you issue tokens with a different claim.
- **`useAuth()` with no args means "any authenticated user."** Without it, the handler runs even for anonymous callers (with `AnonymousUser` as `request.user`). The middleware resolves; the gate enforces.

## The two layers, in detail

### Layer 1 — AuthenticationMiddleware resolves the user

For every request, the middleware walks its backends in order and stops at the first that succeeds:

```
request
  → backend 1 (e.g. JWT)      → success? use it
  → backend 2 (e.g. session)  → success? use it
  → ...
  → none succeed              → request.user = AnonymousUser
```

On success a backend returns an `AuthResult(identity, scope)`. The middleware then calls `user_model.load_user(identity)` to build the full user object and stores it on `request.scope["user"]`. It also stores the backend's `scope` string (e.g. `"jwt"`, `"session"`, `"apikey"`) on `request.scope["auth"]`.

So the central arrow in sillo auth is: **credential → identity string → `load_user` → `request.user`**. Everything else is a way of producing that identity.

### Layer 2 — useAuth enforces policy

`useAuth` runs *after* the middleware, right before your handler. It inspects `request.user` and `request.scope["auth"]` and decides yes/no:

```python
@app.get("/me", auth=useAuth())                          # any authenticated user
@app.get("/api", auth=useAuth(scopes=["jwt"]))           # only JWT callers
@app.get("/users", auth=useAuth(permissions=["read:users"]))
@app.get("/feed", auth=useAuth(required=False))          # runs either way
```

On failure it raises `AuthenticationFailed` (401) or `PermissionDenied` (403). See [Protecting Routes](/guides/protecting-routes/) for the full gate reference.

<aside type="caution" title="The middleware sets the user; the gate enforces it">
`AuthenticationMiddleware` only *resolves* the user. It deliberately never rejects a request — an anonymous caller still reaches your handler with `request.user.is_authenticated == False`. Rejecting unauthorized callers is the job of `useAuth`. Put `auth=useAuth()` (or a stricter variant) on every protected route rather than hand-checking `request.user` inside the handler — it's the single, testable boundary.
</aside>

## Scope strings

Each backend stamps a `scope` on `request.scope["auth"]`. That string is what `useAuth(scopes=[...])` checks against:

| Backend | `request.scope["auth"]` |
| --- | --- |
| `JWTAuthBackend` | `"jwt"` |
| `SessionAuthBackend` | `"session"` |
| `APIKeyAuthBackend` | `"apikey"` |

`scopes=[]` (the default) accepts *any* method. `scopes=["jwt"]` restricts a route to JWT callers — self-documenting and a useful guard against the wrong credential type reaching a handler.

## Combining backends

Pass a list to accept more than one credential type. **Order matters** — the first backend that succeeds wins:

```python
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=[
        JWTAuthBackend(secret_key=JWT_SECRET, identifier="sub"),
        SessionAuthBackend(),
    ],
))
```

A request with a valid bearer token authenticates as `"jwt"`; one with only a session cookie as `"session"`; one with neither gets `AnonymousUser` and `request.scope["auth"]` is `None`. Combining JWT + session is common for an app that serves both a browser UI and a JSON API.

## Choosing a strategy

| Strategy | Credential | Best for |
| --- | --- | --- |
| JWT | `Authorization: Bearer <token>` | SPAs, mobile, stateless APIs |
| Session | signed cookie (via `SessionMiddleware`) | server-rendered web apps |
| API key | `X-API-Key` header | server-to-server, programmatic access |

You are not limited to one — compose them as above. Each has its own page:

- [JWT Authentication](/guides/jwt-auth/)
- [Session Authentication](/guides/session-auth/)
- [API Keys](/guides/api-keys/)

## What a user object looks like

Every `user_model` satisfies the `AbstractBaseUser` contract: `is_authenticated`, `identity`, `display_name`, `has_permission`, and a `load_user(identity)` classmethod. sillo ships a ready `User` model (Record/Tortoise-backed), a `SimpleUser` for tests, and `AnonymousUser` as the unauthenticated sentinel. The identity the middleware hands to `load_user` is a **string** (the backend's choice — for JWT it's the `sub` claim; for session, the stored user id; for API keys, the `user_id`).

See [Users & User Models](/guides/users/) for the built-in `User`, building custom users, permissions, and password hashing.

## Writing a custom backend

A backend is just `authenticate(request) -> AuthResult`. Return `AuthResult(success=True, identity=..., scope=...)` to accept, or `AuthResult(success=False, ...)` to decline (so the next backend gets a turn). This is how you'd add, say, a Bearer-token-vs-API-key-within-one-header scheme, or an OAuth introspection backend:

```python
from sillo.auth.backends.base import AuthenticationBackend
from sillo.auth.model import AuthResult

class HeaderBackend(AuthenticationBackend):
    async def authenticate(self, request):
        token = request.headers.get("X-Service-Token")
        if not token:
            return AuthResult(success=False, identity="", scope="")
        # ... verify token, resolve a user id ...
        return AuthResult(success=True, identity=str(user_id), scope="service")
```

Register it like any built-in: `AuthenticationMiddleware(user_model=User, backend=HeaderBackend())`. The scope string `"service"` then becomes available to `useAuth(scopes=["service"])`.

## Error handling

Both auth failures surface as HTTP exceptions you can catch and reformat like any other:

```python
from sillo.auth.exceptions import AuthenticationFailed, PermissionDenied

@app.add_exception_handler(AuthenticationFailed)
async def on_401(request, response, exc):
    return response.json({"error": "unauthorized"}, status_code=401)
```

| Condition | Status | Exception |
| --- | --- | --- |
| No user + `required=True` | 401 | `AuthenticationFailed` |
| Scope mismatch | 401 | `AuthenticationFailed` |
| Permission denied | 403 | `PermissionDenied` |

## How it all connects

```
credential (token / cookie / key)
   │  AuthenticationMiddleware
   ├─ backend resolves identity "1"   (scope "jwt"/"session"/"apikey")
   ├─ user_model.load_user("1")  ──►  request.user (loaded User)
   ▼
useAuth()  ── checks is_authenticated / scope / permissions ──►  401 / 403 / handler
```

If you keep that diagram in mind, every other auth feature in sillo is just a different way of producing the credential or the identity on the left.

## Next steps

- [Protecting Routes](/guides/protecting-routes/) — every `useAuth` option, scopes, permissions, subclassing
- [Users & User Models](/guides/users/) — `User`, `AbstractBaseUser`, `SimpleUser`, passwords
- [JWT Authentication](/guides/jwt-auth/) — issuing and verifying tokens
- [Session Authentication](/guides/session-auth/) — `SessionGuard` and cookie login
- [API Keys](/guides/api-keys/) — scoped, hashed keys
