---
title: Philosophy
description: Why Sillo is assembled rather than composed — the fitting cost the framework exists to pay, the five principles it is held to, and the things it deliberately refuses to do.
head:
- tag: meta
  attrs:
    property: og:title
    content: "The Sillo Philosophy"
- tag: meta
  attrs:
    property: og:description
    content: The fitting cost, the five principles Sillo is held to, what follows from them, and where the philosophy costs you something.
---

#  Philosophy

The [Introduction](/v1.0/guides/introduction/) makes a claim in one paragraph
and then moves on to the API. This page is the claim itself, and what follows
from believing it.

##  The fitting cost

A backend is roughly fifteen solved problems. Routing is solved. Validation is
solved. Password hashing is very solved. There is a good library for every one
of them, most of them written by people who have thought about that problem
much harder than you are going to.

What is not solved is the space between them.

Two libraries, each excellent, will disagree about configuration — one reads a
settings module, one reads environment variables, one wants a dict passed to a
constructor. They will disagree about lifecycle: one opens its connection pool
on first use, one needs an explicit `startup`, one assumes a process fork that
your deployment does not do. They will disagree about what a user is. They will
disagree about what an error is, and one of them will raise something your
error handler has never heard of. And they will disagree about when to release
a breaking change, so an upgrade you needed for a security fix in one drags a
rewrite in another.

None of that work produces a feature. It is not in the plan, it does not
survive as anything you can point at, and it comes back every time one of the
fifteen releases a major version. Call it the fitting cost. On a real project
it is not a rounding error — it is most of the first month, and a tax on every
month after.

Sillo's whole argument is that this cost should be paid once, by the framework,
rather than again by every application.

That is what "batteries included" means here. Not that you get more code — that
you get code that was designed against the rest of it. The ORM, the auth layer,
the scheduler and the cache were written knowing about each other. They share
one configuration model, one application lifecycle, one idea of a user, and one
set of exceptions. Sessions know what a user is because the auth layer defined
it. The scheduler starts when the application starts because there is only one
place that decides what starting means.

##  Five principles

The framework is held to five. They are short enough to remember, which is the
point — a principle you cannot recall while reviewing a pull request is
decoration.

###  Strong defaults, open boundaries

Every subsystem should do the right thing with no arguments, and every
subsystem should be replaceable.

Those are not in tension, they are the same commitment read from two ends. A
default is only defensible if you can get out of it. So password hashing picks
a sensible scheme and lets you register your own; the cache runs in memory and
takes a Redis URL or a driver you wrote; sessions, auth backends, storage
drivers and hashers are all contracts before they are implementations.

What this rules out: a default so entangled that overriding it means forking.
If a subsystem cannot be swapped, its default is not a default — it is a
requirement wearing a default's clothes. See
[Extending Sillo](/v1.0/advanced/extending/) and
[Auth Backends](/v1.0/advanced/auth-backends/) for the seams.

###  Convenience without mystery

Sillo will do things for you. It will not do things you cannot see.

Returning a `dict` from a handler sends JSON. That is convenience. It is also
one function, documented, that you can call yourself or replace — not a
metaclass reaching into your module at import time. `Depend(...)` resolves your
dependencies before the handler runs; the resolution order is written down and
the failure is an exception with a name, not a silent `None`.

What this rules out: implicit global state, import-time side effects that
change behaviour depending on what you imported first, and any behaviour whose
only explanation is "the framework does that". If you cannot answer *what ran
and in what order*, the convenience was not worth it.

###  Documentation is part of the interface

A behaviour that is not written down is not shipped, and a defect that is known
is written down next to the thing that has it.

This is why these guides carry `:::caution` and `:::danger` blocks that say a
function is wrong, show the failure, and give the working alternative — rather
than describing intended behaviour and letting you find the difference at
11pm. Documentation that only describes the happy path is a liability disguised
as an asset.

###  Compatibility and upgrade paths matter

Breaking changes are sometimes correct. Breaking changes without a written path
across them are not.

Two versions of these docs exist side by side for exactly this reason: v0.x is
what is released and what an unversioned link lands on, and v1.0 says at the
top of every page that it describes something unreleased. Where 1.0 moves
something out of the framework — the admin, the HTML templating layer,
WebSocket rooms — the page it moved to exists and says where it came from.

