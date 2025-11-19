# Redis Integration

Redis integration for Nexios web framework, providing seamless caching, session storage, and data management capabilities with comprehensive dependency injection support.

## Features

- 🚀 **High-Performance Redis Client**: Async Redis client with connection pooling and health checks
- 🔄 **Dependency Injection**: Multiple DI patterns for clean, testable code
- 🏗️ **Connection Management**: Automatic connection lifecycle management
- 📊 **Data Structure Support**: Strings, Hashes, Lists, Sets, JSON operations
- ⚙️ **Configuration**: Environment-based and programmatic configuration
- 🛡️ **Error Handling**: Robust error handling with custom exceptions
- 🧪 **Testing Support**: Easy mocking and testing utilities
- 📈 **Monitoring**: Built-in connection health monitoring

## Installation

```bash
# Install with pip
pip install nexios-contrib-redis[redis]

# Or with uv (recommended)
uv add nexios-contrib[redis]
```

### Requirements

- Python 3.9+
- Nexios 2.11.3+
- Redis server (4.0+ recommended)
- redis-py (auto-installed)

## Quick Start

### Basic Setup

```python
from nexios import NexiosApp
from nexios_contrib.redis import init_redis

app = NexiosApp()

# Initialize Redis with default settings
init_redis(app)

@app.get("/cache/{key}")
async def get_cache(request: Request, response: Response, key: str):
    from nexios_contrib.redis import redis_get

    value = await redis_get(key)
    if value is None:
        return response.status(404).json({"error": "Key not found"})

    return {"key": key, "value": value}
```

### With Custom Configuration

```python
from nexios import NexiosApp
from nexios_contrib.redis import init_redis, RedisConfig

app = NexiosApp()

# Custom Redis configuration
config = RedisConfig(
    url="redis://localhost:6379/1",
    password="your_password",
    db=1,
    decode_responses=True
)

# Initialize with custom config
init_redis(app, config=config)
```

### Environment Configuration

```python
from nexios_contrib.redis import RedisConfig

# Load configuration from environment variables
config = RedisConfig.from_env()  # Looks for REDIS_* variables

# Or with custom prefix
config = RedisConfig.from_env("MY_REDIS_")
```

## Dependency Injection

### Basic Pattern

```python
from nexios import NexiosApp, Depend
from nexios_contrib.redis import get_redis

app = NexiosApp()

@app.get("/user/{user_id}")
async def get_user(
    request: Request,
    response: Response,
    user_id: str,
    redis: Depend(get_redis)  # Inject RedisClient
):
    # Use redis client directly
    cached_user = await redis.json_get(f"user:{user_id}")
    if cached_user:
        return {"user": cached_user, "source": "cache"}

    return {"user": {"id": user_id, "name": "Unknown"}, "source": "default"}
```

### Simplified Pattern

```python
from nexios import NexiosApp
from nexios_contrib.redis import RedisDepend

app = NexiosApp()

@app.get("/user/{user_id}")
async def get_user(
    request: Request,
    response: Response,
    user_id: str,
    redis: RedisClient = RedisDepend()  # Cleaner syntax
):
    user_data = await redis.json_get(f"user:{user_id}")
    return {"user": user_data or {"id": user_id, "name": "Unknown"}}
```

### Operation-Level Injection

```python
from nexios import NexiosApp
from nexios_contrib.redis import RedisOperationDepend

app = NexiosApp()

@app.get("/counter/{name}")
async def get_counter(
    request: Request,
    response: Response,
    name: str,
    counter_value: int = RedisOperationDepend("get", f"counter:{name}")
):
    # counter_value is already the result of redis.get(f"counter:{name}")
    return {"counter": name, "value": counter_value or 0}

@app.post("/counter/{name}/incr")
async def increment_counter(
    request: Request,
    response: Response,
    name: str,
    new_value: int = RedisOperationDepend("incr", f"counter:{name}", 1)
):
    # new_value is already the result of redis.incr(f"counter:{name}", 1)
    return {"counter": name, "value": new_value}
```

### Key-Based Injection

```python
from nexios import NexiosApp
from nexios_contrib.redis import RedisKeyDepend

app = NexiosApp()

@app.get("/user/{user_id}")
async def get_user(
    request: Request,
    response: Response,
    user_id: str,
    user_data: dict = RedisKeyDepend(
        f"user:{{user_id}}",  # Uses path parameter
        "json_get",
        {"name": "Unknown"}   # Default value
    )
):
    # user_data is already fetched from Redis with fallback
    return {"user": user_data}
```

### Cache Pattern

```python
from nexios import NexiosApp
from nexios_contrib.redis import RedisCacheDepend

app = NexiosApp()

@app.get("/expensive-computation/{param}")
async def expensive_computation(
    request: Request,
    response: Response,
    param: str,
    result: str = RedisCacheDepend(f"expensive:{param}", ttl=600)
):
    # In a real implementation, this would check cache first
    # and compute/fallback if not found
    return {"param": param, "result": f"computed_{param}"}
```

