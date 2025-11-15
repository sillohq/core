# JSON-RPC Integration

Lightweight helpers for running JSON-RPC 2.0 over HTTP with Nexios.

## What is JSON-RPC?

JSON-RPC (JavaScript Object Notation Remote Procedure Call) is a stateless, light-weight remote procedure call (RPC) protocol. It allows you to call methods on a remote server as if they were local functions. The protocol uses JSON for data encoding and is transport agnostic, though HTTP is the most common transport layer.

### Key Benefits of JSON-RPC:
- **Simplicity**: Clean, minimal protocol with just request/response patterns
- **Language Agnostic**: Works with any programming language that supports JSON
- **Stateless**: Each request is independent, making it scalable and reliable
- **Type Safety**: Clear parameter and return type definitions
- **Error Handling**: Standardized error codes and messages

This contrib provides:

- **JSON-RPC 2.0 Server Implementation**: Full-featured server that handles method registration, request parsing, and response formatting
- **JSON-RPC Client**: Async client for making remote procedure calls with proper error handling
- **Method Registry System**: Decorator-based method registration with support for both sync and async functions
- **Comprehensive Error Handling**: Built-in error types following JSON-RPC 2.0 specification
- **Zero External Dependencies**: Uses only Python standard library for maximum compatibility

## Installation

The JSON-RPC contrib is included with the main nexios_contrib package, making it easy to get started with remote procedure calls.

Install the JSON-RPC contrib with Nexios:

```bash
pip install nexios_contrib
```

**Why No External Dependencies?**
This contrib intentionally uses only Python standard library modules for several reasons:
- **Reduced Dependency Conflicts**: No version conflicts with your existing packages
- **Faster Installation**: No need to download additional dependencies
- **Better Security**: Fewer attack vectors from third-party packages
- **Easier Deployment**: Simpler containerization and deployment processes
- **Long-term Stability**: Less likely to break due to dependency updates

## Quick Start

### Basic Server Setup

Creating a JSON-RPC server with Nexios is straightforward. The server automatically handles request parsing, method dispatch, and response formatting.

```python
# server.py
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.registry import get_registry

def main():
    app = NexiosApp()
    registry = get_registry()

    @registry.register("add")
    def add(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b

    @registry.register("echo")
    async def echo(msg: str) -> str:
        """Echo back the input message."""
        return f"Server says: {msg}"

    JsonRpcPlugin(app, {"path_prefix": "/rpc"})
    app.run(host="0.0.0.0", port=3020)

if __name__ == "__main__":
    main()
```

::: details View Complete Server Example with Detailed Comments

```python
# server.py
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.registry import get_registry

def main():
    # Create Nexios app - this is your main application instance
    app = NexiosApp()

    # Get the global registry - this is a singleton that stores all RPC methods
    # The registry acts as a central method dispatcher for JSON-RPC calls
    registry = get_registry()

    # Register a synchronous method using the decorator pattern
    # The method name "add" will be the RPC method name clients call
    @registry.register("add")
    def add(a: int, b: int) -> int:
        """Add two numbers together.
        
        This docstring becomes part of the method's metadata and can be
        used for auto-generating API documentation.
        
        Args:
            a: First number to add
            b: Second number to add
            
        Returns:
            The sum of a and b
        """
        return a + b

    # Register an asynchronous method - the registry handles both sync and async
    # Async methods are useful for I/O operations like database calls or HTTP requests
    @registry.register("echo")
    async def echo(msg: str) -> str:
        """Echo back the input message with a server prefix.
        
        This demonstrates how async methods work in the JSON-RPC system.
        The registry will automatically await async functions.
        """
        return f"Server says: {msg}"

    # Mount the JSON-RPC plugin to your Nexios app
    # This creates an HTTP endpoint that accepts JSON-RPC requests
    # The plugin integrates with Nexios's routing and middleware system
    JsonRpcPlugin(app, {"path_prefix": "/rpc"})

    print("🚀 JSON-RPC Server starting on port 3020...")
    print("📋 Available JSON-RPC methods:")
    print("   - add(a, b) -> int")
    print("   - echo(msg) -> str")
    print("\n🔗 JSON-RPC endpoint: http://localhost:3020/rpc")
    print("\n📖 Example JSON-RPC request:")
    print('   POST /rpc')
    print('   {"jsonrpc": "2.0", "method": "add", "params": {"a": 5, "b": 3}, "id": 1}')

    # Start the server - this will block and serve requests
    app.run(host="0.0.0.0", port=3020)

if __name__ == "__main__":
    main()
```
:::

**Understanding the Server Components:**

1. **NexiosApp**: The main application instance that handles HTTP requests and routing
2. **Registry**: A method storage and dispatch system that maps method names to Python functions
3. **JsonRpcPlugin**: The bridge between Nexios HTTP handling and JSON-RPC protocol
4. **Method Registration**: The `@registry.register()` decorator makes Python functions available as RPC methods
5. **Path Prefix**: The `/rpc` endpoint where all JSON-RPC requests are sent

### Basic Client Usage

The JSON-RPC client provides a simple async interface for calling remote methods. It handles connection management, request serialization, and error handling automatically.

```python
# client.py
import asyncio
from nexios_contrib.jrpc.client import JsonRpcClient

async def main() -> None:
    client = JsonRpcClient("http://localhost:3020/rpc")
    result = await client.call("add", a=2, b=3)
    print(f"Addition result: {result}")  # Output: 5

    result = await client.call("echo", msg="Hello, server!")
    print(f"Echo result: {result}")  # Output: Server says: Hello, server!

if __name__ == "__main__":
    asyncio.run(main())
```


::: details View Complete Client Example with Detailed Explanations

```python
# client.py
import asyncio
from nexios_contrib.jrpc.client import JsonRpcClient

async def main() -> None:
    # Create a client connection to the JSON-RPC server
    # Using async context manager ensures proper connection cleanup
    client = JsonRpcClient("http://localhost:3020/rpc"):
        
    # Call the 'add' method with named parameters
    # This sends: {"jsonrpc": "2.0", "method": "add", "params": {"a": 2, "b": 3}, "id": <auto>}
    result = await client.call("add", a=2, b=3)
    print(f"Addition result: {result}")  # Output: Addition result: 5

    # Call the 'echo' method - demonstrates async method calls
    # The client automatically handles the JSON-RPC protocol details
    result = await client.call("echo", msg="Hello, server!")
    print(f"Echo result: {result}")  # Output: Echo result: Server says: Hello, server!

    # Method call with positional arguments
    # This creates: {"jsonrpc": "2.0", "method": "multiply", "params": [3.14, 2.0], "id": 2}
    result = await client.call("multiply", 3.14, 2.0)
    print(f"Multiplication: 3.14 * 2.0 = {result}")
    
    # Method call with complex data structures
    user_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "age": 30,
        "preferences": {
            "theme": "dark",
            "notifications": True
        }
    }
    result = await client.call("process_user_data", user_data=user_data)
    print(f"Processed user: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```
:::

**Understanding the Client:**


1. **Method Calls**: `client.call()` translates Python function calls into JSON-RPC requests
2. **Parameter Handling**: Named parameters become the `params` object in the JSON-RPC request
3. **Automatic ID Management**: The client generates unique request IDs for tracking responses
4. **Response Parsing**: The client automatically extracts the result from JSON-RPC response format

**What Happens Under the Hood:**
- Client serializes your method call into JSON-RPC 2.0 format
- HTTP POST request is sent to the server endpoint
- Server deserializes the request and calls the registered method
- Method result is serialized back into JSON-RPC response
- Client receives and deserializes the response, returlt

