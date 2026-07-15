---
title: Authentication
description: Build a complete authentication system with sillo from scratch — database setup with Record ORM, JWT and session backends, login, logout, token refresh, protected routes, and middleware wiring. Every example is a complete, runnable code block.
head:
- tag: meta
  attrs:
    property: og:title
    content: Authentication in sillo
- tag: meta
  attrs:
    property: og:description
    content: Build a complete auth system from scratch — Record ORM database setup, JWT and session backends, login, logout, refresh, and protected routes.
---

# Authentication

This guide walks through building a complete authentication system with sillo — from an empty file to a running application with registration, login, logout, token refresh, JWT and session backends, and protected routes. Every code block is a complete, working snippet. Copy them into your project and they will run.

You will build:

- A database-backed `User` model using Record ORM
- JWT-based authentication with access + refresh tokens
- Session-based login with cookie storage
- Registration, login, logout, and token refresh endpoints
- Protected routes using `useAuth`
- A multi-backend setup that tries JWT first, then falls back to session

---

## Complete Application — From Scratch

Here is the entire application in one file. Read through it, then we'll break down every section in detail.

```python
# app.py — complete auth system
import os
from datetime import datetime, timezone

from tortoise import fields
from sillo import silloApp
from sillo.record import Model, setup_record, DatabaseConfig
from sillo.users.base import AbstractBaseUser
from sillo.users.managers import UserManager
from sillo.users.password import make_password, check_password
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.jwt_auth import JWTAuthBackend, TokenForUser
from sillo.auth.session_auth import SessionAuthBackend, SessionGuard
from sillo.session.middleware import SessionMiddleware


# ═══════════════════════════════════════════════════════════════
# 1. USER MODEL
# ═══════════════════════════════════════════════════════════════

class User(Model, AbstractBaseUser):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True, index=True)
    username = fields.CharField(max_length=150, unique=True, index=True)
    password = fields.CharField(max_length=128)
    is_active = fields.BooleanField(default=True)
    is_staff = fields.BooleanField(default=False)
    is_superuser = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True, default=None)
    email_verified_at = fields.DatetimeField(null=True, default=None)

    class Meta:
        table = "users"

    @property
    def is_authenticated(self) -> bool:
        return self.is_active

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def identity(self) -> str:
        return str(self.id)

    def has_perm(self, perm: str) -> bool:
        if self.is_superuser:
            return True
        return perm in getattr(self, "_permissions", [])

    def set_password(self, raw_password: str) -> None:
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    async def set_last_login(self) -> None:
        self.last_login = datetime.now(timezone.utc)
        await self.save(update_fields=["last_login"])

    @classmethod
    async def load_user(cls, identity: str):
        return await User.objects.get_by_id(int(identity))


User.objects = UserManager()


# ═══════════════════════════════════════════════════════════════
# 2. APPLICATION & DATABASE
# ═══════════════════════════════════════════════════════════════

app = silloApp()

JWT_SECRET = os.environ.get("JWT_SECRET", "a-very-long-secret-key-change-in-production")

db = setup_record(
    app,
    DatabaseConfig.sqlite("myapp.db"),
    model_modules=["__main__"],
)


# ═══════════════════════════════════════════════════════════════
# 3. MIDDLEWARE STACK
# ═══════════════════════════════════════════════════════════════

# Required for session auth — signs and decrypts session cookies
app.use(SessionMiddleware(secret_key=os.environ.get("SESSION_SECRET", "session-secret")))

# Authentication middleware — tries JWT first, then session
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=[
        JWTAuthBackend(secret_key=JWT_SECRET),
        SessionAuthBackend(),
    ],
))

# Session guard for session-based login
guard = SessionGuard(user_model=User)


# ═══════════════════════════════════════════════════════════════
# 4. AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/auth/register")
async def register(request, response):
    body = await request.json
    user = await User.objects.create_user(
        email=body["email"],
        username=body["username"],
        password=body["password"],
    )
    return response.json({"id": user.identity, "email": user.email}, status_code=201)


@app.post("/auth/login")
async def login(request, response):
    body = await request.json
    user = await User.objects.get_by_email(body["email"])

    if user is None or not user.check_password(body["password"]):
        return response.json({"error": "Invalid email or password"}, status_code=401)

    await user.set_last_login()

    # Issue JWT token pair
    tokens = TokenForUser(user, secret=JWT_SECRET)
    return response.json(tokens.token_pair())


@app.post("/auth/session-login")
async def session_login(request, response):
    form = await request.form
    email = form.get("email")
    password = form.get("password")

    if await guard.attempt(request, email=email, password=password):
        return response.redirect("/dashboard")

    return response.html("<p>Invalid credentials</p>", status_code=401)


@app.post("/auth/refresh", auth=useAuth())
async def refresh(request, response):
    body = await request.json
    refresh_token = body.get("refresh_token")

    if not refresh_token:
        return response.json({"error": "refresh_token is required"}, status_code=400)

    try:
        pair = await request.user.refresh_token_pair(refresh_token, secret=JWT_SECRET)
        return response.json(pair)
    except ValueError as e:
        return response.json({"error": str(e)}, status_code=401)


@app.post("/auth/logout", auth=useAuth())
async def logout(request, response):
    # Extract the current access token from the Authorization header
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")

    if token:
        await request.user.blacklist_token(token, secret=JWT_SECRET)

    return response.json({"message": "Logged out"})


@app.post("/auth/session-logout", auth=useAuth())
async def session_logout(request, response):
    await guard.logout(request)
    return response.redirect("/login")


# ═══════════════════════════════════════════════════════════════
# 5. PROTECTED ROUTES
# ═══════════════════════════════════════════════════════════════

@app.get("/me", auth=useAuth())
async def me(request, response):
    return response.json({
        "id": request.user.identity,
        "email": request.user.email,
        "username": request.user.display_name,
        "is_active": request.user.is_active,
    })


@app.get("/admin", auth=useAuth(scopes=["jwt"], permissions=["admin"]))
async def admin(request, response):
    return response.json({"message": "Admin access granted"})


# ═══════════════════════════════════════════════════════════════
# 6. PUBLIC ROUTES
# ═══════════════════════════════════════════════════════════════

@app.get("/feed", auth=useAuth(required=False))
async def feed(request, response):
    if request.user.is_authenticated:
        return response.json({
            "feed": "personalized",
            "user": request.user.display_name,
        })
    return response.json({"feed": "public"})
```

