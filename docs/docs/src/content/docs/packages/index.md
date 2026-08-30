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
| [Wire](/packages/wire/) | `sillo-wire` | `sillo_wire` | Rooms, presence and fan-out for WebSockets |

## How they attach

They do not. Each one is an ordinary top-level package that happens to be built
for Sillo:

```python
from sillo_wire import Hub, Peer
```

An earlier version of Wire installed itself as `sillo.wire`, by shipping into
the framework's own package directory. It worked, and the import read better —
but two distributions sharing one directory goes wrong in both directions.
Installing the framework from a checkout moves where `sillo` resolves, orphaning
whatever the other package left in site-packages; and removing or replacing the
framework can leave that directory standing with no `__init__.py` in it, which
is an override rather than an addition.

The prefix was not worth that. A separate top-level name costs one underscore,
and guarantees nothing a package does can reach the framework's own files.

## What stays in core

Anything with no third-party dependency that every application is likely to
reach for. The line is not size — it is whether keeping something in core
forces a decision on people who will never use it.
