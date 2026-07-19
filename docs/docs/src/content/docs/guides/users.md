---
title: Users & User Models
description: How sillo turns an auth identity into a request.user — the simplest integration first, then the AbstractBaseUser contract, the built-in Record-backed User, UserManager, password hashing, and building custom user classes.
head:
- tag: meta
  attrs:
    property: og:title
    content: Users & User Models in sillo
- tag: meta
  attrs:
    property: og:description
    content: sillo users — simplest integration, AbstractBaseUser contract, built-in User, UserManager, and password hashing.
---

# Users & User Models

Every authenticated request in sillo ends with one thing: a `request.user` object. This page shows the simplest way to get there, then goes deep on the contract that makes it work, the built-in `User` model, and how to build your own.

## The simplest integration

You don't need to understand the whole contract to get a working user. sillo ships a `User` model and a `UserManager`; you register them with the database, hand `User` to the auth middleware, and `request.user` appears.

```python
# app.py
from sillo import silloApp
from sillo.record import setup_record, DatabaseConfig
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.jwt_auth import JWTAuthBackend
from sillo.users import User

app = silloApp()

# 1. Connect the database (creates the "users" table)
db = setup_record(app, DatabaseConfig.sqlite("app.db"), model_modules=["myapp.models"])

# 2. Resolve request.user from a JWT
app.use(AuthenticationMiddleware(
    user_model=User,
    backend=JWTAuthBackend(secret_key="change-me", identifier="sub"),
))

# 3. Protect a route — request.user is a loaded User instance
@app.get("/me", auth=useAuth())
async def me(request, response):
    return {"id": request.user.identity, "email": request.user.email}
```

That's the whole loop. To make `/me` reachable, you create a user and issue a token:

```python
# myapp/models.py
from sillo.users import User

# somewhere at startup / in a seed script:
user = await User.objects.create_user(
    email="alice@example.com",
    username="alice",
    password="StrongP@ss1",
)
```

Now any request carrying a valid bearer token for that user hits `/me` with `request.user.identity == "1"`, `request.user.email == "alice@example.com"`, and `request.user.is_authenticated == True`.

<aside type="tip" title="Pass the class, not an instance">
`user_model=User` is the **class**. The middleware calls `User.load_user(identity)` as a classmethod — never instantiate the model to hand to the middleware.
</aside>

Everything below explains what just happened and how to customize it.

## What "a user" means to sillo

Authentication only produces an **identity** — a string. The middleware's job is to turn that string into a real object via your user class's `load_user(identity)` classmethod:

```
backend resolves identity "1"
  → user = await User.load_user("1")      # your classmethod
  → request.scope["user"] = user          # becomes request.user
```

- If `load_user` returns a user, that's `request.user`.
- If it returns `None`, the middleware tries the next backend.
- If every backend fails (or there are none), sillo attaches `AnonymousUser` and `request.scope["auth"]` is `None`.

So a user class only has to do two things: describe itself through a few properties, and know how to load one of itself from an identity string. That contract is `AbstractBaseUser`.

## The built-in `User`

`User` is a Record/Tortoise model that already implements `AbstractBaseUser` plus `TimestampsMixin` (created/updated timestamps) and `SoftDeletesMixin` (recoverable deletes). For almost every app, this is the user class you want.

```python
from sillo.users import User

user = await User.load_user("1")        # what the middleware calls internally
print(user.identity)                     # "1"
print(user.display_name)                 # "alice"  (== username)
print(user.is_authenticated)             # True (alias of is_active)
print(user.has_perm("anything"))         # False unless superuser / wired up
```

### Fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `IntField(pk=True)` | Auto-increment primary key |
| `email` | `CharField(255, unique, indexed)` | Unique, indexed lookup |
| `username` | `CharField(150, unique, indexed)` | Unique, indexed lookup |
| `password` | `CharField(128)` | bcrypt hash — the raw password is never stored |
| `is_active` / `is_staff` / `is_superuser` | `BooleanField` | `is_authenticated` is an alias of `is_active` |
| `last_login` | `DatetimeField(nullable)` | Set via `set_last_login()` |
| `email_verified_at` | `DatetimeField(nullable)` | Set via `mark_email_verified()` |

### Identity, display name, permissions

