---
title: Users & User Models
description: Reference documentation for every class, method, and utility in sillo.users — AbstractBaseUser, User (Record-backed), BaseUser, UserManager, password utilities, and middleware integration.
head:
- tag: meta
  attrs:
    property: og:title
    content: Users & User Models
- tag: meta
  attrs:
    property: og:description
    content: Complete user model reference — AbstractBaseUser contract, Record-backed User, BaseUser password mixin, UserManager, and password utilities.
---

# Users & User Models

The `sillo.users` module is a standalone user management system. It lives outside `sillo.auth` — you can use it with or without sillo's authentication middleware. Every class in this module serves a specific purpose.

```python
from sillo.users import (
    AbstractBaseUser,    # the contract — every user class MUST extend this
    BaseUser,            # AbstractBaseUser + password management
    AnonymousUser,       # sentinel for unauthenticated requests
    User,                # built-in Record-backed database model
    UserManager,         # create_user, create_superuser, lookups
    SimpleUser,          # lightweight in-memory user for testing
    UnauthenticatedUser, # legacy name for AnonymousUser
    make_password,       # bcrypt hash
    check_password,      # bcrypt verify (constant-time)
    validate_password,   # strength validator (length, case, digits, special)
    password_strength,   # quantitative score (weak/medium/strong)
    is_password_usable,  # checks the "unusable" marker
    needs_rehash,        # checks if bcrypt rounds need upgrading
)
```

---

## AbstractBaseUser

`AbstractBaseUser` is the contract. Every user class you pass as `user_model` to `AuthenticationMiddleware` **must** descend from this class. It defines the minimum interface that the middleware and `useAuth` depend on.

### Why It Exists

When `AuthenticationMiddleware` successfully authenticates a request, it calls `user_model.load_user(identity)`. The result is stored on `request.scope["user"]`. From that point on, the framework accesses these properties:

- `request.user.is_authenticated` — checked by `useAuth` and your handlers
- `request.user.identity` — returned by `get_id()`, used in permission checks
- `request.user.display_name` — human-readable name for logs/UI
- `request.user.has_perm(perm)` — checked by permission systems

Without `AbstractBaseUser`, there is no contract — the middleware has no way to know what interface your user object provides.

### Interface

```python
from sillo.users import AbstractBaseUser

class AbstractBaseUser:
    # ── Properties you MUST implement ──────────────────────────

    @property
    def is_authenticated(self) -> bool: ...

    @property
    def display_name(self) -> str: ...

    @property
    def identity(self) -> str: ...

    # ── Properties with defaults ────────────────────────────────

    @property
    def is_anonymous(self) -> bool:
        return not self.is_authenticated

    @property
    def is_active(self) -> bool:
        return True

    # ── Methods with defaults ───────────────────────────────────

    def get_id(self) -> str:
        return self.identity

    def get_display_name(self) -> str:
        return self.display_name

    def has_perm(self, perm: str) -> bool:
        return False

    def has_perms(self, perm_list: list[str]) -> bool:
        return all(self.has_perm(p) for p in perm_list)

    def has_permission(self, permission: str) -> bool:
        raise NotImplementedError

    # ── Class methods ───────────────────────────────────────────

    @classmethod
    async def load_user(cls, identity: str) -> Optional[Self]: ...

    @classmethod
    def get_email_field_name(cls) -> str:
        return "email"
```

### How `load_user` Works

Every auth backend returns an `AuthResult(identity="some_string")`. The middleware then calls:

```python
user = await YourUserClass.load_user(auth_result.identity)
request.scope["user"] = user
```

If `load_user` returns `None`, the middleware treats it as authentication failure and tries the next backend. If all backends fail, `UnauthenticatedUser` is used instead.

The `identity` string comes from the backend:
- `JWTAuthBackend` — the `sub` claim from the JWT payload
- `SessionAuthBackend` — the `id` field from the session data
- `APIKeyAuthBackend` — the raw key or `user_id` from the manager
- Custom backends — whatever you return in `AuthResult.identity`

### Extending AbstractBaseUser — Custom User Classes

Because `AbstractBaseUser` is just an interface contract, you can build ANY kind of user on top of it. The only requirement is implementing the properties and `load_user`.

**LDAP-backed user:**

```python
from sillo.users import AbstractBaseUser

class LDAPUser(AbstractBaseUser):
    def __init__(self, dn: str, cn: str, groups: list[str]):
        self.dn = dn
        self.cn = cn
        self.groups = groups

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.cn

    @property
    def identity(self) -> str:
        return self.dn

    def has_perm(self, perm: str) -> bool:
        return perm in self.groups

    @classmethod
    async def load_user(cls, identity: str):
        entry = await ldap_server.search(identity)
        if entry:
            return cls(entry.dn, entry.cn, entry.groups)
        return None

# Pass it to middleware:
app.use(AuthenticationMiddleware(
    user_model=LDAPUser,   # ← the CLASS, not an instance
    backend=LDAPBackend(),
))
```