## Server Implementation

### Method Registration Deep Dive

The method registry is the heart of the JSON-RPC server. It manages method storage, validation, and execution.

```python
from nexios_contrib.jrpc.registry import get_registry

# Get the global singleton registry instance
# This ensures all parts of your application share the same method registry
registry = get_registry()

# Register synchronous methods - these execute immediately and return results
@registry.register("multiply")
def multiply(x: float, y: float) -> float:
    """Multiply two numbers.
    
    Synchronous methods are best for:
    - Pure computations (math operations, data transformations)
    - Quick operations that don't involve I/O
    - Methods that don't need to wait for external resources
    
    Args:
        x: First number to multiply
        y: Second number to multiply
        
    Returns:
        The product of x and y
    """
    return x * y

# Register asynchronous methods - these can await other async operations
@registry.register("fetch_data")
async def fetch_data(url: str) -> dict:
    """Fetch data from a URL using async HTTP client.
    
    Async methods are essential for:
    - HTTP requests to external APIs
    - Database operations
    - File I/O operations
    - Any operation that might block or take time
    
    The registry automatically detects async functions and awaits them properly.
    """
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# Register with custom name - function name doesn't have to match RPC method name
@registry.register("get_time")
def current_timestamp() -> float:
    """Get current timestamp.
    
    This demonstrates method name aliasing:
    - Python function: current_timestamp()
    - RPC method name: "get_time"
    
    This is useful when:
    - You want more descriptive Python function names
    - You need to maintain backward compatibility
    - You're wrapping existing functions with different naming conventions
    """
    import time
    return time.time()

# You can also register methods without decorators
def calculate_area(length: float, width: float) -> float:
    """Calculate rectangle area."""
    return length * width

# Manual registration - useful for conditional registration or dynamic methods
registry.register_method("area", calculate_area)
```

**Registry Features Explained:**

1. **Singleton Pattern**: `get_registry()` always returns the same instance, ensuring method consistency
2. **Type Detection**: The registry automatically detects sync vs async functions
3. **Method Validation**: Ensures method names are unique and functions are callable
4. **Execution Context**: Handles both sync and async execution contexts properly
5. **Method Metadata**: Stores function signatures, docstrings, and type hints for introspection

### Error Handling Deep Dive

Proper error handling is crucial for robust JSON-RPC services. The protocol defines standard error codes and allows custom error data.

```python
from nexios_contrib.jrpc.exceptions import JsonRpcError

@registry.register("divide")
def divide(a: float, b: float) -> float:
    """Divide two numbers with comprehensive error handling.
    
    This method demonstrates several error handling patterns:
    - Input validation
    - Business logic errors
    - Structured error responses
    """
    # Input type validation
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise JsonRpcError(
            code=-32602,  # Invalid params - standard JSON-RPC error code
            message="Parameters must be numbers",
            data={
                "received_types": {
                    "a": type(a).__name__,
                    "b": type(b).__name__
                },
                "expected_types": ["int", "float"]
            }
        )
    
    # Business logic validation
    if b == 0:
        raise JsonRpcError(
            code=-32602,  # Invalid params
            message="Division by zero is not allowed",
            data={
                "dividend": a,
                "divisor": b,
                "suggestion": "Use a non-zero divisor"
            }
        )
    
    return a / b

@registry.register("validate_email")
def validate_email(email: str) -> dict:
    """Validate email format with detailed feedback.
    
    Returns validation result with detailed information about why
    an email might be invalid.
    """
    import re
    
    # Type validation
    if not isinstance(email, str):
        raise JsonRpcError(
            code=-32602,
            message="Email must be a string",
            data={
                "expected": "string",
                "received": type(email).__name__,
                "value": str(email)[:50]  # Truncate for safety
            }
        )
    
    # Length validation
    if len(email) > 254:  # RFC 5321 limit
        raise JsonRpcError(
            code=-32602,
            message="Email address too long",
            data={
                "max_length": 254,
                "received_length": len(email)
            }
        )
    
    # Format validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_valid = bool(re.match(pattern, email))
    
    return {
        "is_valid": is_valid,
        "email": email,
        "checks": {
            "format": is_valid,
            "length": len(email) <= 254,
            "has_at_symbol": "@" in email,
            "has_domain": "." in email.split("@")[-1] if "@" in email else False
        }
    }

@registry.register("process_user_data")
async def process_user_data(user_data: dict) -> dict:
    """Process user data with comprehensive validation and error handling."""
    
    # Required fields validation
    required_fields = ["name", "email", "age"]
    missing_fields = [field for field in required_fields if field not in user_data]
    
    if missing_fields:
        raise JsonRpcError(
            code=-32602,
            message="Missing required fields",
            data={
                "missing_fields": missing_fields,
                "required_fields": required_fields,
                "provided_fields": list(user_data.keys())
            }
        )
    
    # Age validation
    try:
        age = int(user_data["age"])
        if age < 0 or age > 150:
            raise ValueError("Age out of valid range")
    except (ValueError, TypeError) as e:
        raise JsonRpcError(
            code=-32602,
            message="Invalid age value",
            data={
                "age_value": user_data["age"],
                "error": str(e),
                "valid_range": "0-150"
            }
        )
    
    # Simulate processing that might fail
    try:
        # This could be a database operation, API call, etc.
        processed_data = {
            "id": f"user_{hash(user_data['email']) % 10000}",
            "name": user_data["name"].strip().title(),
            "email": user_data["email"].lower(),
            "age": age,
            "status": "processed"
        }
        return processed_data
        
    except Exception as e:
        # Catch unexpected errors and convert to JSON-RPC errors
        raise JsonRpcError(
            code=-32603,  # Internal error
            message="Failed to process user data",
            data={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "user_data_keys": list(user_data.keys())
            }
        )
```

**JSON-RPC Error Codes Reference:**

- **-32700**: Parse error (invalid JSON)
- **-32600**: Invalid request (malformed JSON-RPC)
- **-32601**: Method not found
- **-32602**: Invalid params (use this for validation errors)
- **-32603**: Internal error (server-side errors)
- **-32000 to -32099**: Server error (reserved for implementation-defined errors)

**Error Handling Best Practices:**

1. **Use Standard Codes**: Stick to JSON-RPC standard error codes when possible
2. **Provide Context**: Include helpful data in the error response
3. **Validate Early**: Check inputs before processing to fail fast
4. **Structured Data**: Use consistent error data structures
5. **Security**: Don't expose sensitive information in error messages
6. **Logging**: Log errors server-side for debugging while returning clean errors to clients

### Advanced Server Configuration

The JSON-RPC plugin offers extensive configuration options for production deployments and complex scenarios.

