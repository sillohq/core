---
title: "Auth Backends"
description: "Session auth, JWT auth, API key auth, token lifecycle"
---

**Version:** 2026-08-11
**Audience:** Core maintainers, backend developers, security engineers
**Purpose:** Document the three shipped authentication backends — session, JWT, and API key — including their models, mixins, and token lifecycle

---

## Overview

Sillo ships three authentication backends, each targeting a different credential transport:

| Backend | Credential Source | Scheme Name | OpenAPI Type |
|---------|-------------------|-------------|--------------|
| `SessionAuthBackend` | Session cookie | `"sessionCookie"` | `apiKey` in cookie |
| `JWTAuthBackend` | `Authorization: Bearer` header | `"bearerAuth"` | `http` bearer |
| `APIKeyAuthBackend` | Custom header (default `X-API-Key`) | `"apiKeyHeader"` | `apiKey` in header |

Each backend follows the same contract: read a credential from the request, verify it, return an `AuthResult`. Each has a corresponding user mixin that adds lifecycle methods (create, revoke, list) to the user model.

```mermaid
flowchart TD
    subgraph Backends
        SB[SessionAuthBackend]
        JB[JWTAuthBackend]
        AB[APIKeyAuthBackend]
    end

    subgraph Models
        SM[Session model]
        JM[JWTToken / TokenBlacklist]
        AM[ApiKey model]
    end

    subgraph Mixins
        SUM[SessionUserMixin]
        JUM[JWTUserMixin]
        AUM[ApiKeyUserMixin]
    end

    SB --> SM
    JB --> JM
    AB --> AM
    SM --> SUM
    JM --> JUM
    AM --> AUM
```

---

## Backend Architecture

All three backends inherit from `AuthenticationBackend` and override:

- `name` — the OpenAPI security scheme name
- `describe()` — returns the OpenAPI `SecurityScheme` object
- `authenticate(request)` — extracts and verifies the credential

The backends are lazy-loaded from `core/sillo/auth/__init__.py` via `deferred()` to avoid pulling in Tortoise ORM or PyJWT at import time:

```python
__getattr__ = deferred(
    __name__,
    {
        "APIKeyAuthBackend": ".apikey",
        "JWTAuthBackend": ".jwt_auth",
        "SessionAuthBackend": ".session_auth",
        "create_jwt": ".jwt_auth",
        "decode_jwt": ".jwt_auth",
    },
)
```

---

## Session Authentication

**Files:**
- `core/sillo/auth/session_auth/backend.py` — `login()`, `logout()`, `SessionAuthBackend`
- `core/sillo/auth/session_auth/models.py` — `Session` model
- `core/sillo/auth/session_auth/mixins.py` — `SessionUserMixin`
- `core/sillo/auth/session_auth/guard.py` — `SessionGuard`

### login() and logout()

**File:** `core/sillo/auth/session_auth/backend.py` (lines 22–91)

```python
def login(request, user, session_key="user", identifier="id"):
    assert "session" in request.scope, "No Session Middleware Installed"
    if request.session.get(session_key):
        del request.session[session_key]
    request.session[session_key] = {
        identifier: user.identity,
        "display_name": user.display_name,
    }

def logout(request, session_key="user"):
    assert "session" in request.scope, "No Session Middleware Installed"
    del request.session[session_key]
```

`login()` writes the user's identity and display name into the session dictionary. It removes any existing entry first to ensure a clean state. `logout()` deletes the session entry.

Both require the session middleware to be installed — they assert on `request.scope["session"]`.

### SessionAuthBackend

**File:** `core/sillo/auth/session_auth/backend.py` (lines 94–197)

```python
class SessionAuthBackend(AuthenticationBackend):
    name = "sessionCookie"

    def __init__(self, session_key="user", identifier="id", cookie_name="session_id",
                 name=None, description=None): ...

    def describe(self):
        from sillo.openapi.models import APIKey
        return APIKey(type="apiKey", name=self.cookie_name, description=self.description, **{"in": "cookie"})

    async def authenticate(self, request):
        assert "session" in request.scope, "No Session Middleware Installed"
        user = request.session.get(self.session_key)
        if not user:
            return AuthResult(success=False, identity="", scope="")
        return AuthResult(success=True, identity=user.get(self.identifier, ""), scope=self.name)
```

