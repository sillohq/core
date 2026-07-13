---
title: Events
description: Typed pub/sub event system — Event, EventDispatcher, listeners, wildcards, propagation, custom stores.
---

# Events (`sillo.work.queue.events`)

A typed pub/sub event system.  Events are `@dataclass` instances carrying
typed data.  Listeners are async callables registered per event type.
The `EventDispatcher` brokers between them with priority ordering,
wildcard matching, and propagation control.

## Why Events?

Events decouple side effects from the code that triggers them.  When an
order is shipped, you don't want the shipping handler to know about email
notifications, analytics tracking, inventory updates, and Slack alerts.
Instead, you **dispatch** an `OrderShipped` event and let **listeners**
handle their own concerns:

```python
# Shipping handler — one responsibility:
await dispatcher.dispatch(OrderShipped(order_id="42", tracking="1Z999"))

# Listeners — each handles one concern:
@listen(OrderShipped)
async def notify_customer(event): ...

@listen(OrderShipped)
async def update_analytics(event): ...

@listen(OrderShipped)
async def alert_slack(event): ...
```

## Defining Events

```python
from dataclasses import dataclass
from sillo.work.queue.events import Event

@dataclass
class OrderShipped(Event):
    order_id: str
    tracking_number: str
    carrier: str = "UPS"
```

## Listening

```python
from sillo.work.queue.events import EventDispatcher, listen

dispatcher = EventDispatcher()

@listen(OrderShipped)
async def handle(event: OrderShipped):
    await email.send(...)

dispatcher.register(OrderShipped, handle, priority=10)
```

## Dispatching

```python
await dispatcher.dispatch(OrderShipped(order_id="42", tracking="1Z999"))

# Stop remaining listeners:
event.stop_propagation()
```

## Priority

```python
dispatcher.register(EventType, high_prio, priority=100)  # fires first
dispatcher.register(EventType, low_prio, priority=0)     # fires last
```

## Wildcards

```python
from sillo.work.queue.listener import ListenerRegistry

registry = ListenerRegistry(dispatcher)
registry.on("Order*", handle_any_order)
registry.once("UserRegistered", send_welcome)
```

## Real-World: Checkout Handler

```python
@dataclass
class CheckoutCompleted(Event):
    order_id: str; user_id: str; total: float

dispatcher = EventDispatcher()

@listen(CheckoutCompleted)
async def create_invoice(event): ...

@listen(CheckoutCompleted)
async def update_inventory(event): ...

@listen(CheckoutCompleted)
async def schedule_delivery(event): ...

@app.post("/checkout")
async def checkout(request, response):
    order = await create_order(...)
    await dispatcher.dispatch(CheckoutCompleted(
        order_id=order.id, user_id=order.user_id, total=order.total,
    ))
    return response.json({"order_id": order.id}, status_code=201)
```

## Custom Event Store

```python
class PersistentDispatcher(EventDispatcher):
    async def dispatch(self, event):
        await db.events.insert({"type": type(event).__name__, "data": event.__dict__})
        return await super().dispatch(event)
```
