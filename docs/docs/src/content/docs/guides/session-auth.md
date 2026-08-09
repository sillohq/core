---
title: Session Authentication
description: Cookie-based session auth in sillo - SessionMiddleware, SessionAuthBackend, the SessionGuard login helper, and the SessionUserMixin for managing active sessions.
head:
- tag: meta
  attrs:
    property: og:title
    content: Session Authentication in sillo
- tag: meta
  attrs:
    property: og:description
    content: sillo session auth - SessionMiddleware, SessionAuthBackend, SessionGuard, SessionUserMixin.
---

#  Session Authentication

Sessions are **stateful**: the server stores the signed session in a cookie and looks the user up on each request. Best for server-rendered web apps and browser UIs where you want `remember me`, "log out everywhere", and per-device session lists.

Two middleware pieces are involved:

| Middleware | Job |
| --- | --- |
| `SessionMiddleware` | Reads/writes the signed session cookie; gives you `request.session` |
| `AuthenticationMiddleware` + `SessionAuthBackend` | Turns the session into `request.user` |

##  1. Minimal setup

`SessionMiddleware` **must** run before `AuthenticationMiddleware` (the auth backend reads `request.session`):

```python
from sillo import SilloApp
from sillo.session import SessionMiddleware, SessionConfig
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.session_auth import SessionAuthBackend
from sillo.users import User

app = SilloApp()

app.use(SessionMiddleware(
    SessionConfig(secret_key="change-me"),   # signs the cookie
))
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=SessionAuthBackend(),
))
```

`SessionAuthBackend` reads `request.session["user"]["id"]` (defaults: key `"user"`, identifier `"id"`). On success `request.scope["auth"]` becomes `"session"`.

<aside type="caution" title="Order matters">
`SessionAuthBackend.authenticate` asserts `"session" in request.scope`. If you forget `SessionMiddleware` (or put it after auth), every request fails with `"No Session Middleware Installed"`. Always mount `SessionMiddleware` first.
</aside>

##  2. Logging a user in

The `SessionGuard` helper bundles credential check + session write. It needs `user_model` so it can look users up by email:

```python
from sillo.auth.session_auth import SessionGuard

guard = SessionGuard(user_model=User)

@app.post("/login")
async def login(request, response):
    data = await request.json
    ok = await guard.attempt(
        request, email=data["email"], password=data["password"]
    )
    if not ok:
        return response.json({"error": "invalid credentials"}, status_code=401)
    return {"ok": True}
```

`attempt(request, email=, password=)` returns `True` on success and writes the session (it also calls `user.set_last_login()` if available). The next request arrives with `request.user` populated.

###  Guard API

| Method | Returns | Notes |
| --- | --- | --- |
| `attempt(request, email=, password=)` | `bool` | Verify creds, then `login`. |
| `login(request, user)` | `None` | Writes session for an already-known user object. |
| `logout(request)` | `None` | Clears the session key (deletes cookie). |
| `user(request)` | `User \| None` | Loads the user via `user_model.objects.get_by_id`. |
| `id(request)` | `str \| None` | The stored identity. |
| `check(request)` | `bool` | `True` if a session key is present. |
| `validate(request, {email,password})` | `bool` | Like `attempt` but stores the user on `request.scope["_validated_user"]` instead of logging in. |

##  3. Logout and protecting routes

```python
@app.post("/logout")
async def logout(request, response):
    await guard.logout(request)
    return {"ok": True}

@app.get("/dashboard", auth=useAuth(schemes=["sessionCookie"]))
async def dashboard(request, response):
    return {"user": request.user.display_name}
```

`useAuth(schemes=["sessionCookie"])` restricts the route to cookie-authenticated callers, and documents it as such.

##  4. Managing sessions per user

Add `SessionUserMixin` to your user class to track and revoke device sessions. Each call writes a `Session` row (with `session_key`, `ip_address`, `user_agent`, `device_name`, `expires_at`).

```python
from sillo.users import User
from sillo.auth.session_auth.mixins import SessionUserMixin

class AppUser(User, SessionUserMixin):
    ...

user = await AppUser.load_user("1")

await user.create_session(
    session_key="abc123",
    ip_address="203.0.113.5",
    user_agent="Mozilla/5.0",
    device_name="Alice's Laptop",
    duration_seconds=86400,
)

sessions = await user.get_active_sessions()   # non-expired, active rows
count = await user.active_session_count()
await user.logout_session("abc123")           # terminate one
await user.logout_everywhere()                # terminate all for this user
```

These mixin methods use `int(str(self.identity))` as the `user_id`, matching how `SessionAuthBackend` and `User.load_user` resolve identities.

<aside type="note" title="Two session concepts">
There are two distinct "session" things in sillo:
- **`request.session`** — the cookie-backed key/value store from `SessionMiddleware` (config in `SessionConfig`).
- **`Session` model** — the DB row created by `SessionUserMixin.create_session` for device tracking.