**Key behaviors:**
- Reads user data from `request.session[session_key]`
- Returns `self.name` (`"sessionCookie"`) as the scope, not the legacy `"session"` label
- The `cookie_name` parameter must match `SessionConfig.session_cookie_name` or the OpenAPI document names a cookie the application never sets
- The `name` parameter allows per-instance scheme naming (e.g. two session backends for different cookie names)

### Session Model

**File:** `core/sillo/auth/session_auth/models.py`

Tortoise model for per-user, per-device session tracking. Table: `user_sessions`.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | `IntField(pk=True)` | Primary key |
| `user_id` | `IntField(index=True)` | Owning user's ID |
| `session_key` | `CharField(255, unique=True, index=True)` | Unique session token |
| `ip_address` | `CharField(45, null=True)` | Client IP |
| `user_agent` | `TextField(null=True)` | Raw User-Agent header |
| `last_activity` | `DatetimeField(auto_now=True)` | Heartbeat timestamp |
| `expires_at` | `DatetimeField()` | Session expiration |
| `is_active` | `BooleanField(default=True)` | Soft-termination flag |
| `device_name` | `CharField(255, null=True)` | Human-readable device label |

**Methods:**

| Method | Purpose |
|--------|---------|
| `is_expired` (property) | `datetime.now(utc) > expires_at` |
| `mark_activity()` | Updates `last_activity` to now |
| `terminate()` | Sets `is_active = False` |
| `extend(duration_seconds)` | Extends `expires_at` by N seconds |
| `terminate_all_for_user(user_id)` (classmethod) | Deactivates all sessions for a user |
| `cleanup_expired()` (classmethod) | Deactivates all expired sessions |

### SessionUserMixin

**File:** `core/sillo/auth/session_auth/mixins.py`

Adds session management to user models:

| Method | Purpose |
|--------|---------|
| `create_session(session_key, ip_address, user_agent, device_name, duration_seconds)` | Creates a `Session` row |
| `get_active_sessions()` | Returns all active, non-expired sessions |
| `logout_everywhere()` | Terminates all sessions via `Session.terminate_all_for_user` |
| `logout_session(session_key)` | Terminates a specific session |
| `active_session_count()` | Counts active, non-expired sessions |

### SessionGuard

**File:** `core/sillo/auth/session_auth/guard.py`

High-level auth guard that wraps the session backend:

| Method | Purpose |
|--------|---------|
| `attempt(request, **credentials)` | Login with email/password. Returns `True`/`False`. |
| `login(request, user)` | Logs user in, calls `set_last_login()` if available. |
| `logout(request)` | Removes session data. |
| `user(request)` | Loads full user record from session. |
| `check(request)` | Lightweight session existence check. |
| `id(request)` | Returns raw user ID from session. |
| `validate(request, credentials)` | Validates credentials without creating a session. Stashes user on `request.scope["_validated_user"]`. |

```mermaid
sequenceDiagram
    participant Client
    participant Guard as SessionGuard
    participant DB as User Model
    participant Session as Session Store

    Client->>Guard: attempt(request, email, password)
    Guard->>DB: get_by_email(email)
    DB-->>Guard: user
    Guard->>Guard: user.check_password(password)
    Guard->>Session: login(request, user)
    Guard->>DB: user.set_last_login()
    Guard-->>Client: True
```

---

## JWT Authentication

**Files:**
- `core/sillo/auth/jwt_auth/__init__.py` — `create_jwt()`, `decode_jwt()`
- `core/sillo/auth/jwt_auth/backend.py` — `JWTAuthBackend`
- `core/sillo/auth/jwt_auth/tokens.py` — `TokenForUser`
- `core/sillo/auth/jwt_auth/models.py` — `JWTToken`, `TokenBlacklist`
- `core/sillo/auth/jwt_auth/mixins.py` — `JWTUserMixin`

### create_jwt / decode_jwt

**File:** `core/sillo/auth/jwt_auth/__init__.py`

Top-level helper functions that wrap the lower-level `sillo.helpers.jwt` module:

```python
def create_jwt(payload, secret, algorithm="HS256", expires_in=None) -> str:
    if expires_in and "exp" not in payload:
        payload = {**payload, "exp": datetime.now(timezone.utc) + expires_in}
    return jwt_helpers.encode(payload, secret, algorithm)

def decode_jwt(token, secret, algorithms=None) -> dict:
    try:
        return jwt_helpers.decode(token, secret, algorithms=algorithms or ["HS256"])
    except jwt_helpers.ExpiredTokenError:
        raise ValueError("Token has expired")
    except jwt_helpers.InvalidTokenError_:
        raise ValueError("Invalid token")
```

