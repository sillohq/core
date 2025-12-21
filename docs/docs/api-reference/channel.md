# Channel

The `Channel` class represents a WebSocket connection in Nexios, providing methods for sending messages and managing connection lifecycle. It's used internally by the WebSocket system to handle individual client connections.

## 📋 Class Definition

```python
class Channel:
    def __init__(
        self,
        websocket: WebSocket,
        payload_type: str,
        expires: Optional[int] = None,
    )
```

## ⚙️ Constructor Parameters

### websocket: WebSocket
**Type**: `WebSocket`  
**Required**: Yes

The WebSocket connection instance that this channel wraps.

```python
from nexios.websockets import WebSocket

# Channel is typically created internally
channel = Channel(websocket=websocket, payload_type="json")
```

### payload_type: str
**Type**: `str`  
**Required**: Yes  
**Valid Values**: `"json"`, `"text"`, `"bytes"`

The type of payload this channel will send. Determines how messages are serialized.

```python
# JSON payload channel
json_channel = Channel(websocket, payload_type="json")

# Text payload channel  
text_channel = Channel(websocket, payload_type="text")

# Binary payload channel
bytes_channel = Channel(websocket, payload_type="bytes")
```

### expires: Optional[int]
**Type**: `int`  
**Default**: `None`

Time-to-live for the channel in seconds. If set, the channel will be considered expired after this duration.

```python
# Channel expires after 1 hour
channel = Channel(websocket, payload_type="json", expires=3600)

# Channel never expires
channel = Channel(websocket, payload_type="json", expires=None)
```

## 📊 Properties

### uuid: UUID
**Type**: `uuid.UUID`  
**Read-only**

Unique identifier for the channel, automatically generated.

```python
channel = Channel(websocket, payload_type="json")
print(f"Channel ID: {channel.uuid}")
```

### created: float
**Type**: `float`  
**Read-only**

Timestamp when the channel was created (Unix timestamp).

```python
import time

channel = Channel(websocket, payload_type="json")
age = time.time() - channel.created
print(f"Channel age: {age} seconds")
```

### websocket: WebSocket
**Type**: `WebSocket`  
**Read-only**

The underlying WebSocket connection.

```python
channel = Channel(websocket, payload_type="json")
client_info = channel.websocket.client
```

### payload_type: str
**Type**: `str`  
**Read-only**

The payload type for this channel.

```python
channel = Channel(websocket, payload_type="json")
print(f"Payload type: {channel.payload_type}")  # "json"
```

### expires: Optional[int]
**Type**: `int | None`  
**Read-only**

The expiration time in seconds, if set.

```python
channel = Channel(websocket, payload_type="json", expires=3600)
print(f"Expires in: {channel.expires} seconds")
```

## 🔧 Methods

### _send()
Send a message through the channel.

```python
async def _send(self, payload: Any) -> None
```

**Parameters:**
- `payload`: The message to send. Type depends on `payload_type`.

**Usage:**
```python
# Send JSON data
await channel._send({"message": "Hello", "user_id": 123})

# Send text data (if payload_type is "text")
await text_channel._send("Hello World")

# Send binary data (if payload_type is "bytes")
await bytes_channel._send(b"binary data")
```

### _is_expired()
Check if the channel has expired.

```python
async def _is_expired(self) -> bool
```

**Returns:**
- `bool`: True if the channel has expired, False otherwise.

**Usage:**
```python
channel = Channel(websocket, payload_type="json", expires=3600)

# Check if expired
if await channel._is_expired():
    print("Channel has expired")
else:
    print("Channel is still active")
```

## 💡 Usage Examples

### Basic Channel Usage

```python
from nexios.websockets import WebSocket, Channel

async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    
    # Create a channel for JSON messages
    channel = Channel(
        websocket=websocket,
        payload_type="json",
        expires=3600  # 1 hour
    )
    
    # Send a welcome message
    await channel._send({
        "type": "welcome",
        "message": "Connected successfully",
        "channel_id": str(channel.uuid)
    })
    
    # Keep connection alive
    try:
        while True:
            # Check if channel expired
            if await channel._is_expired():
                await channel._send({"type": "expired"})
                break
                
            # Wait for messages (simplified)
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"Channel error: {e}")
    finally:
        await websocket.close()
```

