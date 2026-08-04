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

#  Protecting Routes

`useAuth` is the gate you put on a route to decide whether the already-resolved `request.user` is allowed to call the handler. Pass it as the `auth=` argument to any route registration — decorators (`@app.get`), `app.route`, `Route(...)`, and router decorators all accept it.

It runs after `AuthenticationMiddleware` has set `request.user`, but before your handler body. If the check fails it raises `AuthenticationFailed` (401) or `PermissionDenied` (403) and the handler never executes.

##  Quick reference

```python
from sillo.auth import useAuth

@app.get("/profile", auth=useAuth())                       # any logged-in user
@app.get("/admin", auth=useAuth(scopes=["jwt"]))           # only JWT callers
@app.get("/users", auth=useAuth(permissions=["read:users"]))
@app.get("/dash", auth=useAuth(scopes=["jwt", "session"],
                               permissions=["access:dashboard"]))
@app.get("/feed", auth=useAuth(required=False))            # runs either way
@app.get("/internal", auth=useAuth(backends=[APIKeyAuthBackend()]))
async def handler(request, response): ...
```

##  Parameters

| Parameter | Type | Default | Effect |
| --- | --- | --- | --- |
| `scopes` | `list[str]` | `[]` | At least one must match `request.scope["auth"]`. Empty = accept any method. |
| `permissions` | `list[str]` | `[]` | Every string must pass `user.has_permission(perm)`. |
| `backends` | `list[AuthenticationBackend]` | `None` | Replace the global middleware backends for this route only. |
| `user_model` | `type[BaseUser]` | `SimpleUser` | User class used when `backends` is set. |
| `required` | `bool` | `True` | If `False`, anonymous callers pass through with `UnauthenticatedUser`. |

##  Required authentication

```python
@app.get("/profile", auth=useAuth())
async def profile(request, response):
    return {"username": request.user.display_name}
```

Unauthenticated → 401. Authenticated → handler runs with `request.user` fully loaded.

##  Scope restriction

Each backend stamps a scope string on `request.scope["auth"]` (`"jwt"`, `"session"`, `"apikey"`). `scopes=[...]` requires at least one match:

```python
@app.get("/webhook", auth=useAuth(scopes=["apikey"]))
async def webhook(request, response): ...
```

A JWT-authenticated caller hitting `/webhook` gets 401 — authenticated, but via the wrong method.

##  Permissions

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

##  Optional authentication

`required=False` never rejects. Use it for endpoints that personalize for logged-in users but still serve anonymous visitors:

```python
@app.get("/feed", auth=useAuth(required=False))
async def feed(request, response):
    if request.user.is_authenticated:
        return {"feed": "personalized", "user": request.user.display_name}
    return {"feed": "public"}
```

##  Per-route backend override

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

##  Subclassing for custom gates

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

##  Inside routers

The gate is identical on `Router` decorators:

```python
api = Router(prefix="/api")
@api.get("/users", auth=useAuth(scopes=["jwt"]))
async def list_users(request, response): ...
app.mount_router(api)
```

##  Failure matrix

| Condition | Status | Exception |
| --- | --- | --- |
| No user + `required=True` | 401 | `AuthenticationFailed` |
| Scope mismatch | 401 | `AuthenticationFailed` |
| Permission denied | 403 | `PermissionDenied` |
| Backend override fails + `required=True` | 401 | `AuthenticationFailed` |
| `required=False` + anonymous | 200 (handler runs) | — |

##  Best practices

- Put `auth=useAuth()` on every protected route. Don't re-check `request.user.is_authenticated` by hand inside handlers — the gate is the single, testable boundary.
- Be specific with `scopes` when you know the expected method; it's self-documenting and blocks the wrong credential type.
- Express business rules as `permissions` strings (`read:users`, `admin:settings`) rather than ad-hoc checks.
- Push cross-cutting rules (IP allow-list, org membership, per-user rate limit) into a reusable `useAuth` subclass.

##  Related

- [Permissions](/guides/permissions/) — full permission system with groups, caching, and inheritance
- [Authentication](/guides/authentication/) — middleware + backend model
- [Users & User Models](/guides/users/) — `has_permission`, `UserProtocol`
- [JWT](/guides/jwt-auth/) · [Sessions](/guides/session-auth/) · [API Keys](/guides/api-keys/)


##  Defence in depth

A route-level requirement is the outermost of four layers, and it is the
weakest on its own because it protects the route rather than the data.

**Route level** declares that a caller must be authenticated, or hold a
scope. Visible in code review and in generated documentation, and
impossible to forget inside a long handler.

**Object level** checks that this caller may act on this specific record.
This is where most real authorization lives, and no route declaration can
do it — the route does not know which order id was requested.

**Query level** scopes every query by the authenticated principal, so
code that forgot to check still cannot see other people's rows.

**Database level** — foreign keys, row-level security — survives
application bugs entirely.

The failure that route-level protection cannot catch is the common one:
an authenticated user reading someone else's record by changing an
identifier. Scope the query rather than checking afterwards.

```python title="the shape that is actually safe"
order = await Order.get_or_none(id=order_id, owner_id=request.user.id)
if order is None:
    raise HTTPException(status_code=404)
```

Returning 404 rather than 403 avoids confirming the record exists, which
matters when identifiers are sequential and enumerable.

##  Failing closed

