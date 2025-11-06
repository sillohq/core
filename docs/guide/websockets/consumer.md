---
title: WebSocket Consumers in Nexios
description: Nexios provides a powerful `WebSocketConsumer` class that simplifies building robust WebSocket endpoints. This class-based approach offers structure, reusability, and built-in channel management for your real-time applications.
head:
  - - meta
    - property: og:title
      content: WebSocket Consumers in Nexios
  - - meta
    - property: og:description
      content: Nexios provides a powerful `WebSocketConsumer` class that simplifies building robust WebSocket endpoints. This class-based approach offers structure, reusability, and built-in channel management for your real-time applications.
---

# 🎮 WebSocket Consumers in Nexios

Nexios provides a powerful `WebSocketConsumer` class that simplifies building robust WebSocket endpoints. This class-based approach offers structure, reusability, and built-in channel management for your real-time applications.

## 🏗️ Consumer Basics

The `WebSocketConsumer` class handles the complete connection lifecycle:

```python
from nexios.websockets.consumers import WebSocketConsumer

class ChatConsumer(WebSocketConsumer):
    encoding = "json"  # Auto-decode JSON messages
    
    async def on_connect(self, websocket: WebSocket):
        await websocket.accept()
        await self.join_group("general_chat")
        
    async def on_receive(self, websocket: WebSocket, data: typing.Any):
        await self.broadcast(data, "general_chat")
        
    async def on_disconnect(self, websocket: WebSocket, close_code: int):
        await self.leave_group("general_chat")
```

Key lifecycle methods:
- `on_connect`: Called when connection is established
- `on_receive`: Handles incoming messages
- `on_disconnect`: Cleans up when connection closes

## ✨ Core Features

### **Automatic Message Decoding**
Set `encoding` to automatically handle different message formats:

```python
class MyConsumer(WebSocketConsumer):
    encoding = "json"  # Also supports "text" or "bytes"
    
    async def on_receive(self, ws, data):
        # data is already parsed JSON
        print(data["message"])
```

### **Built-in Channel Management**
Each connection automatically gets a `Channel` instance:

```python
async def on_connect(self, ws):
    print(f"New channel ID: {self.channel.uuid}")
    print(f"Expires at: {self.channel.created + self.channel.expires}")
```

## 👥 Group Communication

### **Joining and Leaving Groups**
```python
async def on_connect(self, ws):
    await self.join_group("room_42")  # Add to group

async def on_disconnect(self, ws, code):
    await self.leave_group("room_42")  # Remove from group
```

### **Broadcasting Messages**
```python
async def on_receive(self, ws, data):
    await self.broadcast(
        {"user": "anon", "message": data},
        group_name="room_42",
        save_history=True
    )
```

### **Targeted Messaging**
```python
async def send_private_message(self, user_id, message):
    await self.send_to(user_id, {"private": message})
```

## 🚀 Advanced Usage

### **Custom Route Registration**
Convert consumers to routes easily:

```python
from nexios.routing import WebsocketRoute

# Register consumer as route
chat_route = ChatConsumer.as_route("/chat")
app.add_ws_route(chat_route)
```

### **Middleware Support**
Add middleware to your consumers:

### **Error Handling**
Override default error behavior:

```python
async def on_receive(self, ws, data):
    try:
        # Your logic
    except Exception as e:
        self.logger.error(f"Error: {e}")
        await ws.close(code=status.WS_1011_INTERNAL_ERROR)
```

## ✅ Best Practices

1. **Keep consumers focused** - One consumer per logical endpoint
2. **Use encoding** - Let the consumer handle message parsing
3. **Clean up groups** - Always leave groups in `on_disconnect`
4. **Add middleware** - For cross-cutting concerns like auth
5. **Log key events** - Connection, disconnection, and errors

## 💬 Example: Complete Chat Consumer

```python
class ChatConsumer(WebSocketConsumer):
    encoding = "json"
    
    async def on_connect(self, ws):
        user = ws.scope["user"]
        await ws.accept()
        await self.join_group(f"user_{user.id}")
        await self.broadcast(
            {"system": f"{user.name} joined"},
            group_name="lobby"
        )
        
    async def on_receive(self, ws, data):
        user = ws.scope["user"]
        await self.broadcast(
            {"user": user.name, "message": data["text"]},
            group_name="lobby"
        )
        
    async def on_disconnect(self, ws, code):
        user = ws.scope["user"]
        await self.leave_group(f"user_{user.id}")
        await self.broadcast(
            {"system": f"{user.name} left"},
            group_name="lobby"
        )
```

This pattern provides:
- Structured WebSocket handling
- Built-in channel/group management
- Easy integration with existing auth systems
- Clean separation of concerns