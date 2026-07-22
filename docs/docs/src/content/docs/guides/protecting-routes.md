---
title: Protecting Routes
description: Enforce authentication and authorization on routes with useAuth — sillo's route-level auth gate. Covers required auth, scopes, permissions, optional auth, per-route backend overrides, and subclassing.
head:
- tag: meta
  attrs:
    property: og:title
    content: Protecting Routes with useAuth
- tag: meta
  attrs:
    property: og:description
    content: Enforce auth and authorization with useAuth — scopes, permissions, optional auth, backend overrides, subclassing.
---

# Protecting Routes

`useAuth` is the gate you put on a route to decide whether the already-resolved `request.user` is allowed to call the handler. Pass it as the `auth=` argument to any route registration — decorators (`@app.get`), `app.route`, `Route(...)`, and router decorators all accept it.

It runs after `AuthenticationMiddleware` has set `request.user`, but before your handler body. If the check fails it raises `AuthenticationFailed` (401) or `PermissionDenied` (403) and the handler never executes.

## Quick reference

```python
from sillo.auth import useAuth

@app.get("/profile", auth=useAuth())                       # any logged-in user
@app.get("/admin", auth=useAuth(scopes=["jwt"]))           # only JWT callers
@app.get("/users", auth=useAuth(permissions=["read:users"]))
@app.get("/dash", auth=useAuth(scopes=["jwt", "session"],
                               permissions=["access:dashboard"]))
@app.get("/feed", auth=useAuth(required=False))            # runs either way
@app.get("/internal", auth=useAuth(backends=[APIKeyAuthBackend()]))
```

## Parameters

| Parameter | Type | Default | Effect |
| --- | --- | --- | --- |
| `scopes` | `list[str]` | `[]` | At least one must match `request.scope["auth"]`. Empty = accept any method. |
| `permissions` | `list[str]` | `[]` | Every string must pass `user.has_permission(perm)`. |
| `backends` | `list[AuthenticationBackend]` | `None` | Replace the global middleware backends for this route only. |
| `user_model` | `type[BaseUser]` | `SimpleUser` | User class used when `backends` is set. |
| `required` | `bool` | `True` | If `False`, anonymous callers pass through with `UnauthenticatedUser`. |

## Required authentication

```python
@app.get("/profile", auth=useAuth())
async def profile(request, response):
    return {"username": request.user.display_name}
```

Unauthenticated → 401. Authenticated → handler runs with `request.user` fully loaded.

## Scope restriction

Each backend stamps a scope string on `request.scope["auth"]` (`"jwt"`, `"session"`, `"apikey"`). `scopes=[...]` requires at least one match:

```python
@app.get("/webhook", auth=useAuth(scopes=["apikey"]))
async def webhook(request, response): ...
```

A JWT-authenticated caller hitting `/webhook` gets 401 — authenticated, but via the wrong method.

## Permissions

Permission strings are checked via `user.has_permission(perm)` (all must pass). For production apps, use the DB-backed permission system from `sillo.permissions`:

```python
from sillo.permissions import PermissionMixin, Permission
from sillo.users import UserBaseModel

# Mixin must come FIRST in bases
class Account(PermissionMixin, UserBaseModel):
    class Meta:
        table = "accounts"

# Define & assign in your startup code
await Permission.define("delete:users")
await Permission.assign(current_user, "delete:users")

# Then gate routes
@app.delete("/users/{id}", auth=useAuth(permissions=["delete:users"]))
async def delete_user(request, response, id: int): ...
```

Permission logic in `PermissionMixin`: superusers pass all checks, inactive users fail all checks, everyone else is matched against their cached permission set (loaded via `load_permissions()` after login). The cache includes both **direct** assignments and **group-inherited** permissions — users automatically get whatever permissions their groups hold, with no extra configuration.

For contract-only users (no database), implement `has_permission` directly:

```python
from sillo.users import UserProtocol

class User(UserProtocol):
    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions

@app.delete("/users/{id}", auth=useAuth(permissions=["delete:users"]))
async def delete_user(request, response, id: int): ...
```

A JWT-authenticated non-admin → 403.

See [DB-backed permissions](/guides/users/#db-backed-permissions) for the full API.

## Optional authentication

`required=False` never rejects. Use it for endpoints that personalize for logged-in users but still serve anonymous visitors:

```python
@app.get("/feed", auth=useAuth(required=False))
async def feed(request, response):
    if request.user.is_authenticated:
        return {"feed": "personalized", "user": request.user.display_name}
    return {"feed": "public"}
```

## Per-route backend override

Replace the globally configured backends for one route. On success, `request.scope["user"]` and `request.scope["auth"]` are overwritten:

```python
from sillo.auth.apikey import APIKeyAuthBackend

@app.get("/internal/health", auth=useAuth(
    backends=[APIKeyAuthBackend(header_name="X-Internal-Key")],
    user_model=ServiceUser,
))
async def health(request, response):
    return {"service": request.user.display_name}
```

Use this when an endpoint should accept only one credential type (e.g. API keys) regardless of what the app otherwise allows.

## Subclassing for custom gates

Subclass `useAuth` and override `authenticate()` to add checks that run *after* the standard user/scope/permission checks:

```python
from sillo.auth import useAuth
from sillo.auth.exceptions import AuthenticationFailed

class OrgScoped(useAuth):
    def __init__(self, org_id_param: str, **kwargs):
        super().__init__(**kwargs)
        self.org_id_param = org_id_param

    async def authenticate(self, request) -> bool:
        if not await super().authenticate(request):
            return False
        org_id = request.path_params[self.org_id_param]
        if not request.user.belongs_to_org(org_id):
            raise AuthenticationFailed
        return True

@app.get("/orgs/{org_id}/members",
         auth=OrgScoped(org_id_param="org_id",
                        scopes=["jwt"],
                        permissions=["read:members"]))
async def org_members(request, response, org_id: str): ...
```

Call `super().authenticate(request)` first (it raises on failure), then layer your logic. Rate limiting per user, IP allow-lists, and tenancy checks all fit this pattern.

## Inside routers and class-based views

The gate is identical on `Router` decorators and on `APIView`:

```python
api = Router(prefix="/api")
@api.get("/users", auth=useAuth(scopes=["jwt"]))
async def list_users(request, response): ...
app.mount_router(api)
```

## Failure matrix

| Condition | Status | Exception |
| --- | --- | --- |
| No user + `required=True` | 401 | `AuthenticationFailed` |
| Scope mismatch | 401 | `AuthenticationFailed` |
| Permission denied | 403 | `PermissionDenied` |
| Backend override fails + `required=True` | 401 | `AuthenticationFailed` |
| `required=False` + anonymous | 200 (handler runs) | — |

## Best practices

- Put `auth=useAuth()` on every protected route. Don't re-check `request.user.is_authenticated` by hand inside handlers — the gate is the single, testable boundary.
- Be specific with `scopes` when you know the expected method; it's self-documenting and blocks the wrong credential type.
- Express business rules as `permissions` strings (`read:users`, `admin:settings`) rather than ad-hoc checks.
- Push cross-cutting rules (IP allow-list, org membership, per-user rate limit) into a reusable `useAuth` subclass.

## Related

- [Permissions](/guides/permissions/) — full permission system with groups, caching, and inheritance
- [Authentication](/guides/authentication/) — middleware + backend model
- [Users & User Models](/guides/users/) — `has_permission`, `UserProtocol`
- [JWT](/guides/jwt-auth/) · [Sessions](/guides/session-auth/) · [API Keys](/guides/api-keys/)
