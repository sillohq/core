---
title: Framework Commands
description: "sillo version, sillo serve and sillo routes — the three commands that need no project, with every argument and what each one is for."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Framework Commands
  - tag: meta
    attrs:
      property: og:description
      content: version, serve and routes — the commands available with or without a project.
---

Three commands need no project. They are registered before discovery runs, so
they work in an empty directory and survive an application that fails to
import.

## `sillo version`

```bash
sillo version
```

Aliased to `sillo about`. Reports the installed version, the Python running it,
where the package lives, and which optional feature groups are installed:

```
  sillo    0.1.0b1
  python   3.12.4
  path     /Users/you/project/.venv/lib/python3.12/site-packages/sillo

Optional features
  • record
  • cache
  • jwt
      templating — not installed
      graphql — not installed
      bcrypt — not installed
      argon2 — not installed
```

Each feature is tested by importing the module that proves it, not by reading
your `pyproject.toml`. `record` is present when `tortoise` imports, `cache`
when `redis` does, `jwt` when `jwt` does. So this reports the environment you
are actually running in, which is the question worth asking when something
that should work does not.

That makes it the first thing to run when a feature is missing. An extra
declared in `pyproject.toml` but never installed shows up here as absent.

## `sillo serve`

```bash
sillo serve
sillo serve --reload
sillo serve --host 0.0.0.0 --port 8080
```

Runs the application with [uvicorn](https://www.uvicorn.org/).

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `app` | argument | discovered | Import string, e.g. `app.main:app` |
| `--host` | option | `127.0.0.1` | Interface to bind |
| `-p`, `--port` | option | `8000` | Port to bind |
| `-r`, `--reload` | flag | off | Restart when the source changes |

The import string is resolved by uvicorn, not by `sillo` — which is what makes
`--reload` work. Reloading requires re-importing the application in a fresh
process, so uvicorn needs the string rather than the object.

The address is printed before the server starts:

```
  app       app.main:app
  address   http://127.0.0.1:8000
```

uvicorn is not a dependency of the framework. If it is not installed the
command says so and tells you what to install rather than raising an
`ImportError`.

:::note[Development only]
`--reload` watches the filesystem and restarts the process. Do not use it in
production — run uvicorn or [granian](https://github.com/emmett-framework/granian)
directly with a process manager, as described in
[Deployment](/guides/start/deployment/).
:::

### Why this one is synchronous

Every other command in `sillo` is an `async def handle`. `serve` is a plain
`def`, because uvicorn owns the event loop and starting it from inside one
would nest two. The console notices the difference and does not create a loop
for it — see [Building a console](/cli/standalone-consoles/#loops).

## `sillo routes`

```bash
sillo routes
sillo routes --method post
sillo routes app.worker:app
```

Lists every route the application registers, sorted by path.

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `app` | argument | discovered | Import string |
| `-m`, `--method` | option | all | Only routes accepting this method |

```
  method     path                     name
  ─────────────────────────────────────────────────────
  GET        /                         home
  POST       /api/auth/login           login
  GET,POST   /api/posts                posts
  GET        /api/posts/{id:int}       post_detail
  WEBSOCKET  /ws/chat                  chat
  MOUNT      /static                   static

  6 routes
```

### Mounted routers are followed

A mounted router is one entry in `router.routes` holding routes of its own, and
its children carry paths relative to the mount. `routes` descends into them and
prints the full path — listing only the top level would show `/api` and hide
every route under it, which is the opposite of what anyone runs this to find
out.

### The three method labels

- A **verb list** — the route's own `methods`, sorted.
- **`WEBSOCKET`** — no methods, and a WebSocket route type.
- **`MOUNT`** — no methods and not a WebSocket. A static file directory is the
  usual one. It is labelled honestly rather than guessed at.

Paths are printed as declared, converters included, so
`/api/posts/{id:int}` appears with its converter rather than as a resolved
example. That is the pattern you would grep the codebase for.
