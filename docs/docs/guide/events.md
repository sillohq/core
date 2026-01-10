---
title: Introduction to the Event System
description: The Nexios event system provides a powerful way to implement loosely coupled, event-driven architectures in your applications. It allows components to communicate without direct dependencies, making your code more maintainable and flexible.
head:
  - - meta
    - property: og:title
      content: Introduction to the Event System
  - - meta
    - property: og:description
      content: The Nexios event system provides a powerful way to implement loosely coupled, event-driven architectures in your applications. It allows components to communicate without direct dependencies, making your code more maintainable and flexible.
---
# Introduction to the Event System

The Nexios event system provides a powerful way to implement loosely coupled, event-driven architectures in your applications. It allows components to communicate without direct dependencies, making your code more maintainable and flexible.

## 🚀 Basic Event Usage

```python
from nexios import NexiosApp

app = NexiosApp()

@app.events.on("user.created")
async def handle_user_created(user):
    print(f"User created: {user['name']}")

# Trigger the event
app.events.emit("user.created", {"name": "Bob"})
```

At its core, Nexios events implement the [publish-subscribe (pub-sub) pattern](https://en.wikipedia.org/wiki/Publish%E2%80%93subscribe_pattern).

::: warning Events are for Side Effects ONLY
Events should be used primarily for side effects (e.g., sending emails, tracking analytics, logging) that do not block the main request flow. Avoid using events to modify data that the main request cycle depends on.
:::

## 📡 Subscribing to Events

To subscribe to an event, use the `on` method:

```python{3}
from nexios import NexiosApp
app = NexiosApp()
@app.events.on("user.created")
async def handle_user_created(user):
    print(f"User created: {user['name']}")
```

This allows you to register a function that will be called when the "user.created" event is emitted.

## 📤 Emitting Events

To emit an event, use the `emit` method:

```python{3}
@app.post("/users")
async def create_user(req, res):
    await app.events.emit("user.created", {"name": "Bob"})
    ...
```

This endpoint will emit the "user.created" event when a new user is created. The `handle_user_created` function will then be called with the user data.

## ⚙️ Managing Event Instances

Each event is associated with a specific event emitter instance. This means that you can create multiple event emitters and manage their events independently.

The `NexiosApp` and `Router` classes provide a default event emitter instance called `events`, but you can also create your own event emitters.

```python{3}
from nexios import NexiosApp
from nexios.events import EventEmitter

app = NexiosApp()

emitter = EventEmitter("custom")

emitter.on("user.created")
async def handle_user_created(user):
    print(f"User created: {user['name']}")

emitter.emit("user.created", {"name": "Bob"})
```

## 🗑️ Removing Event Listeners

You can remove event listeners when they're no longer needed:

```python
# Define handler
async def temporary_handler(data):
    print(f"Processing data: {data}")

# Add handler
app.events.on("data.received", temporary_handler)

# Later, remove the handler
app.events.off("data.received", temporary_handler)

# Or remove all handlers for an event
app.events.off("data.received")
```

## ⭐ Priority Listeners

You can set a priority for event listeners. The higher the priority, the earlier the listener is called. By default, listeners are called in the order they are added.

```python
from nexios.events import EventPriority
events.on("data.received", temporary_handler, priority=EventPriority.LOW)
events.on("data.received", temporary_handler, priority=EventPriority.MEDIUM)
events.on("data.received", temporary_handler, priority=EventPriority.HIGH)
```

## 🎯 One-time Listeners

```python
@emitter.once('first.login')  # Special decorator
def first_login(user):
    print(f"🎉 Welcome {user}")

emitter.emit('first.login', 'Alice')  # Fires
emitter.emit('first.login', 'Alice')  # Doesn't fire
```

## 🏷️ Namespaces

For more complex applications, you can create separate event namespaces:

```python
from nexios.events import EventEmitter
app = EventEmitter()
ui = app.namespace('ui')  # Creates 'ui' namespace

@ui.on('button.click')  # Actually listens to 'ui:button.click'
def handle_click(btn):
    print(f"{btn} clicked!")

# All these work:
ui.emit('button.click', 'submit')
app.emit('ui:button.click', 'submit')  # Same as above

```

## 🔄 Asynchronous Events

Nexios fully supports async event handlers.

```python
from nexios.events import AsyncEventEmitter

events = AsyncEventEmitter()
@events.on('user.created')
async def handle_user_created(user):
    print(f"User created: {user['name']}")
```

::: tip Always Use Async Handlers
To avoid blocking the main application loop, always use `async def` for your event listeners. Synchronous listeners will block the entire event loop while they execute, degrading performance.
:::
