---
title: Frequently Asked Questions
description: The questions people ask before adopting Sillo — versions, dependencies, what is optional, what moved in 1.0, and what the framework does not do.
head:
- tag: meta
  attrs:
    property: og:title
    content: "Sillo: Frequently Asked Questions"
- tag: meta
  attrs:
    property: og:description
    content: Versions, dependencies, what is optional, what moved in 1.0, and the honest answers about maturity and scope.
---

#  Frequently Asked Questions

The questions that come up before the first `uv add`, answered without
marketing. Where an answer is unflattering it is still the answer.

##  Choosing Sillo

###  Is Sillo production ready?

This manual is the released line, and the version number is not false modesty
— the API still moves between minor releases, and 1.0 relocates several things
that are in the framework today. Read [What changes in 1.0](#what-changes-in-10)
before you start something you intend to keep.

What *is* stable is the shape: routing, handlers, validation, dependency
injection and the response layer have not changed conceptually since early
0.x, and the [official starter](/v0.x/guides/start/) is booted and exercised
route-by-route in CI on three Python versions on every push. Applications are
running on it. It is a reasonable bet for a project you control the deployment
of, and a poor bet for one where you cannot absorb a breaking change on your
own schedule.

###  Is this just FastAPI plus Django?

Not quite, and the difference is the point rather than the pieces.

The typed, Pydantic-validated, async request layer will feel like FastAPI. The
ORM's query API — `.filter()`, `Q`, `F`, lookups like `name__icontains` — will
feel like Django, because Tortoise deliberately borrows that API. If those were
the only two facts, gluing the two together yourself would be the sensible
move, and plenty of teams do.

What you do not get by gluing them is one configuration model, one lifecycle,
one idea of a user shared by sessions and permissions and API keys and OAuth,
one exception hierarchy, and one release cadence across all of it. That is the
[fitting cost](/v0.x/guides/philosophy/), and it is what the framework exists
to pay. See also the comparison table in the
[Introduction](/v0.x/guides/introduction/#comparison).

###  Is it fast?

It is an async ASGI framework with no runtime magic in the hot path, running
on uvicorn by default and granian if you install it. In practice your latency
will be dominated by your database and your outbound calls, not by the routing
layer, and any benchmark that says otherwise is measuring an application you
are not writing.

The performance question that actually matters is
[Concurrency](/v0.x/guides/concurrency/) — specifically, what happens when a
blocking call ends up inside an `async` handler. That page is worth reading
before you deploy, not after.

###  Who is it not for?

If you need a single HTTP handler, a script with a webhook on it, or a
framework that owns nothing beyond routing, this is more framework than the
job needs — Starlette or Flask will serve you better. If you need a decade of
third-party packages and Stack Overflow answers, Django has them and Sillo
does not.

##  Installing

###  What does `uv add sillo-framework` actually install?

Five packages: `uvicorn`, `anyio`, `python-multipart`, `pydantic`, and
`typing-extensions` on Python below 3.13. That is the whole base install.

No database driver, no Redis client, no `cryptography`, no JWT library, no
Jinja, no hashing backend beyond the standard library's. Each of those is an extra you
opt into, because carrying it in core would force a decision on people who
will never use that subsystem. See [What's in the Box](/v0.x/guides/ecosystem/)
for the full list and [Installation](/v0.x/guides/installation/) to get going.

###  Which Python versions are supported?

3.10 and up, tested through 3.14.

###  Why are there so many extras?

Because the alternative is worse. `cryptography` is a compiled dependency;
`tortoise-orm` brings a database stack; `redis` brings a client you do not
need if you are running one process. An install that includes all of them by
default makes every user pay for the subsystems they are not using, in install
time, in image size, and in CVE surface.

`uv add "sillo-framework[all]"` exists if you would rather not think about it.

###  Do I have to use the ORM?

No. `sillo.record` is behind the `record` extra and nothing in the framework
imports it unless you do. SQLAlchemy, raw `asyncpg`, an HTTP API, or no
persistence at all are all fine — routing, validation, DI, auth, jobs and
WebSockets do not know or care where your data lives.

What you give up is the parts that were designed against Record: the
[factories](/v0.x/orm/factories/), the Pydantic bridge, and the ORM-aware
[pagination](/v0.x/orm/pagination/) helpers.

###  Do I have to use Pydantic?

For request validation and configuration, effectively yes — `request_model=`
takes a `BaseModel` and [`Config`](/v0.x/guides/configuration/) is one. Pydantic
is one of the five base dependencies for that reason.

For everything else, no. A handler can read the raw body and validate it
however you like. See the [Pydantic manual](/v0.x/pydantic/) for how far the
integration goes.

###  Does it need Redis?

No. The cache and the event system both run in memory by default and take a
Redis URL when you have more than one process. The queue is the honest
exception: durable, cross-process job delivery needs somewhere durable to put
the jobs, and in-memory queues lose them on restart. See
[Caching](/v0.x/guides/cache/) and [Background Work](/v0.x/guides/work/).

##  Using it

###  Is it async-only?

Handlers are `async`, yes. Blocking code is not forbidden — it just must not
run on the event loop, and the framework gives you a thread pool to put it on.

This is the most common way a Sillo application gets mysteriously slow: one
synchronous database driver or `requests` call inside a handler, and every
other request on that worker waits behind it.
[Concurrency](/v0.x/guides/concurrency/) covers the symptoms and the fix.

###  Can I mount it inside another ASGI app, or mount other apps inside it?

Both. Sillo is an ASGI application, so anything that speaks ASGI can host it,
and it can host anything that speaks ASGI. Sub-applications and prefixed
routers are first-class — see
[Routers & Sub-Apps](/v0.x/guides/routers-and-subapps/).

###  Can I use third-party ASGI middleware?

Yes. Raw ASGI middleware works unchanged alongside Sillo's own function and
class middleware. [Middleware](/v0.x/guides/middleware/) covers all three
forms and the order they run in.

###  How do I serve a front end?

Four options, and they are genuinely different choices rather than four ways to
do one thing. Serve a built SPA as [static files](/v0.x/guides/static-files/)
and talk to it over JSON; use [Inertia](/v0.x/guides/inertia/) with React or
Vue if you want server-driven pages without writing an API; render server-side
HTML with [templating](/v0.x/guides/templating/); or return HTML yourself.
[Frontend (SPA)](/v0.x/guides/frontend/) lays out the trade-offs.

Templating is the one to think twice about: it is in the framework in 0.x and
is removed in 1.0.

###  Where do I put my application's configuration?

In a `Config` subclass, which is a Pydantic model, validated at startup.
Secrets come from the environment. See
[Configuration](/v0.x/guides/configuration/) and
[Environment & .env](/v0.x/guides/environment/).

##  Versions

###  Should I install v0.x or v1.0?

Install 0.x — it is what `uv add sillo-framework` gives you, it is what an
unversioned documentation link lands on, and it is the manual you are reading
right now. The v1.0 manual describes an unreleased version and every page in it
says so at the top.

The version switcher sits at the foot of the sidebar.

###  What changes in 1.0?

The handler signature, and the boundary of the framework. Both are worth
knowing about before you write a lot of code.

Handlers will take a single `HttpContext` rather than a `request` and a
`response`, and returning a `dict` will be enough — the response builder stays
for when you need to set a status or a header:

```python
# 0.x — what this manual documents
async def home(request, response):
    return response.json({"message": "hi"})

# 1.0
async def home(ctx: HttpContext):
    return {"message": "hi"}
```

Four things leave the framework and become packages of their own:

| In 0.x | In 1.0 |
|---|---|
| Built-in [admin panel](/v0.x/orm/admin/) | [`warder`](/packages/warder/), a separate install with a React interface |
| [HTML templating layer](/v0.x/guides/templating/) (Jinja) | Gone from core; mail templates are the one place Jinja remains |
| [WebSocket rooms, channels and groups](/v0.x/guides/websockets/channels/) | [`sillo-wire`](/packages/wire/) |
| [`sillo.graphql`](/v0.x/guides/graphql/) | [`sillo-graphql`](/packages/graphql/), which claims that same import name |

Each of those leaves for the same reason: a dependency, a release cadence, or a
scope that core should not carry on everyone's behalf. See
[What's in the Box](/v0.x/guides/ecosystem/).

One practical consequence today: because 0.x still ships `sillo.graphql`, the
`sillo-graphql` package refuses to load against it rather than shadowing the
module. On 0.x, use the [built-in GraphQL support](/v0.x/guides/graphql/).

###  Will there be an upgrade guide?

Yes, when 1.0 releases. Until then the two manuals sit side by side — switch
with the control at the foot of the sidebar — and the table above is the
summary.

##  Deploying

###  What server should I run it on?

`uvicorn` is the default and is installed with the framework. `granian` is an
extra if you want it. Anything that speaks ASGI will work.
[Deployment](/v0.x/guides/start/deployment/) covers process management,
logging and the things that break first.

###  How do I run it in development?

`vise serve` — one command that boots the application, replaces uvicorn's
logging with something readable, and mounts an operations dashboard beside it.
It installs separately as `sillo-vise`.

###  How do I test it?

There is a test client that drives the application in-process, without a
server. Routes, validation, dependencies, auth and jobs are all exercisable
from a normal `pytest` test. See [Testing](/v0.x/guides/start/testing/).

##  Still stuck

- [Coming from FastAPI, Django or Flask](/v0.x/guides/coming-from/) — if the
  question is really "how do I do *this thing* here"
- [Glossary](/v0.x/advanced/glossary/) — if a term in these docs is doing
  unfamiliar work
- [Architectural Decisions](/v0.x/advanced/decisions/) — if the question is
  "why on earth is it like that"
- [github.com/sillohq/core](https://github.com/sillohq/core) — if it is a bug