## Redis Operations

### String Operations

```python
from nexios_contrib.redis.utils import (
    redis_get, redis_set, redis_delete, redis_exists,
    redis_expire, redis_ttl, redis_incr, redis_decr
)

# Get and set strings
await redis_set("user:123:name", "John Doe", ex=3600)  # Expire in 1 hour
name = await redis_get("user:123:name")

# Atomic increment
count = await redis_incr("counter:page_views", 1)

# Check existence
exists = await redis_exists("user:123:name")  # Returns 1 if exists

# Delete keys
deleted = await redis_delete("user:123:name", "user:123:email")
```

### Hash Operations

```python
from nexios_contrib.redis.utils import redis_hget, redis_hset, redis_hgetall

# Set hash fields
await redis_hset("user:123", "name", "John Doe")
await redis_hset("user:123", "email", "john@example.com")

# Get single field
name = await redis_hget("user:123", "name")

# Get all fields
user_data = await redis_hgetall("user:123")
# Returns: {"name": "John Doe", "email": "john@example.com"}
```

### List Operations

```python
from nexios_contrib.redis import redis_lpush, redis_rpush, redis_lpop, redis_llen

# Add to list
await redis_lpush("messages", "Hello", "World")
await redis_rpush("messages", "!")

# Get list length
length = await redis_llen("messages")  # Returns 3

# Pop from list
first_msg = await redis_lpop("messages")  # Returns "World"
last_msg = await redis_rpop("messages")   # Returns "!"
```

### Set Operations

```python
from nexios_contrib.redis import redis_sadd, redis_smembers, redis_srem, redis_scard

# Add to set
added = await redis_sadd("tags", "python", "redis", "cache")

# Get all members
tags = await redis_smembers("tags")
# Returns: ["python", "redis", "cache"]

# Remove members
removed = await redis_srem("tags", "cache")

# Get cardinality
count = await redis_scard("tags")  # Returns 2
```

### JSON Operations

```python
from nexios_contrib.redis import redis_json_get, redis_json_set

# Set JSON data
user_data = {
    "name": "John Doe",
    "age": 30,
    "preferences": {"theme": "dark", "language": "en"}
}
await redis_json_set("user:123", ".", user_data)

# Get JSON data
user = await redis_json_get("user:123")
# Returns: {"name": "John Doe", "age": 30, "preferences": {...}}

# Get nested path
theme = await redis_json_get("user:123", ".preferences.theme")
```

### Advanced Operations

```python
from nexios_contrib.redis import redis_keys, redis_flushdb, redis_execute

# Get keys by pattern
user_keys = await redis_keys("user:*")

# Execute raw Redis commands
info = await redis_execute("INFO", "memory")

# Flush database (use with caution!)
await redis_flushdb()
```

## Configuration

### RedisConfig Options

```python
from nexios_contrib.redis import RedisConfig

config = RedisConfig(
    url="redis://localhost:6379/1",           # Redis URL
    db=1,                                     # Database number
    password="your_password",                 # Authentication
    decode_responses=True,                    # Decode to strings
    encoding="utf-8",                         # String encoding
    socket_timeout=5.0,                       # Socket timeout
    socket_connect_timeout=5.0,               # Connection timeout
    socket_keepalive=True,                    # TCP keepalive
    health_check_interval=30,                 # Health check interval
    max_connections=20,                       # Connection pool size
    retry_on_timeout=False,                   # Retry on timeout
)
```

### Environment Variables

Configure Redis using environment variables:

```bash
export REDIS_URL="redis://localhost:6379/1"
export REDIS_PASSWORD="your_secure_password"
export REDIS_DB="1"
export REDIS_DECODE_RESPONSES="true"
export REDIS_SOCKET_TIMEOUT="5.0"
export REDIS_MAX_CONNECTIONS="20"
```

Then load in code:

```python
from nexios_contrib.redis import RedisConfig

config = RedisConfig.from_env()
```

## Connection Management

### Automatic Lifecycle

The Redis client automatically manages connections:

```python
from nexios import NexiosApp
from nexios_contrib.redis import init_redis

app = NexiosApp()

# Initialize Redis - automatically handles startup/shutdown
init_redis(app, url="redis://localhost:6379")

# Redis client connects on first use and disconnects on app shutdown
```

### Manual Connection Control

```python
from nexios_contrib.redis import RedisClient, RedisConfig

config = RedisConfig(url="redis://localhost:6379")
client = RedisClient(config)

# Manual connection management
await client.connect()
try:
    await client.get("my_key")
finally:
    await client.close()
```

### Health Monitoring

