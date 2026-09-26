---
title: Framework Commands
description: "sillo version and sillo routes, the two commands that need no project, with every argument and what each one is for."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Framework Commands
  - tag: meta
    attrs:
      property: og:description
      content: version and routes, the commands available with or without a project.
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
  sillo    0.2.0
  python   3.12.4
  path     /Users/you/project/.venv/lib/python3.12/site-packages/sillo

Optional features
  • record
  • cache
  • jwt
      mail — not installed
      graphql — not installed
      bcrypt — not installed
      argon2 — not installed
```

Each feature is tested by importing the module that proves it, not by reading
your `pyproject.toml`. `record` is present when `tortoise` imports, `cache`
when `redis` does, `mail` when `jinja2` does. So this reports the environment you
are actually running in, which is the question worth asking when something
that should work does not.

That makes it the first thing to run when a feature is missing. An extra
declared in `pyproject.toml` but never installed shows up here as absent.

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
prints the full path, listing only the top level would show `/api` and hide
every route under it, which is the opposite of what anyone runs this to find
out.

### The three method labels

- A **verb list**: the route's own `methods`, sorted.
- **`WEBSOCKET`**: no methods, and a WebSocket route type.
- **`MOUNT`**: no methods and not a WebSocket. A static file directory is the
  usual one. It is labelled honestly rather than guessed at.

Paths are printed as declared, converters included, so
`/api/posts/{id:int}` appears with its converter rather than as a resolved
example. That is the pattern you would grep the codebase for.

## `sillo dev`

```bash
sillo dev
sillo dev app.worker:app --port 9000
sillo dev --host 0.0.0.0 --reload-dir src
sillo dev --no-reload
```

Starts a local development server at `http://127.0.0.1:8000`. It finds the
application using the same rules as every other Sillo command, watches the
current project directory for Python changes, and reloads by default. The
server owns the terminal experience: startup links and each completed response
use Sillo's compact log format rather than Uvicorn's access logger.

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `app` | argument | discovered | Import string for the application |
| `--host` | option | `127.0.0.1` | Interface to bind |
| `--port` | option | `8000` | Port to bind |
| `--no-reload` | flag | reload on | Do not restart on source changes |
| `--reload-dir` | option | current directory | A directory to watch; may be repeated |

`sillo dev` is for local development. For a production deployment, run your
chosen ASGI server directly and choose its workers, proxy settings, and process
supervision deliberately.