Every branch that cannot decide must deny. An unknown scope, a missing
role, a resource type the checker does not recognise, an exception inside
the check — each must result in refusal.

The reason is that permission code accumulates cases, and the case
somebody adds without updating the checker will hit the default. A
default of allow means each new resource type ships unprotected.

The same applies to configuration. A missing environment variable that
disables a check silently is a check that will be disabled in exactly one
environment, and it will be the one that matters.

##  Auditing what is protected

Route protection is worth testing structurally rather than per endpoint,
because the endpoint somebody adds next month is the one that will be
missed:

```python title="a test that catches unprotected routes"
PUBLIC = {"/", "/health", "/docs", "/openapi.json", "/login"}


def test_all_routes_require_auth():
    for route in app.router.routes:
        if route.raw_path in PUBLIC:
            continue
        response = client.get(route.raw_path.replace("{id}", "1"))
        assert response.status_code in (401, 403, 405), route.raw_path
```

An explicit allowlist of public paths makes adding one a deliberate act
that shows up in a diff. Without it, protection is a convention, and
conventions decay.


##  Public by default is the wrong default

An application where routes are open unless protected accumulates
unprotected routes, because forgetting is easier than remembering.

Invert it where you can: apply the requirement at the router level so
everything mounted under it inherits protection, and mark the handful of
genuinely public routes explicitly. A new endpoint added to that router
is protected without anyone thinking about it, and making one public
becomes a visible, reviewable line.

```python title="protected by default"
api = Router(prefix="/api", auth=useAuth())
public = Router(prefix="/public")
```

The same principle applies inside a handler: start from "deny" and
narrow, rather than starting from "allow" and excluding.

##  Related

- [Authentication](/guides/authentication/) — establishing who the caller is
- [Permissions](/guides/permissions/) — deciding what they may do
- [Scopes & Events](/guides/record/scopes-events/) — query-level enforcement
- [Middleware](/guides/middleware/) — where authentication runs
- [Security](/guides/security/) — the wider checklist


##  Documenting what is protected

A route requiring authentication should say so in its generated
documentation, or integrators discover it by receiving a 401 they had no
way to anticipate. The declaration that enforces and the declaration that
documents should be the same one; where they are separate, the two drift
and the schema becomes a lie about your security posture.

Test both directions. A route documented as secure but unprotected is a
vulnerability that reads as safe. A route protected but undocumented is
an integration failure that reads as a bug in the client.


##  Common mistakes

**Checking after fetching.** `order = await Order.get(id=x)` followed by
an ownership check leaks existence through timing and through error
shape, and forgets the check on one path eventually. Filter in the query.

**Trusting a client-supplied identity.** A `user_id` in the body or a
header is a value the caller chose. Identity comes from the verified
credential.

**Protecting the read and forgetting the write.** `GET /orders/{id}` gets
scrutiny; `PATCH /orders/{id}` often does not, and it is the more
damaging one.

**Relying on an unguessable identifier.** A UUID is not an authorization
mechanism. It is harder to enumerate and no harder to share, log, or leak
through a referrer header.

**Exempting an endpoint temporarily.** Every exemption outlives the
incident that created it. Put a comment with a date and review the list.


##  Performance

An authorization check that queries the database runs on every protected
request. Two things keep that affordable.

Cache the coarse part. A user's roles change rarely, and a short-lived
cache keyed by user id removes a query from every request without
meaningfully delaying a permission change.

Do not cache the fine-grained part. Ownership depends on the specific
record, so a cached `can_edit(user)` is a value that is right for one
resource and wrong for the rest — and the failure is silent.

Where a handler checks and then fetches, combine them. Filtering the
query by owner is one round trip; checking then fetching is two, and the
two-step version is the one that forgets the check.


##  Summary

Declare the requirement at the route or router so it is visible and hard
to forget. Enforce ownership in the query rather than after the fetch.
Fail closed on every branch that cannot decide. Test the wrong-user case,
not just the anonymous one. And prefer protected-by-default routers, so
that making something public is a deliberate, reviewable act.


##  Worked example

An orders API where every route is protected by default and ownership is
enforced in the query rather than after it.

```python title="the whole pattern in one place"
from sillo import Path, Router
from sillo.exceptions import HTTPException
from sillo.auth import useAuth

api = Router(prefix="/api", auth=useAuth())


@api.get("/orders")
async def list_orders(request, response):
    rows = await Order.filter(owner_id=request.user.id).order_by("-id").limit(50)
    return response.json([OrderOut.model_validate(r).model_dump() for r in rows])


@api.get("/orders/{order_id}")
async def get_order(request, response, order_id: int = Path(type=int)):
    order = await Order.get_or_none(id=order_id, owner_id=request.user.id)
    if order is None:
        raise HTTPException(status_code=404)
    return response.json(OrderOut.model_validate(order).model_dump())


@api.delete("/orders/{order_id}")
async def cancel_order(request, response, order_id: int = Path(type=int)):
    deleted = await Order.filter(id=order_id, owner_id=request.user.id).delete()
    if not deleted:
        raise HTTPException(status_code=404)
    return response.json(None, status_code=204)


app.mount_router(api)
```

Three things this gets right. The router carries the authentication
requirement, so a fourth route added later inherits it. Every query is
scoped by `owner_id`, so there is no path where a check can be forgotten.
And the delete filters rather than fetching-then-checking, so the
authorization and the action are one statement that cannot drift apart.
