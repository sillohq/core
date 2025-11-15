# Timeout Middleware

Timeout middleware and utilities for Nexios web framework, providing flexible request timeout handling, duration tracking, and timeout-based control flow.

## Features

- ⏱️ **Global and Per-Request Timeouts**: Set timeouts at both application and request levels
- 🔍 **Automatic Timeout Extraction**: Extract timeout values from headers or query parameters
- ⚡ **Async Timeout Control**: Built-in support for async/await patterns
- 📊 **Request Duration Tracking**: Monitor how long requests take to process
- 🛠️ **Flexible Error Handling**: Customize timeout responses or raise exceptions
- 🔄 **Timeout Utilities**: Helper functions for common timeout-related tasks

## Installation

```bash
# Install with pip
pip install nexios-contrib

# Or with uv (recommended)
uv add nexios-contrib
```

## Quick Start

### Basic Usage

```python
from nexios import NexiosApp
from nexios_contrib.timeout import Timeout

app = NexiosApp()

# Add timeout middleware with default 30s timeout
app.add_middleware(Timeout(default_timeout=30.0))

@app.get("/slow-endpoint")
async def slow_endpoint():
    # This will be automatically interrupted if it takes longer than 30 seconds
    await asyncio.sleep(35)
    return {"message": "This will never be reached"}
```

### Per-Request Timeout

```python
from nexios import NexiosApp, Request
from nexios_contrib.timeout import Timeout, get_timeout_from_request

app = NexiosApp()
app.add_middleware(Timeout())

@app.get("/api/data")
async def get_data(request: Request):
    # Get timeout from request headers or query params
    timeout = get_timeout_from_request(request, default_timeout=10.0)
    
    # Use the timeout for your operations
    try:
        result = await some_operation()
        return {"data": result}
    except asyncio.TimeoutError:
        return {"error": "Operation timed out"}
```

## Configuration Options

### Timeout Middleware

The `Timeout` middleware accepts the following parameters:

```python
app.add_middleware(
    Timeout(
        default_timeout=30.0,      # Default timeout in seconds
        max_timeout=300.0,         # Maximum allowed timeout (None for no limit)
        min_timeout=0.1,           # Minimum allowed timeout
        timeout_header="X-Request-Timeout",  # Header to check for timeout
        timeout_param="timeout",   # Query parameter to check for timeout
        track_duration=True,       # Add X-Request-Duration header
        timeout_response_enabled=True,  # Return timeout responses
        exception_on_timeout=False  # Raise exception instead of returning response
    )
)
```

### Timeout Sources

Timeouts can be specified in multiple ways (in order of precedence):

1. **Request Header**: `X-Request-Timeout: 5.0`
2. **Query Parameter**: `?timeout=5.0`
3. **Default Timeout**: As specified in middleware configuration

## Advanced Usage

### Using the Timeout Decorator

```python
from nexios_contrib.timeout import timeout_after, TimeoutException

@timeout_after(5.0)  # 5 second timeout
async def fetch_data():
    # This will raise TimeoutException if it takes longer than 5 seconds
    return await some_long_running_operation()

# In your route handler
@app.get("/fetch")
async def get_data():
    try:
        data = await fetch_data()
        return {"data": data}
    except TimeoutException as e:
        return {"error": str(e)}
```

### Timeout with Fallback

```python
from nexios_contrib.timeout import timeout_with_fallback

@app.get("/cached-data")
async def get_cached_data():
    # Try to get fresh data, fall back to cache if it takes too long
    data = await timeout_with_fallback(
        fetch_fresh_data(),  # Primary data source
        timeout=2.0,         # 2 second timeout
        fallback_value=get_cached_version(),  # Fallback value
        fallback_exception=None  # Or raise an exception instead
    )
    return {"data": data}
```

### Custom Timeout Response

```python
from nexios.http import Response
from nexios_contrib.timeout import create_timeout_response

@app.exception_handler(TimeoutException)
async def timeout_exception_handler(request, exc):
    return create_timeout_response(
        timeout=exc.timeout,
        detail={
            "error": "Request Timeout",
            "message": f"The request took longer than {exc.timeout} seconds",
            "status_code": 408
        }
    )
```

## Request Duration Tracking

When `track_duration` is enabled, the middleware adds an `X-Request-Duration` header to responses:

```
X-Request-Duration: 1.234s
```

### Accessing Duration Information

```python
@app.get("/api/stats")
async def get_stats(request, response):
    # Duration is automatically tracked and added to response headers
    return {"message": "Check the X-Request-Duration header"}

@app.middleware
async def duration_logger(request, response, call_next):
    from nexios_contrib.timeout import get_request_duration
    
    response = await call_next()
    
    duration = get_request_duration(request)
    if duration:
        print(f"Request took {duration:.3f} seconds")
    
    return response
```

## Examples

### API with Different Timeout Strategies