```python
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.registry import Registry, get_registry
import logging

app = NexiosApp()

# Method 1: Using Custom Registry (Isolated Method Namespace)
# Create a separate registry for specific functionality
custom_registry = Registry()

@custom_registry.register("custom_method")
def custom_method(param: str) -> str:
    """Custom method in isolated registry.
    
    Custom registries are useful for:
    - Separating different API versions
    - Creating isolated method namespaces
    - Testing without affecting global registry
    - Multi-tenant applications
    """
    return f"Custom: {param}"

# Method 2: Multiple JSON-RPC Endpoints
# You can mount multiple JSON-RPC endpoints with different configurations

# Admin API endpoint with restricted methods
admin_registry = Registry()

@admin_registry.register("system_status")
def get_system_status() -> dict:
    """Get system status - admin only."""
    import psutil
    return {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent
    }

@admin_registry.register("restart_service")
async def restart_service(service_name: str) -> dict:
    """Restart a system service - admin only."""
    # This would typically require authentication/authorization
    return {"status": "restarted", "service": service_name}

# Public API endpoint with general methods
public_registry = get_registry()  # Use global registry

@public_registry.register("health_check")
def health_check() -> dict:
    """Public health check endpoint."""
    return {"status": "healthy", "timestamp": time.time()}

# Configure multiple JSON-RPC endpoints
JsonRpcPlugin(app, {
    "path_prefix": "/api/v1/rpc",
    "registry": public_registry,
    "cors_enabled": True,
    "max_request_size": 1024 * 1024,  # 1MB limit
    "timeout": 30.0  # 30 second timeout
})

JsonRpcPlugin(app, {
    "path_prefix": "/admin/rpc",
    "registry": admin_registry,
    "cors_enabled": False,  # Disable CORS for admin endpoint
    "require_auth": True,   # Custom auth requirement
    "rate_limit": "10/minute"  # Rate limiting
})

# Method 3: Advanced Configuration with Middleware Integration
class AuthenticatedJsonRpcPlugin(JsonRpcPlugin):
    """Custom JSON-RPC plugin with authentication."""
    
    async def authenticate_request(self, request):
        """Custom authentication logic."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise JsonRpcError(
                code=-32001,
                message="Authentication required",
                data={"auth_type": "Bearer token"}
            )
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        # Validate token here (check database, JWT, etc.)
        if not self.validate_token(token):
            raise JsonRpcError(
                code=-32002,
                message="Invalid authentication token"
            )
    
    def validate_token(self, token: str) -> bool:
        """Validate authentication token."""
        # Implement your token validation logic
        return token == "valid_token_123"

# Use custom plugin with authentication
AuthenticatedJsonRpcPlugin(app, {
    "path_prefix": "/secure/rpc",
    "registry": admin_registry
})

# Method 4: Configuration with Environment Variables
import os

# Production-ready configuration
production_config = {
    "path_prefix": os.getenv("JSONRPC_PATH", "/rpc"),
    "max_request_size": int(os.getenv("JSONRPC_MAX_SIZE", "2097152")),  # 2MB
    "timeout": float(os.getenv("JSONRPC_TIMEOUT", "60.0")),
    "enable_introspection": os.getenv("JSONRPC_INTROSPECTION", "false").lower() == "true",
    "log_requests": os.getenv("JSONRPC_LOG_REQUESTS", "true").lower() == "true",
    "cors_origins": os.getenv("JSONRPC_CORS_ORIGINS", "*").split(",")
}

JsonRpcPlugin(app, production_config)

# Method 5: Registry with Method Introspection
@public_registry.register("list_methods")
def list_available_methods() -> dict:
    """List all available RPC methods with their signatures.
    
    This is useful for API discovery and documentation generation.
    """
    methods = {}
    for method_name, method_func in public_registry.methods.items():
        import inspect
        sig = inspect.signature(method_func)
        methods[method_name] = {
            "parameters": [
                {
                    "name": param.name,
                    "type": str(param.annotation) if param.annotation != param.empty else "Any",
                    "default": str(param.default) if param.default != param.empty else None
                }
                for param in sig.parameters.values()
            ],
            "return_type": str(sig.return_annotation) if sig.return_annotation != sig.empty else "Any",
            "docstring": method_func.__doc__ or "No documentation available"
        }
    return methods

if __name__ == "__main__":
    # Configure logging for production
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    app.run(host="0.0.0.0", port=8000)
```

**Configuration Options Explained:**

1. **path_prefix**: URL path where JSON-RPC endpoint is mounted
2. **registry**: Which method registry to use (allows multiple isolated APIs)
3. **cors_enabled**: Enable Cross-Origin Resource Sharing for web clients
4. **max_request_size**: Limit request payload size to prevent abuse
5. **timeout**: Maximum time to wait for method execution
6. **require_auth**: Enable authentication middleware
7. **rate_limit**: Limit requests per time period per client
8. **enable_introspection**: Allow clients to discover available methods
9. **log_requests**: Log all incoming requests for debugging/monitoring

**Use Cases for Multiple Endpoints:**

- **API Versioning**: `/api/v1/rpc` and `/api/v2/rpc`
- **Access Control**: Public vs admin endpoints
- **Service Separation**: Different microservices on same server
- **Environment Isolation**: Development vs production methods

## Client Implementation Deep Dive

### Basic Client Usage with Detailed Explanations

```python
import asyncio
from nexios_contrib.jrpc.client import JsonRpcClient

async def example_client():
    """Comprehensive client usage examples."""
    
    # Create client with explicit configuration
    # The client manages HTTP connections, request/response serialization,
    # and error handling automatically
    client = JsonRpcClient(
        url="http://localhost:3020/rpc",
        timeout=30.0,  # Request timeout in seconds
        headers={       # Custom HTTP headers
            "User-Agent": "MyApp/1.0",
            "Authorization": "Bearer your-token-here"
        }
    )
    
    try:
        # Single method call with named parameters
        # This creates a JSON-RPC request like:
        # {"jsonrpc": "2.0", "method": "add", "params": {"a": 10, "b": 20}, "id": 1}
        result = await client.call("add", a=10, b=20)
        print(f"Addition: 10 + 20 = {result}")
        
        # Method call with keyword arguments (same as above, different syntax)
        result = await client.call("echo", msg="Hello World")
        print(f"Echo response: {result}")
        
        # Method call with positional arguments
        # This creates: {"jsonrpc": "2.0", "method": "multiply", "params": [3.14, 2.0], "id": 2}
        result = await client.call("multiply", 3.14, 2.0)
        print(f"Multiplication: 3.14 * 2.0 = {result}")
        
        # Method call with no parameters
        result = await client.call("get_time")
        print(f"Server time: {result}")
        
        # Method call with complex data structures
        user_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "preferences": {
                "theme": "dark",
                "notifications": True
            }
        }
        result = await client.call("process_user_data", user_data=user_data)
        print(f"Processed user: {result}")
        
    except Exception as e:
        print(f"Client error: {e}")
    finally:
        # Always close the client to free resources
        await client.close()

# Context manager approach (recommended)
async def context_manager_example():
    """Using context manager for automatic resource cleanup."""
    
    # The async context manager automatically handles:
    # 1. Connection setup
    # 2. Resource cleanup on exit
    # 3. Proper error handling
    client = JsonRpcClient("http://localhost:3020/rpc") 
        
    # Multiple calls in sequence
    results = []
    for i in range(5):
        result = await client.call("add", a=i, b=i+1)
        results.append(result)
    
    print(f"Sequential results: {results}")
        
    # The client connection is automatically closed when exiting the context

# Concurrent calls for better performance
async def concurrent_calls_example():
    """Making multiple concurrent JSON-RPC calls."""
    
   client = JsonRpcClient("http://localhost:3020/rpc") :
        
        # Create multiple concurrent calls
        # This is much faster than sequential calls for independent operations
    tasks = [
        client.call("add", a=1, b=2),
        client.call("multiply", 3, 4),
        client.call("echo", msg="concurrent"),
        client.call("get_time"),
    ]
    
    # Wait for all calls to complete
    results = await asyncio.gather(*tasks)
        
    print("Concurrent results:")
    for i, result in enumerate(results):
        print(f"  Task {i}: {result}")

# Run examples
if __name__ == "__main__":
    asyncio.run(example_client())
    asyncio.run(context_manager_example())
    asyncio.run(concurrent_calls_example())
```

