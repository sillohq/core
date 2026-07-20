---
title: Events
description: The sillo event system — a powerful publish/subscribe layer with pluggable backends (memory, Redis, persistent, record) for in-process and cross-instance event delivery.
---

# Events

The sillo event system implements the [publish–subscribe (pub/sub)
pattern](https://en.wikipedia.org/wiki/Publish%E2%80%93subscribe_pattern):
components communicate without direct dependencies, making your code loosely
coupled, maintainable, and flexible.

At its core, each emitter owns a registry of named events. You **subscribe**
listeners with `on` / `once`, and **emit** events with `emit` (synchronous,
in-process) or `emit_async` (all backends). Listeners run in priority order and
support capture/bubble propagation, cancellation, weak references, and
performance metrics.

:::caution Events are for side effects ONLY
Use events primarily for side effects (sending emails, analytics, logging,
cache invalidation) that should not block the main request flow. Do not use
events to mutate data the request cycle depends on.
:::

## Basic usage

```python
from sillo import silloApp

app = silloApp()

@app.events.on("user.created")
async def handle_user_created(user):
    print(f"User created: {user['name']}")

# Trigger the event (async, every backend)
await app.events.emit_async("user.created", {"name": "Bob"})
```

The `silloApp` and `Router` classes expose a default emitter at `app.events`.
You can also create standalone emitters (see [Creating emitters](#creating-emitters)).

## Subscribing to events

Use `on` to register a listener that runs every time the event fires:

```python {3}
from sillo import silloApp
app = silloApp()
@app.events.on("user.created")
async def handle_user_created(user):
    print(f"User created: {user['name']}")
```

`once` registers a listener that fires **only the first time** and is then
removed automatically:

```python
@app.events.once("first.login")
async def welcome(user):
    print(f"Welcome {user['name']}!")
```

## Emitting events

Emit with `emit_async` (works on every backend) or, for the default in-process
`memory` backend, the synchronous `emit`:

```python {3}
@app.post("/users")
async def create_user(req, res):
    await app.events.emit_async("user.created", {"name": "Bob"})
    ...
```

```python
# memory backend only — returns listener execution stats
stats = app.events.emit("user.created", {"name": "Bob"})
# {'event_id': '...', 'listeners_executed': 1, 'execution_time': 0.0001, ...}
```

::: tip Async listeners are awaited
Coroutine listeners are **awaited** in priority order. Always prefer `async def`
handlers — a synchronous handler blocks the event loop while it runs.
:::

## Removing listeners

Remove a single listener with `remove_listener`, or clear listeners with
`remove_all_listeners` (per event or for the whole emitter):

```python
# Define a handler
async def temporary_handler(data):
    print(f"Processing data: {data}")

app.events.on("data.received", temporary_handler)

# Later, remove it
app.events.remove_listener("data.received", temporary_handler)

# Or remove all handlers for an event
app.events.remove_all_listeners("data.received")
```

## Priority listeners

Listeners execute in priority order — higher priority first. The default is
`NORMAL`.

```python
from sillo.events import EventPriority

app.events.on("data.received", high_handler, priority=EventPriority.HIGH)
app.events.on("data.received", low_handler, priority=EventPriority.LOW)
```

Priorities, highest to lowest: `HIGHEST`, `HIGH`, `NORMAL`, `LOW`, `LOWEST`.

## Namespaces

Group related events under a prefix without repeating it. A namespace wraps an
emitter and prefixes every name with `"<namespace>:"`:

```python
ui = app.events.namespace("ui")

@ui.on("button.click")        # listens on "ui:button.click"
async def on_click(btn):
    print(f"{btn} clicked!")

ui.emit("button.click", "submit")          # -> "ui:button.click"
app.events.emit("ui:button.click", "submit")  # equivalent
```

Nested namespaces are supported via `ui.namespace("modal")`.

---

## Backends

The event system is **backend-agnostic**. The backend decides *where* an emitted
event goes — in-process, across Redis instances, onto a durable backlog, or into
your database. Select a backend with `EventEmitter(backend=...)` (or
`app.events = EventEmitter("redis", ...)`).

| Backend | Dependency | Delivery | Use when |
|---|---|---|---|
| `memory` | none | In-process, synchronous | Default; single-process apps, tests. |
| `redis` | `redis>=5` | Cross-instance fan-out (pub/sub) | Multiple app instances must react to the same event. |
| `persistent` | `redis>=5` | Durable, at-least-once (Redis backlog) | You cannot lose events emitted while a consumer is offline. |
| `record` | `tortoise-orm` | Persisted as DB rows (audit log + replay) | You need an audit trail or crash recovery. |

```bash
pip install "sillo[events]"     # redis driver for redis / persistent
pip install "sillo[record]"     # tortoise-orm for the record backend
```

All optional dependencies are imported **lazily** — `backend="memory"` works
with nothing extra installed, and `redis` / `tortoise` are only imported when
you actually construct that backend.

::: tip Networked backends need `start()`
`redis` and `persistent` spawn a background subscriber/worker loop. You must
`await emitter.start()` (typically on app startup) and `await emitter.stop()`
on shutdown. `memory` and `record` need no loop.
:::

### Memory (default)

In-process delivery — the original sillo behaviour. No external services, no
serialization round-trip. Use the synchronous `emit` or `emit_async`:

```python
from sillo.events import EventEmitter

emitter = EventEmitter("memory")          # or just EventEmitter()
emitter.on("ping")(lambda: print("pong"))
emitter.emit("ping")                       # synchronous, in-process
```

### Redis (cross-instance)

Every emit `PUBLISH`es a JSON envelope to a Redis channel; every emitter
subscribes to the channels it has listeners for and re-dispatches received
envelopes to its local listeners. This gives true fan-out across processes and
instances.

```python
from sillo.events import EventEmitter

emitter = EventEmitter("redis", url="redis://localhost:6379/0")
await emitter.start()                      # spawn the subscriber loop

@emitter.on("order.placed")
async def on_order(order):
    ship(order)

await emitter.emit_async("order.placed", order)
```

:::caution Redis pub/sub is fire-and-forget
A message is delivered only to subscribers connected *at the moment of publish*
— there is no backlog, so an instance that is down misses events. If you need
at-least-once delivery across restarts, use `persistent` instead.
:::

### Persistent (durable, at-least-once)

Events are pushed onto a Redis **list** (the backlog). A worker loop blocks on
`BRPOP`, dispatches each message, then acknowledges it. Because the message lives
in Redis until acknowledged, events survive a process restart and are delivered
at-least-once. Failed deliveries are requeued up to `max_retries` times.

```python
from sillo.events import EventEmitter

emitter = EventEmitter("persistent", url="redis://localhost:6379/0", max_retries=5)
await emitter.start()                      # spawn the BRPOP worker

@emitter.on("invoice.due")
async def charge(invoice):
    await billing.charge(invoice)

await emitter.emit_async("invoice.due", invoice)
```

In-flight messages remain in the backlog after `stop()`, so the next `start()`
drains them — that is what makes delivery at-least-once across restarts.

### Record (audit log + replay)

Every emit writes a `EventMessage` Tortoise row (`channel`, `payload`, `status`,
`attempts`) **and** fires local listeners. Rows left `pending`/`failed` can be
replayed on startup via `replay()` for crash recovery.

```python
from sillo.events import EventEmitter
from sillo.events.transports import setup_event_record

# Build the model once (after setup_record) and register it in model_modules
EventMessage = setup_event_record()

emitter = EventEmitter("record")           # no background loop needed
emitter.on("audit.trail")(lambda e: ...)
await emitter.emit_async("audit.trail", event)

# On startup, recover undelivered events from a previous run:
recovered = await emitter.transport.replay(limit=500)
```

### Custom backends

Register your own transport by dotted path:

```python
from sillo.events.transports import register_transport, get_transport

register_transport("kafka", "myapp.transports:KafkaTransport")
emitter = EventEmitter("kafka")
```

A custom transport subclasses `sillo.events.transports.BaseTransport` and
implements `publish()` (and a receive loop in `start()` if it receives remotely).

---

## Wiring into the app lifecycle

For networked backends, create the emitter and start/stop it with the
application lifespan:

```python
from sillo import silloApp
from sillo.events import EventEmitter

app = silloApp()
app.events = EventEmitter("redis", url="redis://localhost:6379/0")

@app.on_startup
async def start_events():
    await app.events.start()

@app.on_shutdown
async def stop_events():
    await app.events.stop()
```

Listeners registered via `app.events.on(...)` before `start()` still connect,
because subscribing lazily starts the loop if needed.

---

## Creating emitters

Each `EventEmitter` is independent — you can run several with different
backends or namespaces:

```python
from sillo.events import EventEmitter

# Standalone emitter
emitter = EventEmitter("memory")
emitter.on("user.created")(lambda u: print(u))
emitter.emit("user.created", {"name": "Bob"})

# Pass a pre-built transport directly
from sillo.events.transports import get_transport
transport = get_transport("redis", url="redis://localhost:6379/0")
custom = EventEmitter(transport=transport)
```

---

## API reference

| Symbol | Kind | Purpose |
|---|---|---|
| `EventEmitter` | class | The emitter; owns listeners and delegates delivery to a transport. |
| `EventNamespace` | class | Prefixes event names (`namespace("ui").on("x")` → `"ui:x"`). |
| `AsyncEventEmitter` | class | **Deprecated.** Use `EventEmitter` (native async listeners). |
| `Event` | class | A single named event (priority, propagation, metrics). |
| `EventPriority` | enum | `HIGHEST` … `LOWEST`. |
| `EventPhase` | enum | `CAPTURING`, `AT_TARGET`, `BUBBLING`. |
| `BaseTransport` | class | Abstract delivery backend contract. |
| `get_transport(name, **opts)` | function | Build a transport by backend name. |
| `register_transport(name, path)` | function | Register a custom `module:Class` backend. |
| `setup_event_record()` | function | Build the `EventMessage` model for the `record` backend. |

### `EventEmitter` methods

| Method | Notes |
|---|---|
| `on(name, fn=None, *, priority, weak_ref)` | Register a listener (decorator or direct). |
| `once(name, fn=None, *, priority, weak_ref)` | Register a one-time listener. |
| `emit(name, *args, **kwargs)` | **memory only** — synchronous, returns stats. |
| `emit_async(name, *args, **kwargs)` | All backends — async, returns `{"event_id", "backend"}`. |
| `start()` / `stop()` | Start/stop the transport's background loop. |
| `remove_listener(name, fn)` / `remove_all_listeners(name=None)` | Detach listeners. |
| `namespace(prefix)` | Return an `EventNamespace`. |
| `transport` | The underlying `BaseTransport` instance. |
