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

A package like Wire ships its module *into* the `sillo` package directory, so
there is no import hook and no namespace package involved:

```python
from sillo.wire import Hub, Peer
```

Type checkers resolve it, tracebacks name it, and `pip uninstall sillo-wire`
takes exactly its own files with it. What you install and what you import
differ only because the distribution name has to be unique on PyPI and the
import path should read as part of the framework.

## What stays in core

Anything with no third-party dependency that every application is likely to
reach for. The line is not size — it is whether keeping something in core
forces a decision on people who will never use it.
