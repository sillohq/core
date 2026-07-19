---
title: Users & User Models
description: The sillo.users contract and built-ins — AbstractBaseUser, the Record-backed User, SimpleUser, AnonymousUser, UserManager, and password utilities. How the middleware resolves a user from an identity.
head:
- tag: meta
  attrs:
    property: og:title
    content: Users & User Models in sillo
- tag: meta
  attrs:
    property: og:description
    content: AbstractBaseUser contract, the built-in User model, UserManager, SimpleUser, and password hashing — how sillo resolves request.user.
---

# Users & User Models

Authentication produces an **identity** (a string). To turn that identity into a usable object, sillo calls your user class's `load_user(identity)` classmethod. Everything you attach to `AuthenticationMiddleware(user_model=...)` must satisfy the `AbstractBaseUser` contract.

sillo ships four ready pieces:

| Class | Role |
| --- | --- |
| `AbstractBaseUser` | The contract every user class implements |
| `User` | Record/Tortoise-backed database model (the one you usually want) |
| `SimpleUser` | In-memory user for tests and prototypes |
| `AnonymousUser` / `UnauthenticatedUser` | Sentinel attached when no backend succeeds |

And `UserManager` (creation + lookups) plus password helpers (`make_password`, `check_password`, `validate_password`, …).

## The contract in one minute

The middleware only touches a few members. If these exist, your class works:

```python
from sillo.users import AbstractBaseUser
from typing import Optional

class MyUser(AbstractBaseUser):
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

How a request becomes a user:

```
backend resolves identity "42"
  → user = await MyUser.load_user("42")   # your classmethod
  → request.scope["user"] = user
```

If `load_user` returns `None`, the middleware moves to the next backend; if every backend fails, `AnonymousUser` is attached and `request.scope["auth"]` is `None`.

<aside type="tip" title="Pass the class, not an instance">
`user_model=User` — the class itself. `load_user` is called as a classmethod, so never instantiate the user model to hand to the middleware.
</aside>

## The built-in User

For almost every app, use `User`. It's a Record/Tortoise model that already extends `AbstractBaseUser`, `TimestampsMixin`, and `SoftDeletesMixin`.

```python
from sillo.users import User

user = await User.objects.create_user(
    email="alice@example.com",
    username="alice",
    password="StrongP@ss1",
)
print(user.identity)        # "1"  (string of the auto id)
print(user.is_authenticated) # True (== is_active)
```

### Fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `IntField(pk=True)` | Auto-increment primary key |
| `email` | `CharField(255, unique, indexed)` | Unique, indexed lookup |
| `username` | `CharField(150, unique, indexed)` | Unique, indexed lookup |
| `password` | `CharField(128)` | bcrypt hash — never the raw value |
| `is_active` / `is_staff` / `is_superuser` | `BooleanField` | `is_authenticated` is an alias of `is_active` |
| `last_login` | `DatetimeField(nullable)` | Set via `set_last_login()` |
| `email_verified_at` | `DatetimeField(nullable)` | Set via `mark_email_verified()` |

`identity` returns `str(self.id)`; `display_name` returns `username`. `has_perm(perm)` returns `True` for superusers, otherwise checks an in-memory `_permissions` list (empty by default — wire up your own permission source by overriding `has_perm`/`has_permission`).

`load_user(identity)` resolves through `UserManager().get_by_id(int(identity))`, which only returns **active** users:

```python
user = await User.load_user("1")   # ← what the middleware calls
```

### Passwords

```python
user.set_password("new-secret")           # stores bcrypt hash
user.check_password("new-secret")         # True (constant-time compare)
user.set_unusable_password()              # "!" marker — nothing will ever match
user.has_usable_password()                # False
await user.set_last_login()               # updates last_login, saves field
```

### Extending User

`User` is meant to be subclassed. Add fields and override behavior freely:

```python
from sillo.record import Model
from sillo.users import AbstractBaseUser

