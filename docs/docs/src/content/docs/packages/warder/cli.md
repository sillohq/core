---
title: The CLI
description: Checking an admin without starting the application, and creating the account that opens it.
---

Five commands, all against a `module:attribute` target — the same spelling ASGI
servers use.

```bash
warder check       app.admin:admin
warder create-admin app.admin:admin
warder users       app.admin:admin
warder permissions app.admin:admin
warder routes      app.admin:admin
```

## check

```console
$ warder check app:admin
Ridgeway College: 13 resources, 2 pages, 53 permissions. Every reference resolves.
```

Resolves every declaration against its models, exactly as `mount()` does, and
exits non-zero on the first problem — so a misspelled column fails in CI rather
than in production. No server, no port, no database connection; only the models
importable.

```console
$ warder check app:admin
Resource(Post).list column 'titel' is not a field of Post.
  Did you mean 'title'?
  Declared at app.py:292
```

`--all` reports every problem rather than stopping at the first.

## create-admin

```console
$ warder create-admin app:admin
Email: head@ridgeway.edu
Username [head]:
Password:
Password again:
Created superuser head@ridgeway.edu (username head).
Sign in at /admin/login
```

Writes wherever the admin authenticates from: the column the sign-in form asks
for, only the flags the model actually has, hashed through `sillo.hashing`. It
prompts **only at a terminal** — in a script it says which flag to pass rather
than waiting forever for an answer nobody will give.

```bash
warder create-admin app:admin --email a@b.c --password "…" --staff
warder create-admin app:admin --email a@b.c --password "…" --set department=4
```

It refuses up front, naming what to do, when:

- the user model is not registered with the ORM — Tortoise's own answer,
  `default_connection … cannot be None`, says nothing about what to do;
- its table has not been migrated in;
- the model cannot hash a password, or has no column matching `Login(field=…)`;
- the model needs a column Warder cannot know about — `--set` fills those in.

It writes to the database the application already configured, rather than asking
for a second copy of the URL that is a second thing to get wrong.

## users

```console
$ warder users app:admin
EMAIL                    USERNAME    ROLE        ACTIVE  LAST SIGN-IN
head@ridgeway.edu        head        superuser   yes     2026-09-02 13:49
bursar@ridgeway.edu      bursar      staff       yes     never
```

## permissions

```console
$ warder permissions app:admin
attendance.add
attendance.change
…
```

What the site declares, derived from what is registered — so it is how you seed a
fixtures file or write a role against what exists rather than what you remember.

## routes

```console
$ warder routes app:admin
GET,HEAD,POST    /admin/login                 warder.login
GET,HEAD         /admin/student               warder.student.index
GET,HEAD         /admin/student/{id}/edit     warder.student.edit
…
```

Every URL mounting the admin added — nine per resource, plus pages, the asset
mount and login.
