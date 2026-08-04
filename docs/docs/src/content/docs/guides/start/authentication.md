---
title: Users & Authentication
description: One user model for the application and the admin, session auth over JSON, the password policy, and how to switch to JWT.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Users & Authentication in a Sillo Project
  - tag: meta
    attrs:
      property: og:description
      content: One user model for the application and the admin, session auth over JSON, and how to switch to JWT.
---

#  Users & Authentication

A new project has **one user model**. Everyone is a row in `users` — the
person who signs up through the API and the person who signs in to the
admin. What separates them is `is_staff`, not a second table.

##  The model

```python
# database/models/user.py
from sillo.record.fields import PasswordField
from sillo.users import UserBaseModel, UserManager
from tortoise import fields


class User(UserBaseModel):
    """A person who can sign in to Myapp, including to the admin."""

    objects = UserManager()

    password = PasswordField()

    full_name = fields.CharField(max_length=150, null=True)

    class Meta:
        table = "users"

    def __str__(self) -> str:
        return self.email


User.objects.contribute_to_class(User, "objects")
```

Four things in that file are load-bearing.

###  `UserBaseModel` supplies the contract

Email, username, hashed password, the `is_active`/`is_staff`/`is_superuser`
flags, `last_login`, `email_verified_at`, and the behaviour authentication
depends on: `set_password`, `check_password`, `verify_credentials`,
`has_perm`, `load_user`.

Subclassing it — rather than using `sillo.users.User` directly — gives you
a model you can add fields to.

###  `password = PasswordField()` is declared, not inherited

`UserBaseModel` types that column as a plain `CharField`, which stores
exactly what it is handed. So this:

```python
user.password = "hunter2"
await user.save()
```

writes the **plaintext**, silently. `PasswordField` hashes on the way to
the database, and it is what the admin's own user model uses — declaring
it here is what makes your model the same kind of thing.

Going through `set_password()` or `objects.create_user()` was always safe.
Direct assignment was not, and direct assignment is what someone reaches
for at 2am.

###  The manager is bound explicitly

```python
User.objects.contribute_to_class(User, "objects")
```

Tortoise does not call Django's `contribute_to_class` hook, so without
that line the manager has no model and falls back to sillo's built-in
`User` — which the project does not register, producing a confusing
`default_connection cannot be None` at the first query.

###  Some names are properties, not fields

`display_name`, `identity` and `is_authenticated` are read-only properties
on the base class. Declaring a field with one of those names shadows the
property and fails on assignment.

##  Creating accounts

```bash
uv run python console.py user create ada@example.com ada    # an ordinary user
uv run python console.py user admin  ada@example.com ada    # …who can reach /admin/
```

In code:

```python
from sillo.users.commands import create_user, create_admin
from database.models.user import User

user = await create_user("ada@example.com", "ada", "Hunter2!pass", model=User)
boss = await create_admin("boss@example.com", "boss", "Hunter2!pass", model=User)
```

or through the manager, when you want the model's own API:

```python
user = await User.objects.create_user(
    email="ada@example.com", username="ada", password="Hunter2!pass"
)
```

###  The password policy

At least 8 characters, one uppercase letter, one digit, one special
character. Enforced by the framework, and it names what failed:

```text
Password must be at least 8 characters. Password must contain at least one
uppercase letter. Password must contain at least one digit. Password must
contain at least one special character.
```

One place decides what a valid password is, so the API, the console and
the admin cannot disagree about it.

##  How sign-in works

Sessions, not tokens. A cookie holds the session id; the user is loaded on
each request by `AuthenticationMiddleware`.

```python
from sillo.auth.session_auth import login, logout
from database.models.user import User

user = await User.verify_credentials(identifier, password)
if user:
    login(request, user)
```

`verify_credentials` does the whole job: looks the user up **by email or
username**, rejects inactive accounts, verifies the hash, and stamps
`last_login`. Handlers stay about HTTP and never touch a password hash.

The starter's `/api/auth/login` is exactly that:

```python
@router.post("/login", request_model=LoginRequest, summary="Sign in")
async def login_route(request, response, payload):
    user = await User.verify_credentials(payload.identifier, payload.password)
    if user is None:
        # One message for every failure mode, so the response cannot be used
        # to discover which accounts exist.
        return response.json({"detail": "Invalid credentials."}, status_code=401)

    start_session(request, user)
    return response.json({"user": _serialize(user)})
```

That single error message is deliberate. Distinguishing "no such account"
from "wrong password" turns the login endpoint into an account-existence
oracle.

###  Registration

```python
if await User.objects.get_by_email(payload.email) is not None:
    return response.json({"detail": "That email is already registered."}, status_code=409)
if await User.objects.get_by_username(payload.username) is not None:
    return response.json({"detail": "That username is taken."}, status_code=409)

user = await User.objects.create_user(...)
```

