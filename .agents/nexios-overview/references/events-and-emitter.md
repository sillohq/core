# Nexios Events And Emitters

Use this reference when the request is about the Nexios event system itself rather than general app lifecycle.

## Table of Contents

1. [Pub Sub Basics](#pub-sub-basics)
2. [Subscribing](#subscribing)
3. [Emitting](#emitting)
4. [Custom Emitters](#custom-emitters)
5. [Removing Listeners](#removing-listeners)
6. [Priority, Once, and Namespaces](#priority-once-and-namespaces)
7. [Best Practices](#best-practices)

## Pub Sub Basics

Nexios events follow a publish-subscribe model:

```python
from nexios import NexiosApp

app = NexiosApp()

@app.events.on("user.created")
async def handle_user_created(user):
    print(f"User created: {user['name']}")
```

Teach events as loose coupling for side effects, not as the main request-path control flow.

## Subscribing

Use `on(...)` to register listeners:

```python
@app.events.on("invoice.paid")
async def invoice_paid(invoice):
    print(f"Paid invoice: {invoice['id']}")
```

This is the cleanest first example when introducing the feature.

## Emitting

Use `emit(...)` inside a handler or service:

```python
@app.post("/users")
async def create_user(request, response):
    payload = await request.json
    await app.events.emit("user.created", payload)
    return response.json(payload, status_code=201)
```

This is useful for analytics, email, logging, and follow-up work.

## Custom Emitters

Nexios also documents stand-alone emitters:

```python
from nexios.events import EventEmitter

emitter = EventEmitter("custom")

@emitter.on("cache.warmed")
async def handle_cache_warmed(payload):
    print(payload)
```

Use this when you want a separate event surface from `app.events`.

## Removing Listeners

```python
async def temporary_handler(data):
    print(data)

app.events.on("data.received", temporary_handler)
app.events.off("data.received", temporary_handler)
```

This matters when teaching lifecycle cleanup or temporary subscriptions.

## Priority, Once, And Namespaces

### Priority

```python
from nexios.events import EventPriority

events.on("data.received", temporary_handler, priority=EventPriority.HIGH)
```

### One-Time Listeners

```python
@emitter.once("first.login")
async def first_login(user):
    print(f"Welcome {user}")
```

### Namespaces

```python
ui = emitter.namespace("ui")

@ui.on("button.click")
async def handle_click(button):
    print(button)
```

Teach these as scaling tools for event-heavy applications.

## Best Practices

- Use events for side effects only
- Prefer `async def` listeners
- Keep the request path independent from event success where possible
- Use clear event names such as `user.created`, `invoice.paid`, or `email.sent`
