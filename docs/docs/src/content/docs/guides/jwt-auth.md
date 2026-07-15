---
title: JWT Authentication
description: sillo's jwt_auth module provides a complete JWT authentication system — token creation, verification, refresh with rotation, family tracking, reuse detection, blacklisting, and user mixins for seamless integration.
head:
- tag: meta
  attrs:
    property: og:title
    content: JWT Authentication
- tag: meta
  attrs:
    property: og:description
    content: Complete JWT auth with token creation, refresh rotation, family tracking, reuse detection, blacklisting, and user mixins.
---

# JWT Authentication

The `sillo.auth.jwt_auth` module is a self-contained JWT authentication system. It includes the backend for request authentication, a token factory bound to users, Record-backed models for persistence and blacklisting, and a mixin that adds token management methods directly to your User model.

## Module Structure

```
sillo/auth/jwt_auth/
├── backend.py    — JWTAuthBackend
├── tokens.py     — TokenForUser
├── models.py     — JWTToken, TokenBlacklist
├── mixins.py     — JWTUserMixin
└── __init__.py   — public exports
```

## JWTAuthBackend

The backend extracts Bearer tokens from the `Authorization` header, decodes them, and optionally checks a blacklist.

```python
from sillo.auth.jwt_auth import JWTAuthBackend

backend = JWTAuthBackend(
    secret_key="your-256-bit-secret",
    identifier="id",          # payload key for user identity
    check_blacklist=True,     # check TokenBlacklist before accepting
)

app.use(AuthenticationMiddleware(user_model=User, backend=backend))
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `secret_key` | `str` | `None` | Required. HMAC secret or RSA public key. |
| `identifier` | `str` | `"id"` | JWT payload key containing the user identifier. |
| `check_blacklist` | `bool` | `True` | If `True`, rejects blacklisted tokens. |

The backend expects tokens in the standard format: `Authorization: Bearer <token>`. On success it returns `AuthResult(success=True, identity=<user_id>, scope="jwt")`.

## TokenForUser

`TokenForUser` creates JWT tokens bound to a specific user instance. It wraps sillo's JWT helpers with sensible defaults.

```python
from sillo.auth.jwt_auth import TokenForUser

user = await User.objects.get_by_id(42)
tokens = TokenForUser(
    user,
    secret="your-secret",
    algorithm="HS256",
    issuer="my-app",
    audience="my-api",
)
```

### Issuing Tokens

```python
from datetime import timedelta

# Single access token (15 min default)
access = tokens.access_token()
access = tokens.access_token(expires_in=timedelta(minutes=30))

# Single refresh token (7 day default)
refresh = tokens.refresh_token()
refresh = tokens.refresh_token(expires_in=timedelta(days=14))

# Token pair — returns dict with access_token, refresh_token, token_type
pair = tokens.token_pair()
pair = tokens.token_pair(
    access_expires=timedelta(hours=1),
    refresh_expires=timedelta(days=30),
)
# {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
```

### Verifying Tokens

```python
# Full verification (signature, expiry, audience, issuer)
payload = tokens.verify(access_token)
# {"sub": "42", "iat": 1700000000, "typ": "access", "exp": 1700000900, ...}

# Verify but ignore expiry (for refresh flows)
payload = tokens.verify_no_expire(refresh_token)

# Decode without signature verification (inspect claims)
claims = TokenForUser.decode_unverified(token)

# Get header without verification
header = TokenForUser.get_unverified_header(token)
# {"alg": "HS256", "typ": "JWT"}
```

## JWTToken Model — Persistence

`JWTToken` is a Record (Tortoise ORM) model that stores every issued token. It enables refresh token rotation with family tracking and **reuse detection**.

```python
from sillo.auth.jwt_auth.models import JWTToken

# Schema
class JWTToken:
    id            — IntField(pk=True)
    user_id       — IntField(indexed)
    token_jti     — CharField(255, unique, indexed)
    token_family  — CharField(64, indexed)
    token_type    — CharField(16)  — "access" or "refresh"
    expires_at    — DatetimeField
    consumed_at   — DatetimeField(nullable)  — set when refresh is used
    revoked       — BooleanField(default=False)
```

### Token Families

When you issue a token pair, both the access and refresh tokens share a `token_family`. On refresh, the old refresh token is marked `consumed` and a **new pair** is created with the same family.

**Reuse detection**: if a refresh token that's already been consumed is presented again, the entire family is revoked — this protects against token theft.

```python
# Revoke an entire family
count = await JWTToken.revoke_family("abc123...")

# Revoke all tokens for a user
count = await JWTToken.revoke_all_for_user(user_id=42)

# Cleanup expired tokens
count = await JWTToken.cleanup_expired()
```

## TokenBlacklist Model

`TokenBlacklist` is for immediate invalidation of specific tokens — useful when a user logs out or an admin revokes access.

```python
from sillo.auth.jwt_auth.models import TokenBlacklist

# Schema
class TokenBlacklist:
    id             — IntField(pk=True)
    token_jti      — CharField(512, unique, indexed)
    blacklisted_at — DatetimeField(auto_now_add)
    expires_at     — DatetimeField