```python
# Check connection health
from nexios_contrib.redis import get_redis

redis = get_redis()
is_healthy = await redis.ping()  # Returns True if connected
```

## Error Handling

```python
from nexios_contrib.redis import RedisConnectionError, RedisOperationError

try:
    value = await redis_get("my_key")
except RedisConnectionError as e:
    # Handle connection issues
    print(f"Connection failed: {e}")
except RedisOperationError as e:
    # Handle operation failures
    print(f"Operation failed: {e}")
```

## Examples

### Complete Application

```python
from nexios import NexiosApp
from nexios.http import Request, Response
from nexios_contrib.redis import (
    init_redis, RedisDepend, RedisOperationDepend
)

app = NexiosApp()

# Initialize Redis
init_redis(app, url="redis://localhost:6379", db=1)

@app.get("/user/{user_id}")
async def get_user(
    request: Request,
    response: Response,
    user_id: str,
    redis: RedisClient = RedisDepend()
):
    # Try cache first
    cached = await redis.json_get(f"user:{user_id}")
    if cached:
        return {"user": cached, "source": "cache"}

    # Simulate database fetch
    user_data = {
        "id": user_id,
        "name": "John Doe",
        "email": "john@example.com"
    }

    # Cache for 5 minutes
    await redis.json_set(f"user:{user_id}", ".", user_data, ex=300)

    return {"user": user_data, "source": "database"}

@app.post("/user/{user_id}/visit")
async def record_visit(
    request: Request,
    response: Response,
    user_id: str,
    visit_count: int = RedisOperationDepend("incr", f"user:{user_id}:visits", 1)
):
    return {"user_id": user_id, "visits": visit_count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Session Management

```python
from nexios import NexiosApp
from nexios_contrib.redis import RedisDepend
import json
import uuid

app = NexiosApp()
init_redis(app)

@app.post("/login")
async def login(request: Request, response: Response, redis: RedisClient = RedisDepend()):
    user_data = await request.json

    # Create session
    session_id = str(uuid.uuid4())
    session_data = {
        "user_id": user_data["id"],
        "username": user_data["username"],
        "login_time": "2024-01-01T00:00:00Z"
    }

    # Store session in Redis (expire in 24 hours)
    await redis.json_set(f"session:{session_id}", ".", session_data, ex=86400)

    return {"session_id": session_id}

@app.get("/profile")
async def get_profile(
    request: Request,
    response: Response,
    redis: RedisClient = RedisDepend()
):
    # Get session ID from header/cookie (implement as needed)
    session_id = request.headers.get("X-Session-ID")

    if not session_id:
        return response.status(401).json({"error": "No session"})

    # Get session data
    session_data = await redis.json_get(f"session:{session_id}")
    if not session_data:
        return response.status(401).json({"error": "Invalid session"})

    return {"user": session_data}
```

## Testing

### Mock Redis Client

```python
from unittest.mock import AsyncMock, patch
import pytest
from nexios_contrib.redis import get_redis

@pytest.fixture
def mock_redis():
    mock_client = AsyncMock()
    mock_client.get.return_value = "test_value"
    mock_client.set.return_value = True

    with patch('nexios_contrib.redis.get_redis', return_value=mock_client):
        yield mock_client

async def test_my_handler(mock_redis):
    # Your test code here
    pass
```

### Test Utilities

```python
# Test with real Redis (requires Redis server)
async def test_with_real_redis():
    from nexios_contrib.redis import init_redis, redis_set, redis_get

    app = NexiosApp()
    init_redis(app, url="redis://localhost:6379/15")  # Use test database

    await redis_set("test_key", "test_value")
    value = await redis_get("test_key")

    assert value == "test_value"
```

## Performance Tips

1. **Connection Pooling**: Redis client uses connection pooling by default
2. **Pipeline Operations**: Use Redis pipelines for multiple operations
3. **JSON Path Queries**: Use specific JSON paths instead of root "." when possible
4. **TTL Management**: Set appropriate TTL values to prevent memory bloat
5. **Key Naming**: Use consistent key naming patterns for better organization

## Troubleshooting

### Common Issues

**Connection Refused**
```bash
# Check if Redis is running
redis-cli ping

# Verify connection details
redis-cli -h localhost -p 6379 ping
```

**Authentication Failed**
```python
# Check password in Redis config
config = RedisConfig(
    url="redis://localhost:6379",
    password="your_correct_password"  # Ensure this matches Redis config
)
```

**Memory Issues**
```python
# Monitor Redis memory usage
info = await redis_execute("INFO", "memory")

# Set appropriate TTL values
await redis_set("temp_key", "value", ex=300)  # 5 minutes
```

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging

logging.getLogger("nexios.redis").setLevel(logging.DEBUG)
```

Built with ❤️ by the [@nexios-labs](https://github.com/nexios-labs) community.