**To run:**

```bash
pip install sillo bcrypt pyjwt
python app.py
# or: sillo run app:app
```

The database file `myapp.db` is created automatically. The `users` table is generated on first startup.

---

## Section-by-Section Breakdown

### Section 1: User Model

The `User` class combines four things:

| Inheritance | Provides |
|-------------|----------|
| `Model` | Database persistence — `.save()`, `.filter()`, `.create()`, `.all()` |
| `AbstractBaseUser` | Auth contract — `is_authenticated`, `identity`, `display_name`, `load_user()` |

The `load_user` classmethod is the critical piece. When `AuthenticationMiddleware` successfully authenticates a request, it calls `User.load_user(identity_string)`. Your implementation must:

1. Take an identity string (the user ID as a string)
2. Query the database
3. Return the `User` instance or `None`

```python
@classmethod
async def load_user(cls, identity: str):
    return await User.objects.get_by_id(int(identity))
```

The `identity` property returns `str(self.id)` — so `load_user` takes a string ID, converts to int, and looks up in the database. This is the standard pattern.

`User.objects = UserManager()` attaches the manager. This is where `create_user` and `create_superuser` come from.

### Section 2: Application & Database

```python
app = silloApp()
JWT_SECRET = os.environ.get("JWT_SECRET", "a-very-long-secret-key-change-in-production")

db = setup_record(
    app,
    DatabaseConfig.sqlite("myapp.db"),
    model_modules=["__main__"],
)
```

`setup_record` does four things:

1. Creates a `DatabaseManager` wrapping Tortoise ORM
2. Registers `__main__` as a model module (since the `User` class is defined in this file)
3. Registers `app.on_startup(db.init)` — connects to the database and creates tables on startup
4. Registers `app.on_shutdown(db.shutdown)` — closes connections on shutdown

If your `User` model is in a separate file like `myapp/models.py`, change the module path:

```python
model_modules=["myapp.models"]
```

For PostgreSQL:

```python
db = setup_record(
    app,
    DatabaseConfig.postgres("myapp", "password", host="localhost"),
    model_modules=["__main__"],
)
```

### Section 3: Middleware Stack

The order matters. Middleware runs in the order you register it — last registered wraps the outside, so it runs first.

```
Request → SessionMiddleware → AuthenticationMiddleware → Route Handler
```

**SessionMiddleware:**

```python
app.use(SessionMiddleware(secret_key="session-secret"))
```

This decrypts the session cookie on every request and attaches a `Session` object to `request.session`. Without this, session auth won't work. Even if you're only using JWT, you might still want this if you plan to add session login later.

**AuthenticationMiddleware:**

