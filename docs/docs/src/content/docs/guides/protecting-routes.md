---
title: Protecting Routes
description: Enforce authentication and authorisation on your routes with useAuth — sillo's primary route protection API. Covers required auth, scopes, permissions, optional auth, backend overrides and subclassing.
head:
- tag: meta
  attrs:
    property: og:title
    content: Protecting Routes with useAuth
- tag: meta
  attrs:
    property: og:description
    content: Enforce authentication and authorisation with useAuth — scopes, permissions, optional auth, backend overrides and subclassing.
---

# Protecting Routes

`useAuth` is the primary — and recommended — way to protect routes in sillo. It replaces the older `@auth()` decorator pattern with a clean, composable route-argument approach.

## Quick Reference

```python
from sillo.auth import useAuth

# Require any authenticated user
@app.get("/profile", auth=useAuth())

# Require a specific auth method
@app.get("/admin", auth=useAuth(scopes=["jwt"]))

# Require permissions
@app.get("/users", auth=useAuth(permissions=["read:users"]))

# Combine scopes and permissions
@app.get("/dashboard", auth=useAuth(scopes=["jwt", "session"], permissions=["access:dashboard"]))

# Optional — attach user if present, allow through if not
@app.get("/feed", auth=useAuth(required=False))

# Override middleware backends for one route
@app.get("/internal", auth=useAuth(backends=[APIKeyAuthBackend()]))
```

## How It Works

`useAuth` runs inside the route handler pipeline, after dependencies are resolved but before your handler executes. This means:

1. The middleware has already run and set `request.user` and `request.scope["auth"]`
2. Your dependencies are already injected
3. Your request body is already validated (if `request_model` is set)
4. `useAuth` checks auth → if it fails, your handler never runs
5. If it passes, your handler receives a fully-resolved authenticated user

## Full Parameter Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scopes` | `list[str]` | `[]` | Auth method scopes required. Empty list = any method accepted. Each backend sets a scope string on `request.scope["auth"]` (e.g. `"jwt"`, `"session"`, `"apikey"`). At least one listed scope must match. |
| `permissions` | `list[str]` | `[]` | Permission strings checked via `user.has_permission(perm)`. All must pass. |
| `backends` | `list[AuthenticationBackend]` | `None` | Replace the globally configured middleware backends for this route only. On success, `request.scope["user"]` and `request.scope["auth"]` are overwritten. |
| `user_model` | `type[BaseUser]` | `None` | User model for loading identities when `backends` is provided. Defaults to `SimpleUser`. |
| `required` | `bool` | `True` | When `False`, unauthenticated requests pass through with an `UnauthenticatedUser` on the scope. No rejection. |

## Required Authentication

The simplest form — any authenticated user, regardless of how they authenticated.

```python
from sillo.auth import useAuth

@app.get("/profile", auth=useAuth())
async def profile(request, response):
    return response.json({
        "username": request.user.display_name,
    })
```

Unauthenticated requests → **401 Unauthorized**. Authenticated requests → your handler runs.

```bash
# No token → 401
curl http://localhost:8000/profile
# {"detail": "Authentication failed"}

# Valid token → 200
curl -H "Authorization: Bearer eyJ..." http://localhost:8000/profile
# {"username": "alice"}
```

## Scope Restriction

Restrict which auth methods are accepted. Each backend sets a scope string — `"jwt"`, `"session"`, `"apikey"` — and `useAuth(scopes=...)` checks that at least one matches.

```python
# Only JWT
@app.get("/api/v2", auth=useAuth(scopes=["jwt"]))
async def api_v2(request, response): ...

# JWT or session
@app.get("/dashboard", auth=useAuth(scopes=["jwt", "session"]))
async def dashboard(request, response): ...

# Only API keys
@app.get("/webhook", auth=useAuth(scopes=["apikey"]))
async def webhook(request, response): ...
```

A JWT-authenticated user hitting `/webhook` gets a **401** — even though they're authenticated, they're not authenticated via an API key.

