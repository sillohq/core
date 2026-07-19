---
title: JWT Authentication
description: Issuing and verifying JSON Web Tokens in sillo — JWTAuthBackend, TokenForUser for stateless tokens, JWTUserMixin for DB-backed refresh/revocation, and the two current gotchas (identifier claim and refresh jti).
head:
- tag: meta
  attrs:
    property: og:title
    content: JWT Authentication in sillo
- tag: meta
  attrs:
    property: og:description
    content: sillo JWT auth — backend, TokenForUser, JWTUserMixin, refresh, revocation, and known gotchas.
---

# JWT Authentication

JWTs give you **stateless** auth: a signed token carries the user identity, and the server verifies the signature on each request without a session store. sillo provides three layers:

| Layer | Class | Use when |
| --- | --- | --- |
| Read bearer tokens | `JWTAuthBackend` | You want `Authorization: Bearer <token>` → `request.user` |
| Mint tokens | `TokenForUser` | You issue tokens in a login handler (no DB needed) |
| DB-backed lifecycle | `JWTUserMixin` | You want refresh chains, revocation, and blacklisting |

## 1. Protecting routes with the backend

```python
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.jwt_auth import JWTAuthBackend
from sillo.users import User

app.use(AuthenticationMiddleware(
    user_model=User,
    backend=JWTAuthBackend(secret_key="change-me", identifier="sub"),
))

@app.get("/me", auth=useAuth(scopes=["jwt"]))
async def me(request, response):
    return {"id": request.user.identity}
```

The backend reads the `Authorization: Bearer <token>` header, decodes with `secret_key`, and sets `request.scope["auth"] = "jwt"`.

<aside type="caution" title="You must set identifier='sub'">
`JWTAuthBackend` defaults to `identifier="id"`, but sillo's token builder writes the user id into the **`sub`** claim (never `id`). With the default, `payload.get("id", "")` is empty, so `identity` is `""` and the user fails to load. **Always pass `identifier="sub"`** when using `TokenForUser`/`JWTUserMixin` to issue tokens.
</aside>

Backend parameters:

| Param | Default | Meaning |
| --- | --- | --- |
| `secret_key` | required | HS256 signing secret. Raises `RuntimeError` if omitted. |
| `identifier` | `"id"` | Claim name to read the user identity from. Use `"sub"` with sillo-issued tokens. |
| `check_blacklist` | `True` | Rejects tokens present in the `TokenBlacklist` table. |

## 2. Issuing tokens (stateless)

`TokenForUser` builds signed tokens. No database required — verification is pure signature checking.

```python
from sillo.auth.jwt_auth import TokenForUser

tokens = TokenForUser(user, secret="change-me")
pair = tokens.token_pair()   # {"access_token", "refresh_token", "token_type": "bearer"}

# or individually
access = tokens.access_token(expires_in=timedelta(minutes=15))
refresh = tokens.refresh_token(expires_in=timedelta(days=7))

payload = tokens.verify(access)        # raises on bad signature / expiry
```

A typical login handler:

```python
@app.post("/login")
async def login(request, response):
    data = await request.json()
    user = await User.objects.get_by_email(data["email"])
    if not user or not user.check_password(data["password"]):
        return response.json({"error": "invalid credentials"}, status_code=401)

    pair = TokenForUser(user, secret=JWT_SECRET).token_pair()
    return pair
```

The access token's payload looks like:

```json
{ "sub": "1", "iat": 1719000000, "typ": "access", "exp": 1719000900 }
```

`sub` is `str(user.identity)`. `TokenForUser` also supports `issuer=`, `audience=`, and `algorithm=` (passed through to verification). Use `verify_no_expire(token)` to decode without checking expiry, and `TokenForUser.decode_unverified(token)` / `get_unverified_header(token)` for introspection.

## 3. DB-backed tokens with JWTUserMixin

When you need **refresh rotation, revocation, and reuse detection**, add `JWTUserMixin` to your user class. It persists each issued token in the `jwt_tokens` table and tracks families.