# Prune expired entries
count = await TokenBlacklist.prune_expired()
```

When `JWTAuthBackend(check_blacklist=True)` is used, every incoming token is checked against the blacklist before being accepted.

## JWTUserMixin

Add `JWTUserMixin` to your User model for direct token management methods.

```python
from tortoise import fields
from sillo.record import Model
from sillo.users import BaseUser
from sillo.auth.jwt_auth.mixins import JWTUserMixin

class User(Model, BaseUser, JWTUserMixin):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255)
    password = fields.CharField(max_length=128)
```

### Available Methods

**issue_token_pair** — Create a new pair with token family tracking:

```python
user = await User.objects.get_by_id(42)
pair = await user.issue_token_pair(
    secret="your-secret",
    access_expires=timedelta(hours=1),
    refresh_expires=timedelta(days=30),
)
# Returns: {"access_token": ..., "refresh_token": ..., "token_type": "bearer", "token_family": "..."}
```

**refresh_token_pair** — Rotate tokens with reuse detection:

```python
# In your refresh endpoint:
@app.post("/auth/refresh")
async def refresh(request, response):
    body = await request.json
    refresh_token = body["refresh_token"]
    user = request.user  # from existing valid access token

    try:
        pair = await user.refresh_token_pair(refresh_token, secret="your-secret")
        return response.json(pair)
    except ValueError as e:
        return response.json({"error": str(e)}, status_code=401)
```

If the refresh token has already been consumed (replay attack), `ValueError("Refresh token already consumed — possible token theft")` is raised and the entire token family is revoked.

**revoke_all_tokens** — Log out everywhere:

```python
count = await user.revoke_all_tokens()
# Returns: number of tokens revoked
```

**blacklist_token** — Invalidate a specific token immediately:

```python
success = await user.blacklist_token(compromised_token, secret="your-secret")
# Returns: True if blacklisted, False if token was invalid
```

**active_token_count** — Monitor active sessions:

```python
count = await user.active_token_count()
# Returns: number of non-revoked, non-expired tokens
```

## Complete Example

```python
from datetime import timedelta
from sillo import silloApp
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.jwt_auth import JWTAuthBackend
from sillo.auth.jwt_auth.mixins import JWTUserMixin
from sillo.record import Model
from sillo.users import BaseUser, UserManager

# User model with JWT mixin
class User(Model, BaseUser, JWTUserMixin):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    username = fields.CharField(max_length=150, unique=True)
    password = fields.CharField(max_length=128)
    objects = UserManager()

    class Meta:
        table = "users"

app = silloApp()
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=JWTAuthBackend(secret_key="super-secret-key"),
))

SECRET = "super-secret-key"

@app.post("/login")
async def login(request, response):
    body = await request.json
    user = await User.objects.get_by_email(body["email"])
    if not user or not user.check_password(body["password"]):
        return response.json({"error": "Invalid credentials"}, status_code=401)

    await user.set_last_login()
    pair = await user.issue_token_pair(secret=SECRET)
    return response.json(pair)

@app.post("/refresh")
async def refresh(request, response):
    body = await request.json
    user = request.user
    if not user.is_authenticated:
        return response.json({"error": "Authentication required"}, status_code=401)

    try:
        pair = await user.refresh_token_pair(body["refresh_token"], secret=SECRET)
        return response.json(pair)
    except ValueError as e:
        return response.json({"error": str(e)}, status_code=401)

@app.post("/logout", auth=useAuth())
async def logout(request, response):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    await request.user.blacklist_token(token, secret=SECRET)
    return response.json({"message": "Logged out"})

@app.post("/logout-everywhere", auth=useAuth())
async def logout_everywhere(request, response):
    count = await request.user.revoke_all_tokens()
    return response.json({"message": f"Revoked {count} tokens"})

@app.get("/me", auth=useAuth(scopes=["jwt"]))
async def me(request, response):
    return response.json({
        "id": request.user.identity,
        "email": request.user.email,
        "active_tokens": await request.user.active_token_count(),
    })
```

## Database Setup

The `JWTToken` and `TokenBlacklist` models need database tables. If using Tortoise:

```python
await Tortoise.init(
    db_url="sqlite://db.sqlite3",
    modules={"models": [
        "sillo.auth.jwt_auth.models",
        "myapp.models",
    ]},
)
await Tortoise.generate_schemas()
```

## Security Considerations

1. **Use a strong secret** — at least 256 bits for HMAC. Store it in an environment variable, never in code.
2. **Enable blacklist checks** — `JWTAuthBackend(check_blacklist=True)` prevents blacklisted tokens from being reused.
3. **Use short-lived access tokens** — the default 15 minutes limits the window of a compromised token.
4. **Rotate refresh tokens** — each refresh consumes the old refresh token and issues a new pair. If a consumed refresh token is presented again, the entire family is revoked.
5. **Prune expired data** — call `JWTToken.cleanup_expired()` and `TokenBlacklist.prune_expired()` periodically (e.g. via a scheduled task).
6. **Use HTTPS** — JWT tokens are bearer credentials. Never transmit them over unencrypted connections.