```python
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=[
        JWTAuthBackend(secret_key=JWT_SECRET),
        SessionAuthBackend(),
    ],
))
```

This is the core. For every request, it:

1. Tries `JWTAuthBackend` — reads `Authorization: Bearer <token>`, decodes the JWT, extracts the user ID from the `sub` claim
2. If JWT fails (no header, invalid token, expired), tries `SessionAuthBackend` — reads `request.session["user"]` to find a logged-in user
3. If neither succeeds, attaches `UnauthenticatedUser` — the request still proceeds
4. If one succeeds, calls `User.load_user(identity)` to load the full user from the database
5. Sets `request.scope["user"]` = user instance
6. Sets `request.scope["auth"]` = backend scope string (`"jwt"` or `"session"`)

The `user_model` parameter tells the middleware **which class** to use for loading users. It must be a class (not an instance) that has a `load_user(identity)` classmethod.

### Section 4: Auth Endpoints

**Registration:**

```python
@app.post("/auth/register")
async def register(request, response):
    body = await request.json
    user = await User.objects.create_user(
        email=body["email"],
        username=body["username"],
        password=body["password"],
    )
    return response.json({"id": user.identity, "email": user.email}, status_code=201)
```

`create_user` handles password hashing automatically via `set_password()`. The password stored in the database is a bcrypt hash — never the raw password.

**JWT Login:**

```python
@app.post("/auth/login")
async def login(request, response):
    body = await request.json
    user = await User.objects.get_by_email(body["email"])

    if user is None or not user.check_password(body["password"]):
        return response.json({"error": "Invalid email or password"}, status_code=401)

    await user.set_last_login()

    tokens = TokenForUser(user, secret=JWT_SECRET)
    return response.json(tokens.token_pair())
```

The response format:

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
}
```

`TokenForUser` is a factory bound to the user. It generates HS256 JWTs with:
- `sub`: the user's identity (`user.identity`)
- `iat`: issued-at timestamp
- `exp`: expiration timestamp (15 minutes for access, 7 days for refresh)
- `typ`: `"access"` or `"refresh"`

**Session Login:**

```python
@app.post("/auth/session-login")
async def session_login(request, response):
    form = await request.form
    if await guard.attempt(request, email=form["email"], password=form["password"]):
        return response.redirect("/dashboard")
    return response.html("<p>Invalid credentials</p>", status_code=401)
```

`guard.attempt()` does four things:
1. Looks up the user by email
2. Verifies the password with `check_password()`
3. Stores user data in `request.session`
4. Calls `user.set_last_login()`

After `attempt()` succeeds, every subsequent request from that browser will have the user in the session — the `SessionAuthBackend` reads it and `AuthenticationMiddleware` loads the full user.

**Token Refresh:**

```python
@app.post("/auth/refresh", auth=useAuth())
async def refresh(request, response):
    body = await request.json
    refresh_token = body.get("refresh_token")

    try:
        pair = await request.user.refresh_token_pair(refresh_token, secret=JWT_SECRET)
        return response.json(pair)
    except ValueError as e:
        return response.json({"error": str(e)}, status_code=401)
```

This endpoint is itself protected — you need a valid access token to call it (the `auth=useAuth()` at the top). The `refresh_token_pair` method:
1. Verifies the refresh token (ignoring expiry)
2. Checks if the token has been consumed before (replay attack detection)
3. Issues a new access + refresh pair in the same token family
4. If a consumed token is detected, revokes the entire family (anti-theft)

**JWT Logout:**

```python
@app.post("/auth/logout", auth=useAuth())
async def logout(request, response):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")
    if token:
        await request.user.blacklist_token(token, secret=JWT_SECRET)
    return response.json({"message": "Logged out"})
```

This adds the current access token to the `TokenBlacklist` table. The `JWTAuthBackend` checks this blacklist on every request — so the token becomes invalid immediately, even if it hasn't expired yet.

### Section 5: Protected Routes

```python
@app.get("/me", auth=useAuth())
async def me(request, response):
    return response.json({
        "id": request.user.identity,
        "email": request.user.email,
    })
```

`useAuth()` with no arguments means "any authenticated user, regardless of how they authenticated." JWT, session, API key — all accepted.

```python
@app.get("/admin", auth=useAuth(scopes=["jwt"], permissions=["admin"]))
async def admin(request, response):
    return response.json({"message": "Admin access granted"})
```

This route requires:
1. JWT authentication specifically (`scopes=["jwt"]`)
2. The `"admin"` permission (`permissions=["admin"]`)

### Section 6: Public Routes with Optional Auth

```python
@app.get("/feed", auth=useAuth(required=False))
async def feed(request, response):
    if request.user.is_authenticated:
        return response.json({"feed": "personalized"})
    return response.json({"feed": "public"})