`decode_jwt` translates library-specific exceptions into `ValueError` for a simpler caller interface.

### JWTAuthBackend

**File:** `core/sillo/auth/jwt_auth/backend.py`

```python
class JWTAuthBackend(AuthenticationBackend):
    name = "bearerAuth"

    def __init__(self, identifier="id", secret_key=None, check_blacklist=True,
                 name=None, description=None): ...

    def describe(self):
        from sillo.openapi.models import HTTPBearer
        return HTTPBearer(type="http", scheme="bearer", bearerFormat="JWT", description=self.description)

    async def authenticate(self, request):
        # 1. Extract Authorization: Bearer <token>
        # 2. Check blacklist if enabled
        # 3. Decode and verify JWT
        # 4. Return AuthResult
```

**Authenticate flow:**

```mermaid
flowchart TD
    A[Extract Authorization header] --> B{Header present and starts with Bearer?}
    B -->|no| FAIL[Return AuthResult(success=False)]
    B -->|yes| C[Extract token]
    C --> D{check_blacklist enabled?}
    D -->|yes| E{Token blacklisted?}
    E -->|yes| FAIL
    E -->|no| F[Decode JWT]
    D -->|no| F
    F --> G{Decode succeeds?}
    G -->|no| FAIL
    G -->|yes| H[Return AuthResult success, identity from payload identifier]
```

**Key behaviors:**
- Extracts token from `Authorization: Bearer <token>` header
- Optionally checks `TokenBlacklist` table before decoding
- Uses `_decode_jwt()` internal helper which wraps `sillo.helpers.jwt.decode`
- Returns `self.name` (`"bearerAuth"`) as the scope
- The `name` parameter allows per-instance scheme naming (e.g. user tokens vs admin tokens on different secrets)
- Raises `RuntimeError` if `secret_key` was not provided

### TokenForUser

**File:** `core/sillo/auth/jwt_auth/tokens.py`

Creates JWT tokens bound to a specific user:

```python
class TokenForUser:
    def __init__(self, user, secret, algorithm="HS256", issuer=None, audience=None): ...
```

| Method | Default Expiry | Purpose |
|--------|----------------|---------|
| `access_token(expires_in, jti)` | 15 minutes | Short-lived access token with `typ="access"` |
| `refresh_token(expires_in, jti)` | 7 days | Long-lived refresh token with `typ="refresh"` |
| `token_pair(access_expires, refresh_expires)` | — | Returns `{"access_token", "refresh_token", "token_type": "bearer"}` |
| `verify(token)` | — | Full validation (signature + expiry + issuer/audience) |
| `verify_no_expire(token)` | — | Validates signature and claims but ignores expiration |
| `decode_unverified(token)` (static) | — | Decodes payload without verification |
| `get_unverified_header(token)` (static) | — | Extracts header without verification |

**Base payload** always includes:
- `sub` — user identity string
- `iat` — issued-at timestamp
- `typ` — token type (`"access"` or `"refresh"`)
- `iss` — issuer (if configured)
- `aud` — audience (if configured)

### JWTToken Model

**File:** `core/sillo/auth/jwt_auth/models.py`

Tortoise model tracking issued JWT tokens. Table: `jwt_tokens`.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | `IntField(pk=True)` | Primary key |
| `user_id` | `IntField(index=True)` | Owning user's ID |
| `token_jti` | `CharField(255, unique=True, index=True)` | JWT ID claim |
| `token_family` | `CharField(64, index=True)` | Groups access+refresh pairs |
| `token_type` | `CharField(16, default="access")` | `"access"` or `"refresh"` |
| `expires_at` | `DatetimeField()` | Token expiration |
| `consumed_at` | `DatetimeField(null=True)` | When consumed during refresh |
| `revoked` | `BooleanField(default=False)` | Revocation flag |

**Properties:**
- `is_expired` — `datetime.now(utc) > expires_at`
- `is_active` — `not revoked and not is_expired`

**Methods:**

| Method | Purpose |
|--------|---------|
| `consume()` | Sets `consumed_at` to now (for refresh rotation) |
| `revoke()` | Sets `revoked = True` |
| `revoke_family(token_family)` (classmethod) | Revokes all tokens in a family |
| `revoke_all_for_user(user_id)` (classmethod) | Revokes all tokens for a user |
| `cleanup_expired()` (classmethod) | Deletes all expired token records |

