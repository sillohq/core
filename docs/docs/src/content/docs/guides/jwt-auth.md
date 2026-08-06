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

#  JWT Authentication

JWTs give you **stateless** auth: a signed token carries the user identity, and the server verifies the signature on each request without a session store. sillo provides three layers:

| Layer | Class | Use when |
| --- | --- | --- |
| Read bearer tokens | `JWTAuthBackend` | You want `Authorization: Bearer <token>` → `request.user` |
| Mint tokens | `TokenForUser` | You issue tokens in a login handler (no DB needed) |
| DB-backed lifecycle | `JWTUserMixin` | You want refresh chains, revocation, and blacklisting |

##  1. Protecting routes with the backend

```python
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.jwt_auth import JWTAuthBackend
from sillo.users import User

app.use(AuthenticationMiddleware(
    user_model=User,
    backend=JWTAuthBackend(secret_key="change-me", identifier="sub"),
))

@app.get("/me", auth=useAuth(schemes=["bearerAuth"]))
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

##  2. Issuing tokens (stateless)

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
    data = await request.json
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

##  3. DB-backed tokens with JWTUserMixin

When you need **refresh rotation, revocation, and reuse detection**, add `JWTUserMixin` to your user class. It persists each issued token in the `jwt_tokens` table and tracks families.

```python
from sillo.users import User
from sillo.auth.jwt_auth.mixins import JWTUserMixin

class AppUser(User, JWTUserMixin):
    ...

user = await AppUser.load_user("1")
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

##  4. Working refresh without the DB

If you don't need server-side revocation, refresh is just "verify the refresh token, mint a new pair":

```python
@app.post("/refresh")
async def refresh(request, response):
    body = await request.json
    tokens = TokenForUser(request.user, secret=JWT_SECRET)
    try:
        tokens.verify(body["refresh_token"])   # checks signature + expiry
    except ValueError:
        return response.json({"error": "invalid refresh token"}, status_code=401)
    return tokens.token_pair()
```

This is fully stateless and sidesteps the `jti` issue. Choose it when you can live without server-side revocation (you can still short-circuit tokens by rotating the `secret` or via short expiries).

##  5. Lower-level helpers

`create_jwt` / `decode_jwt` issue and verify a raw payload:

```python
from sillo.auth.jwt_auth import create_jwt, decode_jwt
from datetime import timedelta

token = create_jwt({"sub": "1", "role": "admin"}, secret=JWT_SECRET, expires_in=timedelta(hours=1))
payload = decode_jwt(token, secret=JWT_SECRET)   # raises ValueError on expiry/invalid
```

##  6. Configuration cheat-sheet

| Goal | What to use |
| --- | --- |
| Verify bearer tokens | `JWTAuthBackend(secret_key=..., identifier="sub")` |
| Issue tokens in login | `TokenForUser(user, secret=...).token_pair()` |
| Refresh (stateless) | `TokenForUser(...).verify(refresh)` → `token_pair()` |
| Refresh + revoke (DB) | `JWTUserMixin.issue_token_pair` / `refresh_token_pair` (note jti caveat) |
| Kill a token now | `JWTUserMixin.blacklist_token` + `check_blacklist=True` |
| Custom claims (iss/aud) | `TokenForUser(..., issuer=, audience=)` |

##  Related

- [Authentication](/guides/authentication/) — middleware + backend model
- [Protecting Routes](/guides/protecting-routes/) — `useAuth(schemes=["bearerAuth"])`
- [Users & User Models](/guides/users/) — `User`, `JWTUserMixin` wiring
- [Sessions](/guides/session-auth/) · [API Keys](/guides/api-keys/)


##  What a JWT is and is not

A JWT is a signed, base64-encoded JSON payload. Signed means tamper-evident;
it does not mean encrypted. Anyone holding the token can read every claim
in it without the key.

That single fact determines what belongs in one. Put an identifier, an
expiry, and coarse claims a client may see. Never put anything private:
an email address, a role that reveals organisational structure,
an internal id you would not print in a URL.

The second fact that matters: verification is local. That is the entire
appeal — a service can validate a token without asking anyone — and it is
also the drawback, because nothing local can know the token was revoked.

##  Algorithm confusion is the classic attack

A JWT header declares its own algorithm, and a verifier that trusts that
declaration can be tricked.

**`alg: none`.** A library that honours it accepts an unsigned token as
valid. Any modern library refuses by default; never re-enable it.

**HS256 versus RS256.** With RS256 the public key verifies and the
private key signs. A verifier that reads `alg` from the token and uses
the configured key material will accept an HS256 token signed with the
*public* key — which is public. The attacker forges arbitrary claims.

