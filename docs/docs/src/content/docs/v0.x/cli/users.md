---
title: User Commands
description: "The user:* command family: creating accounts and administrators, listing, inspecting, changing passwords, and activating or revoking access from the terminal."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo User Commands
  - tag: meta
    attrs:
      property: og:description
      content: user:create, user:admin, user:list, user:show, user:password, user:active and user:staff.
---

The `user:*` commands appear alongside the database commands: both need the
manager `setup_record` put on `app.state`. They act on the model your
application authenticates against, or on
[sillo's own `User`](/v0.x/guides/users/) when the project has not defined one.

## The one you are looking for

```bash
sillo user:admin you@example.com
```

Creates an administrator and prompts for the password. This is the first thing
you run against a new project so you can sign in at `/admin/`.

## How passwords are read

No command takes a password as an argument. A password in `argv` is a password
in your shell history, in the process list, and in any log that records command
lines.

Instead, in order:

1. **`SILLO_PASSWORD`**, if it is set.
2. **A hidden prompt**, asked twice and required to match.

With neither (a pipe, a CI job, a non-interactive shell) the command fails and
names the variable rather than prompting into a pipe and hanging:

```
No terminal to read a password from. Set SILLO_PASSWORD instead.
```

Which is how you seed an account non-interactively:

```bash
SILLO_PASSWORD="$SEED_PASSWORD" sillo user:admin ops@example.com
```

## `user:create`

```bash
sillo user:create someone@example.com someone
sillo user:create someone@example.com someone --admin
```

| Parameter | Kind | Meaning |
| --- | --- | --- |
| `email` | argument | Email address. Must not already be registered |
| `username` | argument | Username. Must not already be taken |
| `--admin` | flag | Give the account admin access |

Rejections come from the framework's own rules, and it names which one failed,
which address is taken, or which part of the password policy was not met.

## `user:admin`

```bash
sillo user:admin you@example.com
sillo user:admin you@example.com admin
```

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `email` | argument | required | Email address |
| `username` | argument | the mailbox | Username |

The same as `user:create --admin`, kept separate because it is what people look
for by name when setting a project up. Omit the username and the mailbox part
of the address is used. `you@example.com` becomes `you`.

On success it tells you where to go:

```
✓ Created you@example.com.
  Sign in at /admin/
```

## `user:list`

```bash
sillo user:list
sillo user:list --staff
sillo user:list --limit 10 --offset 20
```

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `-l`, `--limit` | option | `50` | Maximum rows |
| `--offset` | option | `0` | Rows to skip |
| `--staff` | flag | off | Only accounts with admin access |

Newest first.

```
   id  email                username    admin   active
  ──────────────────────────────────────────────────────
    3  ops@example.com      ops          yes     yes
    2  someone@example.com  someone              yes
    1  you@example.com      you          yes     yes

  3 shown
```

## `user:show`

```bash
sillo user:show you@example.com
sillo user:show you
```

Takes either an email address or a username.

```
  id        1
  email     you@example.com
  username  you
  admin     yes
  active    yes
```

## `user:password`

```bash
sillo user:password you@example.com
```

Prompts for the new password, twice. Same identifier rules as `user:show`, and
the same `SILLO_PASSWORD` fallback.

## `user:active`

```bash
sillo user:active someone@example.com          # activate
sillo user:active someone@example.com --off    # deactivate
```

A deactivated account keeps its rows and its history. It simply cannot sign in.
That is almost always what "delete this user" should actually mean: the posts
they wrote, the orders they placed and the audit trail they appear in all still
have to resolve to something.

## `user:staff`

```bash
sillo user:staff someone@example.com            # grant
sillo user:staff someone@example.com --revoke   # revoke
```

Grants or revokes admin access, the `is_staff` flag the [admin
panel](/v0.x/orm/admin/) checks.

## Which model these act on

`sillo` binds these commands to the application's `auth_user_model`. When a
project has not set one, `sillo.users.commands` falls back to the built-in
`User`, so the commands work on a fresh project rather than failing on a model
that does not exist yet.

If you are building a console of your own, pass the model explicitly:

```python
from sillo.users.console import user_commands

console.add_many(user_commands(model=Account, context=database))
```

`context` is opened around every command. The ORM has to be initialised before
these touch a model, and that is the application's job, not the command's. See
[Building a console](/v0.x/cli/standalone-consoles/).

## See also

- [Users and user models](/v0.x/guides/users/)
- [Permissions](/v0.x/guides/permissions/): groups and per-object rules, which are
  managed in the admin rather than here.