```

`required=False` means the route always runs. If the user is authenticated, `request.user` is a fully loaded `User` instance. If not, it's `UnauthenticatedUser` — `is_authenticated` returns `False`.

---

## How Requests Flow

Here's the exact sequence when a client hits `GET /me` with a valid JWT:

```
1. ASGI server receives GET /me with Authorization: Bearer eyJ...

2. SessionMiddleware.process_request()
   → reads session cookie → decrypts → attaches request.session

3. AuthenticationMiddleware.process_request()
   → tries JWTAuthBackend:
     a. Reads Authorization header
     b. Extracts "eyJ..." token
     c. Decodes + verifies JWT signature with secret_key
     d. Checks TokenBlacklist — not found, token is valid
     e. Extracts sub claim → "42"
     f. Returns AuthResult(success=True, identity="42", scope="jwt")
   → Calls User.load_user("42")
     → User.objects.get_by_id(42) → SELECT * FROM users WHERE id=42 AND is_active=true
     → Returns User(id=42, email="alice@...", username="alice", ...)
   → Sets request.scope["user"] = User(...)
   → Sets request.scope["auth"] = "jwt"

4. Route matching → GET /me matches

5. Route.get_route_handler()
   → Resolves dependencies
   → Validates request body (none configured)
   → useAuth.authenticate(request):
     a. Checks request.scope["user"] → User instance, is_authenticated=True ✓
     b. Checks scopes → [] (empty, any scope accepted) ✓
     c. Checks permissions → [] (empty, no permissions required) ✓
     d. Returns True
   → Calls handler(request, response)

6. Handler executes:
   request.user → User instance (fully loaded from database)
   request.user.email → "alice@example.com"
   request.user.is_authenticated → True
   return response.json({...})

7. SessionMiddleware.process_response()
   → Sets session cookie on response

8. Response sent to client: 200 OK {"id": "42", ...}
```

When the JWT is missing or invalid, step 3 falls through to `SessionAuthBackend`. If that also fails, `request.scope["user"]` is set to `UnauthenticatedUser`. Then in step 5, `useAuth.authenticate()` sees `is_authenticated=False`, raises `AuthenticationFailed`, and the handler never runs — the client receives a 401.

---

## Custom Authentication Backend

Create your own backend by subclassing `AuthenticationBackend`:

```python
from sillo.auth.backends.base import AuthenticationBackend
from sillo.auth.model import AuthResult

class HMACBackend(AuthenticationBackend):
    def __init__(self, shared_secret: str):
        self.shared_secret = shared_secret

    async def authenticate(self, request):
        signature = request.headers.get("X-HMAC-Signature")
        user_id = request.headers.get("X-User-Id")

        if not signature or not user_id:
            return AuthResult(success=False, identity="", scope="")

        if self._verify_hmac(request, signature):
            return AuthResult(
                success=True,
                identity=user_id,
                scope="hmac",
            )

        return AuthResult(success=False, identity="", scope="")

    def _verify_hmac(self, request, signature: str) -> bool:
        # Your HMAC verification logic here
        ...
```

**AuthResult parameters:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | `True` if authentication passed |
| `identity` | `str` | User identifier — passed to `User.load_user(identity)` |
| `scope` | `str` | Auth method label — checked by `useAuth(scopes=...)` |

Wire it into the middleware:

```python
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=HMACBackend(shared_secret="..."),
))
```

---

## Error Handling

```python
from sillo.auth.exceptions import AuthenticationFailed  # → 401
from sillo.auth.exceptions import PermissionDenied      # → 403
```

Both are HTTP exceptions. They can be raised anywhere — in your handler, in middleware, in a backend — and will produce the correct JSON error response:

```json
{"detail": "Authentication failed"}
```

To customize the error response, register an exception handler:

```python
from sillo.auth.exceptions import AuthenticationFailed

async def custom_401(request, response, exc):
    return response.json({"error": "Please log in"}, status_code=401)

app.add_exception_handler(AuthenticationFailed, custom_401)
```

---

## Next Steps

- [Protecting Routes](/guides/protecting-routes/) — every `useAuth` feature in detail
- [Users & User Models](/guides/users/) — password hashing, custom users, UserManager
- [JWT Authentication](/guides/jwt-auth/) — token families, rotation, reuse detection, blacklisting
- [Session Authentication](/guides/session-auth/) — per-device tracking, logout everywhere
- [API Keys](/guides/api-keys/) — key generation, scoped keys, manager