### TokenBlacklist Model

**File:** `core/sillo/auth/jwt_auth/models.py`

For immediate invalidation of specific tokens. Table: `token_blacklist`.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | `IntField(pk=True)` | Primary key |
| `token_jti` | `CharField(512, unique=True, index=True)` | Blacklisted token's JTI |
| `blacklisted_at` | `DatetimeField(auto_now_add=True)` | When blacklisted |
| `expires_at` | `DatetimeField()` | Original token expiration (for pruning) |

`prune_expired()` removes entries whose tokens have naturally expired.

### JWTUserMixin

**File:** `core/sillo/auth/jwt_auth/mixins.py`

Adds JWT lifecycle management to user models:

| Method | Purpose |
|--------|---------|
| `issue_token_pair(secret, access_expires, refresh_expires, algorithm)` | Creates a new family with access+refresh tokens, persists tracking rows |
| `refresh_token_pair(refresh_token, secret, algorithm)` | Rotates refresh token with theft detection |
| `revoke_all_tokens()` | Revokes all JWT tokens for this user |
| `blacklist_token(token, secret)` | Adds token's JTI to blacklist |
| `active_token_count()` | Counts non-revoked, non-expired tokens |

#### Token Rotation with Theft Detection

```mermaid
sequenceDiagram
    participant Client
    participant Mixin as JWTUserMixin
    participant DB as JWTToken table
    participant BL as TokenBlacklist

    Client->>Mixim: refresh_token_pair(refresh_token, secret)
    Mixim->>Mixim: verify_no_expire(refresh_token)
    Mixim->>DB: filter(token_jti=jti)
    DB-->>Mixim: existing token row

    alt Token family revoked
        Mixim->>DB: revoke_family(family)
        Mixim-->>Client: ValueError("Token family has been revoked")
    else Token already consumed
        Mixim->>DB: revoke_family(family)
        Mixim-->>Client: ValueError("Refresh token already consumed")
    else Token valid
        Mixim->>DB: consume() old refresh token
        Mixim->>DB: create new access + refresh tokens (same family)
        Mixim-->>Client: New token pair
    end
```

The theft detection works by tracking token families. When a refresh token is rotated:
1. The old token is marked as consumed
2. A new pair is created in the same family
3. If a consumed token is presented again, the entire family is revoked (someone stole the token)
4. If a revoked family is accessed, all tokens in it are invalidated

---

## API Key Authentication

**Files:**
- `core/sillo/auth/apikey/models.py` — `generate_api_key()`, `verify_api_key()`, `hash_api_key()`, `ApiKey`, `ApiKeyManager`
- `core/sillo/auth/apikey/backend.py` — `APIKeyAuthBackend`
- `core/sillo/auth/apikey/mixins.py` — `ApiKeyUserMixin`

### Key Generation and Verification

**File:** `core/sillo/auth/apikey/models.py` (lines 12–80)

```python
def generate_api_key(prefix="sillo") -> tuple[str, str, str]:
    raw = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, raw, key_hash

def verify_api_key(raw_key, stored_hash) -> bool:
    computed = hashlib.sha256(raw_key.encode()).hexdigest()
    return secrets.compare_digest(computed, stored_hash)

def hash_api_key(raw_key) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()
```

**Security properties:**
- `generate_api_key` uses `secrets.token_urlsafe(32)` for cryptographic randomness
- Keys are stored as SHA-256 hashes — plaintext is never persisted
- `verify_api_key` uses `secrets.compare_digest` for constant-time comparison (prevents timing attacks)
- The full key format is `{prefix}_{raw}` (e.g. `sillo_abc123...`)

### ApiKey Model

**File:** `core/sillo/auth/apikey/models.py` (lines 83–178)

Tortoise model for API key records. Table: `api_keys`.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | `IntField(pk=True)` | Primary key |
| `name` | `CharField(255)` | Human-readable label |
| `key_hash` | `CharField(255, unique=True, index=True)` | SHA-256 hex digest |
| `last_used_at` | `DatetimeField(null=True)` | Last authentication timestamp |
| `expires_at` | `DatetimeField(null=True)` | Optional expiration |
| `is_active` | `BooleanField(default=True)` | Revocation flag |
| `scopes` | `JSONField(null=True)` | Permission scope strings |
| `user_id` | `IntField(index=True)` | Owning user's ID |

