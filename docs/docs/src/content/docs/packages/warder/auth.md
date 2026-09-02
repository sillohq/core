---
title: Signing in
description: Three arrangements, one backend interface, and the command that makes the first account.
---

![The sign-in screen](./images/login.png)

`Admin()` with no `auth=` already has a working sign-in: the bundled
`AdminUser`, a session backend, `Gate.staff()`, and session middleware installed
on mount if the application has none — a sign-in page without a session is a
form that forgets you.

## Three arrangements

**Standalone.** The bundled `AdminUser` and an admin-only sign-in page. Right for
an internal tool with no public user model.

```python
Admin(title="Ops")
```

**Shared model, admin login.** Your accounts, your password hashes, a separate
sign-in page. This is where `Gate.staff()` earns its keep.

```python
Admin(auth=Auth(users=User, gate=Gate.staff()))
```

**Shared session.** Signed into the product is signed into the admin, subject to
the gate. A backend is three methods.

```python
Admin(auth=Auth(users=User, backend=YourBackend()))
```

The third is what most applications want.

## The first account

```bash
warder create-admin app:admin     # prompts for email and password
warder users app:admin            # who can sign in, and when they last did
sillo user:admin you@example.com  # the framework's own, same table
```

`create-admin` writes wherever the admin authenticates from. It writes the column
the **sign-in form** asks for, sets only the flags the model actually has, reads
the password twice without echo, and hashes through `sillo.hashing`. It prompts
only at a terminal, so a script gets an error naming the flag rather than a hang.

It refuses up front, naming what to do, when the model is unregistered, its table
has not been migrated in, it cannot hash a password, or it needs a column Warder
cannot know about — `--set column=value` fills in the last of those.

## The bundled models are not registered for you

```python
setup_record(app, config, model_modules=["myapp.models", "warder.models"])
```

Model discovery scans a module's namespace, so a package that imported its own
models would put `warder_users` and `warder_activity` in the database of every
project that installed it — including the majority that pass their own user model
and would never write a row to either. You name it to opt in.

## A backend is three methods

```python
class YourBackend:
    async def current(self, ctx):
        """The signed-in account, or None."""

    async def login(self, ctx, identity, secret) -> bool:
        """Sign somebody in."""

    async def logout(self, ctx) -> None:
        """Sign the current person out."""
```

Implement them against JWT, LDAP, your own session table or anything else, and
pass it as `Auth(backend=…)`.

## Session policy

```python
Auth(session=Session(idle="30m", absolute="12h", concurrent=1, secure=True))
```

Two lifetimes, because they answer different questions. *idle* is "you walked
away"; *absolute* is "this session is old regardless of how busy you have been",
and only the second bounds a stolen cookie.

The policy drives the cookie itself — name, `Secure`, `SameSite`, lifetime. On
plain HTTP over localhost you need `secure=False`, because a `Secure` cookie is
never sent back over `http` and you would be signed out on the redirect after
login.

The session carries **an id and two timestamps, never a user**. Every request
reloads the account, so deactivating somebody takes effect on their next click
rather than their next sign-in — which is the only version of "revoke" worth the
word.

## Throttling

```python
Auth(login=Login(throttle="5/15m", remember=True, field="email"))
```

Counted per identity **and** per address. Per identity alone lets one machine
work through a list of usernames; per address alone lets a botnet work through
one password. Both, or neither is worth having.

A wrong password and an unknown account get the same message, so the form cannot
be used to find out which accounts exist. Only being locked out is distinguished,
because otherwise you stop trying the password that works.

The throttle lives in process memory, which is the honest scope: it survives a
page reload and not a restart, and two workers count separately. That is enough
to stop a script and not enough to stop a botnet — for which the answer is a
shared store, and `Throttle` is the seam to replace.

## The session key

```python
Admin(secret="…")          # or WARDER_SECRET_KEY, or SILLO_SECRET_KEY
```

Without one a random key is generated and said so out loud: it works, and every
restart signs everybody out — fine on a laptop, and not a thing to discover in
production from a support ticket.