- `identity` returns `str(self.id)` — the stable string used by backends and `load_user`.
- `display_name` returns `username` — for logs and UI.
- `has_perm(perm)` returns `True` for superusers, otherwise checks an in-memory `_permissions` list (empty by default). To drive permissions from your own source (a role table, an enum, an external service), override `has_perm` / `has_permission` — see [Custom user classes](#custom-user-classes).
- `load_user(identity)` resolves through `UserManager().get_by_id(int(identity))`, which returns **only active** users. A deactivated (`is_active=False`) or soft-deleted user fails to load and is treated as unauthenticated.

### Passwords

```python
user.set_password("new-secret")           # stores a bcrypt hash
user.check_password("new-secret")         # True  (constant-time compare)
user.set_unusable_password()              # "!" marker — nothing will ever match
user.has_usable_password()                # False
await user.set_last_login()               # updates last_login, saves that field
await user.mark_email_verified()          # sets email_verified_at
```

## Creating and finding users — UserManager

`User.objects` is already a `UserManager` (it lazy-resolves to the `User` model), so you don't wire anything by hand. It handles creation and lookups:

```python
user = await User.objects.create_user(
    email="bob@example.com",
    username="bob",
    password="StrongP@ss1",        # omitted → sets an unusable password
)
admin = await User.objects.create_superuser(
    email="admin@example.com",
    username="admin",
    password="VeryStr0ng!",
)
```

| Method | Behavior |
| --- | --- |
| `create_user(email, username, password=None, **extra)` | Hashes the password; missing password sets an unusable marker. `**extra` passes through to the model constructor. |
| `create_superuser(...)` | Forces `is_staff`/`is_superuser`/`is_active=True` and runs `validate_password()` — a weak password raises `ValueError`. |
| `get_by_id(id)` / `get_by_email(email)` / `get_by_username(username)` | All filter `is_active=True`. |
| `get_by_natural_key(identifier)` | Tries email, then username. Useful for backends that accept either. |

## Passwords, in depth

All hashing uses **bcrypt** (cost 12 by default) with a per-password salt, and verification is constant-time (resistant to timing attacks). The helpers live in `sillo.users.password` and are re-exported from `sillo.users`.

```python
from sillo.users import make_password, check_password, validate_password

hashed = make_password("my-secret")        # "$2b$12$..." — 60 chars, salt included
check_password("my-secret", hashed)        # True
check_password("wrong", hashed)            # False
check_password("", hashed)                 # False (empty never matches)
```

**Unusable passwords.** A user with no password (OAuth-only accounts, invited-but-not-yet-set) gets a marker prefix `"!"`:

```python
from sillo.users import UNUSABLE_PASSWORD_PREFIX, is_password_usable

make_password(None)            # "!" + 40 random hex chars
is_password_usable(hashed)     # False when it starts with "!"
user.set_unusable_password()   # same effect, on an instance
```

`check_password` also short-circuits to `False` for empty input or the unusable marker.

**Validation.** `validate_password(pw, min_length=8)` returns a list of human-readable errors (empty list = passes). Rules: ≥8 chars, at least one uppercase, one lowercase, one digit, one special character.

```python
validate_password("weak")
# ["Password must be at least 8 characters.",
#  "Password must contain at least one uppercase letter.",
#  "Password must contain at least one lowercase letter.",
#  "Password must contain at least one digit.",
#  "Password must contain at least one special character."]
validate_password("StrongP@ss1")   # []
```

`password_strength(pw)` gives a quantitative readout you can show in a UI: `{"score": int, "strength": "weak"|"medium"|"strong", "feedback": [...]}`. Thresholds: score ≥5 strong, ≥3 medium, else weak.

**Upgrading hashes.** `needs_rehash(hash, rounds=12)` inspects the cost factor baked into an existing bcrypt hash. Call it on login to transparently bump weak hashes to a higher cost:

```python
if needs_rehash(user.password, rounds=14):
    user.set_password(raw_password)   # re-hash at the new cost
    await user.save()
```

## Custom user classes

The built-in `User` is just one implementation of `AbstractBaseUser`. You can build any user — backed by LDAP, an external API, an in-memory dict, or a completely different database. The contract is small.

### The full contract

```python
from sillo.users import AbstractBaseUser
from typing import Optional

class MyUser(AbstractBaseUser):
    # ── You implement these ──
    @property
    def is_authenticated(self) -> bool: ...   # True for real users
    @property
    def identity(self) -> str: ...             # stable string id
    @property
    def display_name(self) -> str: ...         # for logs / UI
    def has_permission(self, perm: str) -> bool: ...

    @classmethod
    async def load_user(cls, identity: str) -> Optional["MyUser"]: ...
```

`AbstractBaseUser` provides sane defaults for the rest: `is_anonymous` (= `not is_authenticated`), `is_active` (= `True`), `get_id()` (→ `identity`), `has_perm` / `has_perms` (→ `False` / all), and `get_email_field_name()` (→ `"email"`). Implement the four members above and your class works everywhere — middleware, `useAuth`, guards.

### Example: LDAP-backed user

```python
class LDAPUser(AbstractBaseUser):
    def __init__(self, dn: str, cn: str, groups: list[str]):
        self.dn, self.cn, self.groups = dn, cn, groups

    @property
    def is_authenticated(self) -> bool: return True
    @property
    def identity(self) -> str: return self.dn
    @property
    def display_name(self) -> str: return self.cn
    def has_permission(self, perm: str) -> bool: return perm in self.groups

    @classmethod
    async def load_user(cls, identity: str):
        entry = await ldap_server.search(identity)
        return cls(entry.dn, entry.cn, entry.groups) if entry else None

app.use(AuthenticationMiddleware(user_model=LDAPUser, backend=LDAPBackend()))
```

### Example: permissions from your own source

The built-in `User.has_perm` only consults an in-memory `_permissions` list. Override it to read from a role table or service:

```python
class User(Model, AbstractBaseUser, TimestampsMixin, SoftDeletesMixin):
    # ... standard fields ...

    def has_perm(self, perm: str) -> bool:
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        return perm in (self.permissions or [])
```

## SimpleUser & AnonymousUser

**`SimpleUser`** needs no database — ideal for tests and prototypes. `has_permission` checks a passed-in list; `load_user` returns `SimpleUser(identity, [identity])`.

```python
from sillo.users import SimpleUser

u = SimpleUser("alice", permissions=["read", "write"])
u.is_authenticated            # True
u.has_permission("read")     # True
u.has_permission("admin")    # False
```

**`AnonymousUser`** (also exported as `UnauthenticatedUser`) is the sentinel attached when no backend authenticates the request. Every capability check returns `False`; `identity` is `""`.

```python
from sillo.users import AnonymousUser

a = AnonymousUser()
a.is_authenticated   # False
a.has_permission("x") # False
```

You'll rarely construct these yourself — they're what `request.user` *is* on an unauthenticated call (when `useAuth(required=False)` lets it through, or when there's no auth gate at all).

## Adding auth capabilities to User

A user object can manage its own tokens, sessions, and API keys by mixing in the auth mixins. This is what makes `user.issue_token_pair(...)`, `user.create_session(...)`, and `user.create_api_key(...)` available:

```python
from sillo.record import Model
from sillo.users import AbstractBaseUser, TimestampsMixin, SoftDeletesMixin
from sillo.auth.jwt_auth.mixins import JWTUserMixin
from sillo.auth.session_auth.mixins import SessionUserMixin
from sillo.auth.apikey.mixins import ApiKeyUserMixin

class User(Model, AbstractBaseUser, TimestampsMixin, SoftDeletesMixin,
           JWTUserMixin, SessionUserMixin, ApiKeyUserMixin):
    ...
```

Each mixin reads `int(str(self.identity))` as the `user_id`, which matches how `SessionAuthBackend` and `User.load_user` resolve identities. See [JWT](/guides/jwt-auth/), [Sessions](/guides/session-auth/), and [API Keys](/guides/api-keys/) for the methods these add.

## Registering with the database

`User` is a Tortoise model; tables are created when you call `setup_record` with the module that defines your user class:

```python
from sillo.record import setup_record, DatabaseConfig

db = setup_record(
    app,
    DatabaseConfig.sqlite("app.db"),        # or .postgres() / .mysql() / .from_env()
    model_modules=["myapp.models"],          # module containing User
)
```

`setup_record` runs `Tortoise.init()`, creates schemas (`safe=True`, so existing tables are left alone), and closes connections on shutdown. The table name is `Meta.table` — `"users"` for the built-in model; override it on a subclass to rename.

## How it all connects

```
create_user()  ──►  User row in DB (password hashed)
        │
login handler  ──►  TokenForUser/Guard issues credential
        │
request  ──►  AuthenticationMiddleware
        │         └─ backend resolves identity "1"
        │         └─ User.load_user("1")  ──►  loads active User
        ▼
request.user  ──►  useAuth() checks is_authenticated / scopes / permissions
```

If you internalize that arrow — *identity → `load_user` → `request.user`* — every other auth feature in sillo is just a different way of producing the identity on the left.

## Related

- [Authentication](/guides/authentication/) — middleware + backend model
- [Protecting Routes](/guides/protecting-routes/) — `useAuth` and `has_permission`
- [JWT](/guides/jwt-auth/) · [Sessions](/guides/session-auth/) · [API Keys](/guides/api-keys/)
