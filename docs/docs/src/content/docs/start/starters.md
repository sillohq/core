---
title: The Official Starters
description: "What sillohq/starter and sillohq/starter-inertia contain — the layout, the dependencies each pulls in, and how to choose between them."
head:
  - tag: meta
    attrs:
      property: og:title
      content: The Official Sillo Starters
  - tag: meta
    attrs:
      property: og:description
      content: sillohq/starter and sillohq/starter-inertia, and how to choose between them.
---

Two starters are published. Both are real applications with their own CI.

| | |
| --- | --- |
| [`sillohq/starter`](https://github.com/sillohq/starter) | Server-rendered pages and a JSON API. The default. |
| [`sillohq/starter-inertia`](https://github.com/sillohq/starter-inertia) | The same application with a React or Vue frontend over [Inertia.js](/guides/inertia/). |

```bash
sillo-start create-app myapp                              # the default
sillo-start create-app sillohq/starter-inertia myapp      # Inertia
```

## Choosing

Take the **default** when your pages are pages: forms that post and redirect,
server-rendered HTML, an admin panel, a JSON API for whatever else needs one.
It has no build step and no `node_modules`.

Take **Inertia** when you want React or Vue components with the routing,
validation and auth still on the Python side. You get a frontend without
writing an API for your own frontend to consume.

You are not locked in either way — Inertia is a dependency and a mount, and can
be added to a project that started without it.

## What `sillohq/starter` ships

```
app/
  bootstrap.py       assembling the application
  config.py          typed settings, read from .env
  main.py            the ASGI entrypoint — `app.main:app`
  admin.py           what the admin panel exposes
  templating.py      template engine setup
  jobs/              queued job classes
  tasks/             scheduled tasks
database/
  config.py          connection settings
  models/            your models; `user.py` to begin with
  migrations/        `0001_initial.py`, committed
routes/
  api.py             the JSON API
  auth.py            sign in, sign out, register
  web.py             server-rendered pages
templates/           HTML
static/              CSS
tests/               a working suite, with fixtures
storage/             SQLite lives here; gitignored
scripts/smoke.py     boots the app and calls every route
```

Plus `.env.example`, `pyproject.toml`, `.github/workflows/ci.yml`, a `Makefile`
and a `README.md`.

### What is already wired

- **Session authentication** against a real user model, not a stub.
- **The admin panel**, at `/admin/`.
- **Migrations**, with the initial one committed — so `sillo db:migrate` on a
  fresh clone produces a working database rather than an empty one.
- **A queue and a scheduler**, with the directories to put work in.
- **Tests**, including fixtures for an authenticated client.
- **CI** that boots the application and calls every route, on three Python
  versions.

That last one is why this is a repository rather than a template. See
[why a starter](/start/#a-starter-repository-not-a-generator).

### Dependencies

```toml
sillo-framework[hashing-bcrypt,record,templating]
aiosqlite
email-validator
```

SQLite by default, so there is nothing to run before the first request. Swap
the driver for `asyncpg` or `asyncmy` and change `DATABASE_URL` when you want a
server — see [Database setup](/orm/setup/).

## What `sillohq/starter-inertia` ships

The same Python application, plus:

```
js/
  main.tsx           the client entrypoint
  app.css            styles
  types.ts, ui.ts    shared frontend types and helpers
views/
  Layout.tsx         the shell every page renders into
  pages/             one component per page
root.html            the single HTML document Inertia substitutes into
app/inertia.py       the adapter's configuration
vite.config.ts       the frontend build
package.json
```

And it drops Jinja: the only HTML it serves is `root.html`, which the Inertia
adapter reads and substitutes into directly. Every other page is a component.
Installing a template engine to render one static file would be a dependency
never called.

### Dependencies

```toml
sillo-framework[cache,hashing-bcrypt,record]
sillo-inertia
aiosqlite
email-validator
```

Note the absence of `templating`. See [Inertia](/guides/inertia/) for the
frontend side.

## The Makefile

Both starters ship one, and you can ignore it. Every target is a plain `sillo`,
`uvicorn` or `pytest` invocation — it exists so `make` on its own lists what a
project can do, not because anything depends on it.

The documentation uses the underlying commands throughout, so nothing here
requires `make` to be installed.

## Using a different one

Any public GitHub repository works:

```bash
sillo-start create-app acme/our-template myapp
```

See [Custom starters](/start/custom-starters/) for what makes a repository work
well as one.