**External API-backed user:**

```python
class ExternalUser(AbstractBaseUser):
    def __init__(self, api_response: dict):
        self._data = api_response

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self._data["name"]

    @property
    def identity(self) -> str:
        return self._data["id"]

    @classmethod
    async def load_user(cls, identity: str):
        resp = await external_api.get(f"/users/{identity}")
        if resp.status == 200:
            return cls(resp.json())
        return None
```

**In-memory user (for testing only):**

```python
class TestUser(AbstractBaseUser):
    def __init__(self, user_id: str, name: str):
        self._id = user_id
        self._name = name

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self._name

    @property
    def identity(self) -> str:
        return self._id

    @classmethod
    async def load_user(cls, identity: str):
        return cls(identity, f"User-{identity}")
```

### Passing to Middleware

This is the critical connection — whatever class you define (built-in `User`, custom `LDAPUser`, etc.) gets passed as `user_model` to `AuthenticationMiddleware`:

```python
from sillo.auth import AuthenticationMiddleware

app.use(AuthenticationMiddleware(
    user_model=YourUserClass,  # ← THE CLASS ITSELF (not an instance)
    backend=[...],
))
```

The middleware calls `YourUserClass.load_user(identity)` as a **classmethod**. This is why `load_user` is decorated with `@classmethod` — it's called on the class, not on an instance.

Once attached, your handlers receive fully-loaded instances:

```python
@app.get("/me", auth=useAuth())
async def me(request, response):
    user = request.user  # ← YourUserClass instance
    print(type(user))    # <class 'myapp.models.User'>
    print(user.identity) # "42"
    print(user.email)    # "alice@example.com" (if your class has email)
```

---

## User — The Built-in Record-Backed Model

`User` is sillo's built-in database model. It combines four things:

| Inheritance | What It Adds |
|-------------|-------------|
| `Model` (from `sillo.record`) | Database persistence via Tortoise ORM — `.save()`, `.filter()`, `.create()`, `.all()`, `.first()` |
| `AbstractBaseUser` | The auth contract — `is_authenticated`, `identity`, `display_name`, `load_user()`, `has_perm()` |

### Fields

```python
from tortoise import fields
from sillo.record import Model
from sillo.users.base import AbstractBaseUser

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
```

| Field | Type | Purpose |
|-------|------|---------|
| `id` | `IntField(pk=True)` | Auto-incrementing primary key |
| `email` | `CharField(255, unique)` | Unique email address, indexed for lookups |
| `username` | `CharField(150, unique)` | Unique username, indexed |
| `password` | `CharField(128)` | bcrypt hash of the password (never the raw password) |
| `is_active` | `BooleanField(default=True)` | Set to `False` to deactivate (soft-delete handles removal) |
| `is_staff` | `BooleanField(default=False)` | Grants access to admin/staff areas via `has_module_perms()` |
| `is_superuser` | `BooleanField(default=False)` | Bypasses all permission checks in `has_perm()` |
| `last_login` | `DatetimeField(nullable)` | Timestamp updated by `set_last_login()` |
| `email_verified_at` | `DatetimeField(nullable)` | Timestamp set by `mark_email_verified()` |



### Methods

**Auth contract implementations:**

```python
@property
def is_authenticated(self) -> bool:
    return self.is_active         # inactive users are treated as unauthenticated

@property
def display_name(self) -> str:
    return self.username

@property
def identity(self) -> str:
    return str(self.id)           # always a string — middleware uses strings

def has_perm(self, perm: str) -> bool:
    if self.is_superuser:
        return True               # superusers pass everything
    return perm in getattr(self, "_permissions", [])

@classmethod
async def load_user(cls, identity: str):
    return await User.objects.get_by_id(int(identity))
```

**Password management:**

```python
def set_password(self, raw_password: str) -> None:
    self.password = make_password(raw_password)  # bcrypt

def check_password(self, raw_password: str) -> bool:
    return check_password(raw_password, self.password)  # constant-time compare

def set_unusable_password(self) -> None:
    self.password = UNUSABLE_PASSWORD_PREFIX     # "!" prefix — no password matches

def has_usable_password(self) -> bool:
    return is_password_usable(self.password)
```

**Utility methods:**

