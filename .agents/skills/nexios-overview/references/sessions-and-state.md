# Nexios Sessions And State

Use this reference for a deeper view of session storage and session-backed state patterns.

## Table of Contents

1. [Basic Session Setup](#basic-session-setup)
2. [Working With Session Data](#working-with-session-data)
3. [Session Expiry](#session-expiry)
4. [Session Backends](#session-backends)
5. [State Design Notes](#state-design-notes)

## Basic Session Setup

```python
from nexios import NexiosApp
from nexios.session import SessionConfig
from nexios.session.middleware import SessionMiddleware

app = NexiosApp()
app.config.secret_key = "your-secure-secret-key"

session_config = SessionConfig(
    session_cookie_name="nexios_session",
    cookie_secure=True,
    cookie_httponly=True,
    cookie_samesite="lax",
    session_expiration_time=86400
)

app.add_middleware(SessionMiddleware(config=session_config))
```

Teach this as the recommended starting point.

## Working With Session Data

```python
@app.get("/session-demo")
async def session_demo(request, response):
    user_id = request.session.get("user_id", None)
    request.session["last_visit"] = "now"

    if "temporary_data" in request.session:
        del request.session["temporary_data"]

    return response.json({
        "user_id": user_id,
        "session_keys": list(request.session.keys())
    })
```

Useful session operations to mention:

- `session.get(key, default=None)`
- `session[key] = value`
- `del session[key]`
- `session.clear()`
- `session.keys()`
- `session.pop(key, default=None)`

## Session Expiry

Global expiry:

```python
session_config = SessionConfig(
    session_expiration_time=3600
)
```

Per-session expiry:

```python
@app.post("/login")
async def login(request, response):
    request.session["user_id"] = "123"
    request.session.set_expiry(1800)
    return response.json({"success": True})
```

Use this when explaining browser state lifetimes and login flows.

## Session Backends

### Signed Cookie Sessions

```python
from nexios.session.signed_cookies import SignedSessionManager

session_config = SessionConfig(
    manager=SignedSessionManager
)
```

Good for:

- Simpler deployments
- No server-side session store

Tradeoff:

- Session size is limited by cookies

### File-Based Sessions

```python
from nexios.session.file import FileSessionManager

session_config = SessionConfig(
    manager=FileSessionManager,
    session_file_storage_path="sessions",
    session_file_name="session_"
)
```

Good for:

- Server-side invalidation
- Larger state than cookie-only sessions

## State Design Notes

Teach these rules to AI editors:

- Store identifiers and lightweight state, not large blobs
- Use secure and httponly cookies in production
- Separate authentication from general session preferences when the explanation needs that distinction
- Mention Redis or database-backed storage only when the user needs distributed or server-side state management