**Client Features Explained:**

1. **Automatic Connection Management**: The client handles HTTP connection pooling and reuse
2. **Request ID Management**: Each request gets a unique ID for response matching
3. **Serialization**: Python objects are automatically converted to JSON
4. **Deserialization**: JSON responses are converted back to Python objects
5. **Error Handling**: JSON-RPC errors are converted to Python exceptions
6. **Timeout Handling**: Configurable timeouts prevent hanging requests
7. **Custom Headers**: Support for authentication and custom HTTP headers

**Performance Considerations:**

- **Connection Reuse**: The client reuses HTTP connections for multiple requests
- **Concurrent Calls**: Use `asyncio.gather()` for independent parallel requests
- **Context Managers**: Always use context managers or explicit `close()` calls
- **Timeout Configuration**: Set appropriate timeouts based on your use case



### Comprehensive Client Error Handling

Error handling is crucial for robust client applications. The JSON-RPC client provides detailed error information for different failure scenarios.

```python
from nexios_contrib.jrpc.exceptions import JsonRpcError, JsonRpcClientError
import asyncio
import logging

# Configure logging to see detailed error information
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def comprehensive_error_handling():
    """Demonstrate all types of error handling scenarios."""
    
    client = JsonRpcClient("http://localhost:3020/rpc")
        
        # 1. Handle JSON-RPC Protocol Errors
    try:
        # This will raise a JSON-RPC error (division by zero)
        result = await client.call("divide", a=10, b=0)
    except JsonRpcError as e:
        logger.error(f"JSON-RPC Error: {e.message} (Code: {e.code})")
        
        # Handle specific error codes
        if e.code == -32602:  # Invalid params
            logger.info("This is a parameter validation error")
            if e.data:
                logger.info(f"Error details: {e.data}")
        elif e.code == -32601:  # Method not found
            logger.info("The requested method doesn't exist")
        elif e.code == -32603:  # Internal error
            logger.info("Server encountered an internal error")
        
        # Access all error properties
        print(f"Error Code: {e.code}")
        print(f"Error Message: {e.message}")
        print(f"Error Data: {e.data}")
        print(f"Request ID: {e.request_id}")
    
    # 2. Handle Network and Connection Errors
    try:
        # Try to call a method on unreachable server
        unreachable_client = JsonRpcClient("http://nonexistent:9999/rpc")
        result = await unreachable_client.call("test")
    except JsonRpcClientError as e:
        logger.error(f"Client Error: {e}")
        
        # Different types of client errors:
        if "Connection refused" in str(e):
            logger.info("Server is not running or unreachable")
        elif "timeout" in str(e).lower():
            logger.info("Request timed out")
        elif "DNS" in str(e) or "resolve" in str(e):
            logger.info("DNS resolution failed")
    
    # 3. Handle Method Not Found Errors
    try:
        result = await client.call("nonexistent_method", param="value")
    except JsonRpcError as e:
        if e.code == -32601:
            logger.error(f"Method 'nonexistent_method' not found on server")
            # You might want to check available methods
            try:
                methods = await client.call("list_methods")
                logger.info(f"Available methods: {list(methods.keys())}")
            except:
                logger.info("Could not retrieve available methods")
    
    # 4. Handle Invalid Parameter Errors
    try:
        # Send wrong parameter types
        result = await client.call("add", a="not_a_number", b=5)
    except JsonRpcError as e:
        if e.code == -32602:
            logger.error("Parameter validation failed")
            if e.data and "expected_types" in e.data:
                expected = e.data["expected_types"]
                received = e.data["received_types"]
                logger.info(f"Expected: {expected}, Received: {received}")
    
    # 5. Handle Timeout Errors
    try:
        # Create client with short timeout
        timeout_client = JsonRpcClient(
            "http://localhost:3020/rpc",
            timeout=0.1  # Very short timeout
        )
        async with timeout_client:
            result = await timeout_client.call("slow_method")
    except JsonRpcClientError as e:
        if "timeout" in str(e).lower():
            logger.error("Request timed out - server might be overloaded")
    
    # 6. Retry Logic for Transient Errors
    max_retries = 3
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            result = await client.call("unreliable_method")
            logger.info(f"Success on attempt {attempt + 1}")
            break
        except JsonRpcClientError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"All {max_retries} attempts failed")
                raise
        except JsonRpcError as e:
            # Don't retry JSON-RPC errors (they're not transient)
            logger.error(f"JSON-RPC error (not retrying): {e.message}")
            break

async def graceful_degradation_example():
    """Example of graceful degradation when services are unavailable."""
    
    try:
        client = JsonRpcClient("http://localhost:3020/rpc"):
        # Try to get data from remote service
        result = await client.call("get_user_data", user_id=123)
        return result
    except (JsonRpcClientError, JsonRpcError) as e:
        logger.warning(f"Remote service unavailable: {e}")
        
        # Fallback to cached data or default values
        return {
            "user_id": 123,
            "name": "Unknown User",
            "status": "offline",
            "source": "fallback_data"
        }

async def batch_operations_with_error_handling():
    """Handle errors in batch operations gracefully."""
    
    client = JsonRpcClient("http://localhost:3020/rpc"):
        
        # List of operations to perform
    operations = [
        ("add", {"a": 1, "b": 2}),
        ("divide", {"a": 10, "b": 0}),  # This will fail
        ("multiply", {"a": 3, "b": 4}),
        ("nonexistent", {"param": "value"}),  # This will fail
        ("echo", {"msg": "hello"})
    ]
    
    results = []
    
    for method, params in operations:
        try:
            result = await client.call(method, **params)
            results.append({"method": method, "result": result, "success": True})
        except JsonRpcError as e:
            results.append({
                "method": method,
                "error": {"code": e.code, "message": e.message},
                "success": False
            })
        except Exception as e:
            results.append({
                "method": method,
                "error": {"message": str(e)},
                "success": False
            })
    
    # Process results
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    logger.info(f"Successful operations: {len(successful)}")
    logger.info(f"Failed operations: {len(failed)}")
    
    return results

if __name__ == "__main__":
    asyncio.run(comprehensive_error_handling())
    asyncio.run(graceful_degradation_example())
    asyncio.run(batch_operations_with_error_handling())
```

**Error Types Explained:**

1. **JsonRpcError**: Protocol-level errors from the server
   - Method not found (-32601)
   - Invalid parameters (-32602)
   - Internal server error (-32603)
   - Custom application errors

2. **JsonRpcClientError**: Client-side errors
   - Network connectivity issues
   - Timeout errors
   - Invalid server responses
   - Connection failures

**Error Handling Best Practices:**

1. **Specific Exception Handling**: Catch specific error types for appropriate responses
2. **Retry Logic**: Implement retries for transient network errors
3. **Graceful Degradation**: Provide fallback behavior when services are unavailable
4. **Logging**: Log errors with sufficient detail for debugging
5. **User Feedback**: Provide meaningful error messages to end users
6. **Circuit Breaker**: Stop calling failing services to prevent cascading failures


## Integration with Nexios Framework

### Middleware Integration

JSON-RPC seamlessly integrates with Nexios's middleware system, allowing you to add cross-cutting concerns like logging, authentication, and monitoring.

Here's a simple example of adding logging middleware:

```python
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
import time
import logging

app = NexiosApp()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple logging middleware
async def logging_middleware(request, response, call_next):
    start_time = time.time()
    logger.info(f"JSON-RPC Request: {request.method} {request.url}")
    
    response = await call_next()
    
    duration = time.time() - start_time
    logger.info(f"Response: {response.status_code} ({duration:.3f}s)")
    return response

app.add_middleware(logging_middleware)
JsonRpcPlugin(app, {"path_prefix": "/rpc"})
```

::: details View Advanced Middleware Examples

```python
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.exceptions import JsonRpcError
import time
import json
import logging
from collections import defaultdict, deque

app = NexiosApp()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Comprehensive Logging Middleware
async def comprehensive_logging_middleware(request, response, call_next):
    """Comprehensive request/response logging for JSON-RPC calls."""
    
    start_time = time.time()
    request_id = f"req_{int(start_time * 1000000)}"
    
    # Log incoming request
    logger.info(f"[{request_id}] JSON-RPC Request: {request.method} {request.url}")
    
    # For JSON-RPC, log the method being called
    if request.method == "POST" and "/rpc" in str(request.url):
        try:
            body = await request.body()
            if body:
                rpc_data = json.loads(body)
                method_name = rpc_data.get("method", "unknown")
                logger.info(f"[{request_id}] RPC Method: {method_name}")
        except Exception as e:
            logger.warning(f"[{request_id}] Could not parse RPC body: {e}")
    
    response = await call_next()
    
    # Log response
    duration = time.time() - start_time
    logger.info(f"[{request_id}] Response: {response.status_code} ({duration:.3f}s)")
    
    # Add custom headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Processing-Time"] = f"{duration:.3f}"
    
    return response

# 2. Rate Limiting Middleware
class RateLimitingMiddleware:
    """Rate limiting middleware for JSON-RPC endpoints."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_counts = defaultdict(deque)
    
    async def __call__(self, request, response, call_next):
        """Apply rate limiting to JSON-RPC requests."""
        
        # Only rate limit JSON-RPC endpoints
        if not (request.method == "POST" and "/rpc" in str(request.url)):
            return await call_next()
        
        # Get client identifier (IP address)
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old requests outside the window
        client_requests = self.request_counts[client_ip]
        while client_requests and client_requests[0] < current_time - self.window_seconds:
            client_requests.popleft()
        
        # Check rate limit
        if len(client_requests) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32004,
                    "message": "Rate limit exceeded",
                    "data": {
                        "max_requests": self.max_requests,
                        "window_seconds": self.window_seconds,
                        "retry_after": self.window_seconds
                    }
                },
                "id": None
            }
            
            return Response(
                content=json.dumps(error_response),
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": str(self.window_seconds)
                }
            )
        
        # Record this request
        client_requests.append(current_time)
        
        return await call_next()

# 3. CORS Middleware for Web Clients
async def cors_middleware(request, response, call_next):
    """Handle CORS for web-based JSON-RPC clients."""
    
    # Handle preflight requests
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Max-Age": "86400"
            }
        )
    
    # Process request
    response = await call_next()
    
    # Add CORS headers to response
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    
    return response

# Initialize middleware instances
rate_limit_middleware = RateLimitingMiddleware(max_requests=50, window_seconds=60)

# Add middleware to app (order matters!)
app.add_middleware(cors_middleware)  # First - handle CORS
app.add_middleware(comprehensive_logging_middleware)  # Second - log everything
app.add_middleware(rate_limit_middleware)  # Third - rate limiting

# JSON-RPC will automatically use all Nexios middleware
JsonRpcPlugin(app, {"path_prefix": "/rpc"})

if __name__ == "__main__":
    print("🚀 Starting Nexios JSON-RPC server with middleware...")
    print("⚡ Rate limiting: 50 requests per minute per IP")
    print("🌐 CORS: Enabled for web clients")
    
    app.run(host="0.0.0.0", port=8000)
```
:::

**Middleware Benefits:**

1. **Cross-Cutting Concerns**: Handle logging, rate limiting, etc. across all RPC methods
2. **Separation of Concerns**: Keep business logic separate from infrastructure concerns
3. **Reusability**: Middleware can be reused across different endpoints
4. **Composability**: Stack multiple middleware for complex functionality

### Method Registration Patterns

The method registry supports various registration patterns for different use cases:

```python
from nexios_contrib.jrpc.registry import get_registry

registry = get_registry()

# Basic method registration
@registry.register("multiply")
def multiply(x: float, y: float) -> float:
    """Multiply two numbers."""
    return x * y

# Async method registration
@registry.register("fetch_data")
async def fetch_data(url: str) -> dict:
    """Fetch data from a URL."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# Custom method name
@registry.register("get_time")
def current_timestamp() -> float:
    """Get current timestamp."""
    import time
    return time.time()

# Manual registration
def calculate_area(length: float, width: float) -> float:
    """Calculate rectangle area."""
    return length * width

registry.register_method("area", calculate_area)
```

## Real-World Examples

### Calculator Service Example

Here's a simple calculator service to demonstrate JSON-RPC in action:

```python
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.registry import get_registry
from nexios_contrib.jrpc.exceptions import JsonRpcError
import math

app = NexiosApp()
registry = get_registry()

@registry.register("add")
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

@registry.register("divide")
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise JsonRpcError(
            code=-32602,
            message="Division by zero is not allowed"
        )
    return a / b

@registry.register("sqrt")
def square_root(number: float) -> float:
    """Calculate square root."""
    if number < 0:
        raise JsonRpcError(
            code=-32602,
            message="Cannot calculate square root of negative number"
        )
    return math.sqrt(number)

JsonRpcPlugin(app, {"path_prefix": "/calc"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

::: details View Complete Calculator Service with Advanced Features

```python
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.registry import get_registry
from nexios_contrib.jrpc.exceptions import JsonRpcError
import math
import logging
from typing import Union, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = NexiosApp()
registry = get_registry()

def validate_number(value, param_name: str) -> float:
    """Validate and convert input to float with proper error handling."""
    if value is None:
        raise JsonRpcError(
            code=-32602,
            message=f"Parameter '{param_name}' cannot be null",
            data={"parameter": param_name, "received": None}
        )
    
    if isinstance(value, bool):  # bool is subclass of int, check first
        raise JsonRpcError(
            code=-32602,
            message=f"Parameter '{param_name}' cannot be boolean",
            data={"parameter": param_name, "received": value, "type": "boolean"}
        )
    
    if not isinstance(value, (int, float)):
        raise JsonRpcError(
            code=-32602,
            message=f"Parameter '{param_name}' must be a number",
            data={
                "parameter": param_name,
                "expected": ["int", "float"],
                "received": type(value).__name__,
                "value": str(value)[:50]
            }
        )
    
    if math.isnan(value) or math.isinf(value):
        raise JsonRpcError(
            code=-32602,
            message=f"Parameter '{param_name}' must be a finite number",
            data={"parameter": param_name, "received": value}
        )
    
    return float(value)

@registry.register("add")
def add(a, b) -> float:
    """Add two numbers with validation."""
    a_val = validate_number(a, "a")
    b_val = validate_number(b, "b")
    
    result = a_val + b_val
    logger.info(f"Addition: {a_val} + {b_val} = {result}")
    return result

@registry.register("subtract")
def subtract(a, b) -> float:
    """Subtract b from a."""
    a_val = validate_number(a, "a")
    b_val = validate_number(b, "b")
    
    result = a_val - b_val
    logger.info(f"Subtraction: {a_val} - {b_val} = {result}")
    return result

