---
title: Session Authentication
description: sillo's session_auth module provides a complete session-based authentication system — Laravel-style SessionGuard, per-device session tracking, logout everywhere, and user mixins for seamless integration.
head:
- tag: meta
  attrs:
    property: og:title
    content: Session Authentication
- tag: meta
  attrs:
    property: og:description
    content: Laravel-style session auth with SessionGuard, per-device tracking, logout everywhere, and user mixins.
---

# Session Authentication

The `sillo.auth.session_auth` module provides traditional session-based authentication. It includes a backend that reads from sillo's session middleware, a Laravel-style `SessionGuard` with `attempt`-based login, a Record-backed `Session` model for per-device tracking, and a mixin for User model integration.

## Prerequisites

Session authentication requires sillo's `SessionMiddleware`:

```python
from sillo.session.middleware import SessionMiddleware

app.use(SessionMiddleware(secret_key="session-secret"))
```

## Module Structure

```
sillo/auth/session_auth/
├── backend.py    — SessionAuthBackend, login(), logout()
├── guard.py      — SessionGuard
├── models.py     — Session (Record model)
├── mixins.py     — SessionUserMixin
└── __init__.py   — public exports
```

## SessionAuthBackend

The backend reads user data from `request.session` — a dictionary managed by sillo's session middleware.

```python
from sillo.auth.session_auth import SessionAuthBackend
from sillo.session.middleware import SessionMiddleware

app.use(SessionMiddleware(secret_key="session-secret"))
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=SessionAuthBackend(
        session_key="user",   # session dict key (default: "user")
        identifier="id",      # key within session data for user identity
    ),
))
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session_key` | `str` | `"user"` | Key in `request.session` where user data is stored. |
| `identifier` | `str` | `"id"` | Key within the session data dict containing the user identity. |

The session data format:

```python
request.session["user"] = {
    "id": "42",              # user identity
    "display_name": "Alice", # display name
}
```

### login() and logout() Helpers

Low-level helpers to write and clear session user data:

```python
from sillo.auth.session_auth import login, logout

# Store user in session
login(request, user)
# Sets: request.session["user"] = {"id": user.identity, "display_name": user.display_name}

# Clear session user data
logout(request)
# Deletes: request.session["user"]
```

## SessionGuard

`SessionGuard` provides a Laravel-style API for session authentication. It wraps the low-level helpers with credential validation and user loading.

```python
from sillo.auth.session_auth import SessionGuard

guard = SessionGuard(backend=session_backend, user_model=User)
```

### attempt — Login with Credentials

```python
@app.post("/login")
async def login(request, response):
    form = await request.form

    if await guard.attempt(
        request,
        email=form["email"],
        password=form["password"],
    ):
        return response.redirect("/dashboard")

    return response.html("Invalid credentials", status_code=401)
```

`attempt` looks up the user by email, verifies the password with `user.check_password()`, and on success calls `login()` and `user.set_last_login()`.

### Check Authentication State

```python
@app.get("/dashboard")
async def dashboard(request, response):
    if not await guard.check(request):
        return response.redirect("/login")

    user = await guard.user(request)
    return response.html(f"Welcome, {user.display_name}")
```

| Method | Returns | Description |
|--------|---------|-------------|
| `guard.check(request)` | `bool` | Is there a user in the session? |
| `guard.user(request)` | `User` or `None` | Fully loaded user from database. |
| `guard.id(request)` | `str` or `None` | User identity string. |
| `guard.validate(request, credentials)` | `bool` | Validates credentials without logging in. |

### Logout

```python
@app.post("/logout")
async def logout(request, response):
    await guard.logout(request)
    return response.redirect("/")
```

### Full Login Flow

