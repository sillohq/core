---
title: Groups
icon: websocket
description: >
    The **ChannelBox** class in Nexios provides powerful tools for organizing WebSocket channels into groups, enabling features like broadcasting, history tracking, and targeted messaging.  
head:
  - - meta
    - property: og:title
      content: Groups
    - property: og:description
      content: The **ChannelBox** class in Nexios provides powerful tools for organizing WebSocket channels into groups, enabling features like broadcasting, history tracking, and targeted messaging.  
---

# 👥 Groups

The **ChannelBox** class in Nexios provides powerful tools for organizing WebSocket channels into groups, enabling features like broadcasting, history tracking, and targeted messaging.  

---  

## ✨ Key Features of ChannelBox  

| Feature               | Description                                                                 |  
|-----------------------|-----------------------------------------------------------------------------|  
| **Group Management**  | Organize channels into named groups (e.g., `chat_room_1`, `notifications`). |  
| **Broadcasting**      | Send messages to all channels in a group with one call.                     |  
| **Message History**   | Store and retrieve past messages for replay or synchronization.             |  
| **Auto-Cleanup**      | Remove expired or disconnected channels automatically.                      |  

---  

## 🚀 Basic ChannelBox Usage  

## Adding Channels to Groups
```python  
from nexios.websockets.channels import ChannelBox  

@app.websocket("/chat/{room_id}")  
async def chat_room(ws: WebSocket):  
    await ws.accept()  
    room_id = ws.path_params["room_id"]  
    channel = Channel(websocket=ws, payload_type="json")  

    # Add channel to a group (e.g., "chat_room_42")  
    await ChannelBox.add_channel_to_group(channel, group_name=f"chat_{room_id}")  

    try:  
        while True:  
            data = await ws.receive_json()  
            # Broadcast to the entire room  
            await ChannelBox.group_send(  
                group_name=f"chat_{room_id}",  
                payload={"user": "Anonymous", "message": data["text"]},  
                save_history=True  # Store in history  
            )  
    finally:  
        # Remove on disconnect  
        await ChannelBox.remove_channel_from_group(channel, group_name=f"chat_{room_id}")  
```  

## 📤 Broadcasting Messages  
Send to all channels in a group:  
```python  
await ChannelBox.group_send(  
    group_name="notifications",  
    payload={"alert": "Server maintenance in 5 minutes"},  
    save_history=False  
)  
```  

### 📊 Checking Group Status  
```python  
# List all active groups  
groups = await ChannelBox.show_groups()  

# Count channels in a group  
room_channels = await ChannelBox.show_groups().get("chat_room_42", {})  
num_users = len(room_channels)  
```  

---  

## 📜 Message History  

ChannelBox can store sent messages for later retrieval:  

### **1. Saving History**  
Enable with `save_history=True` in `group_send()`:  
```python  
await ChannelBox.group_send(  
    group_name="chat_general",  
    payload={"user": "Alice", "message": "Hello!"},  
    save_history=True  # Saved to history  
)  
```  

### **2. Retrieving History**  
```python  
# Get last 10 messages from a group  
history = await ChannelBox.show_history("chat_general")  
recent_messages = history[-10:] if history else []  
```  

### **3. Controlling History Size**  
Set max history size via environment variable:  
```python  
import os  
os.environ["CHANNEL_BOX_HISTORY_SIZE"] = "5242880"  # 5MB limit  
```  

---  



## 🎯 Targeted Messaging  
Send to specific channels by UUID:  
```python  
await ChannelBox.send_to(  
    channel_id=uuid.UUID("550e8400-e29b-41d4-a716-446655440000"),  
    payload={"private": "This is a secret!"}  
)  
```  

## 🌍 Global Operations  
```python  
# Close all WebSocket connections  
await ChannelBox.close_all_connections()  

# Clear all message history  
await ChannelBox.flush_history()  
```  

---  

