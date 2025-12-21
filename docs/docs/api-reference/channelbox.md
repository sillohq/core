# ChannelBox

The `ChannelBox` class is a singleton manager for WebSocket channels in Nexios. It provides group-based channel management, allowing you to organize channels into groups and broadcast messages to all channels within a group.

## 📋 Class Definition

```python
class ChannelBox:
    CHANNEL_GROUPS: Dict[str, Any] = {}
    CHANNEL_GROUPS_HISTORY: Dict[str, Any] = {}
    HISTORY_SIZE: int = 1_048_576  # 1MB default
```

## 📊 Class Attributes

### CHANNEL_GROUPS: Dict[str, Any]
**Type**: `Dict[str, Dict[Channel, Any]]`  
**Description**: Storage for channel groups. Keys are group names, values are dictionaries of channels.

### CHANNEL_GROUPS_HISTORY: Dict[str, Any]
**Type**: `Dict[str, List[ChannelMessageDC]]`  
**Description**: Message history for each group when `save_history=True`.

### HISTORY_SIZE: int
**Type**: `int`  
**Default**: `1_048_576` (1MB)  
**Description**: Maximum size for group message history. Configurable via `CHANNEL_BOX_HISTORY_SIZE` environment variable.

## 🔧 Methods

### add_channel_to_group()
Add a channel to a specific group.

```python
@classmethod
async def add_channel_to_group(
    cls,
    channel: Channel,
    group_name: str = "default",
) -> ChannelAddStatusEnum
```

**Parameters:**
- `channel`: The Channel instance to add
- `group_name`: Name of the group (default: "default")

**Returns:**
- `ChannelAddStatusEnum.CHANNEL_ADDED`: New group created and channel added
- `ChannelAddStatusEnum.CHANNEL_EXIST`: Channel added to existing group

**Usage:**
```python
from nexios.websockets.channels import ChannelBox, Channel

# Add channel to default group
status = await ChannelBox.add_channel_to_group(channel)

# Add channel to specific group
status = await ChannelBox.add_channel_to_group(channel, "chat_room")
```

### remove_channel_from_group()
Remove a channel from a specific group.

```python
@classmethod
async def remove_channel_from_group(
    cls,
    channel: Channel,
    group_name: str,
) -> ChannelRemoveStatusEnum
```

**Parameters:**
- `channel`: The Channel instance to remove
- `group_name`: Name of the group

**Returns:**
- `ChannelRemoveStatusEnum.CHANNEL_REMOVED`: Channel removed successfully
- `ChannelRemoveStatusEnum.CHANNEL_DOES_NOT_EXIST`: Channel not found in group
- `ChannelRemoveStatusEnum.GROUP_REMOVED`: Channel removed and group deleted (was last channel)
- `ChannelRemoveStatusEnum.GROUP_DOES_NOT_EXIST`: Group doesn't exist

**Usage:**
```python
# Remove channel from group
status = await ChannelBox.remove_channel_from_group(channel, "chat_room")

if status == ChannelRemoveStatusEnum.GROUP_REMOVED:
    print("Group was deleted (no more channels)")
```

### group_send()
Send a message to all channels in a group.

```python
@classmethod
async def group_send(
    cls,
    group_name: str = "default",
    payload: Union[Dict[str, Any], str, bytes] = {},
    save_history: bool = False,
) -> GroupSendStatusEnum
```

**Parameters:**
- `group_name`: Name of the target group (default: "default")
- `payload`: Message to send (dict, str, or bytes)
- `save_history`: Whether to save message in group history

**Returns:**
- `GroupSendStatusEnum.GROUP_SEND`: Message sent successfully
- `GroupSendStatusEnum.NO_SUCH_GROUP`: Group doesn't exist

**Usage:**
```python
# Send JSON message to group
await ChannelBox.group_send(
    group_name="chat_room",
    payload={"type": "message", "text": "Hello everyone!"},
    save_history=True
)

# Send text message
await ChannelBox.group_send(
    group_name="notifications",
    payload="System maintenance in 5 minutes"
)
```

### show_groups()
Get all current channel groups.

```python
@classmethod
async def show_groups(cls) -> Dict[str, Any]
```

**Returns:**
- Dictionary of all groups and their channels

**Usage:**
```python
groups = await ChannelBox.show_groups()
for group_name, channels in groups.items():
    print(f"Group '{group_name}' has {len(channels)} channels")
```

