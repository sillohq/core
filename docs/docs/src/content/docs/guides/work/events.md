---
title: Events
description: The in-process event dispatcher — typed dataclass events, priority ordering, wildcards, propagation control, and why the @listen decorator does not register anything.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Events
  - tag: meta
    attrs:
      property: og:description
      content: The in-process event dispatcher — typed dataclass events, priority ordering, wildcards, propagation control, and why the @listen decorator does not register anything.
---

#  Events

An event system exists to stop one piece of code from knowing about every
consequence of what it does. Shipping an order should not require the
shipping code to import the mailer, the analytics client, the inventory
service, and the Slack webhook. It dispatches `OrderShipped`, and
whatever cares, listens.

```python title="the shape"
from dataclasses import dataclass

from sillo.work.queue import Event, EventDispatcher


@dataclass
class OrderShipped(Event):
    order_id: str
    tracking: str


dispatcher = EventDispatcher()


async def notify_customer(event: OrderShipped):
    await mailer.send_tracking(event.order_id, event.tracking)


dispatcher.register(OrderShipped, notify_customer)

await dispatcher.dispatch(OrderShipped(order_id="42", tracking="1Z999"))
```

##  When to reach for this

Use events when one action has several independent consequences,
especially when those consequences belong to different parts of the
application and change at different rates. Adding a fifth listener should
not mean editing the checkout handler.

Do not use events for a single caller and a single consequence — that is
a function call with extra indirection, and the indirection costs you a
stack trace that says what actually happened.

Do not use events as a queue. Listeners run in the same process, on the
same event loop, inside whatever awaited `dispatch()`. There is no
persistence and no retry. An event whose listener must eventually succeed
should have that listener enqueue a [job](/guides/work/jobs/).

Note that `sillo` has a second, unrelated event system —
[`sillo.events`](/guides/events/) — with its own emitter, priorities, and
transports. This page covers `sillo.work.queue.events`, which is the
typed-dataclass one used by the work subsystem. They do not interoperate.

##  Defining events

An event is a dataclass inheriting `Event`.

```python title="events are data"
from dataclasses import dataclass

from sillo.work.queue import Event


@dataclass
class OrderShipped(Event):
    order_id: str
    tracking: str
    carrier: str = "UPS"


@dataclass
class UserRegistered(Event):
    user_id: int
    email: str
```

The base class contributes two fields, both `init=False`, so they never
appear in your constructor: `_fired_at`, a `time.time()` stamp set at
construction, and `_propagation_stopped`, the flag behind
`stop_propagation()`.

Two rules make events durable as an interface. Carry identifiers, not
objects — a `user_id` stays valid, a `User` instance goes stale between
dispatch and the last listener. And treat the field set as an API: a
listener you did not write may depend on any field, so removing one is a
breaking change even though nothing imports it.

##  Registering listeners

```python title="register"
dispatcher.register(OrderShipped, notify_customer)
dispatcher.register(OrderShipped, update_analytics, priority=10)
dispatcher.register(OrderShipped, alert_slack, priority=-5, name="slack")
```

A listener is any async callable taking the event instance. Higher
priority fires first; the default is `0` and negatives are allowed.
Registration sorts the list immediately, so order does not depend on
registration order — only on priority.

`forget(event_type, callback)` removes a specific listener and returns
whether it found one. `has_listeners(event_type)` tells you whether
anything is registered — though note it returns `True` if any *wildcard*
listener exists, regardless of the type you asked about.

:::danger[`@listen(...)` does not register anything]
The decorator looks like registration and is not. Its entire body is:

```python
func._listens_to = events
func._listener_priority = priority
return func
```

It attaches two attributes and returns the function unchanged. No
dispatcher is involved — there is no global dispatcher for it to use —
so a function decorated with `@listen(OrderShipped)` and never passed to
`register()` is silently never called.

```python
@listen(OrderShipped)
async def notify_customer(event): ...

await dispatcher.dispatch(OrderShipped(...))   # notify_customer does NOT run
```

The decorator is metadata for a discovery step that you have to write.
The five lines that make it work:

```python title="wiring up decorated listeners"
def register_module(dispatcher, module):
    for name in dir(module):
        func = getattr(module, name)
        for event_type in getattr(func, "_listens_to", ()):
            dispatcher.register(
                event_type, func, priority=getattr(func, "_listener_priority", 0)
            )


import myapp.listeners

register_module(dispatcher, myapp.listeners)
```

Call that once at startup, after importing every module that declares
listeners. Until you do, prefer explicit `register()` calls — they are
harder to forget because nothing about them looks finished when it is
not.
:::

##  Dispatching

```python title="dispatch"
event = await dispatcher.dispatch(OrderShipped(order_id="42", tracking="1Z999"))
```