```python
class User(Model, AbstractBaseUser, JWTUserMixin):
    ...

user = await User.load_user("1")
result = await user.issue_token_pair(secret=JWT_SECRET)
# {"access_token", "refresh_token", "token_type", "token_family"}

# revoke everything this user holds
await user.revoke_all_tokens()

# count live tokens
await user.active_token_count()
```

`JWTToken` rows carry `user_id`, `token_jti`, `token_family`, `token_type` (`"access"`/`"refresh"`), `expires_at`, `consumed_at`, and `revoked`. On `refresh_token_pair`, the old refresh row is marked consumed and a new pair is created sharing the family. If a **consumed** or **revoked** refresh is replayed, the whole family is revoked (reuse detection).

You can also blacklist a specific token (immediate kill) via `user.blacklist_token(token, secret=...)`, which writes to `TokenBlacklist`. `JWTAuthBackend(check_blacklist=True)` consults that table.

<aside type="caution" title="Refresh currently needs a jti claim">
`JWTUserMixin.refresh_token_pair` looks up the stored `JWTToken` by the refresh token's **`jti`** claim (`payload.get("jti", refresh_token)`). But `TokenForUser.refresh_token()` (used by `issue_token_pair`) does **not** emit a `jti` claim, so the lookup falls back to the entire token string, which never matches a stored `token_jti` → `ValueError("Unknown refresh token")`.

Until that's fixed upstream, the DB-backed refresh happy-path does not complete out of the box. Workarounds: add a `jti` claim to the refresh payload yourself before calling `issue_token_pair`'s internals, or implement refresh by verifying the token and issuing a fresh pair directly with `TokenForUser`. The `issue`/`revoke`/`blacklist`/`count` paths work correctly.
</aside>

## 4. Working refresh without the DB

If you don't need server-side revocation, refresh is just "verify the refresh token, mint a new pair":

```python
@app.post("/refresh")
async def refresh(request, response):
    body = await request.json()
    tokens = TokenForUser(request.user, secret=JWT_SECRET)
    try:
        tokens.verify(body["refresh_token"])   # checks signature + expiry
    except ValueError:
        return response.json({"error": "invalid refresh token"}, status_code=401)
    return tokens.token_pair()
```

This is fully stateless and sidesteps the `jti` issue. Choose it when you can live without server-side revocation (you can still short-circuit tokens by rotating the `secret` or via short expiries).

## 5. Lower-level helpers

`create_jwt` / `decode_jwt` issue and verify a raw payload:

```python
from sillo.auth.jwt_auth import create_jwt, decode_jwt
from datetime import timedelta

token = create_jwt({"sub": "1", "role": "admin"}, secret=JWT_SECRET, expires_in=timedelta(hours=1))
payload = decode_jwt(token, secret=JWT_SECRET)   # raises ValueError on expiry/invalid
```

## 6. Configuration cheat-sheet

| Goal | What to use |
| --- | --- |
| Verify bearer tokens | `JWTAuthBackend(secret_key=..., identifier="sub")` |
| Issue tokens in login | `TokenForUser(user, secret=...).token_pair()` |
| Refresh (stateless) | `TokenForUser(...).verify(refresh)` → `token_pair()` |
| Refresh + revoke (DB) | `JWTUserMixin.issue_token_pair` / `refresh_token_pair` (note jti caveat) |
| Kill a token now | `JWTUserMixin.blacklist_token` + `check_blacklist=True` |
| Custom claims (iss/aud) | `TokenForUser(..., issuer=, audience=)` |

## Related

- [Authentication](/guides/authentication/) — middleware + backend model
- [Protecting Routes](/guides/protecting-routes/) — `useAuth(scopes=["jwt"])`
- [Users & User Models](/guides/users/) — `User`, `JWTUserMixin` wiring
- [Sessions](/guides/session-auth/) · [API Keys](/guides/api-keys/)