## Permission Checks

Permission strings are checked against `user.has_permission(perm)`. Your User model must implement this method.

```python
from sillo.users import AbstractBaseUser

class User(AbstractBaseUser):
    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions
```

Then protect routes:

```python
@app.get("/users", auth=useAuth(permissions=["read:users"]))
async def list_users(request, response): ...

@app.delete("/users/{id}", auth=useAuth(permissions=["delete:users"]))
async def delete_user(request, response): ...
```

All listed permissions must pass. If the user has `read:users` but not `delete:users`, the delete route returns **403 Forbidden**.

## Combined Scopes + Permissions

```python
@app.get("/admin/users", auth=useAuth(
    scopes=["jwt"],                # must be JWT-authenticated
    permissions=["admin:users"],   # must have admin:users permission
))
async def admin_users(request, response): ...
```

Both conditions must be met. A session-authenticated admin → **401**. A JWT-authenticated non-admin → **403**.

## Optional Authentication

`required=False` lets unauthenticated requests through. The user object is still attached if credentials are present, but no rejection occurs.

```python
@app.get("/feed", auth=useAuth(required=False))
async def feed(request, response):
    if request.user.is_authenticated:
        items = await get_personalized_feed(request.user)
    else:
        items = await get_public_feed()
    return response.json(items)
```

This is perfect for pages that behave differently for logged-in vs anonymous users — like a news feed, a product page with personalized recommendations, or a search page that saves history for authenticated users.

## Route-Level Backend Override

Bypass the globally configured middleware backends for a specific route. This is useful when:

- An internal endpoint should only accept API keys, not JWT
- A specific route needs a different header name for the API key
- You want per-route database-backed API key verification

```python
from sillo.auth.apikey import APIKeyAuthBackend

@app.get("/internal/health", auth=useAuth(
    backends=[APIKeyAuthBackend(header_name="X-Internal-Key")],
))
async def health(request, response):
    return response.json({"status": "ok"})
```

When `backends` is provided, each backend's `authenticate()` is called for this route only. On success, `request.scope["user"]` and `request.scope["auth"]` are overwritten with the new backend's result.

With a custom user model:

```python
class ServiceUser:
    def __init__(self, name):
        self.name = name

    @property
    def is_authenticated(self): return True
    @property
    def identity(self): return self.name
    @property
    def display_name(self): return self.name

    @classmethod
    async def load_user(cls, identity):
        return cls(identity)

@app.get("/internal/status", auth=useAuth(
    backends=[APIKeyAuthBackend(header_name="X-Service-Key")],
    user_model=ServiceUser,
))
async def status(request, response):
    return response.json({"service": request.user.display_name})
```

## Subclassing useAuth

Create custom auth gates by subclassing `useAuth` and overriding `authenticate()`:

```python
from sillo.auth import useAuth
from sillo.auth.exceptions import AuthenticationFailed

class OrgScoped(useAuth):
    def __init__(self, org_id_param: str, **kwargs):
        super().__init__(**kwargs)
        self.org_id_param = org_id_param

    async def authenticate(self, request) -> bool:
        # Run standard checks first (user, scopes, permissions)
        if not await super().authenticate(request):
            return False

        # Custom: verify user belongs to the requested org
        org_id = request.path_params[self.org_id_param]
        if not request.user.belongs_to_org(org_id):
            raise AuthenticationFailed

        return True


@app.get("/orgs/{org_id}/members", auth=OrgScoped(
    org_id_param="org_id",
    scopes=["jwt"],
    permissions=["read:members"],
))
async def org_members(request, response, org_id: str):
    members = await get_members(org_id)
    return response.json(members)
```

The pattern is:
1. Call `super().authenticate(request)` — this checks user, scopes, and permissions
2. Add your custom logic
3. Return `True` to allow, raise `AuthenticationFailed` or `PermissionDenied` to reject

## Subclass Example: Rate Limiting by User