`dispatch` returns the same event instance it was given, which is
occasionally useful — a listener can annotate the event and the caller
can read it back.

Listeners run **sequentially, awaited one at a time**, wildcards first
and then exact-type matches. Sequential execution is deliberate: it is
what makes `stop_propagation()` meaningful. It also means the caller
waits for every listener.

```python title="the cost of a slow listener"
await dispatcher.dispatch(CheckoutCompleted(...))
# returns only after invoice + inventory + delivery + email have all finished
```

If a listener does something slow, the request that dispatched the event
pays for it. Have that listener enqueue a job instead, or dispatch
without awaiting:

```python
asyncio.create_task(dispatcher.dispatch(CheckoutCompleted(...)))
```

Fire-and-forget in that form loses errors and loses the work on restart —
the same tradeoff as a background task, and acceptable for the same kinds
of work.

###  Listener failures are swallowed

`_call_listener` wraps each callback in `try/except Exception` and logs
with `logger.exception`. A listener that raises does not stop the others
and does not fail the dispatch.

This is fail-open by design — an analytics listener must not break
checkout. The consequence is that `dispatch()` returning tells you
nothing about whether the consequences happened. If a listener's success
matters, it must report that itself, and you should alert on the
`sillo.work.queue.events` logger.

###  Stopping propagation

```python title="halting the chain"
async def check_fraud(event: OrderShipped):
    if await is_suspicious(event.order_id):
        event.stop_propagation()
```

Registered at a high priority, that listener prevents every lower-priority
listener from running. The check happens between listeners, so the
currently-running one always completes.

Use it sparingly. A dispatcher where any listener can silently cancel the
rest is hard to reason about, and the listener that stopped the chain is
not recorded anywhere. Where the semantics are really "should this
proceed", an explicit function call reads better than an event.

##  Wildcards

`register_wildcard` adds a listener that receives **every** event:

```python title="an audit log"
async def audit(event: Event):
    await AuditEntry.create(
        type=type(event).__name__, data=event.__dict__, at=event._fired_at
    )


dispatcher.register_wildcard(audit, priority=100)
```

Wildcards run before exact-match listeners, in their own priority order.
At priority 100 the audit above records everything before any handler has
a chance to stop propagation — which is what you want for an audit trail.

`ListenerRegistry` adds name-pattern matching on top, for the cases where
"every event" is too broad:

```python title="pattern matching"
from sillo.work.queue import ListenerRegistry

registry = ListenerRegistry(dispatcher)
registry.on("Order*", handle_any_order)
registry.once("UserRegistered", send_welcome)
```

`once()` removes the listener after its first invocation. Note that
registry-based wildcards dispatch through `dispatch_wildcards()`, a
separate entry point from `EventDispatcher.dispatch` — check which one
your call path uses before assuming a pattern listener fired.

##  A worked example

Checkout, with its consequences separated by what happens if they fail.

```python title="listeners split by criticality"
@dataclass
class CheckoutCompleted(Event):
    order_id: int
    user_id: int
    total_cents: int


# Must happen — hand it to the queue, do not do it inline.
async def bill_customer(event: CheckoutCompleted):
    await enqueue(ChargeCard, event.order_id)


# Should happen, cheap, safe to lose occasionally.
async def decrement_inventory(event: CheckoutCompleted):
    await Inventory.reserve_for(event.order_id)


# Nice to have.
async def track_conversion(event: CheckoutCompleted):
    await analytics.track("checkout", value=event.total_cents)


dispatcher.register(CheckoutCompleted, bill_customer, priority=100)
dispatcher.register(CheckoutCompleted, decrement_inventory, priority=50)
dispatcher.register(CheckoutCompleted, track_conversion, priority=0)


@app.post("/checkout")
async def checkout(request, response):
    order = await create_order(request.validated_data)
    await dispatcher.dispatch(
        CheckoutCompleted(
            order_id=order.id, user_id=request.user.id, total_cents=order.total_cents
        )
    )
    return response.json({"order_id": order.id}, status_code=201)
```

The priorities encode importance, so a listener that throws cannot
prevent a more important one from having run. And the critical listener
does not do the work — it enqueues it, so the guarantee comes from the
queue rather than from the dispatcher.

##  Naming and granularity

Event names are an interface, and the two failure modes are opposite.

Too coarse, and listeners have to re-derive what happened:
`OrderChanged` forces every listener to compare old and new state to
decide whether it cares. Too fine, and you get thirty event classes that
always fire together, plus thirty registrations to keep in sync.

The useful rule is one event per *decision a listener might make
differently*. `OrderPlaced`, `OrderPaid`, `OrderShipped`, and
`OrderCancelled` are four events because four different sets of things
happen. `OrderFieldUpdated` is not an event, it is a database trigger
wearing a costume.