```python
async def set_last_login(self) -> None:
    self.last_login = datetime.now(timezone.utc)
    await self.save(update_fields=["last_login"])

async def mark_email_verified(self) -> None:
    self.email_verified_at = datetime.now(timezone.utc)
    await self.save(update_fields=["email_verified_at"])
```

### Extending User

The `User` class is designed to be extended. Add custom fields, override methods, inject behavior:

```python
class User(Model, AbstractBaseUser):
    # ... standard fields ...

    # ── Custom fields ────────────────────────────────────────
    phone_number = fields.CharField(max_length=20, null=True)
    avatar_url = fields.CharField(max_length=500, null=True)
    timezone = fields.CharField(max_length=50, default="UTC")

    # ── Custom methods ───────────────────────────────────────
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    async def deactivate(self) -> None:
        self.is_active = False
        await self.save(update_fields=["is_active"])

    async def reactivate(self) -> None:
        self.is_active = True
        await self.save(update_fields=["is_active"])

    # ── Override defaults ────────────────────────────────────
    def has_perm(self, perm: str) -> bool:
        if not self.is_active:
            return False                    # deactivated users have no permissions
        if self.is_superuser:
            return True
        return perm in (self.permissions or [])  # custom permissions field
```

Add mixins from auth sub-modules for more capability:

```python
from sillo.auth.jwt_auth.mixins import JWTUserMixin
from sillo.auth.session_auth.mixins import SessionUserMixin
from sillo.auth.apikey.mixins import ApiKeyUserMixin

class User(
    Model, AbstractBaseUser,
    JWTUserMixin,      # issue_token_pair, refresh_token_pair, revoke_all_tokens
    SessionUserMixin,  # create_session, logout_everywhere, get_active_sessions
    ApiKeyUserMixin,   # create_api_key, revoke_all_api_keys
):
    ...
```

### Manager Wiring

`User.objects` must be explicitly wired to `UserManager`:

```python
from sillo.users.managers import UserManager

User.objects = UserManager()
```

Without this line, `User.objects` is Tortoise's default manager — `create_user`, `create_superuser`, `get_by_email`, `get_by_natural_key` won't exist.

### Record ORM Integration

`User` is a Tortoise model. After defining it, register with the database:

```python
from sillo.record import setup_record, DatabaseConfig

app = silloApp()

db = setup_record(
    app,
    DatabaseConfig.sqlite("myapp.db"),   # or .postgres(), .mysql(), .from_env()
    model_modules=["myapp.models"],      # dotted path to the module with your User class
)
```

`setup_record` handles the full lifecycle:
- `Tortoise.init()` — connects to the database
- `Tortoise.generate_schemas(safe=True)` — creates tables if they don't exist
- `Tortoise.close_connections()` — clean disconnect on shutdown

The table name is controlled by `Meta.table` — `"users"` in the built-in model. Change it if you need a different name:

```python
class Meta:
    table = "accounts"  # your custom table name
```

### Full Definition

Here is the complete `User` class as you would define it in your project:

```python
from datetime import datetime, timezone
from tortoise import fields
from sillo.record import Model
from sillo.users.base import AbstractBaseUser
from sillo.users.managers import UserManager
from sillo.users.password import make_password, check_password

class User(Model, AbstractBaseUser):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True, index=True)
    username = fields.CharField(max_length=150, unique=True, index=True)
    password = fields.CharField(max_length=128)
    is_active = fields.BooleanField(default=True)
    is_staff = fields.BooleanField(default=False)
    is_superuser = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True, default=None)

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

# Critical — wire the manager
User.objects = UserManager()
```

---

## BaseUser

`BaseUser` is `AbstractBaseUser` plus password management. Use it when you need a user class that isn't backed by the Record User model but still needs `set_password` / `check_password`.

```python
from sillo.users import BaseUser

class BaseUser(AbstractBaseUser):
    password: str

    def set_password(self, raw_password: str) -> None:
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    def set_unusable_password(self) -> None:
        self.password = UNUSABLE_PASSWORD_PREFIX

    def has_usable_password(self) -> bool:
        return is_password_usable(self.password)
```

**Usage:**

```python
class OfflineUser(BaseUser):
    def __init__(self, email: str):
        self.email = email
        self.password = ""  # will be set by set_password()

    @property
    def identity(self) -> str:
        return self.email

    @property
    def display_name(self) -> str:
        return self.email.split("@")[0]

    @classmethod
    async def load_user(cls, identity: str):
        data = await local_db.get(identity)
        if data:
            user = cls(data["email"])
            user.password = data["password_hash"]
            return user
        return None

user = OfflineUser("a@b.com")
user.set_password("secret")
assert user.check_password("secret")
```

---