The defence in both cases is the same: pass the expected algorithm to the
verifier explicitly and reject anything else. Never let the token choose.

```python
payload = decode(token, key, algorithms=["RS256"])   # not from the header
```

##  Expiry, refresh, and revocation

Access tokens should be short — minutes, not days — because that window
is how long a stolen one is useful, and the only thing that limits it.

A refresh token trades that for usability: long-lived, stored more
carefully, exchanged for a new access token. It must be revocable, which
means server-side state, which means you have not escaped a database
after all. That is the honest trade — stateless access tokens with a
stateful refresh path.

Rotate refresh tokens on use and detect reuse. If a refresh token is
presented twice, one of the two presenters is an attacker, and the
correct response is to invalidate the entire family and force a
re-login.

Validate `exp`, `nbf`, `iss`, and `aud` on every verification. A token
issued by another service, for another audience, is a valid signature and
an invalid credential — and a verifier checking only the signature will
accept it.

##  Where to store a token in a browser

There is no good answer, only a choice of failure mode.

`localStorage` is readable by any JavaScript on the page, so a single XSS
exfiltrates every token. It is convenient and it is the wrong default.

An `HttpOnly` cookie is unreadable by JavaScript, which contains XSS
damage — and reintroduces [CSRF](/guides/csrf/), because cookies are sent
automatically. Solvable with `SameSite` and a token.

In memory only, with a refresh cookie, is the strongest common pattern:
an XSS gets a token expiring in minutes rather than a permanent one.

For a mobile app the question is different and easier — the platform
keychain exists for exactly this.


##  Operational concerns

**Key rotation** needs two keys live at once: verify with both, sign with
the new one, retire the old after the longest token lifetime has passed.
A `kid` header naming the key makes this mechanical instead of
error-prone.

**Clock skew** between services causes tokens to be rejected as
not-yet-valid or accepted slightly past expiry. A tolerance of a few
seconds is standard; anything larger is papering over unsynchronised
clocks, which will cause worse problems elsewhere.

**Token size** matters more than people expect. A JWT travels in a header
on every request, and a token carrying a dozen claims is a kilobyte per
request per client. Keep claims minimal — an identifier and an expiry
plus whatever the client genuinely needs.

##  Related

- [Authentication](/guides/authentication/) — choosing between strategies
- [Protecting Routes](/guides/protecting-routes/) — enforcing the credential
- [JWT helpers](/guides/helpers/jwt/) — the encoding and decoding utilities
- [Sessions](/guides/sessions/) — the cookie-based alternative
- [Security](/guides/security/) — storage and transport concerns


##  When not to use a JWT

The appeal of a JWT is stateless verification. If you are storing session
state server-side anyway — and most applications with a login are — then
a random opaque session identifier is simpler, smaller, revocable
immediately, and reveals nothing to whoever holds it.

Reach for a JWT when verification genuinely needs to happen somewhere
that cannot reach your session store: a separate service, an edge worker,
a partner system. Inside one application, a session cookie does the same
job with fewer sharp edges.


##  A checklist before shipping

Every item here has been the root cause of a real breach somewhere.

The algorithm is pinned by the verifier, not read from the token.
`alg: none` is rejected. `exp` is validated, and short. `iss` and `aud`
are validated if more than one issuer or audience exists. Refresh tokens
rotate and reuse is detected. Signing keys come from the environment, not
the repository. Tokens are never placed in a URL, where they land in
access logs and referrer headers. Nothing private appears in a claim,
because claims are readable by anyone holding the token.

Read the list again against your implementation rather than against your
intentions — the gap between the two is where these bugs live.


##  Debugging a rejected token

Four causes account for nearly every "valid token rejected" report, and
they are distinguishable.

**Expiry.** Decode without verification and read `exp`. If the token is
minutes old and expired, the clocks disagree.

**Wrong key.** A signature failure with a well-formed token means the
verifier has different key material than the issuer — usually a different
environment's secret.

**Wrong algorithm.** A verifier pinned to RS256 rejects an HS256 token
outright, which is correct behaviour and looks like a signature failure.

**Wrong audience or issuer.** A perfectly valid token from another
service. The signature verifies and the claim check fails, which is the
system working.

Log which check failed, not just that verification failed. The difference
between "expired" and "bad signature" is the difference between a
five-minute fix and an afternoon.


##  Summary

A JWT is readable by anyone holding it and verifiable without a
round trip. Pin the algorithm, keep the lifetime short, validate every
claim you rely on, rotate refresh tokens and detect reuse — and if you
are keeping server-side session state anyway, consider whether an opaque
session identifier does the job with fewer edges.
