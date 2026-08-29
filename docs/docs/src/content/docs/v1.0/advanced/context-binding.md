---
title: "Instance Registry"
description: "The shared mechanism behind current_storage(), current_mail(), and every setup_x() that follows — a plain slot filled at startup, reachable from anywhere"
---

> Internal engineering reference for a small piece of infrastructure shared
> across subsystems.
>
> Source: `core/sillo/_internals/registry.py` (~90 lines)

---

## 1. The problem

Every `setup_x(app, config)` in the framework follows the same shape: build
one long-lived instance, put it on `app.state`, register lifecycle hooks,
return it. `setup_record`, `setup_work`, `setup_mail`, `setup_storage` all do
exactly this.

Getting the instance back is where they used to diverge. A handler could hold
a closure over it, or reach through `ctx.base_app.state["storage"]` — both
fine when there is a request in hand and the code holding it does not mind an
import shaped by that. Neither works well for the routes module that wants to
call `bucket(...)` without importing the application that built it (a
circular import, since the application is what registers the routes), and
neither works *at all* for a queue job or a script, where there is no request
and often no `app` object lying around either.

The keys were also picked independently per subsystem —
`app.state["storage"]`, `app.state["mail_client"]`, `app.state["record"]` —
untyped strings a typo in either the write or the read silently breaks.

## 2. What this is, and what it deliberately is not

`InstanceRegistry` is a plain slot: `register(instance)` fills it,
`current(...)` reads it back, and asking before anything was registered raises
a `NotConfiguredError` naming the `setup_x` call that was skipped, rather than
returning `None` for code to accept as if it were valid.

```python
class InstanceRegistry(Generic[T]):
    def __init__(self, label: str) -> None:
        self._label = label
        self._instance: T | None = None

    def register(self, instance: T) -> None:
        self._instance = instance

    def current(self, *, setup: str, example: str) -> T:
        if self._instance is None:
            raise NotConfiguredError(...)
        return self._instance
```

That is the whole mechanism. Two things it is not, on purpose:

**Not a `ContextVar`.** An earlier version of this bound the instance per
request, with a small ASGI middleware setting and resetting a
`contextvars.ContextVar` around each call — the same trick
[`sillo_inertia`](https://github.com/sillohq/inertia) uses for
`current_inertia()`, where it is the right answer: an Inertia response *is* a
function of the request answering it, and there is no such thing as rendering
one outside of one. Mail and storage are different — a queue job sending a
receipt or a script backfilling a bucket has no request to bind from, and
those are not edge cases for either subsystem, they are close to half its
traffic. Tying the lookup to the request lifecycle would have solved the
import problem and reintroduced the exact "how do I reach this from a
background job" problem the design was meant to remove. Registering once, at
startup, removes the request from the question entirely.

**Not per-application.** The registry holds one instance at a time, whichever
`setup_x` call registered most recently — there is no key, no lookup by
`app`. This is the same assumption `app.state["storage"]` already made *for
that application* (one `Storage` per app), made explicit at process scope
instead: one registered `Storage` at a time, full stop. A process serving two
applications with two different storage configurations — most often a test
suite building app after app — gets whichever was set up last, and that is a
deliberate trade for never needing an application object to do the lookup,
not an oversight. It has not needed to be anything more: sillo applications
are one per process in every deployment shape the framework targets.

## 3. Who uses it

| Subsystem | Registry label | Reader |
|---|---|---|
| `sillo.storage` | `"storage"` | `current_storage()`, `bucket(name)` |
| `sillo.mail` | `"mail client"` | `current_mail()`, `send_email(...)` |

Each subsystem owns one `InstanceRegistry[T]` at module scope in its own
`context.py`, and calls `register(instance)` from its `setup_x` function —
that is the entire integration cost. `app.state["storage"]` and
`app.state["mail_client"]` are untouched; this is an addition, not a
replacement, for code that already holds the application object and would
rather use it.

```python
# sillo/storage/context.py
_registry: InstanceRegistry[Storage] = InstanceRegistry("storage")

def register(storage: Storage) -> None:
    _registry.register(storage)

def current_storage() -> Storage:
    return _registry.current(setup="setup_storage", example=_EXAMPLE)
```

```python
# sillo/storage/storage.py — inside setup_storage
storage = Storage(config, secret=secret or _app_secret(app))
app.state["storage"] = storage
app.on_shutdown(storage.close)
register(storage)          # ← the one line each setup_x adds
```

## 4. The failure mode this was built to avoid

A cache miss that returns `None` — instead of a sentinel distinct from every
valid cached value — invites code to accept `None` as data. The same shape
would happen here if `current_storage()` returned `None` before startup: a
handler that forgot to call `setup_storage` would get an `AttributeError` on
whatever it tried to do with `None`, three call frames away from the actual
mistake and looking nothing like it.

`NotConfiguredError` is raised at the point of the mistake, and names the
`setup_x` call that should have run first:

```
No storage has been set up yet.

This reads the storage setup_storage registers. Call it during startup,
before anything asks for the storage back:

    storage = setup_storage(app, StorageConfig(default="attachments", buckets={...}))

If it already runs somewhere, check that this code path executes after it —
module import order, not request order, decides whether that has happened.
```

The last line is the one worth reading twice: because registration happens at
`setup_x` time and not on first request, the failure this actually catches in
practice is an import-order bug — a module reading `current_storage()` at its
own import time, before the application module that calls `setup_storage` has
run.

## 5. Testing

`tests/test_internals/test_registry.py` covers the primitive alone — no app,
no request, nothing async unless the test itself needs to be — proving
`register`/`current` work as a plain function call would. `tests/test_storage/test_context.py`
and `tests/test_mail/test_context.py` cover the wiring: that `setup_storage`
and `setup_mail` actually call `register`, that the last call in a process
wins, and that a `NotConfiguredError` names the right subsystem.
