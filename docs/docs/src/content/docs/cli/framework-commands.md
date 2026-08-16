---
title: Framework Commands
description: "sillo version, sillo serve and sillo routes, the three commands that need no project, with every argument and what each one is for."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Framework Commands
  - tag: meta
    attrs:
      property: og:description
      content: version, serve and routes, the commands available with or without a project.
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

Runs the application on the **Sillo development server**.

:::caution[Do not deploy with this]
`sillo serve` is a development server. It is fine to leave running all day
while you work, and it is not what should be answering requests from the
internet. See [Deployment](/guides/start/deployment/) for what to run instead,
and [Why not in production](#why-not-in-production) below for why.
:::

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `app` | argument | discovered | Import string, e.g. `app.main:app` |
| `--host` | option | `127.0.0.1` | Interface to bind |
| `-p`, `--port` | option | `8000` | Port to bind. `0` asks the OS for a free one |
| `-w`, `--workers` | option | `1` | Worker processes |
| `--log-level` | option | `info` | `debug`, `info`, `warning` or `error` |
| `-r`, `--reload` | flag | off | Restart when the source changes |
| `--no-access-log` | flag | off | Stop logging a line per request |
| `--no-inspect` | flag | off | Do not mount the request inspector |
| `--plain` | flag | off | Use uvicorn's own output instead of Sillo's |

The import string is resolved by uvicorn, not by `sillo`, which is what makes
`--reload` work. Reloading re-imports the application in a fresh process, so
the string is needed rather than the object — and `--workers` needs it for the
same reason.

### What you see

```
  ● sillo 0.1.0b3

    app      app.main:app
    url      http://127.0.0.1:8000
    routes   23
    mode     reload
    pid      48210

    ready in 41ms  ·  press ctrl-c to stop

  14:14:50  GET     200  /                                      527us
  14:14:50  GET     200  /users/42                              406us
  14:14:50  GET     200  /reports/monthly                     151.2ms
  14:14:51  GET     404  /nope                                  431us
```

The route count is the line worth knowing about. No other server prints it,
and a count that reads `0` is usually the entire explanation for the 404 you
were about to go and investigate.

Every access line carries a duration. uvicorn's own access log does not — the
protocol logs at the moment the response starts and never measures how long
the handler took — so Sillo times each request itself, outside everything the
application installs. What it reports is what the client waited for. Durations
past 100ms are tinted, and past a second more strongly, which is enough to
find the slow endpoint in a scrolling log without reading the numbers.

Colour and glyphs degrade on their own. Piped to a file or run in CI, the
output has no escape sequences; on a terminal that cannot take Unicode the
glyphs fall back to ASCII of the same width, so the columns still line up.

### Clicking a request

Every access line is a link. In a terminal that supports OSC 8 hyperlinks —
iTerm2, WezTerm, Kitty, Ghostty, Windows Terminal, VS Code's terminal, GNOME
Terminal and anything else built on VTE — clicking the path opens that request
in your browser:

- how long it took, and when it started
- every request header, and every response header
- query parameters, broken out rather than left in the URL
- the client address, protocol and response size
- the exception, if the handler raised one

The index at `http://127.0.0.1:8000/__sillo/requests` lists the most recent 200,
newest first. There is a `/__sillo/requests/json` endpoint alongside it if you
want to script against the same data.

Terminals that do not support hyperlinks are not broken by this: the line
renders as plain text and the inspector is still reachable by typing the URL.
`SILLO_HYPERLINKS=0` forces them off, `=1` forces them on for a terminal this
does not recognise.

:::caution[It renders request headers, so it is loopback-only]
The inspector shows the headers each request arrived with, which includes
session cookies and `Authorization` tokens. Two things follow.

**It will not mount on an address other machines can reach.** Bound to
`0.0.0.0` or a LAN address it refuses, and the banner says why:

```
    inspect   not mounted: bound to 0.0.0.0, which other machines can reach,
              and it renders request headers
```

**Credentials are redacted even on loopback.** A sensitive header is shown as a
short prefix and a length — `Bearer s… (38 chars, redacted)` — which is enough
to tell which token a request carried without reproducing it.

Records live in a bounded in-memory ring that dies with the process. Nothing is
written to disk. `--no-inspect` turns the whole thing off.
:::

### Underneath

The server is uvicorn. Sillo replaces everything above the HTTP protocol —
the logging configuration, the lifecycle announcements, the access log, the
startup output — and leaves the protocol implementation alone, because
replacing a battle-tested HTTP stack to change some strings would be a bad
trade.

If you need to see what uvicorn itself is saying, `--plain` turns all of it
off and gives you uvicorn's own output. That is the flag to reach for when you
suspect the server rather than the application.

uvicorn is not a dependency of the framework. If it is not installed the
command says so and tells you what to install rather than raising an
`ImportError`.

You can call the same server directly:

```python
from sillo.server import run

run("app.main:app", port=8080, reload=True)
```

### Why not in production

`sillo serve` is a thin, opinionated wrapper for one machine and one developer.
What makes it good at that is what makes it wrong for a deployment:

- **It is a single process by default.** One `--workers 1` uvicorn is one
  Python process on one core. Production wants a process manager that restarts
  a worker that dies, and enough of them to use the machine.
- **`--reload` watches the filesystem.** It restarts the process on any source
  change, which under a deploy that rsyncs files is a server that restarts
  mid-request.
- **The access log is per-request and human-shaped.** It writes a formatted,
  coloured line for every request, aimed at a person watching a terminal. A
  production log wants to be structured and consumed by something else.
- **There is no supervision, no TLS termination, no static file serving, and
  no rate limiting.** Those belong to a reverse proxy and an init system, and
  Sillo does not pretend to provide them.

None of that is a criticism of uvicorn, which is a production-grade server and
is exactly what you should run — just under a process manager, behind a proxy,
with production settings rather than these. [Deployment](/guides/start/deployment/)
covers that.

### Why this one is synchronous

Every other command in `sillo` is an `async def handle`. `serve` is a plain
`def`, because uvicorn owns the event loop and starting it from inside one
would nest two. The console notices the difference and does not create a loop
for it. See [Building a console](/cli/standalone-consoles/#loops).

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