## SimpleUser & AnonymousUser

**SimpleUser** is for testing and quick prototypes. No database needed.

```python
from sillo.users import SimpleUser

user = SimpleUser("alice", permissions=["read", "write"])

user.is_authenticated   # True
user.display_name       # "alice"
user.identity           # "alice"
user.has_permission("read")  # True
user.has_permission("admin") # False
user.permissions        # ["read", "write"]

# load_user returns SimpleUser(identity, [identity])
loaded = await SimpleUser.load_user("bob")
loaded.username    # "bob"
loaded.permissions # ["bob"]
```

**AnonymousUser** is the sentinel attached when no backend authenticates the request:

```python
from sillo.users import AnonymousUser

anon = AnonymousUser()
anon.is_authenticated  # False
anon.is_anonymous      # True
anon.identity          # ""
anon.has_perm("x")     # False
```

---

## UserManager

`UserManager` provides creation methods and database lookups.

```python
from sillo.users import UserManager

User.objects = UserManager()   # wire to your User class
```

### create_user

```python
user = await User.objects.create_user(
    email="alice@example.com",
    username="alice",
    password="secure-password",  # optional — if omitted, unusable password is set
    # any extra kwargs are passed to User(...)
)

# Internally:
# 1. user = User(email=..., username=..., **extra)
# 2. user.set_password(raw_password) — bcrypt hash
# 3. await user.save() — persists to database
# 4. returns user
```

Without a password:

```python
user = await User.objects.create_user(
    email="oauth@example.com",
    username="oauth_user",
)
# user.password starts with "!" — no password will ever match
user.has_usable_password()  # False
user.check_password("x")    # False
```

### create_superuser

```python
admin = await User.objects.create_superuser(
    email="admin@example.com",
    username="admin",
    password="VeryStr0ng!",
)

admin.is_superuser  # True
admin.is_staff      # True
admin.is_active     # True
admin.has_perm("anything")  # True — superusers bypass permission checks
```

`create_superuser` runs `validate_password()` first. A weak password raises `ValueError`.

### Lookups

```python
user = await User.objects.get_by_id(42)
user = await User.objects.get_by_email("alice@example.com")
user = await User.objects.get_by_username("alice")

# Tries email first, then username
user = await User.objects.get_by_natural_key("alice@example.com")  # email match
user = await User.objects.get_by_natural_key("alice")              # username match
```

All lookups filter `is_active=True`. Inactive users are not returned.

---

## Password Utilities

### make_password

Hashes a raw password with bcrypt. Uses cost factor 12 by default. The resulting string is 60 characters and contains the salt.

```python
from sillo.users import make_password

hashed = make_password("my-password")
# "$2b$12$LJ3m4ys3GluO2v..."

# With custom salt (rarely needed)
import bcrypt
hashed = make_password("my-password", salt=bcrypt.gensalt(rounds=14))
```

### check_password

Verifies a raw password against a bcrypt hash. Uses constant-time comparison (resistant to timing attacks).

```python
from sillo.users import check_password

check_password("correct", hashed)   # True
check_password("wrong", hashed)     # False
check_password("", hashed)          # False
check_password(None, hashed)        # False
```

### validate_password

Returns a list of error strings. Empty list means the password passes all checks.

```python
from sillo.users import validate_password

validate_password("weak")
# ["Password must be at least 8 characters.",
#  "Password must contain at least one uppercase letter.",
#  "Password must contain at least one digit.",
#  "Password must contain at least one special character."]

validate_password("StrongP@ss1")       # []
validate_password("abc", min_length=12) # ["Password must be at least 12 characters.", ...]
```

Rules: min 8 chars (configurable), 1 uppercase, 1 lowercase, 1 digit, 1 special char.

### password_strength

Quantitative score with feedback.

```python
from sillo.users.password import password_strength

password_strength("StrongP@ss1")
# {"score": 5, "strength": "strong", "feedback": []}

password_strength("password")
# {"score": 2, "strength": "weak", "feedback": ["Low character diversity"]}
```

Scoring: length points, character class points, diversity check. Thresholds: 5+ strong, 3-4 medium, 0-2 weak.

### is_password_usable

Returns `False` if the hash string starts with `!` (the unusable marker).

```python
from sillo.users import is_password_usable

is_password_usable("$2b$12$...")   # True
is_password_usable("!abc123...")   # False
```

### needs_rehash

Returns `True` if the hash was generated with fewer bcrypt rounds than specified. Use on login to progressively upgrade hashes.

```python
from sillo.users import needs_rehash

if needs_rehash(user.password, rounds=14):
    user.set_password(raw_password)
    await user.save()
```
