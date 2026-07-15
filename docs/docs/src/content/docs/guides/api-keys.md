---
title: API Key Authentication
description: sillo's apikey module provides a complete API key management system — secure key generation, SHA-256 hashing with constant-time comparison, Record-backed persistence, scoped keys, and user mixins.
head:
- tag: meta
  attrs:
    property: og:title
    content: API Key Authentication
- tag: meta
  attrs:
    property: og:description
    content: Complete API key management with secure generation, SHA-256 hashing, constant-time comparison, scoped keys, and user mixins.
---

# API Key Authentication

The `sillo.auth.apikey` module provides server-to-server and programmatic authentication via API keys. It includes secure key generation with SHA-256 hashing, a Record-backed `ApiKey` model with expiry and scoping, an `ApiKeyManager` for CRUD operations, and a mixin for User model integration.

## Module Structure

```
sillo/auth/apikey/
├── backend.py    — APIKeyAuthBackend
├── models.py     — ApiKey (Record model), ApiKeyManager
├── mixins.py     — ApiKeyUserMixin
└── __init__.py   — public exports, utility functions
```

## Security Model

API keys are **never stored in plain text**. When a key is generated, only the SHA-256 hash is persisted. Verification uses `secrets.compare_digest` for constant-time comparison, eliminating timing attacks.

```python
from sillo.auth.apikey import generate_api_key, verify_api_key, hash_api_key

# Generation — returns (full_key, raw, hash)
full_key, raw, key_hash = generate_api_key(prefix="sillo")
# full_key = "sillo_abc123def456..."  ← give this to the user ONCE
# key_hash = "sha256..."              ← store this in the database

# Verification — constant-time comparison
is_valid = verify_api_key(full_key, key_hash)

# Hashing only
hashed = hash_api_key("sillo_abc123...")
```

**Important:** The full key is returned **once** at generation time. After that, you only have the hash. If the user loses their key, you must revoke it and generate a new one.

## APIKeyAuthBackend

The backend reads the API key from a configurable header.

```python
from sillo.auth.apikey import APIKeyAuthBackend

backend = APIKeyAuthBackend(
    header_name="X-API-Key",
    prefix="key",
    verify_with_manager=False,  # simple mode — just passes the raw key as identity
)

app.use(AuthenticationMiddleware(user_model=User, backend=backend))
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `header_name` | `str` | `"X-API-Key"` | HTTP header containing the API key. |
| `prefix` | `str` | `"key"` | Expected prefix (informational, not enforced by default). |
| `verify_with_manager` | `bool` | `False` | If `True`, validates the key against the `ApiKeyManager` (database lookup). |

### Simple Mode (`verify_with_manager=False`)

In simple mode, the backend returns `AuthResult(success=True, identity=<raw_key>, scope="apikey")`. Your `load_user` implementation is responsible for looking up which user owns this key. This is the fastest path and works well when you have a custom key-to-user mapping.

### Manager Mode (`verify_with_manager=True`)

When enabled, each request triggers a database lookup via `ApiKeyManager.verify()`. The key's hash is compared, expiry is checked, and `last_used_at` is updated. On success, the `user_id` from the `ApiKey` record becomes the identity.

```python
backend = APIKeyAuthBackend(
    header_name="X-API-Key",
    verify_with_manager=True,
)

# Now each request:
# 1. Extracts key from header
# 2. Hashes it
# 3. Looks up ApiKey by hash
# 4. Checks is_active + is_expired
# 5. Updates last_used_at
# 6. Returns AuthResult(identity=str(apikey.user_id))
```

## ApiKey Model — Record-Backed

```python
from sillo.auth.apikey import ApiKey

# Schema
class ApiKey:
    id            — IntField(pk=True)
    name          — CharField(255)
    key_hash      — CharField(255, unique, indexed)
    last_used_at  — DatetimeField(nullable)
    expires_at    — DatetimeField(nullable)
    is_active     — BooleanField(default=True)
    scopes        — JSONField(nullable)       # e.g. ["read:users", "write:posts"]
    user_id       — IntField(indexed)
    created_at    — DatetimeField(auto_now_add)  # from TimestampsMixin
    updated_at    — DatetimeField(auto_now)      # from TimestampsMixin
```

### Model Methods

```python
apikey = await ApiKey.filter(id=1).first()

# Check expiry
if apikey.is_expired:
    print("Key has expired")

# Track usage
await apikey.mark_used()  # sets last_used_at = now

# Revoke
await apikey.revoke()     # sets is_active = False
```

## ApiKeyManager

The manager provides high-level operations:

```python
from sillo.auth.apikey import ApiKeyManager

manager = ApiKeyManager()
```

### create_key

```python
from datetime import datetime, timedelta

full_key, apikey = await manager.create_key(
    user_id=42,
    name="Production CLI",
    scopes=["read:users", "write:posts"],
    expires_at=datetime.utcnow() + timedelta(days=90),
    prefix="sillo",
)

# full_key — give to the user (shown once)
# apikey   — ApiKey instance saved to database
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | `int` | required | The user who owns this key. |
| `name` | `str` | required | Human-readable label (e.g. "Staging Server"). |
| `scopes` | `list[str]` | `[]` | Permissions granted to this key. |
| `expires_at` | `datetime` | `None` | When this key expires. `None` = never. |
| `prefix` | `str` | `"sillo"` | Prefix for the generated key string. |

### verify

```python
apikey = await manager.verify(full_key)
if apikey is None:
    return response.json({"error": "Invalid or expired API key"}, status_code=401)

# apikey.user_id — use to load the user
# apikey.scopes  — use to check permissions
# apikey.last_used_at was just updated
```

