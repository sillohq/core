---
title: WebSockets Channels
description: Nexios provides a powerful command-line interface (CLI) that makes it easy to develop, test, and deploy your applications. This guide will walk you through using the CLI, starting with basic commands and gradually introducing the configuration system.
head:
  - - meta
    - property: og:title
      content: WebSockets Channels
  - - meta
    - property: og:description
      content: Nexios provides a powerful command-line interface (CLI) that makes it easy to develop, test, and deploy your applications. This guide covers the basics of the CLI, including configuration and advanced usage.
---

# 📺 Channels

WebSocket connections in Nexios are managed using the `Channel` class, which provides enhanced functionality for handling real-time communication. Channels wrap WebSocket connections with additional features like metadata, expiration, and structured message handling.

## ✨ Channel Features

- **Automatic Message Serialization**: Supports JSON, text, and binary payloads
- **Connection Lifecycle Management**: Built-in handling for connection states
- **Metadata Storage**: Attach custom data to channels
- **Expiration**: Automatic cleanup of inactive channels
- **Error Handling**: Built-in error handling and cleanup

## 🚀 Creating and Using a Channel

### 🏗️ Basic Channel Creation

```python
from datetime import timedelta
from nexios.websockets.channels import Channel, PayloadTypeEnum
from nexios.websockets.base import WebSocketDisconnect

@app.websocket("/chat")
async def chat_handler(ws: WebSocket):
    # Accept the WebSocket connection
    await ws.accept()

    # Create a channel with JSON payload and 30-minute expiration
    channel = Channel(
        websocket=ws,
        payload_type=PayloadTypeEnum.JSON,  # Can be JSON, TEXT, or BINARY
        expires=1800,  # 30 minutes (optional)
        metadata={"username": "anonymous"}  # Optional metadata
    )

    try:
        while True:
            # Receive and process messages
            data = await channel.receive()  # Automatically deserializes based on payload_type

            # Send a response (automatically serializes based on payload_type)
            await channel.send({"response": data, "timestamp": datetime.utcnow().isoformat()})

            # Update channel metadata if needed
            if "username" in data:
                channel.metadata["username"] = data["username"]

    except WebSocketDisconnect:
        print(f"Client disconnected: {channel.id}")
    except Exception as e:
        print(f"Error in chat handler: {e}")
    finally:
        # Clean up resources
        await channel.close()
```

### 🔧 Channel Methods and Properties

```python
# Get channel information
channel_id = channel.id  # UUID of the channel
is_active = channel.is_active  # Check if channel is still connected
created_at = channel.created  # When the channel was created
expires_at = channel.expires  # When the channel will expire

# Send different types of messages
await channel.send({"type": "message", "content": "Hello!"})  # JSON
await channel.send_text("Hello!")  # Plain text
await channel.send_bytes(b"binary_data")  # Binary data

# Receive messages (auto-deserialized based on payload_type)
data = await channel.receive()  # For JSON payloads
text = await channel.receive_text()  # For text payloads
binary = await channel.receive_bytes()  # For binary payloads

# Close the channel with an optional status code and reason
await channel.close(code=1000, reason="User left the chat")
```

### ⏰ Channel Expiration and Heartbeats

Channels can be configured to expire after a period of inactivity. To keep a channel alive, you can implement a heartbeat mechanism:

```python
@app.websocket("/chat-with-heartbeat")
async def chat_handler(ws: WebSocket):
    await ws.accept()

    # Channel with 5-minute expiration
    channel = Channel(
        websocket=ws,
        payload_type=PayloadTypeEnum.JSON,
        expires=300  # 5 minutes
    )

    try:
        while True:
            data = await channel.receive()

            # Handle heartbeat messages
            if data.get("type") == "heartbeat":
                # Reset the expiration timer
                channel.touch()
                await channel.send({"type": "heartbeat_ack"})
                continue

            # Process other messages...

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        await channel.close()
```

## ✅ Best Practices for Channels

1. **Always Close Connections**

   - Use try/finally blocks to ensure channels are properly closed
   - Handle WebSocketDisconnect exceptions gracefully

2. **Use Appropriate Payload Types**

   - Use JSON for structured data
   - Use TEXT for simple string messages
   - Use BINARY for file transfers or raw binary data

3. **Implement Heartbeats**

   - Keep long-lived connections alive with periodic heartbeats
   - Handle timeouts and reconnections on the client side

4. **Validate Input**

   - Always validate and sanitize incoming messages
   - Use Pydantic models for message validation

5. **Monitor Channel Health**
   - Track active channels and their status
   - Log connection events and errors
   - Implement rate limiting if needed
