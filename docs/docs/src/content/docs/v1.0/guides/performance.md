---
title: Performance
description: "Where the time goes in a Sillo request, which server and worker settings change throughput the most, what each middleware form costs, and how to measure your own app."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Performance
  - tag: meta
    attrs:
      property: og:description
      content: The server and worker settings that matter most, what a request costs inside Sillo, and how to measure your own app.
---

#  Performance

Most of the time in a request is **not** spent in Sillo. For a route that does
almost nothing, the framework itself costs roughly 40 µs. The server, the event
loop and the network cost several times that, and your handler and its database
calls cost more again. So the order to work in is:

1. [Run a production server](#the-server) and enough [workers](#workers).
2. Fix what your own handlers and queries spend ([measure them](#measuring-your-app)).
3. Only then look at what Sillo itself costs ([the per-request numbers](#what-sillo-itself-costs)).

:::note[Every number on this page is from one machine]
2019 MacBook Pro, Intel i9-9980HK, Python 3.12, with the load generator
([`oha`](https://github.com/hatoo/oha), 64 connections) **on the same
machine** as the server. Absolute figures will be different on yours, and on a
Linux server with the load generator elsewhere they will be higher. Read the
**ratios**, and re-run the commands below on your own hardware before
deciding anything.
:::

##  The server

The same Sillo app, the same three routes, one worker, different servers:

| Server | `plaintext` | `json` | `rows` (200 objects) |
| --- | ---: | ---: | ---: |
| `uvicorn` with `asyncio` and `h11` (plain `pip install uvicorn`) | 2,971 req/s | 2,837 req/s | 1,205 req/s |
| `uvicorn[standard]`: `uvloop` and `httptools` | 8,370 req/s | 6,753 req/s | 1,658 req/s |
| `granian`, a Rust server, ASGI mode | 12,667 req/s | 11,830 req/s | 1,748 req/s |

**Installing `uvloop` and `httptools` is the largest single change you can make,**
and it needs no code. `uvicorn` uses them automatically once they are
installed:

```bash
pip install "uvicorn[standard]"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

If you want to be certain which ones are in use, name them explicitly:
`uvicorn app.main:app --loop uvloop --http httptools`.

:::caution[`uvloop` does not support Windows]
On Windows, `uvicorn[standard]` installs without it and you get the plain
`asyncio` loop. Granian does run there.
:::

###  Granian

[Granian](https://github.com/emmett-framework/granian) is an HTTP server
written in Rust that serves any ASGI application, Sillo included:

```bash
pip install granian
granian --interface asgi --workers 4 app.main:app
```

It was the fastest option in the table above. Two things to know before you
switch:

- I ran **plain HTTP routes only** against it. Check your WebSocket routes and
  your `lifespan` start-up and shutdown hooks under it before relying on it;
  they are the parts of an ASGI server where implementations differ most.
- Its process, signal and logging options are its own. Your process manager
  and log collector will want a look.

On the `rows` column the three servers are within about 45 % of each other
because that route is dominated by turning 200 objects into JSON inside Sillo,
which no server can speed up. See [the JSON section](#returning-data) below.

##  Workers

One Python process runs one request's Python code at a time. More workers is
more requests at once, up to your core count:

| Server | Workers | `plaintext` | `json` | `rows` |
| --- | ---: | ---: | ---: | ---: |
| `uvicorn[standard]` | 1 | 8,370 req/s | 6,753 req/s | 1,658 req/s |
| `uvicorn[standard]` | 4 | 24,330 req/s | 21,595 req/s | 5,633 req/s |
| `granian` | 4 | 27,948 req/s | 26,890 req/s | 5,783 req/s |

Published framework benchmarks that show tens of thousands of requests per
second are almost always **several workers, a fast event loop and a fast HTTP
parser, on a server-class machine**. Compare like with like: the number you
want is "one worker, `uvloop`" for judging a framework, and "all cores" for
judging what your deployment can take.

A reasonable starting point is **one worker per CPU core**. Then check:

- **Memory.** Every worker holds its own copy of your app, its caches and its
  connection pool.
- **Database connections.** The pool size is *per worker*. Four workers with a
  pool of 20 is 80 connections, which can exceed what your database allows.
- **SQLite.** Several workers writing one file contend for locks. See
  [Workers and SQLite do not mix](/guides/start/deployment/#workers-and-sqlite-do-not-mix).
- **In-memory state.** An in-process cache, rate limiter or queue is not shared
  between workers. Use Redis for anything that must be.

##  What Sillo itself costs

Measured in-process (the ASGI app is called directly, with no server and no
network), one core:

| What the request does | Cost |
| --- | ---: |
| A route that returns a string | about 40 µs |
| Returns a small JSON object | about 60 µs |
| Reads an integer path parameter | about 65 µs |
| Reads three query parameters | about 100 µs |
| Validated JSON `POST` body (Pydantic) | about 85 µs |
| Three nested `Depend()` dependencies | about 8 µs more |
| Each raw ASGI middleware layer | under 1 µs |
| Each `(ctx, call_next)` function middleware layer | **about 0.5 ms** |
| Each route in front of the matching one | about 0.3 µs |

###  Middleware

A function middleware, and a `BaseMiddleware` subclass, can see and change the
response, so the rest of the request runs in its own task whose output is
handed back through an in-memory stream. That is a few event-loop round trips
per layer, and it is the one place where a Sillo feature costs more than the
handler it wraps. For most apps half a millisecond per layer is invisible
next to a database call. It is worth knowing about if you have several layers
on a route that answers in a millisecond.

Raw ASGI middleware does not do this: it wraps the call and adds almost
nothing. Where a layer only needs to read the request, or add a header as the
response starts, an ASGI middleware is the cheaper way to write it. Where it
needs to read or replace the response body, the function form is the right
one, and the cost is the price of that.

###  Routes

Routes are tried in order and the first match wins. Each route is checked with
a cheap prefix comparison before its pattern is run, so a route that cannot
match the path costs well under a microsecond. An application with 300 routes
spends roughly 100 µs on routing for a request that matches the last one,
and a request for an early route pays almost nothing. You do not need to
reorganise routes for speed.

###  Returning data

Return a plain `dict` or `list` and Sillo hands it straight to the C JSON
encoder, asking Python only about the values the standard library cannot
write itself: datetimes, UUIDs, Decimals, Pydantic models, enums. A payload of
200 rows took:

| Payload | Time |
| --- | ---: |
| 200 rows of strings and numbers | about 560 µs |
| 200 rows each with a UUID, a datetime and a Decimal | about 1.9 ms |

Returning the value and wrapping it in `json(...)` cost about the same. If a
payload is large and hot, the best saving is usually to
**send less**: paginate, drop fields the client does not read, and cache the
rendered response.

##  Measuring your app

Guessing is how people spend a week optimising a route that was never slow.

**1. Find the slow routes first.** Time requests per route in your own logs
(the `RequestId` middleware gives every request an ID to correlate them by)
so you know which routes are slow and which are merely frequent.

**2. Profile the framework and your handler together, without a server.** This
removes the network and the load generator from the picture:

```python
import asyncio, cProfile, pstats

from app.main import app  # your SilloApp


def scope(path: str) -> dict:
    return {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "path": path, "raw_path": path.encode(),
        "query_string": b"", "root_path": "", "scheme": "http",
        "headers": [(b"host", b"localhost")],
        "client": ("127.0.0.1", 5000), "server": ("127.0.0.1", 80),
    }


async def hit(path: str, times: int) -> None:
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        pass

    for _ in range(times):
        await app(scope(path), receive, send)


asyncio.run(hit("/orders", 200))                 # warm up
profile = cProfile.Profile()
profile.enable()
asyncio.run(hit("/orders", 2000))
profile.disable()
pstats.Stats(profile).sort_stats("tottime").print_stats(15)
```

`tottime` is the time spent in a function itself, which is the column that
points at the culprit. A handler that waits on a database will show up as
event-loop time, not as CPU: for that, log how long each query takes.

**3. Load-test over real HTTP last,** with the server and settings you will
deploy and the load generator on a different machine:

```bash
oha -z 20s -c 64 http://127.0.0.1:8000/orders
```

Run each configuration several times and compare medians. A difference of a
few percent between single runs is noise.

###  The repository's own benchmark

`benchmarks/` in the Sillo repository compares Sillo with FastAPI, Starlette,
Django and Flask over real HTTP, one worker each, on plain `uvicorn`. That is
deliberate: it isolates what each *framework* adds. It is therefore **not**
a prediction of what your deployment will do. A production setup that follows
this page will be several times faster than any figure it prints.
