---
title: Packages
description: Sillo ships as a small core plus separately versioned packages. This is what exists and what each one is for.
---

Sillo's core is one distribution — `sillo-framework` — and everything on this
page installs alongside it. They are separate for one reason each, and the
reason is always the same shape: the package has a dependency, a release
cadence, or a scope that the core should not carry on everybody's behalf.

Each installs under its own name and imports under a Sillo one.

| Package | Install | Import | What it is |
|---|---|---|---|
| [Wire](/packages/wire/) | `sillo-wire` | `sillo.wire` | Rooms, presence and fan-out for WebSockets |

## How they attach

The code lives in a top-level package — `sillo_wire` — and the framework name
is an alias for it. Both bind the same objects:

```python
from sillo.wire import Hub     # both of these
from sillo_wire import Hub     # name the same class
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

## What stays in core

Anything with no third-party dependency that every application is likely to
reach for. The line is not size — it is whether keeping something in core
forces a decision on people who will never use it.