**Methods:**
- `is_expired` (property) — checks `expires_at` against now
- `mark_used()` — updates `last_used_at`
- `revoke()` — sets `is_active = False`

### ApiKeyManager

**File:** `core/sillo/auth/apikey/models.py` (lines 181–307)

High-level manager for API key operations:

| Method | Purpose |
|--------|---------|
| `create_key(user_id, name, scopes, expires_at, prefix)` | Generates key, persists hash, returns `(full_key, apikey)` |
| `verify(raw_key)` | Hashes key, looks up in DB, checks expiry, marks used |
| `get_for_user(user_id)` | Returns all active keys for a user |
| `revoke_all_for_user(user_id)` | Revokes all active keys for a user |

### APIKeyAuthBackend

**File:** `core/sillo/auth/apikey/backend.py`

```python
class APIKeyAuthBackend(AuthenticationBackend):
    name = "apiKeyHeader"

    def __init__(self, header_name="X-API-Key", prefix="key", verify_with_manager=False,
                 name=None, description=None): ...

    def describe(self):
        from sillo.openapi.models import APIKey
        return APIKey(type="apiKey", name=self.header_name, description=self.description, **{"in": "header"})

    async def authenticate(self, request):
        raw_token = request.headers.get(self.header_name)
        if not raw_token:
            return AuthResult(success=False, identity="", scope="")
        if self.verify_with_manager:
            apikey = await ApiKeyManager().verify(raw_token)
            if apikey is None:
                return AuthResult(success=False, identity="", scope="")
            return AuthResult(success=True, identity=str(apikey.user_id), scope=self.name)
        return AuthResult(success=True, identity=raw_token, scope=self.name)
```

**Two verification modes:**
1. **`verify_with_manager=False`** (default) — any non-empty header value is accepted. The raw token is the identity. Fast, no database lookup.
2. **`verify_with_manager=True`** — the key is verified against the database via `ApiKeyManager`. The user ID is the identity. Supports expiry, revocation, and scope checking.

### ApiKeyUserMixin

**File:** `core/sillo/auth/apikey/mixins.py`

| Method | Purpose |
|--------|---------|
| `create_api_key(name, scopes, expires_at, prefix)` | Creates a new API key for this user |
| `get_api_keys()` | Returns all active API keys |
| `revoke_all_api_keys()` | Revokes all active API keys |
| `revoke_api_key(key_id)` | Revokes a specific key by ID |

---

## Mixin Composition Pattern

All three mixins follow the same pattern:
1. They expect the host class to have an `identity` attribute
2. They use `int(str(self.identity))` to convert to integer for database queries
3. They delegate to their respective models/managers for database operations

**Recommended composition:**

```python
from sillo.users.base import UserBaseModel
from sillo.permissions.mixins import PermissionMixin
from sillo.auth.jwt_auth.mixins import JWTUserMixin
from sillo.auth.session_auth.mixins import SessionUserMixin
from sillo.auth.apikey.mixins import ApiKeyUserMixin

class User(PermissionMixin, JWTUserMixin, SessionUserMixin, ApiKeyUserMixin, UserBaseModel):
    class Meta:
        table = "users"
```

The `PermissionMixin` should come first so its `has_permission` method takes precedence over `UserBaseModel`'s simpler implementation.

---

## Backend Comparison Matrix

| Feature | Session | JWT | API Key |
|---------|---------|-----|---------|
| **Credential transport** | Cookie | Authorization header | Custom header |
| **Stateful** | Yes (session store) | Yes (JWTToken table) | Yes (ApiKey table) |
| **Stateless option** | No | Yes (skip blacklist) | Yes (skip manager) |
| **Default expiry** | Configurable | 15min access / 7day refresh | None |
| **Revocation** | `Session.terminate()` | `JWTToken.revoke()` / blacklist | `ApiKey.revoke()` |
| **Theft detection** | No | Yes (token families) | No |
| **Rotation** | No | Yes (refresh token rotation) | No |
| **OpenAPI scheme** | `apiKey` in cookie | `http` bearer | `apiKey` in header |
| **DB dependency** | Optional (session model) | Optional (token tracking) | Optional (key verification) |

---

## Source Map