`SessionAuthBackend` uses only the cookie. The `Session` model is optional bookkeeping for "show my devices / log out everywhere".
</aside>

##  5. Configuration

`SessionConfig` controls the cookie. Common knobs:

| Option | Default | Purpose |
| --- | --- | --- |
| `secret_key` | — | Signs the cookie (passed to `SessionMiddleware`). |
| `session_cookie_name` | `"session_id"` | Cookie name. |
| `session_expiration_time` | `86400` | Lifetime in seconds. |
| `session_cookie_secure` | `True` | Only send over HTTPS. |
| `session_cookie_httponly` | `True` | Not readable by JS. |
| `session_cookie_samesite` | `"lax"` | CSRF hardening. |
| `session_refresh_each_request` | `True` | Sliding expiry. |

```python
SessionConfig(
    secret_key="change-me",
    session_cookie_name="sid",
    session_expiration_time=3600,        # 1 hour
    session_cookie_secure=True,
    session_cookie_samesite="strict",
)
```

For server-side session storage (instead of signed cookies), pass a `manager` to `SessionMiddleware` (e.g. a file/session interface); otherwise the default `SignedSessionManager` stores everything in the cookie.

##  Related

- [Authentication](/guides/authentication/) — middleware + backend model
- [Protecting Routes](/guides/protecting-routes/) — `useAuth(schemes=["sessionCookie"])`
- [Users & User Models](/guides/users/) — `SessionUserMixin` wiring
- [JWT](/guides/jwt-auth/) · [API Keys](/guides/api-keys/)


##  How session authentication works

The flow is four steps, and each has a security decision attached.

**Login.** Credentials are verified against a stored password hash. A new
session is created server-side and its identifier is set as a cookie. The
identifier must be from a cryptographically secure source and long enough
that guessing is infeasible — 128 bits of randomness is the usual bar.

**Subsequent requests.** The browser sends the cookie automatically.
Middleware looks the session up and attaches the user to the request. The
lookup happens on every request, which is why the session store's latency
is your application's latency.

