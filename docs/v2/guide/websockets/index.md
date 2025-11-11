---
title: WebSockets
icon: websocket
description: >
    WebSockets enable real-time, bidirectional communication between clients and servers, making them ideal for applications like chat systems, live dashboards, and notifications. Nexios provides a robust WebSocket implementation with intuitive APIs for managing connections, channels, and groups.
head:
  - - meta
    - property: og:title
      content: WebSockets
    - property: og:description
      content: WebSockets enable real-time, bidirectional communication between clients and servers, making them ideal for applications like chat systems, live dashboards, and notifications. Nexios provides a robust WebSocket implementation with intuitive APIs for managing connections, channels, and groups.
---
## Basic WebSocket Setup

```python
from nexios import NexiosApp
app = NexiosApp()
@app.ws_route("/ws")
async def ws_handler(ws):
    await ws.accept()
    ...
```

Websocket routing follows the same pattern as other http routes making it easy to use.

::: tip WebSocket Lifecycle

1. **Connection**: Client initiates WebSocket connection
2. **Acceptance**: Server accepts the connection
3. **Communication**: Bidirectional message exchange
4. **Disconnection**: Connection closes (graceful or abrupt)
5. **Cleanup**: Resources are cleaned up
   :::

Websocket also pocessed a `WebsocketRoute` class for more complex routing needs

You can use it like this

```python
from nexios import NexiosApp
app = NexiosApp()
async def ws_handler(ws):
    await ws.accept()
    ...
app.add_ws_route(WebsocketRoute("/ws", ws_handler))
```

## Websocket Router

Websocket also support the `Router` class

```python
from nexios.routing import Router
router = Router()
router.add_ws_route("/ws", ws_handler)
app.mount_router(router, "/ws")
```

::: tip 💡Tip
You can also pass a list of `WebsocketRoute` to the `Router` constructor 
```python
from nexios.routing import Router
router = Router([
    WebsocketRoute("/ws", ws_handler),
    WebsocketRoute("/ws2", ws_handler2),
])
```

:::

::: tip 💡Tip
You can also add prefix to the `Router` similar to using regular `Router`

```python
from nexios.routing import Router
router = Router(prefix="/ws")
router.add_ws_route("/ws", ws_handler)
router.add_ws_route("/ws2", ws_handler2)
app.mount_router(router, "/ws-overide") #this will override /ws

```

:::

## Sending Messages

the `WebSocket` class has some methods that can be used to send messages to a connected client.

```python
from nexios.websockets.base import WebSocket

async def ws_handler(ws):
    await ws.accept()
    await ws.send_text("Hello World")
    # await ws.send_json({"message": "Hello World"})
    # await ws.send_bytes(b"Hello World")
```

## Receiving Messages

The `WebSocket` class has some methods that can be used to receive messages from a connected client.

```python
from nexios.websockets.base import WebSocket

async def ws_handler(ws):
    await ws.accept()
    message = await ws.receive_text()
    # message = await ws.receive_json()
    # message = await ws.receive_bytes()
    print(message)
```

Nexios supports three primary message formats:

**1. Text Messages**

```python
text_data = await ws.receive_text()
await ws.send_text(f"Received: {text_data}")
```

**2. Binary Messages**

```python
binary_data = await ws.receive_bytes()
await ws.send_bytes(binary_data)  # Echo binary data
```

**3. JSON Messages**

```python
json_data = await ws.receive_json()
await ws.send_json({"status": "success", "data": json_data})
```

---

## Connection Lifecycle

A WebSocket connection follows a clear lifecycle:

**Accept the Connection**

```python
await ws.accept()
```

### Receive Messages (Loop)

```python
while True:
    data = await ws.receive()
    # Process data
```

## Handle Disconnections

```python
from nexios.websockets.base import WebSocketDisconnect
except WebSocketDisconnect:
    print("Client disconnected")
```

### Close the Connection

```python
finally:
    await ws.close()
```