@registry.register("multiply")
def multiply(a, b) -> float:
    """Multiply two numbers."""
    a_val = validate_number(a, "a")
    b_val = validate_number(b, "b")
    
    result = a_val * b_val
    logger.info(f"Multiplication: {a_val} * {b_val} = {result}")
    return result

@registry.register("divide")
def divide(a, b) -> float:
    """Divide a by b with comprehensive error handling."""
    a_val = validate_number(a, "a")
    b_val = validate_number(b, "b")
    
    if b_val == 0:
        raise JsonRpcError(
            code=-32602,
            message="Division by zero is not allowed",
            data={
                "dividend": a_val,
                "divisor": b_val,
                "suggestion": "Use a non-zero divisor"
            }
        )
    
    result = a_val / b_val
    logger.info(f"Division: {a_val} / {b_val} = {result}")
    return result

@registry.register("power")
def power(base, exponent) -> float:
    """Raise base to the power of exponent with overflow protection."""
    base_val = validate_number(base, "base")
    exp_val = validate_number(exponent, "exponent")
    
    # Check for potential overflow
    if abs(base_val) > 1000 and abs(exp_val) > 100:
        raise JsonRpcError(
            code=-32602,
            message="Operation would result in overflow",
            data={
                "base": base_val,
                "exponent": exp_val,
                "max_safe_base": 1000,
                "max_safe_exponent": 100
            }
        )
    
    try:
        result = base_val ** exp_val
        if math.isinf(result):
            raise OverflowError("Result is infinite")
        
        logger.info(f"Power: {base_val} ^ {exp_val} = {result}")
        return result
        
    except OverflowError:
        raise JsonRpcError(
            code=-32603,
            message="Calculation resulted in overflow",
            data={"base": base_val, "exponent": exp_val}
        )

@registry.register("sqrt")
def square_root(number) -> float:
    """Calculate square root with domain validation."""
    num_val = validate_number(number, "number")
    
    if num_val < 0:
        raise JsonRpcError(
            code=-32602,
            message="Cannot calculate square root of negative number",
            data={
                "number": num_val,
                "suggestion": "Use a non-negative number"
            }
        )
    
    result = math.sqrt(num_val)
    logger.info(f"Square root: √{num_val} = {result}")
    return result

@registry.register("factorial")
def factorial(n: int) -> int:
    """Calculate factorial with input validation."""
    if not isinstance(n, int):
        raise JsonRpcError(
            code=-32602,
            message="Factorial requires an integer",
            data={"received": type(n).__name__, "value": n}
        )
    
    if n < 0:
        raise JsonRpcError(
            code=-32602,
            message="Factorial is not defined for negative numbers",
            data={"number": n}
        )
    
    if n > 170:  # Factorial of 171 overflows float64
        raise JsonRpcError(
            code=-32602,
            message="Number too large for factorial calculation",
            data={"number": n, "max_safe_value": 170}
        )
    
    result = math.factorial(n)
    logger.info(f"Factorial: {n}! = {result}")
    return result

@registry.register("batch_calculate")
def batch_calculate(operations: List[dict]) -> List[dict]:
    """Perform multiple calculations in a single request."""
    if not isinstance(operations, list):
        raise JsonRpcError(
            code=-32602,
            message="Operations must be a list",
            data={"received": type(operations).__name__}
        )
    
    if len(operations) > 100:
        raise JsonRpcError(
            code=-32602,
            message="Too many operations in batch",
            data={"count": len(operations), "max_allowed": 100}
        )
    
    results = []
    
    for i, op in enumerate(operations):
        try:
            if not isinstance(op, dict):
                results.append({
                    "index": i,
                    "success": False,
                    "error": "Operation must be an object"
                })
                continue
            
            operation = op.get("operation")
            params = op.get("params", {})
            
            if operation == "add":
                result = add(**params)
            elif operation == "subtract":
                result = subtract(**params)
            elif operation == "multiply":
                result = multiply(**params)
            elif operation == "divide":
                result = divide(**params)
            elif operation == "power":
                result = power(**params)
            else:
                raise JsonRpcError(
                    code=-32601,
                    message=f"Unknown operation: {operation}"
                )
            
            results.append({
                "index": i,
                "success": True,
                "result": result,
                "operation": operation
            })
            
        except JsonRpcError as e:
            results.append({
                "index": i,
                "success": False,
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "data": e.data
                },
                "operation": op.get("operation", "unknown")
            })
        except Exception as e:
            results.append({
                "index": i,
                "success": False,
                "error": str(e),
                "operation": op.get("operation", "unknown")
            })
    
    return results

@registry.register("get_calculator_info")
def get_calculator_info() -> dict:
    """Get information about the calculator service."""
    return {
        "service": "Advanced Calculator Service",
        "version": "1.0.0",
        "supported_operations": [
            "add", "subtract", "multiply", "divide", 
            "power", "sqrt", "factorial", "batch_calculate"
        ],
        "features": [
            "Input validation",
            "Overflow protection", 
            "Batch operations",
            "Comprehensive error handling"
        ],
        "limits": {
            "max_batch_operations": 100,
            "max_factorial_input": 170,
            "max_safe_power_base": 1000,
            "max_safe_power_exponent": 100
        }
    }

# Configure JSON-RPC plugin
JsonRpcPlugin(app, {
    "path_prefix": "/calc",
    "cors_enabled": True,
    "max_request_size": 1024 * 1024  # 1MB for batch operations
})

if __name__ == "__main__":
    print("🧮 Advanced Calculator Service")
    print("📊 Features: Input validation, batch operations")
    print("🔗 Endpoint: http://localhost:8000/calc")
    print("\n📋 Available operations:")
    print("   - add(a, b)")
    print("   - subtract(a, b)")
    print("   - multiply(a, b)")
    print("   - divide(a, b)")
    print("   - power(base, exponent)")
    print("   - sqrt(number)")
    print("   - factorial(n)")
    print("   - batch_calculate(operations)")
    print("   - get_calculator_info()")
    
    app.run(host="0.0.0.0", port=8000)
```
:::

**Key Features:**

1. **Input Validation**: Type checking and range validation
2. **Error Handling**: Detailed error messages with helpful data
3. **Batch Operations**: Process multiple calculations in one request
4. **Overflow Protection**: Prevents calculations that would cause overflow
5. **Service Introspection**: Clients can query service capabilities

### Enterprise User Management Service

This example demonstrates a production-ready user management system with comprehensive validation, audit logging, and advanced features.

```python
from nexios import NexiosApp
from nexios_contrib.jrpc.server import JsonRpcPlugin
from nexios_contrib.jrpc.registry import get_registry
from nexios_contrib.jrpc.exceptions import JsonRpcError
import uuid
import time
import re
import hashlib
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = NexiosApp()
registry = get_registry()