`verify` returns `None` if the key doesn't exist, is inactive, or has expired.

### get_for_user

```python
keys = await manager.get_for_user(user_id=42)
for key in keys:
    print(f"{key.name}: active={key.is_active}, last_used={key.last_used_at}")
```

### revoke_all_for_user

```python
count = await manager.revoke_all_for_user(user_id=42)
# Returns: number of keys revoked
```

## ApiKeyUserMixin

Add `ApiKeyUserMixin` to your User model for direct API key management:

```python
from sillo.auth.apikey.mixins import ApiKeyUserMixin

class User(Model, BaseUser, ApiKeyUserMixin):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255)
    password = fields.CharField(max_length=128)
```

### Available Methods

**create_api_key:**

```python
full_key, apikey = await user.create_api_key(
    name="My Mobile App",
    scopes=["read:profile", "write:posts"],
    expires_at=datetime.utcnow() + timedelta(days=365),
)

# Show the key to the user ONCE
print(f"Your API key: {full_key}")
print(f"Store it safely — it won't be shown again.")
```

**get_api_keys:**

```python
keys = await user.get_api_keys()
```

**revoke_all_api_keys:**

```python
count = await user.revoke_all_api_keys()
```

**revoke_api_key:**

```python
success = await user.revoke_api_key(key_id=42)
```

## Complete Example

```python
from datetime import datetime, timedelta
from sillo import silloApp
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.apikey import APIKeyAuthBackend, ApiKeyManager

app = silloApp()
manager = ApiKeyManager()

app.use(AuthenticationMiddleware(
    user_model=User,
    backend=APIKeyAuthBackend(
        header_name="X-API-Key",
        verify_with_manager=True,  # database-backed verification
    ),
))

# Generate a new API key (protected — requires existing auth)
@app.post("/api-keys", auth=useAuth(scopes=["jwt", "session"]))
async def create_key(request, response):
    body = await request.json
    user = request.user

    full_key, apikey = await manager.create_key(
        user_id=int(user.identity),
        name=body["name"],
        scopes=body.get("scopes", []),
        expires_at=datetime.utcnow() + timedelta(days=365),
    )

    return response.json({
        "key": full_key,          # show once
        "id": apikey.id,
        "name": apikey.name,
        "expires_at": apikey.expires_at.isoformat() if apikey.expires_at else None,
    }, status_code=201)

# List the user's API keys
@app.get("/api-keys", auth=useAuth())
async def list_keys(request, response):
    keys = await manager.get_for_user(int(request.user.identity))
    return response.json([{
        "id": k.id,
        "name": k.name,
        "last_used": k.last_used_at.isoformat() if k.last_used_at else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "is_active": k.is_active,
    } for k in keys])

# Revoke a key
@app.delete("/api-keys/{key_id}", auth=useAuth())
async def revoke_key(request, response, key_id: int):
    apikey = await ApiKey.filter(
        id=key_id,
        user_id=int(request.user.identity),
    ).first()

    if not apikey:
        return response.json({"error": "Key not found"}, status_code=404)

    await apikey.revoke()
    return response.json({"message": f"Key '{apikey.name}' revoked"})

# Protected API endpoint — requires API key
@app.get("/api/v2/data", auth=useAuth(scopes=["apikey"]))
async def api_data(request, response):
    return response.json({
        "data": "This is accessible via API key only",
        "user_id": request.user.identity,
    })
```

## Using with useAuth

```python
# Only API keys allowed
@app.get("/api/restricted", auth=useAuth(scopes=["apikey"]))

# Route-level backend override
@app.get("/special", auth=useAuth(
    backends=[APIKeyAuthBackend(header_name="X-Special-Key")],
))

# Combined with permissions using scoped keys
@app.get("/admin-api", auth=useAuth(scopes=["apikey"], permissions=["admin"]))
```

## Scoped API Keys

Scoped keys limit what a key can do — similar to OAuth2 scopes. Store scopes in the `ApiKey.scopes` field and check them in your handler or with `useAuth(permissions=...)`.

```python
# Creating a scoped key
full_key, apikey = await manager.create_key(
    user_id=42,
    name="Read-only access",
    scopes=["read:users", "read:posts"],
)

# In your handler, check scopes from the ApiKey record
@app.get("/api/users", auth=useAuth(scopes=["apikey"]))
async def api_list_users(request, response):
    apikey = await manager.verify(request.headers.get("X-API-Key"))
    if "read:users" not in (apikey.scopes or []):
        return response.json({"error": "Insufficient scope"}, status_code=403)
    # ...
```

## Database Setup

```python
await Tortoise.init(
    db_url="sqlite://db.sqlite3",
    modules={"models": [
        "sillo.auth.apikey.models",
        "myapp.models",
    ]},
)
await Tortoise.generate_schemas()
```

## Security Best Practices

1. **Never store raw API keys** — only the SHA-256 hash. The `generate_api_key` function returns the raw key for one-time display, and `ApiKeyManager.create_key` stores only the hash.
2. **Show the key once** — API keys are like passwords. Display them at creation time and never again.
3. **Use HTTPS** — API keys are bearer credentials. Never transmit over unencrypted connections.
4. **Set expiry dates** — especially for keys used in production. Rotate keys regularly.
5. **Use scopes** — limit each key to the minimum permissions needed.
6. **Monitor usage** — `last_used_at` lets you identify unused keys for cleanup.
7. **Rotate keys** — revoke old keys and create new ones on a schedule.
8. **Different keys per environment** — separate keys for development, staging, and production.
9. **Enable manager verification** — `verify_with_manager=True` ensures keys are checked against the database on every request.
