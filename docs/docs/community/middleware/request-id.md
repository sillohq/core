# Request ID Middleware

A lightweight, production‑ready request ID middleware for the Nexios ASGI framework.

It automatically:

- Generates unique request IDs for all incoming requests
- Extracts request IDs from incoming request headers (`X-Request-ID`)
- Stores request IDs in request objects for later access
- Includes request IDs in response headers for better tracing
- Supports custom header names and configuration options

## Installation

```bash
pip install nexios_contrib
```

## Quick Start

```python
from nexios import NexiosApp
import nexios_contrib.request_id as request_id

app = NexiosApp()

# Add the Request ID middleware (defaults shown)
app.add_middleware(
    request_id.RequestId(
        header_name="X-Request-ID",    # Header name for request ID
        force_generate=False,          # Use existing request ID if provided
        store_in_request=True,         # Store request ID in request object
        include_in_response=True       # Include request ID in response headers
    )
)

@app.get("/")
async def home(request, response):
    # Access request ID from request object
    req_id = getattr(request, 'request_id', None)
    return {"message": "Hello with Request ID!", "request_id": req_id}
```

That's it! Every request will now have a unique request ID that can be used for tracing and debugging.

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `header_name` | `str` | `"X-Request-ID"` | Header name to use for request ID extraction and setting |
| `force_generate` | `bool` | `False` | Always generate new request ID instead of using existing one |
| `store_in_request` | `bool` | `True` | Store request ID in request object for later access |
| `request_attribute_name` | `str` | `"request_id"` | Attribute name to store request ID in request object |
| `include_in_response` | `bool` | `True` | Include request ID in response headers |

## Usage Examples

### Basic Usage

```python
from nexios import NexiosApp
from nexios_contrib.request_id import RequestId

app = NexiosApp()

# Add middleware with default settings
app.add_middleware(RequestId())
```

### Custom Configuration

```python
from nexios import NexiosApp
from nexios_contrib.request_id import RequestId

app = NexiosApp()

# Custom configuration
app.add_middleware(
    RequestId(
        header_name="X-Correlation-ID",  # Use different header name
        force_generate=True,             # Always generate new request ID
        store_in_request=True,           # Store in request object
        include_in_response=True,        # Include in response headers
        request_attribute_name="req_id"  # Custom attribute name
    )
)
```

### Using Helper Functions

```python
from nexios_contrib.request_id import (
    generate_request_id,
    get_or_generate_request_id,
    validate_request_id
)

# Generate a new request ID
new_id = generate_request_id()

# Get or generate request ID from request
req_id = get_or_generate_request_id(request)

# Validate request ID format
is_valid = validate_request_id(some_request_id)
```

### Accessing Request ID in Handlers

```python
@app.get("/api/users")
async def get_users(request, response):
    # Method 1: Get from request object
    request_id = getattr(request, 'request_id', None)

    # Method 2: Extract from headers
    request_id = request.headers.get('X-Request-ID')

    # Method 3: Use helper function
    from nexios_contrib.request_id import get_request_id_from_request
    request_id = get_request_id_from_request(request)

    return {"users": [], "request_id": request_id}
```

## Features

- **Automatic Generation**: Generates UUID4-based request IDs automatically
- **Header Support**: Extracts request IDs from incoming request headers
- **Request Storage**: Stores request IDs in request objects for easy access
- **Response Headers**: Includes request IDs in response headers for client-side tracing
- **Customizable**: Highly configurable with various options for different use cases
- **Validation**: Built-in validation for request ID format
- **Thread Safe**: Safe for use in concurrent ASGI applications

## Advanced Usage

### Logging with Request ID

```python
import logging
from nexios_contrib.request_id import RequestId

app = NexiosApp()
app.add_middleware(RequestId())

# Configure logging to include request ID
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
)

@app.middleware
async def logging_middleware(request, response, call_next):
    request_id = getattr(request, 'request_id', 'unknown')
    
    # Add request ID to log context
    logger = logging.getLogger(__name__)
    logger = logging.LoggerAdapter(logger, {'request_id': request_id})
    
    logger.info(f"Processing request: {request.method} {request.url.path}")
    
    response = await call_next()
    
    logger.info(f"Request completed with status: {response.status_code}")
    return response

@app.get("/api/data")
async def get_data(request, response):
    request_id = getattr(request, 'request_id', None)
    logging.info(f"Processing request {request_id}")

    # Your handler logic here
    return {"data": "example", "request_id": request_id}
```

### Custom Request ID Format

```python
from nexios_contrib.request_id import RequestIdMiddleware

class CustomRequestIdMiddleware(RequestIdMiddleware):
    def __init__(self, prefix: str = "req", **kwargs):
        super().__init__(**kwargs)
        self.prefix = prefix

    def generate_request_id(self) -> str:
        # Generate custom request ID with prefix
        import uuid
        return f"{self.prefix}-{uuid.uuid4().hex[:8]}"

app.add_middleware(CustomRequestIdMiddleware(prefix="api"))
```