```python
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimited(useAuth):
    _attempts = defaultdict(list)

    def __init__(self, max_requests: int, window_seconds: int, **kwargs):
        super().__init__(**kwargs)
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)

    async def authenticate(self, request) -> bool:
        if not await super().authenticate(request):
            return False

        now = datetime.now()
        user_key = request.user.identity
        self._attempts[user_key] = [
            t for t in self._attempts[user_key]
            if now - t < self.window
        ]

        if len(self._attempts[user_key]) >= self.max_requests:
            raise AuthenticationFailed("Rate limit exceeded")

        self._attempts[user_key].append(now)
        return True


@app.get("/expensive", auth=RateLimited(max_requests=5, window_seconds=60))
async def expensive(request, response):
    return response.json({"data": compute_expensive_thing()})
```

## Subclass Example: IP Whitelist

```python
class IPWhitelisted(useAuth):
    def __init__(self, allowed_ips: list[str], **kwargs):
        super().__init__(**kwargs)
        self.allowed_ips = set(allowed_ips)

    async def authenticate(self, request) -> bool:
        if not await super().authenticate(request):
            return False

        client_ip = request.client.host if request.client else None
        if client_ip not in self.allowed_ips:
            raise AuthenticationFailed("IP not whitelisted")

        return True

ADMIN_IPS = ["10.0.0.1", "10.0.0.2"]

@app.get("/admin", auth=IPWhitelisted(
    allowed_ips=ADMIN_IPS,
    scopes=["jwt"],
    permissions=["admin"],
))
async def admin(request, response): ...
```

## Using useAuth with Routers

`useAuth` works identically on `Router` instances — useful for protecting entire groups of routes:

```python
from sillo.routing import Router

api = Router(prefix="/api")

@api.get("/users", auth=useAuth(scopes=["jwt"]))
async def list_users(request, response): ...

@api.get("/users/{id}", auth=useAuth(scopes=["jwt"], permissions=["read:users"]))
async def get_user(request, response, id: int): ...

app.mount_router(api)
```

## Using useAuth with Class-Based Views

If you're using class-based handlers, `useAuth` is passed the same way:

```python
from sillo.views import View

class UserProfileView(View):
    async def get(self, request, response):
        return response.json({"user": request.user.display_name})

# Register with auth
app.route("/profile", UserProfileView, methods=["GET"], auth=useAuth())
```

## What Happens on Failure

| Condition | HTTP Status | Exception |
|-----------|-------------|-----------|
| No user / not authenticated + `required=True` | 401 | `AuthenticationFailed` |
| Scope mismatch | 401 | `AuthenticationFailed` |
| Permission denied | 403 | `PermissionDenied` |
| Backend override fails + `required=True` | 401 | `AuthenticationFailed` |
| `required=False` + no user | 200 (handler runs) | None |

## Best Practices

1. **Use `useAuth` on every protected route** — never rely on manual `if request.user.is_authenticated` checks in the handler. The gate should run before your handler to keep it clean.
2. **Be specific with scopes** — `useAuth(scopes=["jwt"])` is clearer than `useAuth()` when you know which auth method is expected.
3. **Use permissions for business logic** — `read:users`, `write:posts`, `admin:settings` are self-documenting permission strings.
4. **Subclass for cross-cutting concerns** — IP whitelisting, rate limiting, org membership — these belong in a reusable auth gate, not in every handler.
5. **Pass `user_model` with `backends`** — when overriding backends, specify the user model so `load_user` works correctly.
6. **Prefer `useAuth` over the old `@auth()` decorator** — the decorator is maintained for backward compatibility only. All new code should use `useAuth`.

## Related

- [Authentication](/guides/authentication/) — full auth system setup guide
- [JWT Authentication](/guides/jwt-auth/) — `TokenForUser`, token families, blacklisting
- [Session Authentication](/guides/session-auth/) — `SessionGuard`, `Session` model
- [API Keys](/guides/api-keys/) — `ApiKeyManager`, scoped keys
- [Users & User Models](/guides/users/) — password hashing, custom users