```python
from sillo import silloApp
from sillo.auth.session_auth import SessionAuthBackend, SessionGuard
from sillo.session.middleware import SessionMiddleware

app = silloApp()
app.use(SessionMiddleware(secret_key="session-secret"))

session_backend = SessionAuthBackend()
guard = SessionGuard(backend=session_backend, user_model=User)

app.use(AuthenticationMiddleware(user_model=User, backend=session_backend))

@app.route("/login", methods=["GET", "POST"])
async def login(request, response):
    if request.method == "GET":
        return response.html("""
            <form method="post">
                <input name="email" type="email" placeholder="Email">
                <input name="password" type="password" placeholder="Password">
                <button type="submit">Login</button>
            </form>
        """)

    form = await request.form
    if await guard.attempt(request, email=form["email"], password=form["password"]):
        return response.redirect("/dashboard")
    return response.html("Invalid credentials", status_code=401)

@app.get("/dashboard", auth=useAuth(scopes=["session"]))
async def dashboard(request, response):
    user = await guard.user(request)
    sessions = await user.get_active_sessions()
    return response.json({
        "user": user.display_name,
        "active_sessions": len(sessions),
    })

@app.post("/logout", auth=useAuth())
async def logout(request, response):
    await guard.logout(request)
    return response.redirect("/login")
```

## Session Model — Per-Device Tracking

The `Session` model (Record-backed) tracks individual user sessions with device metadata.

```python
from sillo.auth.session_auth.models import Session

# Schema
class Session:
    id             — IntField(pk=True)
    user_id        — IntField(indexed)
    session_key    — CharField(255, unique, indexed)
    ip_address     — CharField(45, nullable)
    user_agent     — TextField(nullable)
    last_activity  — DatetimeField(auto_now)
    expires_at     — DatetimeField
    is_active      — BooleanField(default=True)
    device_name    — CharField(255, nullable)
```

### Session Operations

```python
# Mark activity (auto-updates last_activity)
await session.mark_activity()

# Extend session lifetime
await session.extend(duration_seconds=7200)  # 2 more hours

# Terminate a single session
await session.terminate()

# Terminate ALL sessions for a user
count = await Session.terminate_all_for_user(user_id=42)

# Cleanup expired sessions
count = await Session.cleanup_expired()
```

## SessionUserMixin

Add `SessionUserMixin` to your User model for session management methods:

```python
from sillo.auth.session_auth.mixins import SessionUserMixin

class User(Model, BaseUser, SessionUserMixin):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255)
    password = fields.CharField(max_length=128)
```

### Available Methods

**create_session** — Track a new session:

```python
await user.create_session(
    session_key=request.session.session_id,
    ip_address=request.client.host,
    user_agent=request.headers.get("User-Agent"),
    device_name="Chrome on macOS",
    duration_seconds=86400,  # 24 hours
)
```

**get_active_sessions** — List the user's active sessions:

```python
sessions = await user.get_active_sessions()
for s in sessions:
    print(f"{s.device_name} — last active {s.last_activity} from {s.ip_address}")
```

**logout_everywhere** — Terminate all sessions:

```python
count = await user.logout_everywhere()
# Returns: number of sessions terminated
```

**logout_session** — Terminate a specific session:

```python
success = await user.logout_session("session_key_value")
```

**active_session_count** — Count active sessions:

```python
count = await user.active_session_count()
```

## Complete Example — Logout Everywhere

```python
@app.post("/logout-everywhere", auth=useAuth(scopes=["session"]))
async def logout_everywhere(request, response):
    user = request.user
    count = await user.logout_everywhere()
    return response.json({
        "message": f"Logged out from {count} devices",
    })
```

## Session vs JWT — When to Use Each

| Scenario | Recommendation |
|----------|---------------|
| Traditional server-rendered web app | Session auth — cookies are automatic |
| Mobile app or SPA | JWT — stateless, works without cookies |
| API for third-party developers | API keys or JWT |
| Both web + API in same app | Combine — session for web, JWT for API |
| Need "logout everywhere" | Sessions with `Session` model, or JWT with `revoke_all_tokens` |

## Database Setup

The `Session` model needs a database table:

```python
await Tortoise.init(
    db_url="sqlite://db.sqlite3",
    modules={"models": [
        "sillo.auth.session_auth.models",
        "myapp.models",
    ]},
)
await Tortoise.generate_schemas()
```
