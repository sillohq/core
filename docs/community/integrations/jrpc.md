# JSON-RPC Integration

Lightweight helpers for running JSON-RPC 2.0 over HTTP with Nexios.

This contrib provides:

- A JSON-RPC 2.0 server implementation
- A JSON-RPC client for making remote calls
- Method registration and error handling
- No external dependencies required

## Installation

Install the JSON-RPC contrib with Nexios:

```bash
pip install nexios_contrib
```

This contrib uses only standard library modules for maximum compatibility.

## Quick Start

### Server Setup

```python
# server.py
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.registry import get_registry

def main():
    # Create Nexios app
    app = NexiosApp()

    # Get the global registry and register methods
    registry = get_registry()

    @registry.register("add")
    def add(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b

    @registry.register("echo")
    async def echo(msg: str) -> str:
        """Echo back the input message."""
        return f"Server says: {msg}"

    # Mount the JSON-RPC plugin
    JsonRpcPlugin(app, {"path_prefix": "/rpc"})

    print("🚀 JSON-RPC Server starting on port 3020...")
    print("📋 Available JSON-RPC methods:")
    print("   - add(a, b) -> int")
    print("   - echo(msg) -> str")
    print("\n🔗 JSON-RPC endpoint: http://localhost:3020/rpc")

    # Start the server
    app.run(host="0.0.0.0", port=3020)

if __name__ == "__main__":
    main()
```

### Client Usage

```python
# client.py
import asyncio
from nexios_contrib.jrpc.client import JsonRpcClient

async def main() -> None:
    async with JsonRpcClient("http://localhost:3020/rpc") as client:
        result = await client.call("add", a=2, b=3)
        print(result)  # Output: 5

        result = await client.call("echo", msg="Hello, server!")
        print(result)  # Output: Server says: Hello, server!

if __name__ == "__main__":
    asyncio.run(main())
```

## Server Implementation

### Method Registration

```python
from nexios_contrib.jrpc.registry import get_registry

registry = get_registry()

# Register synchronous methods
@registry.register("multiply")
def multiply(x: float, y: float) -> float:
    """Multiply two numbers."""
    return x * y

# Register asynchronous methods
@registry.register("fetch_data")
async def fetch_data(url: str) -> dict:
    """Fetch data from a URL."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# Register with custom name
@registry.register("get_time")
def current_timestamp() -> float:
    """Get current timestamp."""
    import time
    return time.time()
```

### Error Handling

```python
from nexios_contrib.jrpc.exceptions import JsonRpcError

@registry.register("divide")
def divide(a: float, b: float) -> float:
    """Divide two numbers."""
    if b == 0:
        raise JsonRpcError(
            code=-32602,  # Invalid params
            message="Division by zero",
            data={"dividend": a, "divisor": b}
        )
    return a / b

@registry.register("validate_email")
def validate_email(email: str) -> bool:
    """Validate email format."""
    import re
    
    if not isinstance(email, str):
        raise JsonRpcError(
            code=-32602,
            message="Invalid parameter type",
            data={"expected": "string", "received": type(email).__name__}
        )
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

### Advanced Server Configuration

```python
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.registry import Registry

app = NexiosApp()

# Create custom registry
custom_registry = Registry()

@custom_registry.register("custom_method")
def custom_method(param: str) -> str:
    return f"Custom: {param}"

# Configure JSON-RPC plugin
JsonRpcPlugin(app, {
    "path_prefix": "/api/rpc"
})
```

## Client Implementation

### Basic Client Usage

```python
import asyncio
from nexios_contrib.jrpc.client import JsonRpcClient

async def example_client():
    # Create client
    client = JsonRpcClient("http://localhost:3020/rpc")
    
    try:
        # Single method call
        result = await client.call("add", a=10, b=20)
        print(f"10 + 20 = {result}")
        
        # Method call with keyword arguments
        result = await client.call("echo", msg="Hello World")
        print(f"Echo: {result}")
        
        # Method call with positional arguments
        result = await client.call("multiply", 3.14, 2.0)
        print(f"3.14 * 2.0 = {result}")
        
    finally:
        await client.close()

# Or use as context manager
async def context_manager_example():
    async with JsonRpcClient("http://localhost:3020/rpc") as client:
        result = await client.call("add", a=5, b=7)
        print(f"5 + 7 = {result}")