```python
from nexios import NexiosApp
from nexios_contrib.timeout import Timeout, timeout_after, TimeoutException

app = NexiosApp()

# Global timeout middleware
app.add_middleware(
    Timeout(
        default_timeout=30.0,
        max_timeout=120.0,
        track_duration=True
    )
)

@app.get("/api/quick")
async def quick_endpoint():
    # Uses global timeout (30s)
    await asyncio.sleep(1)
    return {"message": "Quick response"}

@app.get("/api/custom-timeout")
async def custom_timeout_endpoint(request):
    # Client can specify timeout via header: X-Request-Timeout: 60
    # Or query param: ?timeout=60
    await asyncio.sleep(45)
    return {"message": "Custom timeout response"}

@timeout_after(10.0)
@app.get("/api/decorated")
async def decorated_endpoint():
    # Uses decorator timeout (10s) regardless of global settings
    await asyncio.sleep(5)
    return {"message": "Decorated response"}

@app.get("/api/fallback")
async def fallback_endpoint():
    from nexios_contrib.timeout import timeout_with_fallback
    
    # Try fast operation, fallback to cached data
    try:
        data = await timeout_with_fallback(
            fetch_live_data(),
            timeout=5.0,
            fallback_value={"cached": True, "data": "fallback"}
        )
        return {"data": data}
    except TimeoutException:
        return {"error": "Both live and fallback failed"}
```

### Database Query Timeouts

```python
import asyncpg
from nexios_contrib.timeout import timeout_after

@timeout_after(10.0)
async def get_user_from_db(user_id: int):
    async with asyncpg.connect("postgresql://...") as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

@app.get("/users/{user_id}")
async def get_user(request, response, user_id: int):
    try:
        user = await get_user_from_db(user_id)
        if user:
            return {"user": dict(user)}
        else:
            return {"error": "User not found"}, 404
    except TimeoutException:
        return {"error": "Database query timed out"}, 504
```

### External API Calls with Timeout

```python
import httpx
from nexios_contrib.timeout import timeout_after

@timeout_after(15.0)
async def fetch_external_data(api_key: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.example.com/data",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0  # httpx timeout
        )
        return response.json()

@app.get("/external-data")
async def get_external_data(request, response):
    api_key = request.headers.get("Authorization")
    
    try:
        data = await fetch_external_data(api_key)
        return {"external_data": data}
    except TimeoutException:
        return {"error": "External API call timed out"}, 504
    except httpx.TimeoutException:
        return {"error": "HTTP request timed out"}, 504
```

## Best Practices

1. **Set Reasonable Timeouts**: Always set appropriate timeouts for your application's needs
2. **Graceful Degradation**: Use fallbacks when operations time out
3. **Monitor Timeouts**: Track timeout occurrences to identify performance issues
4. **Document Timeout Behavior**: Let API consumers know about timeout behavior and limits
5. **Layer Timeouts**: Use different timeout strategies at different levels (HTTP client, database, application)

### Production Configuration

```python
from nexios import NexiosApp
from nexios_contrib.timeout import Timeout
import logging

app = NexiosApp()

# Configure timeout middleware for production
app.add_middleware(
    Timeout(
        default_timeout=30.0,      # 30 second default
        max_timeout=300.0,         # 5 minute maximum
        min_timeout=1.0,           # 1 second minimum
        track_duration=True,       # Track request durations
        timeout_response_enabled=True
    )
)

# Log timeout events
@app.middleware
async def timeout_logger(request, response, call_next):
    from nexios_contrib.timeout import get_request_duration
    
    try:
        response = await call_next()
        
        duration = get_request_duration(request)
        if duration and duration > 10.0:  # Log slow requests
            logging.warning(f"Slow request: {request.url.path} took {duration:.2f}s")
        
        return response
    except TimeoutException as e:
        logging.error(f"Request timeout: {request.url.path} after {e.timeout}s")
        raise
```

## API Reference

### Classes

- **`Timeout`**: Middleware for request timeout handling
- **`TimeoutException`**: Exception raised on timeouts

### Functions

- **`timeout_after`**: Decorator for adding timeouts to async functions
- **`timeout_with_fallback`**: Execute with timeout and fallback
- **`get_timeout_from_request`**: Extract timeout from request
- **`create_timeout_response`**: Create a timeout error response
- **`is_timeout_error`**: Check if an exception is timeout-related
- **`format_timeout_duration`**: Format duration in human-readable format
- **`get_request_duration`**: Get request processing duration
- **`set_request_start_time`**: Set request start time for duration tracking

### Utility Functions

```python
from nexios_contrib.timeout import (
    format_timeout_duration,
    is_timeout_error,
    get_request_start_time
)

# Format duration for display
duration_str = format_timeout_duration(123.456)  # "2m 3.456s"

# Check if exception is timeout-related
if is_timeout_error(some_exception):
    print("This was a timeout error")

# Get when request started
start_time = get_request_start_time(request)
```

## Troubleshooting

### Common Issues

**Timeouts not working**
- Ensure the middleware is added to your app
- Check that async operations are properly awaited
- Verify timeout values are reasonable

**Duration tracking not working**
- Ensure `track_duration=True` in middleware config
- Check that response headers are being sent
- Verify middleware order

**Custom timeouts ignored**
- Check header name configuration
- Verify query parameter name
- Ensure values are within min/max limits

### Debug Timeout Issues

```python
@app.middleware
async def timeout_debug(request, response, call_next):
    from nexios_contrib.timeout import get_timeout_from_request
    
    timeout = get_timeout_from_request(request)
    print(f"Request timeout: {timeout}s")
    
    start_time = time.time()
    try:
        response = await call_next()
        duration = time.time() - start_time
        print(f"Request completed in {duration:.3f}s")
        return response
    except Exception as e:
        duration = time.time() - start_time
        print(f"Request failed after {duration:.3f}s: {e}")
        raise
```

Built with ❤️ by the [@nexios-labs](https://github.com/nexios-labs) community.