### Distributed Tracing Integration

```python
from nexios_contrib.request_id import RequestId
import opentelemetry.trace as trace

app = NexiosApp()
app.add_middleware(RequestId())

@app.middleware
async def tracing_middleware(request, response, call_next):
    request_id = getattr(request, 'request_id', None)
    
    # Add request ID to OpenTelemetry span
    span = trace.get_current_span()
    if span and request_id:
        span.set_attribute("request.id", request_id)
    
    return await call_next()
```

### Request ID Propagation

```python
import httpx
from nexios_contrib.request_id import get_request_id_from_request

@app.get("/api/external")
async def call_external_api(request, response):
    request_id = get_request_id_from_request(request)
    
    # Propagate request ID to external services
    async with httpx.AsyncClient() as client:
        external_response = await client.get(
            "https://api.example.com/data",
            headers={"X-Request-ID": request_id}
        )
    
    return {
        "external_data": external_response.json(),
        "request_id": request_id
    }
```

## Best Practices

1. **Always include request IDs in logs** for better debugging and tracing
2. **Use consistent header names** across your microservices
3. **Store request IDs early** in the middleware chain to ensure they're available to all handlers
4. **Consider using different header names** for internal vs external request IDs
5. **Validate request IDs** from external sources before using them
6. **Propagate request IDs** to downstream services for distributed tracing

### Production Configuration

```python
from nexios import NexiosApp
from nexios_contrib.request_id import RequestId
import logging

app = NexiosApp()

# Configure request ID middleware
app.add_middleware(
    RequestId(
        header_name="X-Request-ID",
        force_generate=False,  # Use client-provided IDs when available
        store_in_request=True,
        include_in_response=True
    )
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "request_id": "%(request_id)s", "message": "%(message)s"}'
)

@app.middleware
async def structured_logging(request, response, call_next):
    request_id = getattr(request, 'request_id', 'unknown')
    logger = logging.LoggerAdapter(
        logging.getLogger(__name__), 
        {'request_id': request_id}
    )
    
    start_time = time.time()
    logger.info(f"Request started: {request.method} {request.url.path}")
    
    try:
        response = await call_next()
        duration = time.time() - start_time
        logger.info(f"Request completed: {response.status_code} in {duration:.3f}s")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Request failed: {str(e)} in {duration:.3f}s")
        raise
```

## Integration Examples

### With Database Queries

```python
import asyncpg
from nexios_contrib.request_id import get_request_id_from_request

@app.get("/api/users/{user_id}")
async def get_user(request, response, user_id: int):
    request_id = get_request_id_from_request(request)
    
    # Include request ID in database queries for tracing
    async with asyncpg.connect("postgresql://...") as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1 -- Request ID: $2",
            user_id, request_id
        )
    
    return {"user": dict(user), "request_id": request_id}
```

### With Background Tasks

```python
from nexios_contrib.request_id import get_request_id_from_request
import asyncio

@app.post("/api/process")
async def start_processing(request, response):
    request_id = get_request_id_from_request(request)
    data = await request.json
    
    # Pass request ID to background task
    asyncio.create_task(process_data_async(data, request_id))
    
    return {"status": "processing", "request_id": request_id}

async def process_data_async(data, request_id):
    logger = logging.LoggerAdapter(
        logging.getLogger(__name__), 
        {'request_id': request_id}
    )
    
    logger.info("Starting background processing")
    # Process data...
    logger.info("Background processing completed")
```

### With Error Handling

```python
from nexios.exceptions import HTTPException
from nexios_contrib.request_id import get_request_id_from_request

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    request_id = get_request_id_from_request(request)
    
    return {
        "error": exc.detail,
        "status_code": exc.status_code,
        "request_id": request_id,
        "timestamp": datetime.utcnow().isoformat()
    }, exc.status_code

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    request_id = get_request_id_from_request(request)
    
    # Log the error with request ID
    logger = logging.LoggerAdapter(
        logging.getLogger(__name__), 
        {'request_id': request_id}
    )
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return {
        "error": "Internal server error",
        "request_id": request_id
    }, 500
```

## Troubleshooting

### Request ID Not Appearing

If request IDs aren't being generated or stored:

1. Ensure the middleware is added to your app
2. Check that `store_in_request=True`
3. Verify the middleware is added early in the chain

### Duplicate Request IDs

If you're seeing duplicate request IDs:

1. Check if `force_generate=True` is needed
2. Verify that client-provided IDs are unique
3. Consider using a different ID generation strategy

### Performance Issues

If request ID generation is causing performance issues:

1. Consider using shorter ID formats
2. Use custom ID generation for better performance
3. Profile your application to identify bottlenecks

Built with ❤️ by the [@nexios-labs](https://github.com/nexios-labs) community.