asyncio.run(example_client())
```



### Error Handling in Client

```python
from nexios_contrib.jrpc.exceptions import JsonRpcError, JsonRpcClientError

async def error_handling_example():
    async with JsonRpcClient("http://localhost:3020/rpc") as client:
        try:
            # This will raise an error
            result = await client.call("divide", a=10, b=0)
        except JsonRpcError as e:
            print(f"JSON-RPC Error: {e.message} (Code: {e.code})")
            if e.data:
                print(f"Error data: {e.data}")
        except JsonRpcClientError as e:
            print(f"Client Error: {e}")
```


## Integration with Nexios

### Using with Nexios Dependency Injection

```python
from nexios import NexiosApp, Depend
from nexios_contrib.jrpc.registry import get_registry

app = NexiosApp()

# Dependency function
def get_database():
    # Return database connection
    return {"connection": "db_connection"}

registry = get_registry()

@registry.register("get_user")
async def get_user(user_id: int, db=Depend(get_database)):
    """Get user from database."""
    # Use database connection
    return {"id": user_id, "name": "John Doe", "db": db["connection"]}
```

### Middleware Integration

```python
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin

app = NexiosApp()

# Add Nexios middleware
async def logging_middleware(request, response, call_next):
    print(f"JSON-RPC request: {request.method} {request.url}")
    response = await call_next()
    print(f"JSON-RPC response: {response.status_code}")
    return response
app.add_middleware(logging_middleware)

# JSON-RPC will use Nexios middleware
JsonRpcPlugin(app, {"path_prefix": "/rpc"})
```

## Examples

### Calculator Service

```python
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.registry import get_registry
from nexios_contrib.jrpc.exceptions import JsonRpcError

app = NexiosApp()
registry = get_registry()

@registry.register("add")
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

@registry.register("subtract")
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b

@registry.register("multiply")
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

@registry.register("divide")
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise JsonRpcError(
            code=-32602,
            message="Division by zero is not allowed"
        )
    return a / b

@registry.register("power")
def power(base: float, exponent: float) -> float:
    """Raise base to the power of exponent."""
    return base ** exponent

JsonRpcPlugin(app, {"path_prefix": "/calc"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

### User Management Service

```python
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.registry import get_registry
from nexios_contrib.jrpc.exceptions import JsonRpcError
import uuid

app = NexiosApp()
registry = get_registry()

# In-memory user storage (use database in production)
users = {}

@registry.register("create_user")
def create_user(name: str, email: str) -> dict:
    """Create a new user."""
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "name": name,
        "email": email
    }
    users[user_id] = user
    return user

@registry.register("get_user")
def get_user(user_id: str) -> dict:
    """Get user by ID."""
    if user_id not in users:
        raise JsonRpcError(
            code=-32602,
            message="User not found",
            data={"user_id": user_id}
        )
    return users[user_id]

@registry.register("list_users")
def list_users() -> list:
    """List all users."""
    return list(users.values())

@registry.register("update_user")
def update_user(user_id: str, name: str = None, email: str = None) -> dict:
    """Update user information."""
    if user_id not in users:
        raise JsonRpcError(
            code=-32602,
            message="User not found",
            data={"user_id": user_id}
        )
    
    user = users[user_id]
    if name is not None:
        user["name"] = name
    if email is not None:
        user["email"] = email
    
    return user

@registry.register("delete_user")
def delete_user(user_id: str) -> bool:
    """Delete user by ID."""
    if user_id not in users:
        raise JsonRpcError(
            code=-32602,
            message="User not found",
            data={"user_id": user_id}
        )
    
    del users[user_id]
    return True

JsonRpcPlugin(app, {"path_prefix": "/users"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

## Testing

### Testing JSON-RPC Methods

```python
import pytest
from nexios_contrib.jrpc.registry import Registry

def test_calculator_methods():
    registry = Registry()
    
    @registry.register("add")
    def add(a: float, b: float) -> float:
        return a + b
    
    # Test method registration
    assert "add" in registry.methods
    
    # Test method execution
    result = registry.call("add", {"a": 2, "b": 3})
    assert result == 5

@pytest.mark.asyncio
async def test_async_methods():
    registry = Registry()
    
    @registry.register("async_add")
    async def async_add(a: int, b: int) -> int:
        return a + b
    
    result = await registry.call_async("async_add", {"a": 5, "b": 7})
    assert result == 12
```


Built with ❤️ by the [@nexios-labs](https://github.com/nexios-labs) community.