###  Anything done on your behalf can be read, overridden, or replaced

The strongest form of the other four. There is no privileged layer. The
middleware pipeline is a list you can inspect. The router is an object. The
config system is Pydantic models you declared. The
[Advanced manual](/v1.0/advanced/) documents the internals as internals — not
because you should depend on them, but because a framework that cannot survive
being read is a framework that will surprise you.

##  What follows from this

Principles are cheap. These are the concrete consequences, which are the part
worth arguing with.

**One config model.** Every subsystem reads configuration the same way, from
[`sillo.config.Config`](/v1.0/guides/configuration/) — a Pydantic model, so
configuration is validated at startup rather than discovered as an `AttributeError`
in a job worker at 3am. There is no second convention for "the cache's config"
or "the ORM's config".

**One lifecycle.** Startup and shutdown are the application's, and subsystems
attach to it. The scheduler does not have its own idea of when the process is
ready. See [Startup & Shutdown](/v1.0/guides/startups-and-shutdowns/).

**One idea of a user.** The auth layer defines it; sessions, permissions, API
keys, JWT and the OAuth package all mean the same object by it. This is the
single largest source of fitting cost in an assembled stack, and removing it is
most of the value.

**Declarations that cannot drift.** `auth=useAuth(...)` on a route both gates
the request and writes that route's `securityScheme` into the OpenAPI
document. There is no second place to update, so the spec cannot quietly stop
describing the application. The same shape shows up in validation: the model
that rejects the request body is the model that documents it.

**Cross-cutting concerns are middleware, not per-project rewrites.** ETags,
range requests, content negotiation and security headers ship as middleware
because every project needs them and no project should be writing them again.

##  What Sillo will not do

The refusals are more informative than the features.

**It will not generate an application.** `sillo-start` does not template code
into existence — it copies a working application whose CI boots it and calls
every route on every push. Generated code is code nobody has run. See
[Creating a Project](/v1.0/guides/start/).

**It will not install what you did not ask for.** The base install is five
dependencies. The ORM, Redis, JWT, `cryptography`, S3 storage and every hashing
backend are [extras](/v1.0/guides/ecosystem/), because keeping something in
core forces a decision on people who will never use it. The line is not size —
it is imposition.

**It will not keep something in core for the maintainers' convenience.** When a
subsystem grows a dependency, a release cadence, or a scope of its own, it
leaves — that is why Wire, GraphQL and Warder are [packages](/packages/) rather
than modules.

**It will not hide a failure.** No `fail_open` that quietly stops enforcing, no
swallowed exception, no default that degrades to unsafe without saying so.
Where the framework has chosen the unsafe-but-available side of that trade —
rate limiting, notably — the [decision is written down](/v1.0/advanced/decisions/)
with its reasoning.

##  Where this philosophy costs you something

Every position has a price, and pretending otherwise is how documentation loses
your trust.

**Opinions you may not share.** A framework that assembles the pieces has
chosen the pieces. The ORM is Tortoise-shaped; if you want SQLAlchemy's session
and unit-of-work model, you can have it — Record is optional and nothing else
depends on it — but you are then outside the coherence you came for.

**Async-first is a real constraint.** Handlers are `async`. A blocking call in
one blocks the event loop and the whole process gets slower in a way that is
hard to attribute. There is a thread pool for it and
[Concurrency](/v1.0/guides/concurrency/) explains when to use it, but this is
the single most common source of production surprise and no amount of framework
design removes it.

**Ecosystem and years.** Django and Flask have both, and there is no argument
against them that survives contact with a decade of third-party packages and
Stack Overflow answers. Sillo's claim is scope and coherence. It is not
maturity, and where these docs say otherwise they are wrong.

**Coherence is a constraint on you too.** Subsystems designed against each
other are subsystems with expectations. Replacing one is always possible and
sometimes more work than it would be in a stack where nothing knew about
anything.

##  Related

- [Introduction](/v1.0/guides/introduction/) — what the framework is, and the
  comparison table
- [Frequently Asked Questions](/v1.0/guides/faq/) — the version, dependency and
  adoption questions
- [What's in the Box](/v1.0/guides/ecosystem/) — where the line between core,
  extras and packages actually falls
- [Architectural Decisions](/v1.0/advanced/decisions/) — the same reasoning
  applied to fifteen specific choices, with the alternatives that were rejected