Name them in the past tense, after the fact rather than the intent.
`SendWelcomeEmail` is a command — it names what the listener should do,
which couples the dispatcher to the consequence and means only one
listener can sensibly handle it. `UserRegistered` is a fact; any number
of listeners can react to it, and the code that dispatched it does not
need updating when a fifth one appears.

Keep events in one module that neither the dispatchers nor the listeners
own. If `checkout.py` defines `CheckoutCompleted` and `inventory.py`
imports it to listen, inventory now depends on checkout — exactly the
coupling the event system was meant to remove. A shared `events.py` that
imports nothing keeps the dependency arrows pointing one way.

##  Persisting events

Subclassing the dispatcher is the clean extension point:

```python title="an event log"
class RecordingDispatcher(EventDispatcher):
    async def dispatch(self, event):
        await EventLog.create(
            type=type(event).__name__,
            payload=json.dumps(event.__dict__, default=str),
            fired_at=event._fired_at,
        )
        return await super().dispatch(event)
```

Two caveats. `event.__dict__` includes `_fired_at` and
`_propagation_stopped`, so strip them if the log is user-facing. And the
write happens before listeners run — if the insert fails, no listener
runs at all, which turns your audit log into a single point of failure.
Wrap it in a `try` if the events matter more than the log.

##  What not to do

**Do not rely on `@listen(...)` to register.** It attaches attributes and
nothing else.

**Do not use events for work that must complete.** Listener failures are
logged and swallowed.

**Do not put slow work in a listener.** The dispatcher awaits every one
in turn.

**Do not carry model instances on an event.** Carry ids.

**Do not remove a field from an event class** without treating it as a
breaking change.

**Do not rely on `has_listeners()` for a specific type.** Any wildcard
makes it `True`.

**Do not use `stop_propagation()` for control flow** you could express as
a function call.

**Do not confuse this with `sillo.events`.** They are separate systems
with separate dispatchers.

##  Testing listeners

Listeners are ordinary async functions, so the useful tests do not
involve the dispatcher at all:

```python title="test the listener directly"
async def test_notify_customer_sends_tracking():
    await notify_customer(OrderShipped(order_id="42", tracking="1Z999"))
    assert outbox.last().body.contains("1Z999")
```

Test the *wiring* separately, and once, with a dispatcher you construct
in the test — not the application's shared one, which accumulates
registrations across tests and makes failures order-dependent:

```python title="test the registration"
async def test_checkout_dispatches_to_all_listeners():
    dispatcher = EventDispatcher()
    seen = []
    dispatcher.register(CheckoutCompleted, lambda e: seen.append(e))

    await dispatcher.dispatch(CheckoutCompleted(order_id=1, user_id=2, total_cents=100))
    assert len(seen) == 1
```

The failure this catches is the one the swallowing behaviour hides: a
listener that raises on every event still leaves `dispatch()` returning
normally, so a test that only asserts "checkout succeeded" passes while
nothing downstream works. Assert on the effect, not on the dispatch.

##  Performance notes

Dispatch is a dict lookup and a sequential loop. The dispatcher itself is
never your bottleneck; the listeners are, and they add up because they
run one after another.

Registration sorts the listener list on every `register()` call, which is
irrelevant at startup and worth avoiding in a hot path — do not register
listeners per request.

Wildcard listeners run for every event of every type. An audit wildcard
that writes a database row turns every dispatch into a write, which is a
meaningful cost on a high-traffic path. Sample it, batch it, or restrict
it to the event types you actually need.

##  API reference

| Member | Signature | Notes |
|---|---|---|
| `Event` | dataclass base | Adds `_fired_at`, `_propagation_stopped` |
| `Event.stop_propagation` | `() -> None` | Halts remaining listeners |
| `EventDispatcher.register` | `(event_type, callback, *, priority=0, name="")` | Higher priority fires first |
| `EventDispatcher.register_wildcard` | `(callback, *, priority=0)` | Receives every event |
| `EventDispatcher.forget` | `(event_type, callback) -> bool` | |
| `EventDispatcher.has_listeners` | `(event_type) -> bool` | `True` if any wildcard exists |
| `EventDispatcher.dispatch` | `(event) -> event` | Sequential; failures swallowed |
| `listen` | `(*events, priority=0)` | **Metadata only — does not register** |
| `ListenerRegistry` | `(dispatcher)` | `.on(pattern, cb)`, `.once(...)`, `.clear()` |
| `WildcardListener` | | Pattern matching on event class names |

##  Related

- [Work Overview](/guides/work/) — where the shared dispatcher lives in `app.state`
- [Jobs](/guides/work/jobs/) — what a critical listener should enqueue
- [Queue System](/guides/work/queue/) — durability for consequences that matter
- [Background Tasks](/guides/work/background/) — the other fire-and-forget option
- [Events (`sillo.events`)](/guides/events/) — the separate application-level emitter
