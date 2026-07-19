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

# Session Authentication

Sessions are **stateful**: the server stores the signed session in a cookie and looks the user up on each request. Best for server-rendered web apps and browser UIs where you want `remember me`, "log out everywhere", and per-device session lists.

Two middleware pieces are involved:

| Middleware | Job |
| --- | --- |
| `SessionMiddleware` | Reads/writes the signed session cookie; gives you `request.session` |
| `AuthenticationMiddleware` + `SessionAuthBackend` | Turns the session into `request.user` |

## 1. Minimal setup

`SessionMiddleware` **must** run before `AuthenticationMiddleware` (the auth backend reads `request.session`):

```python
from sillo import silloApp
from sillo.session import SessionMiddleware, SessionConfig
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.session_auth import SessionAuthBackend
from sillo.users import User

app = silloApp()

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

## 2. Logging a user in

The `SessionGuard` helper bundles credential check + session write. It needs `user_model` so it can look users up by email:

```python
from sillo.auth.session_auth import SessionGuard

guard = SessionGuard(user_model=User)

@app.post("/login")
async def login(request, response):
    data = await request.json()
    ok = await guard.attempt(
        request, email=data["email"], password=data["password"]
    )
    if not ok:
        return response.json({"error": "invalid credentials"}, status_code=401)
    return {"ok": True}
```

`attempt(request, email=, password=)` returns `True` on success and writes the session (it also calls `user.set_last_login()` if available). The next request arrives with `request.user` populated.

### Guard API

| Method | Returns | Notes |
| --- | --- | --- |
| `attempt(request, email=, password=)` | `bool` | Verify creds, then `login`. |
| `login(request, user)` | `None` | Writes session for an already-known user object. |
| `logout(request)` | `None` | Clears the session key (deletes cookie). |
| `user(request)` | `User \| None` | Loads the user via `user_model.objects.get_by_id`. |
| `id(request)` | `str \| None` | The stored identity. |
| `check(request)` | `bool` | `True` if a session key is present. |
| `validate(request, {email,password})` | `bool` | Like `attempt` but stores the user on `request.scope["_validated_user"]` instead of logging in. |

## 3. Logout and protecting routes

```python
@app.post("/logout")
async def logout(request, response):
    await guard.logout(request)
    return {"ok": True}

@app.get("/dashboard", auth=useAuth(scopes=["session"]))
async def dashboard(request, response):
    return {"user": request.user.display_name}
```

`useAuth(scopes=["session"])` restricts the route to cookie-authenticated callers.

## 4. Managing sessions per user

Add `SessionUserMixin` to your user class to track and revoke device sessions. Each call writes a `Session` row (with `session_key`, `ip_address`, `user_agent`, `device_name`, `expires_at`).

```python
class User(Model, AbstractBaseUser, SessionUserMixin):
    ...

user = await User.load_user("1")

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

## 5. Configuration

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

## Related

- [Authentication](/guides/authentication/) — middleware + backend model
- [Protecting Routes](/guides/protecting-routes/) — `useAuth(scopes=["session"])`
- [Users & User Models](/guides/users/) — `SessionUserMixin` wiring
- [JWT](/guides/jwt-auth/) · [API Keys](/guides/api-keys/)
