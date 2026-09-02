---
title: Packages
description: Sillo ships as a small core plus separately versioned packages. This is what exists and what each one is for.
---

Sillo's core is one distribution — `sillo-framework` — and everything on this
page installs alongside it. They are separate for one reason each, and the
reason is always the same shape: the package has a dependency, a release
cadence, or a scope that the core should not carry on everybody's behalf.

| Package | Install | Import | What it is |
|---|---|---|---|
| [Wire](/packages/wire/) | `sillo-wire` | `sillo.wire` | Rooms, presence and fan-out for WebSockets |
| [GraphQL](/packages/graphql/) | `sillo-graphql` | `sillo.graphql` | A production GraphQL endpoint over a Strawberry schema |
| [Warder](/packages/warder/) | `warder` | `warder` | A declarative admin over your models |

Each has a manual of its own — pick one above and the sidebar becomes its
table of contents.

## How they attach

Wire and GraphQL extend the framework's own surface, so they take a name inside
it. The code lives in a top-level package — `sillo_wire`, `sillo_graphql` — and
the framework name is an alias for it. Both bind the same objects:

```python
from sillo.wire import Hub     # both of these
from sillo_wire import Hub     # name the same class
```

Warder does not, and the difference is deliberate. It is not an extension of
`sillo` — it is an application you mount on yours, the way you would mount any
other. So it keeps its own name:

```python
from warder import Admin
admin.mount(app)
```

The alias is a meta-path finder the package registers through a `.pth` at
interpreter startup, plus PEP 561 partial stubs so type checkers resolve it
too. Nothing is written into the `sillo` package directory.

That last part is the point. Shipping `sillo/wire/` into the framework's own
directory is simpler, and it is what Wire did first — but two distributions
sharing one directory goes wrong in both directions. Installing the framework
from a checkout moves where `sillo` resolves and orphans the copy in
site-packages; removing or replacing the framework leaves that directory
standing with no `__init__.py` in it, which is an override rather than an
addition. Uninstalling either package now leaves the other untouched.

One consequence is worth stating plainly: a package cannot claim a name the
framework still uses. `sillo-graphql` claims `sillo.graphql`, which the
framework shipped until 1.0 — so against an older framework the alias
refuses to load and says why, rather than quietly shadowing it.

## What stays in core

Anything with no third-party dependency that every application is likely to
reach for. The line is not size — it is whether keeping something in core
forces a decision on people who will never use it.
