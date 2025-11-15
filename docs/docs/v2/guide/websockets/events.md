---
title: Integrating Events with WebSockets in Nexios
description: Nexios combines WebSockets with a powerful event system to create reactive, real-time applications. This integration lets different parts of your system communicate seamlessly while keeping code clean and maintainable.
head:
  - - meta
    - property: og:title
      content: Integrating Events with WebSockets in Nexios
  - - meta
    - property: og:description
      content: Nexios combines WebSockets with a powerful event system to create reactive, real-time applications. This integration lets different parts of your system communicate seamlessly while keeping code clean and maintainable.
---

# **Integrating Events with WebSockets in Nexios**  

Nexios combines WebSockets with a powerful event system to create reactive, real-time applications. This integration lets different parts of your system communicate seamlessly while keeping code clean and maintainable.  

---

## **Basic WebSocket Event Integration**  

### **Emitting Events from Connections**  
WebSocket handlers can trigger events that other components can react to:  

```python
@app.ws_route("/chat")
async def chat_handler(ws: WebSocket):
    await ws.accept()
    await app.events.emit("ws.connected", {"client": ws.client})  # Connection event
    
    try:
        while True:
            message = await ws.receive_json()
            await app.events.emit("chat.message", message)  # Message event
    except Exception as e:
        await app.events.emit("ws.error", {"error": str(e)})  # Error event
```

### **Reacting to Events in Handlers**  
Subscribe to events and push updates to connected clients:  

```python
@app.events.on("notification.created")  
async def push_notification(notification):
    await ChannelBox.group_send(
        group_name="notifications",
        payload=notification
    )
```

---

## **Advanced Integration Patterns**  

### **Namespaced WebSocket Events**  
Create isolated event spaces for better organization:  

```python
ws_events = app.events.namespace("websocket")

@ws_events.on("message.received")  
async def process_message(msg):
    print(f"New message: {msg['content']}")

# In handler:
await ws_events.emit("message.received", {"content": "Hello"})
```

### **One-Time Connection Events**  
Execute actions only when a connection first starts:  

```python
@app.events.once("connection.init")  
async def send_welcome(data):
    await data["ws"].send_json({"type": "welcome"})

# During connection:
await app.events.emit("connection.init", {"ws": ws})
```

---

## **Error Handling with Events**  

Centralize error management through events:  

```python
@app.events.on("ws.error")  
async def handle_errors(error):
    logging.error(f"WebSocket failure: {error}")
    # Alert monitoring systems

# In handlers:
try:
    ...
except Exception as e:
    await app.events.emit("ws.error", {"error": str(e)})
```

---

## **Complete Chat Application Example**  

```python
@app.ws_route("/chat/{room}")  
async def chat_room(ws: WebSocket):
    room = ws.path_params["room"]
    channel = Channel(websocket=ws)
    await ChannelBox.add_channel_to_group(channel, f"chat_{room}")

    try:
        while True:
            msg = await ws.receive_json()
            await app.events.emit("room.message", {
                "room": room,
                "message": msg
            })
    finally:
        await ChannelBox.remove_channel_from_group(channel, f"chat_{room}")

@app.events.on("room.message")  
async def broadcast(msg):
    await ChannelBox.group_send(
        group_name=f"chat_{msg['room']}",
        payload=msg
    )
```

---