class User(Model, AbstractBaseUser, TimestampsMixin, SoftDeletesMixin):
    # ... standard fields ...
    phone = fields.CharField(max_length=20, null=True)

    def has_perm(self, perm: str) -> bool:
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        return perm in (self.permissions or [])
```

You can also mix in auth capabilities so a user object can issue its own tokens and sessions:

```python
from sillo.auth.jwt_auth.mixins import JWTUserMixin
from sillo.auth.session_auth.mixins import SessionUserMixin
from sillo.auth.apikey.mixins import ApiKeyUserMixin

class User(Model, AbstractBaseUser, JWTUserMixin, SessionUserMixin, ApiKeyUserMixin):
    ...
```

That gives each user `issue_token_pair(...)`, `create_session(...)`, `create_api_key(...)`, and the rest (see the individual auth pages).

### Registering with the database

`User` is a Tortoise model. Register the module containing it so tables get created:

```python
from sillo.record import setup_record, DatabaseConfig

db = setup_record(
    app,
    DatabaseConfig.sqlite("app.db"),       # or .postgres() / .mysql() / .from_env()
    model_modules=["myapp.models"],         # module that defines User
)
```

`setup_record` calls `Tortoise.init()`, creates schemas (`safe=True`), and closes connections on shutdown. The table name is `Meta.table` — `"users"` for the built-in model.

## UserManager

Creation and lookup helpers. It lazy-resolves its model (falls back to the built-in `User`), so you generally don't need to wire anything manually — `User.objects` already points at it.

```python
from sillo.users import User, UserManager

user = await User.objects.create_user(
    email="bob@example.com", username="bob", password="StrongP@ss1",
)
admin = await User.objects.create_superuser(
    email="admin@example.com", username="admin", password="VeryStr0ng!",
)
```

- `create_user(email, username, password=None, **extra)` — missing password sets an unusable marker.
- `create_superuser(...)` — forces `is_staff`/`is_superuser`/`is_active`, and runs `validate_password()` (weak password → `ValueError`).
- `get_by_id(id)`, `get_by_email(email)`, `get_by_username(username)` — all filter `is_active=True`.
- `get_by_natural_key(identifier)` — tries email, then username.

## SimpleUser & AnonymousUser

`SimpleUser` needs no database — handy for tests and quick prototypes. `AnonymousUser` is what you get for unauthenticated requests.

```python
from sillo.users import SimpleUser, AnonymousUser

u = SimpleUser("alice", permissions=["read", "write"])
u.is_authenticated      # True
u.has_permission("read")   # True
u.has_permission("admin")  # False

a = AnonymousUser()
a.is_authenticated      # False
a.has_permission("x")   # False
```

`SimpleUser.load_user(identity)` returns `SimpleUser(identity, [identity])` — the identity string is used as both name and sole permission.

## Password utilities

All hashing uses bcrypt (cost 12 by default), constant-time comparison.

```python
from sillo.users import make_password, check_password, validate_password

hashed = make_password("my-secret")
check_password("my-secret", hashed)   # True
check_password("nope", hashed)        # False

validate_password("weak")
# ["Password must be at least 8 characters.",
#  "Password must contain at least one uppercase letter.",
#  "Password must contain at least one digit.",
#  "Password must contain at least one special character."]
validate_password("StrongP@ss1")      # []  (passes)
```

`validate_password` rules: ≥8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special. Also available: `password_strength(pw)` → `{"score", "strength", "feedback"}`, `is_password_usable(hash)`, and `needs_rehash(hash, rounds=)` for progressive hash upgrades on login.

## Putting it together

```python
from sillo import silloApp
from sillo.auth import AuthenticationMiddleware, useAuth
from sillo.auth.jwt_auth import JWTAuthBackend
from sillo.users import User

app = silloApp()

app.use(AuthenticationMiddleware(
    user_model=User,
    backend=JWTAuthBackend(secret_key="change-me", identifier="sub"),
))

@app.get("/me", auth=useAuth())
async def me(request, response):
    # request.user is a fully-loaded User instance
    return {"id": request.user.identity, "email": request.user.email}
```

## Related

- [Authentication](/guides/authentication/) — middleware + backends
- [Protecting Routes](/guides/protecting-routes/) — `useAuth` and `has_permission`
- [JWT](/guides/jwt-auth/) · [Sessions](/guides/session-auth/) · [API Keys](/guides/api-keys/)