### Different Payload Types

```python
async def handle_different_payloads(websocket: WebSocket):
    await websocket.accept()
    
    # JSON channel for structured data
    json_channel = Channel(websocket, payload_type="json")
    await json_channel._send({
        "user": "john",
        "action": "login",
        "timestamp": time.time()
    })
    
    # Text channel for simple messages
    text_channel = Channel(websocket, payload_type="text")
    await text_channel._send("Simple text message")
    
    # Binary channel for file data
    bytes_channel = Channel(websocket, payload_type="bytes")
    await bytes_channel._send(b"Binary file content")
```

### Channel with Expiration

```python
import asyncio
import time

async def expiring_channel_example(websocket: WebSocket):
    await websocket.accept()
    
    # Channel expires after 30 seconds
    channel = Channel(
        websocket=websocket,
        payload_type="json",
        expires=30
    )
    
    start_time = time.time()
    
    while True:
        # Check expiration
        if await channel._is_expired():
            await channel._send({
                "type": "session_expired",
                "duration": time.time() - start_time
            })
            break
        
        # Send periodic updates
        await channel._send({
            "type": "heartbeat",
            "timestamp": time.time(),
            "remaining": channel.expires - (time.time() - channel.created)
        })
        
        await asyncio.sleep(5)
```

## 🔧 Integration with ChannelBox

Channels are typically managed by the `ChannelBox` class for group operations:

```python
from nexios.websockets.channels import ChannelBox

async def group_channel_example(websocket: WebSocket):
    await websocket.accept()
    
    # Create channel
    channel = Channel(websocket, payload_type="json")
    
    # Add to a group
    await ChannelBox.add_channel_to_group(channel, group_name="chat_room")
    
    # Send message to all channels in group
    await ChannelBox.group_send(
        group_name="chat_room",
        payload={"message": "New user joined", "user": "john"}
    )
    
    # Remove from group when done
    await ChannelBox.remove_channel_from_group(channel, group_name="chat_room")
```

## ⚠️ Error Handling

```python
async def robust_channel_handler(websocket: WebSocket):
    await websocket.accept()
    
    channel = Channel(websocket, payload_type="json")
    
    try:
        await channel._send({"status": "connected"})
        
        # Simulate some work
        await asyncio.sleep(10)
        
    except RuntimeError as e:
        # WebSocket connection closed
        print(f"Connection closed: {e}")
        
    except Exception as e:
        # Other errors
        print(f"Channel error: {e}")
        try:
            await channel._send({"error": "Internal error occurred"})
        except:
            pass  # Connection might be closed
    
    finally:
        # Cleanup if needed
        print(f"Channel {channel.uuid} cleanup")
```

## 🔄 Channel Lifecycle

```python
async def channel_lifecycle_example(websocket: WebSocket):
    await websocket.accept()
    
    # 1. Create channel
    channel = Channel(
        websocket=websocket,
        payload_type="json",
        expires=300  # 5 minutes
    )
    
    print(f"Channel created: {channel.uuid}")
    print(f"Created at: {channel.created}")
    
    # 2. Use channel
    await channel._send({"status": "active"})
    
    # 3. Monitor expiration
    while not await channel._is_expired():
        await channel._send({
            "heartbeat": time.time(),
            "age": time.time() - channel.created
        })
        await asyncio.sleep(30)
    
    # 4. Handle expiration
    await channel._send({"status": "expired"})
    await websocket.close()
```

## 📝 Channel Representation

```python
channel = Channel(websocket, payload_type="json", expires=3600)
print(repr(channel))
# Output: Channel uuid=UUID('...') payload_type='json' expires=3600
```

## 🔍 See Also

- [WebSocket](websocket.md) - WebSocket connection handling
- [ChannelBox](channelbox.md) - Channel group management
- [Consumer](consumer.md) - WebSocket message consumers