| Component | File | Lines |
|-----------|------|-------|
| `login()` | `core/sillo/auth/session_auth/backend.py` | 22–63 |
| `logout()` | `core/sillo/auth/session_auth/backend.py` | 66–91 |
| `SessionAuthBackend` | `core/sillo/auth/session_auth/backend.py` | 94–197 |
| `Session` model | `core/sillo/auth/session_auth/models.py` | 10–184 |
| `SessionUserMixin` | `core/sillo/auth/session_auth/mixins.py` | 8–163 |
| `SessionGuard` | `core/sillo/auth/session_auth/guard.py` | 16–287 |
| `create_jwt` | `core/sillo/auth/jwt_auth/__init__.py` | 11–42 |
| `decode_jwt` | `core/sillo/auth/jwt_auth/__init__.py` | 45–76 |
| `JWTAuthBackend` | `core/sillo/auth/jwt_auth/backend.py` | 39–173 |
| `TokenForUser` | `core/sillo/auth/jwt_auth/tokens.py` | 8–300 |
| `JWTToken` model | `core/sillo/auth/jwt_auth/models.py` | 27–198 |
| `TokenBlacklist` model | `core/sillo/auth/jwt_auth/models.py` | 200–257 |
| `JWTUserMixin` | `core/sillo/auth/jwt_auth/mixins.py` | 10–236 |
| `generate_api_key` | `core/sillo/auth/apikey/models.py` | 12–37 |
| `verify_api_key` | `core/sillo/auth/apikey/models.py` | 40–61 |
| `hash_api_key` | `core/sillo/auth/apikey/models.py` | 64–80 |
| `ApiKey` model | `core/sillo/auth/apikey/models.py` | 83–178 |
| `ApiKeyManager` | `core/sillo/auth/apikey/models.py` | 181–307 |
| `APIKeyAuthBackend` | `core/sillo/auth/apikey/backend.py` | 11–123 |
| `ApiKeyUserMixin` | `core/sillo/auth/apikey/mixins.py` | 8–131 |

---

## Implementation Deep Dive

### Session Authentication — Complete Flow

#### Login Sequence

```python
# 1. User submits credentials
POST /login
{"email": "user@example.com", "password": "secret123"}

# 2. Handler calls SessionGuard.attempt()
guard = SessionGuard(backend=SessionAuthBackend(), user_model=User)
success = await guard.attempt(request, email="user@example.com", password="secret123")

# 3. Internally:
#    a. user_model.objects.get_by_email("user@example.com") → User instance
#    b. user.check_password("secret123") → True
#    c. login(request, user) → stores {id: "42", display_name: "alice"} in session
#    d. user.set_last_login() → updates last_login timestamp

# 4. Response sets session cookie
Set-Cookie: session_id=<signed_session_data>; Path=/; HttpOnly; SameSite=Lax
```

#### Request Authentication Sequence

```python
# 1. Subsequent request includes session cookie
GET /profile
Cookie: session_id=<signed_session_data>

# 2. SessionMiddleware loads session from cookie → request.session

# 3. SessionAuthBackend.authenticate(request):
#    a. Reads request.session.get("user") → {"id": "42", "display_name": "alice"}
#    b. Returns AuthResult(success=True, identity="42", scope="sessionCookie")

# 4. AuthenticationMiddleware:
#    a. user_model.load_user("42") → User instance from DB
#    b. Sets request.scope["user"] = user
#    c. Sets request.scope["auth"] = "sessionCookie"
#    d. Sets request.scope["auth_scheme"] = "sessionCookie"
```

#### Logout Sequence

```python
# 1. Handler calls logout
await guard.logout(request)

# 2. Internally:
#    a. del request.session["user"]

# 3. SessionMiddleware saves empty session → new cookie (or cleared cookie)
```

### Session Model — Lifecycle Management

```python
# Create a tracked session
session = await user.create_session(
    session_key="abc123",
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0 ...",
    device_name="Chrome on macOS",
    duration_seconds=86400,  # 24 hours
)

# Check active sessions
sessions = await user.get_active_sessions()
for s in sessions:
    print(f"{s.device_name} - {s.ip_address} - {s.last_activity}")

# Terminate a specific session
await user.logout_session("abc123")

# Terminate all sessions (security incident)
count = await user.logout_everywhere()
print(f"Terminated {count} sessions")

# Cleanup expired sessions (maintenance task)
expired = await Session.cleanup_expired()
print(f"Cleaned up {expired} expired sessions")
```

### JWT Authentication — Complete Flow