### flush_groups()
Remove all groups and channels.

```python
@classmethod
async def flush_groups(cls) -> None
```

**Usage:**
```python
# Clear all groups (useful for testing or cleanup)
await ChannelBox.flush_groups()
```

### show_history()
Get message history for a group or all groups.

```python
@classmethod
async def show_history(
    cls,
    group_name: str = "",
) -> Dict[str, Any]
```

**Parameters:**
- `group_name`: Specific group name, or empty string for all groups

**Returns:**
- Message history for the specified group or all groups

**Usage:**
```python
# Get history for specific group
chat_history = await ChannelBox.show_history("chat_room")

# Get history for all groups
all_history = await ChannelBox.show_history()
```

### flush_history()
Clear all message history.

```python
@classmethod
async def flush_history(cls) -> None
```

**Usage:**
```python
# Clear all message history
await ChannelBox.flush_history()
```

### close_all_connections()
Close all WebSocket connections and clear groups.

```python
@classmethod
async def close_all_connections(cls) -> None
```

**Usage:**
```python
# Gracefully close all connections (e.g., during shutdown)
await ChannelBox.close_all_connections()
```

## 💡 Usage Examples

### Basic Group Management

```python
from nexios.websockets import WebSocket
from nexios.websockets.channels import ChannelBox, Channel

async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    
    # Create channel
    channel = Channel(websocket, payload_type="json")
    
    # Add to group
    await ChannelBox.add_channel_to_group(channel, "lobby")
    
    try:
        # Send welcome message to all in lobby
        await ChannelBox.group_send(
            group_name="lobby",
            payload={"type": "user_joined", "message": "New user joined the lobby"}
        )
        
        # Handle messages...
        while True:
            data = await websocket.receive_text()
            # Echo to all users in lobby
            await ChannelBox.group_send(
                group_name="lobby",
                payload={"type": "message", "data": data}
            )
            
    except Exception as e:
        print(f"Connection error: {e}")
    finally:
        # Remove from group when disconnecting
        await ChannelBox.remove_channel_from_group(channel, "lobby")
```

### Chat Room Implementation

```python
class ChatRoom:
    def __init__(self, room_name: str):
        self.room_name = room_name
        self.users = {}
    
    async def join_user(self, websocket: WebSocket, username: str):
        await websocket.accept()
        
        # Create channel for user
        channel = Channel(websocket, payload_type="json")
        self.users[username] = channel
        
        # Add to room group
        await ChannelBox.add_channel_to_group(channel, self.room_name)
        
        # Notify others
        await ChannelBox.group_send(
            group_name=self.room_name,
            payload={
                "type": "user_joined",
                "username": username,
                "message": f"{username} joined the room"
            },
            save_history=True
        )
        
        return channel
    
    async def leave_user(self, username: str):
        if username in self.users:
            channel = self.users[username]
            
            # Remove from group
            await ChannelBox.remove_channel_from_group(channel, self.room_name)
            
            # Notify others
            await ChannelBox.group_send(
                group_name=self.room_name,
                payload={
                    "type": "user_left",
                    "username": username,
                    "message": f"{username} left the room"
                }
            )
            
            del self.users[username]
    
    async def broadcast_message(self, username: str, message: str):
        await ChannelBox.group_send(
            group_name=self.room_name,
            payload={
                "type": "message",
                "username": username,
                "message": message,
                "timestamp": time.time()
            },
            save_history=True
        )

# Usage
chat_room = ChatRoom("general")

@app.websocket("/chat/{username}")
async def chat_endpoint(websocket: WebSocket):
    username = websocket.path_params["username"]
    
    try:
        channel = await chat_room.join_user(websocket, username)
        
        while True:
            data = await websocket.receive_json()
            if data["type"] == "message":
                await chat_room.broadcast_message(username, data["message"])
                
    except Exception as e:
        print(f"Chat error: {e}")
    finally:
        await chat_room.leave_user(username)
```

### Broadcasting System

