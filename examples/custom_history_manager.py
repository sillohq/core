"""
Custom History Manager Examples for Nexios WebSocket Channels

This file demonstrates how to create custom history managers for Nexios
WebSocket channels. You can implement any storage backend (Redis, database,
file system, etc.) by extending the BaseHistoryManager class.
"""

import json
import typing
from pathlib import Path

from nexios.websockets import BaseHistoryManager, ChannelBox
from nexios.websockets.utils import ChannelMessageDC


# =============================================================================
# Example 1: File-Based History Manager
# =============================================================================

class FileHistoryManager(BaseHistoryManager):
    """Store message history in JSON files on disk.
    
    Each group gets its own JSON file in the specified directory.
    Useful for persistence across restarts or debugging.
    
    Args:
        storage_dir: Directory to store history files (default: ./channel_history)
        max_messages: Maximum number of messages to keep per group (default: 1000)
    """

    def __init__(
        self,
        storage_dir: str = "./channel_history",
        max_messages: int = 1000,
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_messages = max_messages

    def _get_file_path(self, group_name: str) -> Path:
        """Get the file path for a group's history."""
        # Sanitize group name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in group_name)
        return self.storage_dir / f"{safe_name}.json"

    async def save_message(
        self,
        group_name: str,
        message: ChannelMessageDC,
    ) -> None:
        """Save a message to the group's JSON file."""
        file_path = self._get_file_path(group_name)
        
        # Load existing history
        history = []
        if file_path.exists():
            with open(file_path, "r") as f:
                history = json.load(f)
        
        # Add new message (convert dataclass to dict)
        history.append({
            "payload": message.payload,
            "uuid": str(message.uuid),
            "created": message.created.isoformat(),
        })
        
        # Trim if exceeds max
        if len(history) > self.max_messages:
            history = history[-self.max_messages:]
        
        # Save back to file
        with open(file_path, "w") as f:
            json.dump(history, f, indent=2)

    async def get_history(
        self,
        group_name: typing.Optional[str] = None,
    ) -> typing.Union[typing.List[typing.Dict], typing.Dict[str, typing.List[typing.Dict]]]:
        """Retrieve message history from files."""
        if group_name:
            file_path = self._get_file_path(group_name)
            if file_path.exists():
                with open(file_path, "r") as f:
                    return json.load(f)
            return []
        
        # Get all history files
        all_history = {}
        for file_path in self.storage_dir.glob("*.json"):
            group_name = file_path.stem
            with open(file_path, "r") as f:
                all_history[group_name] = json.load(f)
        
        return all_history

    async def flush_history(self, group_name: typing.Optional[str] = None) -> None:
        """Delete history files."""
        if group_name:
            file_path = self._get_file_path(group_name)
            if file_path.exists():
                file_path.unlink()
        else:
            # Delete all history files
            for file_path in self.storage_dir.glob("*.json"):
                file_path.unlink()


# =============================================================================
# Example 2: Redis History Manager (Commented - requires redis)
# =============================================================================

# Uncomment and install redis package to use:
# pip install redis

"""
import redis.asyncio as redis

class RedisHistoryManager(BaseHistoryManager):
    '''Store message history in Redis.
    
    Uses Redis lists for each group with automatic expiration.
    Excellent for distributed systems and high-performance scenarios.
    
    Args:
        redis_url: Redis connection URL (default: redis://localhost:6379)
        key_prefix: Prefix for Redis keys (default: "channel_history:")
        max_messages: Maximum messages per group (default: 1000)
        ttl: Time-to-live for history in seconds (default: 3600 = 1 hour)
    '''

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "channel_history:",
        max_messages: int = 1000,
        ttl: int = 3600,
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.max_messages = max_messages
        self.ttl = ttl
        self._client = None

    async def _get_client(self):
        '''Get or create Redis client.'''
        if self._client is None:
            self._client = await redis.from_url(self.redis_url)
        return self._client

    def _get_key(self, group_name: str) -> str:
        '''Get Redis key for a group.'''
        return f"{self.key_prefix}{group_name}"

    async def save_message(
        self,
        group_name: str,
        message: ChannelMessageDC,
    ) -> None:
        '''Save message to Redis list.'''
        client = await self._get_client()
        key = self._get_key(group_name)
        
        # Serialize message
        msg_data = json.dumps({
            "payload": message.payload,
            "uuid": str(message.uuid),
            "created": message.created.isoformat(),
        })
        
        # Add to list and trim
        async with client.pipeline() as pipe:
            await pipe.rpush(key, msg_data)
            await pipe.ltrim(key, -self.max_messages, -1)
            await pipe.expire(key, self.ttl)
            await pipe.execute()

    async def get_history(
        self,
        group_name: typing.Optional[str] = None,
    ) -> typing.Union[typing.List[typing.Dict], typing.Dict[str, typing.List[typing.Dict]]]:
        '''Retrieve messages from Redis.'''
        client = await self._get_client()
        
        if group_name:
            key = self._get_key(group_name)
            messages = await client.lrange(key, 0, -1)
            return [json.loads(msg) for msg in messages]
        
        # Get all history
        pattern = f"{self.key_prefix}*"
        all_history = {}
        
        async for key in client.scan_iter(match=pattern):
            group_name = key.decode().replace(self.key_prefix, "")
            messages = await client.lrange(key, 0, -1)
            all_history[group_name] = [json.loads(msg) for msg in messages]
        
        return all_history

    async def flush_history(self, group_name: typing.Optional[str] = None) -> None:
        '''Delete history from Redis.'''
        client = await self._get_client()
        
        if group_name:
            key = self._get_key(group_name)
            await client.delete(key)
        else:
            # Delete all history keys
            pattern = f"{self.key_prefix}*"
            async for key in client.scan_iter(match=pattern):
                await client.delete(key)

    async def close(self):
        '''Close Redis connection.'''
        if self._client:
            await self._client.close()
"""


# =============================================================================
# Usage Examples
# =============================================================================

def example_file_based_history():
    """Example: Using file-based history manager."""
    from nexios.websockets import ChannelBox
    
    # Set up file-based history
    file_manager = FileHistoryManager(
        storage_dir="./my_channel_history",
        max_messages=500,
    )
    ChannelBox.set_history_manager(file_manager)
    
    print("✓ File-based history manager configured!")
    print(f"  History will be stored in: ./my_channel_history/")


def example_no_history():
    """Example: Disable history to save memory."""
    from nexios.websockets import ChannelBox, NoOpHistoryManager
    
    # Disable history completely
    ChannelBox.set_history_manager(NoOpHistoryManager())
    
    print("✓ History disabled - messages will not be saved")


def example_custom_inmemory_size():
    """Example: Custom in-memory history with different size limit."""
    from nexios.websockets import ChannelBox, InMemoryHistoryManager
    
    # Use in-memory with 5MB limit
    memory_manager = InMemoryHistoryManager(history_size=5_242_880)  # 5MB
    ChannelBox.set_history_manager(memory_manager)
    
    print("✓ In-memory history with 5MB limit configured!")


if __name__ == "__main__":
    print("Nexios Custom History Manager Examples\n")
    print("=" * 60)
    
    print("\n1. File-Based History Manager:")
    example_file_based_history()
    
    print("\n2. Disable History:")
    example_no_history()
    
    print("\n3. Custom In-Memory Size:")
    example_custom_inmemory_size()
    
    print("\n" + "=" * 60)
    print("\nTo use in your app:")
    print("  1. Import: from nexios.websockets import ChannelBox")
    print("  2. Import your custom manager")
    print("  3. Call: ChannelBox.set_history_manager(your_manager)")
    print("  4. Use channels normally - history is handled automatically!")
