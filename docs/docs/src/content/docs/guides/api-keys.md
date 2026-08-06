---
title: API Keys
description: Scoped, hashed API keys in sillo — APIKeyAuthBackend, ApiKey/ApiKeyManager for storage, and ApiKeyUserMixin for issuing keys from a user.
head:
- tag: meta
  attrs:
    property: og:title
    content: API Keys in sillo
- tag: meta
  attrs:
    property: og:description
    content: sillo API key auth — backend, ApiKey model, ApiKeyManager, ApiKeyUserMixin, hashing and scopes.
---

#  API Keys

API keys are for **server-to-server** and **programmatic** access: a long-lived secret sent in a header, scoped to specific permissions, and stored hashed (never plaintext). sillo gives you the full lifecycle — generate, verify, list, revoke.

##  1. Protecting routes with the backend

```python
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.apikey import APIKeyAuthBackend
from sillo.users import User

app.use(AuthenticationMiddleware(
    user_model=User,
    backend=APIKeyAuthBackend(header_name="X-API-Key", verify_with_manager=True),
))

@app.get("/v1/data", auth=useAuth(schemes=["apiKeyHeader"]))
async def data(request, response):
    return {"called_by": request.user.identity}
```

Backend parameters:

| Param | Default | Meaning |
| --- | --- | --- |
| `header_name` | `"X-API-Key"` | Header to read the key from. |
| `prefix` | `"key"` | Expected key prefix (key is `prefix_xxxx`). |
| `verify_with_manager` | `False` | When `True`, validates the key against an `ApiKey` DB row (checks hash, expiry, `is_active`). |

<aside type="note" title="verify_with_manager is what makes keys real">
With `verify_with_manager=False`, the backend only checks the prefix and that *some* value is present — it does **not** validate the key against your database. For any real API key system, pass `verify_with_manager=True`, which hashes the presented key and matches it to an `ApiKey` row, honoring `is_active`, `expires_at`, and `scopes`.
</aside>

On success, `request.scope["auth"]` becomes `"apikey"`.

##  2. Storing keys — ApiKey & ApiKeyManager

Keys are hashed with SHA-256 before storage. You never persist the raw key.

```python
from sillo.auth.apikey import ApiKey, ApiKeyManager

# Generate: returns (full_key, raw, hash)
full_key, raw, key_hash = await ApiKey.generate_api_key(prefix="sillo")

# Persist a row for a user
await ApiKey.create(
    user_id=1,
    name="ci-pipeline",
    key_hash=key_hash,
    scopes=["read:data", "write:data"],
    expires_at=None,           # or datetime in the future
)

# Verify a presented key against the stored hash
ok = ApiKey.verify_api_key(raw, key_hash)

# Look up / revoke via the manager
keys = await ApiKeyManager().get_for_user(1)
await ApiKeyManager().revoke_all_for_user(1)
```

`ApiKey` fields: `name`, `key_hash` (unique), `user_id`, `scopes` (JSON list), `last_used_at`, `expires_at`, `is_active`. Helpers: `mark_used()`, `revoke()`, and the property `is_expired`.

##  3. Issuing keys from a user — ApiKeyUserMixin

Add `ApiKeyUserMixin` to your user class so a user can self-service keys:

```python
from sillo.users import User
from sillo.auth.apikey.mixins import ApiKeyUserMixin

class AppUser(User, ApiKeyUserMixin):
    ...

user = await AppUser.load_user("1")

full_key, apikey = await user.create_api_key(
    name="ci",
    scopes=["read:data"],
    expires_at=None,
    prefix="sillo",
)
# full_key is the only time you see the raw secret; apikey is the DB row

keys = await user.get_api_keys()            # list active key rows
await user.revoke_api_key(key_id)           # revoke one
await user.revoke_all_api_keys()            # revoke all for this user
```

`create_api_key` returns `(full_key, ApiKey)` — `full_key` is shown once; afterwards only the hash exists in the database.

##  4. Scopes and the auth gate

The backend confirms *that* the key is valid but does **not** expose the key's `scopes` on the request — so scope enforcement is your job. Re-verify the presented key in the handler to get the `ApiKey` row (which carries `scopes`):

```python
from sillo.auth.apikey import ApiKeyManager

@app.get("/v1/data", auth=useAuth(schemes=["apiKeyHeader"]))
async def data(request, response):
    raw = request.headers.get("X-API-Key")
    apikey = await ApiKeyManager().verify(raw)   # returns the ApiKey row or None
    if apikey is None or "read:data" not in (apikey.scopes or []):
        return response.json({"error": "insufficient scope"}, status_code=403)
    ...
```

<aside type="note" title="Scope enforcement is manual">
Do not confuse these with the gate. An API key's `scopes` are application-defined permission strings stored on the `ApiKey` row; `useAuth(schemes=["apiKeyHeader"])` only confirms the call came via an API key. To enforce *which* scopes, look the key up with `ApiKeyManager().verify(raw)` and branch on `apikey.scopes`, or write a small `useAuth` subclass that does it once.
</aside>

##  5. Combining with other backends

API keys commonly sit alongside JWT/session so the same endpoints serve both humans and machines:

```python
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=[
        APIKeyAuthBackend(header_name="X-API-Key", verify_with_manager=True),
        JWTAuthBackend(secret_key=JWT_SECRET, identifier="sub"),
        SessionAuthBackend(),
    ],
))
```

A request with `X-API-Key` authenticates as `"apiKeyHeader"`; one with a bearer token as `"bearerAuth"`; one with a cookie as `"sessionCookie"`. Routes can pin a credential with `useAuth(schemes=["apiKeyHeader"])` or accept any with `useAuth()`.

##  Related

- [Authentication](/guides/authentication/) — middleware + backend model
- [Protecting Routes](/guides/protecting-routes/) — `useAuth(schemes=["apiKeyHeader"])`
- [Users & User Models](/guides/users/) — `ApiKeyUserMixin` wiring
- [JWT](/guides/jwt-auth/) · [Sessions](/guides/session-auth/)