#### Token Issuance

```python
# 1. User authenticates (e.g., via email/password)
user = await User.verify_credentials("user@example.com", "secret123")

# 2. Issue token pair
tokens = await user.issue_token_pair(
    secret="my-jwt-secret",
    access_expires=timedelta(minutes=15),
    refresh_expires=timedelta(days=7),
)

# 3. Response
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "token_family": "a1b2c3d4..."
}
```

#### Token Verification

```python
# 1. Request includes Bearer token
GET /api/data
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# 2. JWTAuthBackend.authenticate(request):
#    a. Extracts token from Authorization header
#    b. Checks TokenBlacklist (if enabled)
#    c. Decodes JWT, verifies signature and expiration
#    d. Extracts user ID from payload["id"]
#    e. Returns AuthResult(success=True, identity="42", scope="bearerAuth")
```

#### Token Rotation with Theft Detection

```python
# 1. Client sends refresh token
POST /auth/refresh
{"refresh_token": "eyJhbGciOiJIUzI1NiIs..."}

# 2. JWTUserMixin.refresh_token_pair():
#    a. Decodes refresh token (ignoring expiration)
#    b. Looks up JWTToken row by JTI
#    c. Checks if token family is revoked → if so, revoke entire family
#    d. Checks if token already consumed → if so, revoke entire family
#    e. Marks old refresh token as consumed
#    f. Creates new access + refresh tokens in same family
#    g. Returns new token pair

# 3. Theft scenario:
#    - Attacker steals refresh token
#    - Attacker uses stolen token
#    - Legitimate user uses same token later
#    - System detects "already consumed" → revokes entire family
#    - Both attacker and user must re-authenticate
```

#### Token Blacklisting

```python
# Blacklist a specific token (e.g., on logout)
await user.blacklist_token(access_token, secret="my-jwt-secret")

# Revoke all tokens (e.g., password change)
count = await user.revoke_all_tokens()

# Check active token count
count = await user.active_token_count()

# Cleanup expired tokens (maintenance)
expired = await JWTToken.cleanup_expired()
blacklisted = await TokenBlacklist.prune_expired()
```

### API Key Authentication — Complete Flow

#### Key Generation

```python
# 1. Generate a new API key
full_key, raw, key_hash = generate_api_key(prefix="myapp")
# full_key = "myapp_abc123xyz..."
# raw = "abc123xyz..."
# key_hash = "sha256_hex_digest..."

# 2. Store in database (hash only)
apikey = await ApiKey.create(
    user_id=42,
    name="CI Deploy Key",
    key_hash=key_hash,
    scopes=["deploy", "read"],
    expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
)

# 3. Return full key to user (ONLY TIME IT'S VISIBLE)
# {"key": "myapp_abc123xyz...", "name": "CI Deploy Key"}
```

#### Key Verification (Stateless Mode)

```python
# Request includes API key
GET /api/data
X-API-Key: myapp_abc123xyz...

# APIKeyAuthBackend (verify_with_manager=False):
# 1. Reads header value
# 2. Returns AuthResult(success=True, identity="myapp_abc123xyz...", scope="apiKeyHeader")
# No database lookup — fast but no revocation support
```

#### Key Verification (Database Mode)

```python
# APIKeyAuthBackend (verify_with_manager=True):
# 1. Reads header value
# 2. ApiKeyManager.verify("myapp_abc123xyz..."):
#    a. Hashes the key: hash_api_key("myapp_abc123xyz...")
#    b. Looks up ApiKey by key_hash
#    c. Checks is_active and is_expired
#    d. Updates last_used_at
#    e. Returns ApiKey instance (or None)
# 3. Returns AuthResult(success=True, identity="42", scope="apiKeyHeader")
```

#### Key Management via Mixin

```python
# Create a key
full_key, apikey = await user.create_api_key(
    name="Production API Key",
    scopes=["read", "write"],
    expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
    prefix="prod",
)

# List all keys
keys = await user.get_api_keys()
for key in keys:
    print(f"{key.name} - last used: {key.last_used_at}")

# Revoke a specific key
await user.revoke_api_key(key_id=42)

# Revoke all keys (security incident)
count = await user.revoke_all_api_keys()
```

### Backend Registration Patterns

#### Single backend:

```python
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=JWTAuthBackend(secret_key="..."),
))
```

#### Multiple backends with priority:

```python
# JWT first (most common), then session (browser), then API key (services)
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=[
        JWTAuthBackend(secret_key="..."),
        SessionAuthBackend(),
        APIKeyAuthBackend(verify_with_manager=True),
    ],
))
```

#### Named instances (multiple JWT secrets):

```python
# User tokens and admin tokens on different secrets
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=[
        JWTAuthBackend(secret_key="user-secret", name="userAuth"),
        JWTAuthBackend(secret_key="admin-secret", name="adminAuth"),
    ],
))
```

### Security Considerations

#### Session Security

- **Session fixation:** The `login()` function removes any existing session entry before writing the new one, preventing session fixation attacks.
- **Session hijacking:** The `Session` model tracks IP address and user agent for anomaly detection.
- **Session expiration:** Sessions have explicit `expires_at` timestamps and can be extended.
- **Logout everywhere:** `Session.terminate_all_for_user()` deactivates all sessions for a user.

#### JWT Security

- **Algorithm confusion:** The backend explicitly uses `HS256` and does not accept the `alg` header from the token.
- **Token theft:** The token family mechanism detects reuse of consumed refresh tokens.
- **Blacklisting:** Individual tokens can be blacklisted before expiration.
- **Short-lived access tokens:** Default 15-minute expiration limits exposure window.

#### API Key Security

- **Hash storage:** Only SHA-256 hashes are stored; plaintext keys are never persisted.
- **Timing-safe comparison:** `verify_api_key` uses `secrets.compare_digest` to prevent timing attacks.
- **Prefix identification:** The `prefix_` format allows visual identification of key ownership.
- **Scope restriction:** Keys can be limited to specific permission scopes.

### Error Handling Patterns

#### Backend exceptions are caught:

```python
# In AuthenticationMiddleware.process_request:
for backend in self.backends:
    try:
        auth_result = await backend.authenticate(request)
        if auth_result.success:
            # ... set scope
            break
    except Exception as e:
        # Log but continue to next backend
        backend.handle_exception(response, e)
        continue
```

#### Common error scenarios:

| Scenario | Behavior |
|----------|----------|
| Missing Authorization header | `AuthResult(success=False)` — next backend tried |
| Expired JWT | `ValueError("Token has expired")` → caught → next backend |
| Invalid JWT signature | `ValueError("Invalid token")` → caught → next backend |
| Blacklisted JWT | `AuthResult(success=False)` — next backend tried |
| Database down (session/JWT/API key) | Exception → `handle_exception` → next backend |
| No session middleware | `AssertionError` → caught → next backend |

### Testing Backends

#### Testing JWTAuthBackend:

```python
@pytest.mark.asyncio
async def test_jwt_backend_valid_token():
    backend = JWTAuthBackend(secret_key="test-secret", check_blacklist=False)

    # Create a valid token
    from sillo.auth.jwt_auth import create_jwt
    token = create_jwt({"id": "42"}, "test-secret")

    request = MockRequest(headers={"Authorization": f"Bearer {token}"})
    result = await backend.authenticate(request)

    assert result.success is True
    assert result.identity == "42"
    assert result.scope == "bearerAuth"

@pytest.mark.asyncio
async def test_jwt_backend_expired_token():
    backend = JWTAuthBackend(secret_key="test-secret")

    token = create_jwt({"id": "42"}, "test-secret", expires_in=timedelta(seconds=-1))

    request = MockRequest(headers={"Authorization": f"Bearer {token}"})
    result = await backend.authenticate(request)

    assert result.success is False
```

#### Testing SessionAuthBackend:

```python
@pytest.mark.asyncio
async def test_session_backend_with_session():
    backend = SessionAuthBackend()

    request = MockRequest(scope={"session": {"user": {"id": "42", "display_name": "alice"}}})
    result = await backend.authenticate(request)

    assert result.success is True
    assert result.identity == "42"

@pytest.mark.asyncio
async def test_session_backend_without_session():
    backend = SessionAuthBackend()

    request = MockRequest(scope={"session": {}})
    result = await backend.authenticate(request)

    assert result.success is False
```

#### Testing APIKeyAuthBackend:

```python
@pytest.mark.asyncio
async def test_apikey_backend_stateless():
    backend = APIKeyAuthBackend(verify_with_manager=False)

    request = MockRequest(headers={"X-API-Key": "my-secret-key"})
    result = await backend.authenticate(request)

    assert result.success is True
    assert result.identity == "my-secret-key"
```