**Privilege change.** On login, and on anything that elevates
permissions, a server-backed session identifier must be regenerated.
Reusing it allows session fixation: an attacker who could set the cookie
before login shares the session after it. sillo's default cookie-backed
sessions are not exposed to this — see
[Session fixation](#session-fixation).

**Logout.** The session is deleted server-side and the cookie cleared.
Deleting only the cookie is not logout — the session remains valid for
anyone who captured the identifier.

##  Cookie attributes are the security model

A session cookie without the right attributes is a session waiting to be
stolen. All three matter, and none are optional.

`HttpOnly` prevents JavaScript reading it, which is what contains the
damage when an XSS happens. Without it, one injected script exfiltrates
every logged-in session.

`Secure` prevents it being sent over plain HTTP, closing the
network-interception path.

`SameSite=Lax` stops the cookie riding along on cross-site POSTs, which
removes the classic [CSRF](/guides/csrf/) attack. `Strict` is stronger
and breaks inbound links from other sites, which is usually unacceptable
for a consumer application and fine for an admin panel.

Set `Path=/` and an explicit `Domain` only when you need subdomain
sharing — a cookie scoped to a parent domain is readable by every
subdomain, including one an attacker might control.

##  Expiry on two clocks

An **idle timeout** closes sessions that stop being used, which matters
on shared machines. Thirty minutes to a few hours suits most
applications.

An **absolute lifetime** bounds how long a stolen session is useful
regardless of activity. A day or two for consumer applications, shorter
for anything sensitive.

Both, always. An idle timeout alone means a session kept warm by a
background poll never expires. An absolute lifetime alone means an
abandoned session on a library computer stays open for its full duration.

##  Storage

Where the session lives determines what you can do with it.

**Server-side** — Redis or a database — allows immediate revocation,
unbounded size, and listing a user's active sessions so they can sign out
elsewhere. It costs a lookup per request and requires the store to be
shared across processes; an in-memory store with four workers logs users
out three times in four.

**Cookie-backed** — signed data in the cookie itself — needs no storage
and no lookup, caps you at roughly 4 KB, and cannot be revoked before
expiry. It also travels on every request to the domain, including static
assets.

If you need "sign out everywhere" or immediate revocation on account
compromise, the decision is made for you.

##  What not to do

**Do not skip session regeneration on login** once you use a server-backed
store. Session fixation is still a live attack.

**Do not store permissions in the session.** They are cached at login and
survive revocation. Store identity; look up authorization.

**Do not use an in-memory session store with multiple workers.** Logins
will appear to fail at random.

**Do not clear only the cookie on logout.** Delete the server-side
session.

**Do not omit any of `HttpOnly`, `Secure`, `SameSite`.**

**Do not put sensitive data in a cookie-backed session.** Signed is not
encrypted; the contents are readable.

##  Related

- [Sessions](/guides/sessions/) — the session store and its configuration
- [Authentication](/guides/authentication/) — choosing between strategies
- [CSRF](/guides/csrf/) — the exposure cookie sessions bring with them
- [Cookies](/guides/cookies/) — attributes in detail
- [Hashing helpers](/guides/helpers/hashing/) — verifying passwords
- [Protecting Routes](/guides/protecting-routes/) — enforcing the session


##  A complete login flow

Every decision above, applied.

```python title="login, logout, and the middleware between them"
from sillo.exceptions import HTTPException
from sillo.helpers.hashing import verify_password


@app.post("/login", request_model=LoginForm)
async def login(request, response):
    data = request.validated_data
    user = await User.get_or_none(email=data.email.lower())

    # Same response and comparable timing whether or not the user exists.
    stored = user.password if user else DUMMY_HASH
    if not verify_password(data.password, stored) or user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    request.session["user_id"] = user.id
    request.session["issued_at"] = time.time()

    return response.json({"id": user.id})


@app.post("/logout")
async def logout(request, response):
    request.session.clear()                 # server-side, not just the cookie
    return response.json(None, status_code=204)
```

`clear()` is the whole logout. It marks the session emptied *and* deleted,
and `SessionMiddleware.process_response` hands the emptied session to the
backend before dropping the cookie — so a server-backed store purges its
record rather than leaving a key that anyone holding the old cookie could
still present.

<aside type="caution" title="clear() ends a session; it does not recycle one">
`deleted` is not reset by writing new keys, so `clear()` followed by
`request.session["user_id"] = ...` in the same request saves an **empty**
cookie value. Clear on logout; do not clear and then re-populate.
</aside>

###  Session fixation

With the default `SignedSessionManager` there is no server-side identifier
to fix: the cookie *is* the session, and it is re-signed from the new
contents whenever you write to it. A cookie an attacker planted before
login still decodes to the payload they chose, which has no `user_id` in
it, so it is not an authenticated session.

The attack becomes real the moment you move to a server-backed store,
where the cookie is a key into shared state. sillo ships no
`regenerate()`; issue a fresh key yourself in your
`BaseSessionInterface`, purging the old record as you go.

The dummy-hash comparison is the part people omit. An early `return` when
the user does not exist is measurably faster than one that verifies a
password, and that timing difference is a working user-enumeration
oracle.

##  Absolute lifetime enforcement

An idle timeout is usually handled by the session store's TTL. The
absolute lifetime is not, and has to be checked:

```python title="middleware that expires old sessions"
MAX_SESSION_AGE = 60 * 60 * 24 * 2


async def enforce_session_age(request, response, call_next):
    issued = request.session.get("issued_at")
    if issued and time.time() - issued > MAX_SESSION_AGE:
        request.session.clear()
    return await call_next()
```

Storing the issue time in the session is what makes this possible, which
is why it goes in at login rather than being added later.


##  Remember-me and elevated actions

"Remember me" is a longer absolute lifetime, not a permanent session. Two
tiers work well: a short session for ordinary use and a long-lived
credential that can mint a new session, with the second stored more
carefully and revocable independently.

The complement is **re-authentication for sensitive actions**. Changing a
password, adding a payment method, or deleting an account should require
the password again even inside a valid session — it converts a stolen
session from total compromise into limited access. Record when the user
last authenticated and check the age of that timestamp, not just the
session's validity.

##  Testing session flows

Four tests cover the failures that matter: that logging in issues a
different session identifier than the pre-login one; that logout
invalidates the session server-side and a captured cookie stops working;
that an expired session is rejected; and that a session created for one
user cannot be used to act as another.

The third and fourth are the ones usually missing, and they are the ones
an attacker tries.


##  Summary

Verify the password against a real password hash, in constant-ish time
whether or not the account exists. Regenerate the session identifier at
login if it is server-backed. Set `HttpOnly`, `Secure`, and `SameSite` on
the cookie. Expire on
both an idle and an absolute clock. Store identity rather than
permissions. Destroy the session server-side on logout. And require
re-authentication before anything a stolen session should not be able to
do.


##  Related reading

The mechanics of the session store itself — backends, serialization,
configuration — are in [Sessions](/guides/sessions/). This page covers
the authentication flow built on top of it. The two most common mistakes
live in different places: an in-memory store with multiple workers is a
storage problem, and a missing session regeneration is a flow problem.
Both only arise once you leave the default signed cookie.


##  Multi-factor authentication

Where a second factor is required, the session must record that it was
satisfied — not merely that a password was accepted. A session flagged
`mfa_pending` should reach only the verification endpoint and nothing
else, and the flag must be cleared server-side after the second factor
succeeds.

The failure to avoid is treating the first factor as a login. A session
created before the second factor, without a gate on every other route,
is a full session that skipped half the authentication.