The uniqueness check is explicit rather than left to the database
constraint, because a constraint violation surfaces as a 500 and this
should be a 409.

##  Reading the current user

```python
user = request.user
```

<aside>

**`request.user` raises when no authentication middleware is installed.**
It does not return `None`. Guard it if the route might run without one:

```python
user = getattr(request, "user", None)
if user is None or not user.is_authenticated:
    return response.json({"detail": "Not authenticated."}, status_code=401)
```

</aside>

`is_authenticated` is `True` for an active signed-in user. A deactivated
account that still holds a session reads as not authenticated, so
disabling someone takes effect on their next request rather than at their
next sign-in.

##  Switching to JWT

The wiring is written and commented out in `app/bootstrap.py`. Uncomment
the import and swap the backend:

```python
from sillo.auth.jwt_auth import JWTAuthBackend

backend = JWTAuthBackend(secret_key=config.jwt_secret, identifier="sub")
```

Add `JWT_SECRET` to `.env` and `jwt_secret` to `app/config.py`, then issue
tokens:

```python
from sillo.auth.jwt_auth import TokenForUser

pair = TokenForUser(user, secret=config.jwt_secret).token_pair()
```

<aside>

**`identifier="sub"` is required, not cosmetic.** The backend defaults to
reading an `id` claim, but tokens carry the user id in `sub`. With the
default, every authenticated request silently fails to load a user — no
error, no log line, just an anonymous request where you expected a
signed-in one.

</aside>

**Keep the session middleware either way.** The admin authenticates
through the session regardless of what the rest of the application uses.
Removing it takes the admin down with it.

##  Who may reach the admin

An account needs `is_staff` — which `user admin` sets.

That flag is load-bearing rather than decorative. With one shared user
model, **every registered account holds a session**, so if a session alone
were enough, the sign-up form would be the way into the admin:

```text
POST /api/auth/register  ->  201
POST /api/auth/login     ->  200
GET  /admin/             ->  200        # read and write on every model
```

The rule is: **active, and staff or superuser**. It is checked at sign-in
*and* on every request — the session carries only an identity and a
display name, so revoking `is_staff` has to take effect on the next
request rather than at the next sign-in.

```python
@staticmethod
def may_enter(user) -> bool:
    if not getattr(user, "is_active", True):
        return False
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
```

See [The Admin Panel](/guides/start/admin/).

##  Adding fields

Add them to `User` and migrate:

```python
class User(UserBaseModel):
    objects = UserManager()
    password = PasswordField()

    full_name = fields.CharField(max_length=150, null=True)
    timezone = fields.CharField(max_length=64, default="UTC")
    marketing_opt_in = fields.BooleanField(default=False)
```

```bash
make migration m="add user profile fields"
```

Because there is one user model, that field exists everywhere — the API,
the admin, your scripts — with no second model to mirror it into.

<aside>

**Do not add `sillo.users` to `MODEL_MODULES`.** Models are keyed by class
name, so the framework's built-in `User` would displace yours and your
extra columns would silently stop being created.

Nor `sillo.admin.default_user`, which would add a parallel `admin_users`
table.

</aside>

##  Managing accounts

```bash
uv run python console.py user list                 # everyone, newest first
uv run python console.py user list --staff         # administrators only
uv run python console.py user password ada         # reset a password
```

In code, `sillo.users.commands` has the rest:

```python
from sillo.users.commands import find_user, set_active, set_staff, set_password

user = await find_user("ada@example.com", model=User)   # email or username
await set_staff(user, True, model=User)
await set_active(user, False, model=User)
await set_password("ada", "N3w!password", model=User)
```

`find_user` finds **deactivated** accounts too — you frequently need to
act on an account precisely because it was disabled.

##  Things that will bite you

1. **`request.user` raises without auth middleware.** It does not return
   `None`.

2. **The admin's login form field is `email`.** It accepts an email or a
   username as the *value*, but the field is named `email`. Posting
   `username=` silently fails the form.

3. **`await request.form`, not `await request.form()`.** It is an async
   property. Calling it gives `'coroutine' object is not callable`.

4. **Redeclaring `display_name`, `identity` or `is_authenticated`** as
   fields shadows the base class's properties.

5. **`is_staff` defaults to `False`.** An account created with
   `create_user` cannot reach the admin, which is the intended default.

##  Related

- [The Admin Panel](/guides/start/admin/) — what `is_staff` gets you into
- [The Console](/guides/start/console/) — the `user` commands
- [Authentication](/guides/authentication/) — the framework-level reference
- [JWT Authentication](/guides/jwt-auth/) — tokens in depth
- [Protecting Routes](/guides/protecting-routes/) — guards and permissions
- [Hashing](/guides/hashing/) — the password hashing scheme