@dataclass
class User:
    """User data model with validation and serialization."""
    id: str
    name: str
    email: str
    created_at: float
    updated_at: float
    status: str = "active"
    role: str = "user"
    last_login: Optional[float] = None
    login_count: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> dict:
        """Convert user to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_public_dict(self) -> dict:
        """Convert user to public dictionary (excluding sensitive data)."""
        data = self.to_dict()
        # Remove sensitive fields if needed
        return data

@dataclass
class AuditLog:
    """Audit log entry for tracking user operations."""
    id: str
    user_id: str
    action: str
    timestamp: float
    details: Dict[str, Any]
    performed_by: Optional[str] = None

class UserService:
    """Comprehensive user management service with validation and audit logging."""
    
    def __init__(self):
        # In-memory storage (use database in production)
        self.users: Dict[str, User] = {}
        self.audit_logs: List[AuditLog] = []
        
        # Email validation regex
        self.email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
        
        # Valid user statuses and roles
        self.valid_statuses = {"active", "inactive", "suspended", "deleted"}
        self.valid_roles = {"user", "admin", "moderator", "guest"}
    
    def validate_email(self, email: str) -> None:
        """Validate email format and uniqueness."""
        if not isinstance(email, str):
            raise JsonRpcError(
                code=-32602,
                message="Email must be a string",
                data={"received_type": type(email).__name__}
            )
        
        if not email or len(email.strip()) == 0:
            raise JsonRpcError(
                code=-32602,
                message="Email cannot be empty"
            )
        
        email = email.strip().lower()
        
        if len(email) > 254:  # RFC 5321 limit
            raise JsonRpcError(
                code=-32602,
                message="Email address too long",
                data={"max_length": 254, "received_length": len(email)}
            )
        
        if not self.email_pattern.match(email):
            raise JsonRpcError(
                code=-32602,
                message="Invalid email format",
                data={"email": email, "expected_format": "user@domain.com"}
            )
        
        # Check for existing email
        for user in self.users.values():
            if user.email.lower() == email and user.status != "deleted":
                raise JsonRpcError(
                    code=-32602,
                    message="Email already exists",
                    data={"email": email}
                )
    
    def validate_name(self, name: str) -> str:
        """Validate and normalize user name."""
        if not isinstance(name, str):
            raise JsonRpcError(
                code=-32602,
                message="Name must be a string",
                data={"received_type": type(name).__name__}
            )
        
        name = name.strip()
        
        if not name:
            raise JsonRpcError(
                code=-32602,
                message="Name cannot be empty"
            )
        
        if len(name) < 2:
            raise JsonRpcError(
                code=-32602,
                message="Name must be at least 2 characters long",
                data={"min_length": 2, "received_length": len(name)}
            )
        
        if len(name) > 100:
            raise JsonRpcError(
                code=-32602,
                message="Name too long",
                data={"max_length": 100, "received_length": len(name)}
            )
        
        # Check for valid characters (letters, spaces, hyphens, apostrophes)
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", name):
            raise JsonRpcError(
                code=-32602,
                message="Name contains invalid characters",
                data={"name": name, "allowed_chars": "letters, spaces, hyphens, apostrophes, periods"}
            )
        
        return name
    
    def log_action(self, action: str, user_id: str, details: Dict[str, Any], performed_by: Optional[str] = None):
        """Log user action for audit trail."""
        log_entry = AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            timestamp=time.time(),
            details=details,
            performed_by=performed_by
        )
        self.audit_logs.append(log_entry)
        logger.info(f"Audit: {action} for user {user_id} by {performed_by or 'system'}")

# Initialize user service
user_service = UserService()

@registry.register("create_user")
def create_user(name: str, email: str, role: str = "user", metadata: Optional[Dict[str, Any]] = None) -> dict:
    """Create a new user with comprehensive validation.
    
    This method demonstrates:
    - Input validation and sanitization
    - Business rule enforcement
    - Audit logging
    - Structured error responses
    
    Args:
        name: User's full name (2-100 characters, letters/spaces/hyphens only)
        email: Valid email address (unique, RFC compliant)
        role: User role (user, admin, moderator, guest)
        metadata: Optional additional user data
        
    Returns:
        Created user object with generated ID and timestamps
    """
    # Validate inputs
    validated_name = user_service.validate_name(name)
    user_service.validate_email(email)
    
    # Validate role
    if role not in user_service.valid_roles:
        raise JsonRpcError(
            code=-32602,
            message="Invalid user role",
            data={
                "role": role,
                "valid_roles": list(user_service.valid_roles)
            }
        )
    
    # Validate metadata
    if metadata is not None and not isinstance(metadata, dict):
        raise JsonRpcError(
            code=-32602,
            message="Metadata must be an object",
            data={"received_type": type(metadata).__name__}
        )
    
    # Create user
    user_id = str(uuid.uuid4())
    current_time = time.time()
    
    user = User(
        id=user_id,
        name=validated_name,
        email=email.strip().lower(),
        created_at=current_time,
        updated_at=current_time,
        role=role,
        metadata=metadata or {}
    )
    
    user_service.users[user_id] = user
    
    # Log action
    user_service.log_action(
        action="user_created",
        user_id=user_id,
        details={
            "name": validated_name,
            "email": user.email,
            "role": role
        }
    )
    
    logger.info(f"Created user: {user.name} ({user.email}) with ID {user_id}")
    return user.to_public_dict()

@registry.register("get_user")
def get_user(user_id: str, include_metadata: bool = False) -> dict:
    """Get user by ID with optional metadata inclusion."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise JsonRpcError(
            code=-32602,
            message="User ID must be a non-empty string",
            data={"received": user_id}
        )
    
    user = user_service.users.get(user_id)
    if not user or user.status == "deleted":
        raise JsonRpcError(
            code=-32602,
            message="User not found",
            data={"user_id": user_id}
        )
    
    user_data = user.to_public_dict()
    if not include_metadata:
        user_data.pop("metadata", None)
    
    return user_data

@registry.register("list_users")
def list_users(
    status: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    include_deleted: bool = False
) -> dict:
    """List users with filtering and pagination.
    
    This demonstrates advanced querying capabilities with pagination.
    """
    # Validate parameters
    if limit < 1 or limit > 1000:
        raise JsonRpcError(
            code=-32602,
            message="Limit must be between 1 and 1000",
            data={"limit": limit, "min": 1, "max": 1000}
        )
    
    if offset < 0:
        raise JsonRpcError(
            code=-32602,
            message="Offset must be non-negative",
            data={"offset": offset}
        )
    
    if status and status not in user_service.valid_statuses:
        raise JsonRpcError(
            code=-32602,
            message="Invalid status filter",
            data={"status": status, "valid_statuses": list(user_service.valid_statuses)}
        )
    
    if role and role not in user_service.valid_roles:
        raise JsonRpcError(
            code=-32602,
            message="Invalid role filter",
            data={"role": role, "valid_roles": list(user_service.valid_roles)}
        )
    
    # Filter users
    filtered_users = []
    for user in user_service.users.values():
        # Skip deleted users unless explicitly requested
        if user.status == "deleted" and not include_deleted:
            continue
        
        # Apply filters
        if status and user.status != status:
            continue
        if role and user.role != role:
            continue
        
        filtered_users.append(user)
    
    # Sort by creation date (newest first)
    filtered_users.sort(key=lambda u: u.created_at, reverse=True)
    
    # Apply pagination
    total_count = len(filtered_users)
    paginated_users = filtered_users[offset:offset + limit]
    
    return {
        "users": [user.to_public_dict() for user in paginated_users],
        "pagination": {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        },
        "filters": {
            "status": status,
            "role": role,
            "include_deleted": include_deleted
        }
    }