```python
class BroadcastSystem:
    @staticmethod
    async def send_notification(message: str, target_groups: list[str] = None):
        """Send notification to specific groups or all groups"""
        if target_groups is None:
            # Send to all groups
            groups = await ChannelBox.show_groups()
            target_groups = list(groups.keys())
        
        for group_name in target_groups:
            await ChannelBox.group_send(
                group_name=group_name,
                payload={
                    "type": "notification",
                    "message": message,
                    "timestamp": time.time()
                }
            )
    
    @staticmethod
    async def send_system_message(message: str):
        """Send system message to all connected users"""
        groups = await ChannelBox.show_groups()
        
        for group_name in groups.keys():
            await ChannelBox.group_send(
                group_name=group_name,
                payload={
                    "type": "system",
                    "message": message,
                    "priority": "high"
                },
                save_history=True
            )

# Usage
broadcast = BroadcastSystem()

# Send to specific groups
await broadcast.send_notification(
    "Server maintenance in 10 minutes",
    target_groups=["lobby", "game_room_1"]
)

# Send to all users
await broadcast.send_system_message("New feature available!")
```

### Group Statistics

```python
class GroupStats:
    @staticmethod
    async def get_group_info():
        """Get information about all groups"""
        groups = await ChannelBox.show_groups()
        stats = {}
        
        for group_name, channels in groups.items():
            stats[group_name] = {
                "channel_count": len(channels),
                "channels": [
                    {
                        "uuid": str(channel.uuid),
                        "payload_type": channel.payload_type,
                        "created": channel.created,
                        "expires": channel.expires
                    }
                    for channel in channels.keys()
                ]
            }
        
        return stats
    
    @staticmethod
    async def get_total_connections():
        """Get total number of active connections"""
        groups = await ChannelBox.show_groups()
        total = sum(len(channels) for channels in groups.values())
        return total

# Usage
stats = GroupStats()

# Get detailed group information
group_info = await stats.get_group_info()
print(f"Active groups: {len(group_info)}")

# Get total connections
total_connections = await stats.get_total_connections()
print(f"Total active connections: {total_connections}")
```

### Message History Management

```python
class HistoryManager:
    @staticmethod
    async def get_recent_messages(group_name: str, limit: int = 10):
        """Get recent messages from group history"""
        history = await ChannelBox.show_history(group_name)
        if not history:
            return []
        
        # Return last N messages
        return history[-limit:] if len(history) > limit else history
    
    @staticmethod
    async def clear_old_history():
        """Clear history for groups with no active channels"""
        groups = await ChannelBox.show_groups()
        history = await ChannelBox.show_history()
        
        # Find groups in history but not in active groups
        inactive_groups = set(history.keys()) - set(groups.keys())
        
        for group_name in inactive_groups:
            # Clear history for inactive groups
            if group_name in ChannelBox.CHANNEL_GROUPS_HISTORY:
                del ChannelBox.CHANNEL_GROUPS_HISTORY[group_name]

# Usage
history_manager = HistoryManager()

# Get recent chat messages
recent_messages = await history_manager.get_recent_messages("chat_room", 20)

# Cleanup old history
await history_manager.clear_old_history()
```

### Application Shutdown Handler

```python
from nexios import NexiosApp

app = NexiosApp()

@app.on_event("shutdown")
async def shutdown_handler():
    """Gracefully close all WebSocket connections on shutdown"""
    print("Closing all WebSocket connections...")
    await ChannelBox.close_all_connections()
    print("All connections closed.")
```

## 📋 Status Enums

### ChannelAddStatusEnum
- `CHANNEL_ADDED`: Channel added to new group
- `CHANNEL_EXIST`: Channel added to existing group

### ChannelRemoveStatusEnum
- `CHANNEL_REMOVED`: Channel removed successfully
- `CHANNEL_DOES_NOT_EXIST`: Channel not found
- `GROUP_REMOVED`: Group deleted (was last channel)
- `GROUP_DOES_NOT_EXIST`: Group doesn't exist

### GroupSendStatusEnum
- `GROUP_SEND`: Message sent successfully
- `NO_SUCH_GROUP`: Target group doesn't exist

## ⚙️ Environment Configuration

### CHANNEL_BOX_HISTORY_SIZE
Set the maximum size for message history storage:

```bash
# Set to 2MB
export CHANNEL_BOX_HISTORY_SIZE=2097152

# Set to 512KB
export CHANNEL_BOX_HISTORY_SIZE=524288
```

## 🔍 See Also

- [Channel](channel.md) - Individual WebSocket channel management
- [WebSocket](websocket.md) - WebSocket connection handling
- [Consumer](consumer.md) - WebSocket message consumers