@registry.register("update_user")
def update_user(
    user_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> dict:
    """Update user information with partial updates and validation."""
    user = user_service.users.get(user_id)
    if not user or user.status == "deleted":
        raise JsonRpcError(
            code=-32602,
            message="User not found",
            data={"user_id": user_id}
        )
    
    changes = {}
    
    # Validate and apply name update
    if name is not None:
        validated_name = user_service.validate_name(name)
        if validated_name != user.name:
            changes["name"] = {"old": user.name, "new": validated_name}
            user.name = validated_name
    
    # Validate and apply email update
    if email is not None:
        # Temporarily remove current user from email check
        old_email = user.email
        user.email = ""  # Temporarily clear to avoid self-conflict
        try:
            user_service.validate_email(email)
            new_email = email.strip().lower()
            if new_email != old_email:
                changes["email"] = {"old": old_email, "new": new_email}
                user.email = new_email
            else:
                user.email = old_email  # Restore if no change
        except JsonRpcError:
            user.email = old_email  # Restore on validation error
            raise
    
    # Validate and apply role update
    if role is not None:
        if role not in user_service.valid_roles:
            raise JsonRpcError(
                code=-32602,
                message="Invalid user role",
                data={"role": role, "valid_roles": list(user_service.valid_roles)}
            )
        if role != user.role:
            changes["role"] = {"old": user.role, "new": role}
            user.role = role
    
    # Validate and apply status update
    if status is not None:
        if status not in user_service.valid_statuses:
            raise JsonRpcError(
                code=-32602,
                message="Invalid user status",
                data={"status": status, "valid_statuses": list(user_service.valid_statuses)}
            )
        if status != user.status:
            changes["status"] = {"old": user.status, "new": status}
            user.status = status
    
    # Update metadata
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise JsonRpcError(
                code=-32602,
                message="Metadata must be an object",
                data={"received_type": type(metadata).__name__}
            )
        if metadata != user.metadata:
            changes["metadata"] = {"old": user.metadata, "new": metadata}
            user.metadata = metadata
    
    # Update timestamp if any changes were made
    if changes:
        user.updated_at = time.time()
        
        # Log action
        user_service.log_action(
            action="user_updated",
            user_id=user_id,
            details={"changes": changes}
        )
        
        logger.info(f"Updated user {user_id}: {list(changes.keys())}")
    
    return {
        "user": user.to_public_dict(),
        "changes": changes,
        "updated": len(changes) > 0
    }

@registry.register("delete_user")
def delete_user(user_id: str, hard_delete: bool = False) -> dict:
    """Delete user with soft/hard delete options."""
    user = user_service.users.get(user_id)
    if not user:
        raise JsonRpcError(
            code=-32602,
            message="User not found",
            data={"user_id": user_id}
        )
    
    if user.status == "deleted":
        raise JsonRpcError(
            code=-32602,
            message="User already deleted",
            data={"user_id": user_id}
        )
    
    if hard_delete:
        # Permanently remove user
        del user_service.users[user_id]
        action = "user_hard_deleted"
        logger.info(f"Hard deleted user {user_id}")
    else:
        # Soft delete - mark as deleted
        user.status = "deleted"
        user.updated_at = time.time()
        action = "user_soft_deleted"
        logger.info(f"Soft deleted user {user_id}")
    
    # Log action
    user_service.log_action(
        action=action,
        user_id=user_id,
        details={"hard_delete": hard_delete}
    )
    
    return {
        "user_id": user_id,
        "deleted": True,
        "hard_delete": hard_delete,
        "timestamp": time.time()
    }

@registry.register("search_users")
def search_users(query: str, fields: List[str] = None, limit: int = 20) -> dict:
    """Search users by name or email with flexible field matching."""
    if not isinstance(query, str) or len(query.strip()) < 2:
        raise JsonRpcError(
            code=-32602,
            message="Search query must be at least 2 characters",
            data={"query": query}
        )
    
    if fields is None:
        fields = ["name", "email"]
    
    valid_fields = {"name", "email", "role"}
    invalid_fields = set(fields) - valid_fields
    if invalid_fields:
        raise JsonRpcError(
            code=-32602,
            message="Invalid search fields",
            data={"invalid_fields": list(invalid_fields), "valid_fields": list(valid_fields)}
        )
    
    query = query.strip().lower()
    matching_users = []
    
    for user in user_service.users.values():
        if user.status == "deleted":
            continue
        
        # Check each specified field
        for field in fields:
            field_value = getattr(user, field, "").lower()
            if query in field_value:
                matching_users.append({
                    "user": user.to_public_dict(),
                    "matched_field": field,
                    "match_position": field_value.find(query)
                })
                break  # Don't add the same user multiple times
    
    # Sort by relevance (exact matches first, then by match position)
    matching_users.sort(key=lambda x: (x["match_position"] != 0, x["match_position"]))
    
    return {
        "query": query,
        "fields_searched": fields,
        "results": matching_users[:limit],
        "total_matches": len(matching_users),
        "limited": len(matching_users) > limit
    }

@registry.register("get_user_audit_log")
def get_user_audit_log(user_id: str, limit: int = 50) -> dict:
    """Get audit log for a specific user."""
    user = user_service.users.get(user_id)
    if not user:
        raise JsonRpcError(
            code=-32602,
            message="User not found",
            data={"user_id": user_id}
        )
    
    # Filter audit logs for this user
    user_logs = [
        {
            "id": log.id,
            "action": log.action,
            "timestamp": log.timestamp,
            "details": log.details,
            "performed_by": log.performed_by
        }
        for log in user_service.audit_logs
        if log.user_id == user_id
    ]
    
    # Sort by timestamp (newest first)
    user_logs.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "user_id": user_id,
        "audit_logs": user_logs[:limit],
        "total_logs": len(user_logs),
        "limited": len(user_logs) > limit
    }

@registry.register("get_service_stats")
def get_service_stats() -> dict:
    """Get comprehensive service statistics."""
    total_users = len(user_service.users)
    
    # Count by status
    status_counts = {}
    role_counts = {}
    
    for user in user_service.users.values():
        status_counts[user.status] = status_counts.get(user.status, 0) + 1
        role_counts[user.role] = role_counts.get(user.role, 0) + 1
    
    # Recent activity (last 24 hours)
    recent_threshold = time.time() - 86400  # 24 hours ago
    recent_logs = [log for log in user_service.audit_logs if log.timestamp > recent_threshold]
    
    return {
        "total_users": total_users,
        "status_breakdown": status_counts,
        "role_breakdown": role_counts,
        "recent_activity": {
            "last_24_hours": len(recent_logs),
            "total_audit_logs": len(user_service.audit_logs)
        },
        "service_info": {
            "version": "1.0.0",
            "features": [
                "User CRUD operations",
                "Advanced search and filtering",
                "Audit logging",
                "Soft/hard delete",
                "Input validation",
                "Pagination support"
            ]
        }
    }

# Configure JSON-RPC plugin
JsonRpcPlugin(app, {
    "path_prefix": "/users",
    "cors_enabled": True,
    "max_request_size": 2 * 1024 * 1024  # 2MB for batch operations
})

if __name__ == "__main__":
    print("👥 Enterprise User Management Service")
    print("🔒 Features: Validation, audit logging, search, pagination")
    print("🔗 Endpoint: http://localhost:8000/users")
    print("\n📋 Available operations:")
    print("   - create_user(name, email, role?, metadata?)")
    print("   - get_user(user_id, include_metadata?)")
    print("   - list_users(status?, role?, limit?, offset?, include_deleted?)")
    print("   - update_user(user_id, name?, email?, role?, status?, metadata?)")
    print("   - delete_user(user_id, hard_delete?)")
    print("   - search_users(query, fields?, limit?)")
    print("   - get_user_audit_log(user_id, limit?)")
    print("   - get_service_stats()")
    
    app.run(host="0.0.0.0", port=8000)
```





Built with ❤️ by the [@nexios-labs](https://github.com/nexios-labs) community.