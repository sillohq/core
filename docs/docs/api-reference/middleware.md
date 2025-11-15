# Base Middleware

The `BaseMiddleware` class provides the foundation for creating custom middleware in Nexios, allowing you to intercept and process HTTP requests and responses.

## 📋 Class Definition

```python
class BaseMiddleware:
    def __init__(self, **kwargs: Dict[Any, Any]) -> None:
        pass

    async def __call__(
        self,
        request: Request,
        response: Response,
        call_next: Callable[..., Awaitable[Any]],
    ) -> Any:
        # Implementation
        pass

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: Callable[..., Awaitable[Response]],
    ) -> Any:
        return await call_next()

    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Any:
        return response
```

## 🔧 Creating Custom Middleware

### Basic Middleware Structure

```python
from nexios.middleware import BaseMiddleware

class LoggingMiddleware(BaseMiddleware):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = logging.getLogger(__name__)

    async def process_request(self, request, response, call_next):
        start_time = time.time()
        
        # Log incoming request
        self.logger.info(f"Incoming: {request.method} {request.path}")
        
        # Process request
        result = await call_next()
        
        # Log processing time
        duration = time.time() - start_time
        self.logger.info(f"Processed in {duration:.4f}s")
        
        return result

    async def process_response(self, request, response):
        # Add response headers
        response.set_header("X-Processing-Time", str(time.time()))
        return response
```

### Authentication Middleware

```python
class AuthenticationMiddleware(BaseMiddleware):
    def __init__(self, secret_key: str, **kwargs):
        super().__init__(**kwargs)
        self.secret_key = secret_key

    async def process_request(self, request, response, call_next):
        # Skip authentication for public endpoints
        if request.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next()

        # Extract token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return response.status(401).json({"error": "Authentication required"})

        token = auth_header[7:]  # Remove "Bearer " prefix
        
        try:
            # Verify token
            user = await self.verify_token(token)
            request.state.user = user
            return await call_next()
        except InvalidTokenError:
            return response.status(401).json({"error": "Invalid token"})

    async def verify_token(self, token: str):
        # Token verification logic
        import jwt
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return await get_user_by_id(user_id)
        except jwt.InvalidTokenError:
            raise InvalidTokenError("Token is invalid")
```

### Rate Limiting Middleware

```python
import asyncio
from collections import defaultdict, deque
from time import time

class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, requests_per_minute: int = 60, **kwargs):
        super().__init__(**kwargs)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def process_request(self, request, response, call_next):
        client_ip = self.get_client_ip(request)
        
        async with self.lock:
            now = time()
            minute_ago = now - 60
            
            # Clean old requests
            while (self.requests[client_ip] and 
                   self.requests[client_ip][0] < minute_ago):
                self.requests[client_ip].popleft()
            
            # Check rate limit
            if len(self.requests[client_ip]) >= self.requests_per_minute:
                return response.status(429).json({
                    "error": "Rate limit exceeded",
                    "retry_after": 60
                })
            
            # Record this request
            self.requests[client_ip].append(now)
        
        return await call_next()

    def get_client_ip(self, request):
        # Handle proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
```

## 🔄 Middleware Execution Flow

### Request Processing Flow

```python
class RequestFlowMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        print("1. Before request processing")
        
        # Modify request if needed
        request.state.middleware_data = "processed"
        
        # Call next middleware/handler
        result = await call_next()
        
        print("4. After request processing")
        return result

    async def process_response(self, request, response):
        print("5. Processing response")
        
        # Modify response if needed
        response.set_header("X-Middleware", "processed")
        
        print("6. Response processed")
        return response
```

### Error Handling Middleware

```python
class ErrorHandlingMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        try:
            return await call_next()
        except ValidationError as e:
            return response.status(400).json({
                "error": "Validation failed",
                "details": e.errors()
            })
        except PermissionError:
            return response.status(403).json({
                "error": "Permission denied"
            })
        except NotFoundError:
            return response.status(404).json({
                "error": "Resource not found"
            })
        except Exception as e:
            # Log unexpected errors
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return response.status(500).json({
                "error": "Internal server error"
            })
```

## 🚀 Advanced Middleware Patterns

### Conditional Middleware

```python
class ConditionalMiddleware(BaseMiddleware):
    def __init__(self, condition_func, **kwargs):
        super().__init__(**kwargs)
        self.condition_func = condition_func

    async def process_request(self, request, response, call_next):
        if await self.condition_func(request):
            # Apply middleware logic
            request.state.conditional_applied = True
            return await self.custom_processing(request, response, call_next)
        else:
            # Skip middleware
            return await call_next()

    async def custom_processing(self, request, response, call_next):
        # Custom middleware logic here
        return await call_next()

# Usage
async def is_api_request(request):
    return request.path.startswith("/api/")

conditional_middleware = ConditionalMiddleware(is_api_request)
```

### Caching Middleware

```python
import hashlib
import json

class CacheMiddleware(BaseMiddleware):
    def __init__(self, cache_backend, ttl: int = 300, **kwargs):
        super().__init__(**kwargs)
        self.cache = cache_backend
        self.ttl = ttl

    async def process_request(self, request, response, call_next):
        # Only cache GET requests
        if request.method != "GET":
            return await call_next()

        # Generate cache key
        cache_key = self.generate_cache_key(request)
        
        # Try to get from cache
        cached_response = await self.cache.get(cache_key)
        if cached_response:
            return response.json(cached_response)

        # Process request
        result = await call_next()
        
        # Cache successful responses
        if response.status_code == 200:
            await self.cache.set(cache_key, result, ttl=self.ttl)
        
        return result

    def generate_cache_key(self, request):
        # Create cache key from URL and query parameters
        key_data = {
            "path": request.path,
            "query": dict(request.query_params),
            "user_id": getattr(request.state, "user_id", None)
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
```

### Request/Response Transformation

```python
class TransformationMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        # Transform request data
        if request.is_json:
            json_data = await request.json
            # Convert snake_case to camelCase
            transformed_data = self.snake_to_camel(json_data)
            request.state.transformed_data = transformed_data

        result = await call_next()
        return result

    async def process_response(self, request, response):
        # Transform response data
        if hasattr(response, '_body') and response.content_type == "application/json":
            try:
                response_data = json.loads(response._body.decode())
                # Convert camelCase to snake_case
                transformed_data = self.camel_to_snake(response_data)
                response.set_body(json.dumps(transformed_data).encode())
            except (json.JSONDecodeError, AttributeError):
                pass  # Skip transformation if not valid JSON
        
        return response

    def snake_to_camel(self, data):
        if isinstance(data, dict):
            return {
                self.to_camel_case(key): self.snake_to_camel(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self.snake_to_camel(item) for item in data]
        return data

    def camel_to_snake(self, data):
        if isinstance(data, dict):
            return {
                self.to_snake_case(key): self.camel_to_snake(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self.camel_to_snake(item) for item in data]
        return data

    def to_camel_case(self, snake_str):
        components = snake_str.split('_')
        return components[0] + ''.join(x.capitalize() for x in components[1:])

    def to_snake_case(self, camel_str):
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
```

## 📝 Middleware Registration

### Application-level Middleware

```python
from nexios import NexiosApp

app = NexiosApp()

# Add middleware to the entire application
app.add_middleware(LoggingMiddleware())
app.add_middleware(AuthenticationMiddleware(secret_key="your-secret"))
app.add_middleware(RateLimitMiddleware(requests_per_minute=100))
```

### Router-level Middleware

```python
from nexios.routing import Router

# Create router with middleware
api_router = Router(
    prefix="/api",
    middleware=[
        AuthenticationMiddleware(secret_key="api-secret"),
        RateLimitMiddleware(requests_per_minute=60)
    ]
)

# Or add middleware to existing router
api_router.add_middleware(CacheMiddleware(cache_backend=redis_cache))

app.mount_router(api_router)
```

### Route-specific Middleware

```python
async def admin_only_middleware(request, response, call_next):
    user = getattr(request.state, "user", None)
    if not user or not user.is_admin:
        return response.status(403).json({"error": "Admin access required"})
    return await call_next()

@app.get("/admin/users", middleware=[admin_only_middleware])
async def admin_users(request, response):
    users = await get_all_users_admin()
    return response.json(users)
```

## 🧪 Middleware Testing

### Unit Testing Middleware

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_logging_middleware():
    middleware = LoggingMiddleware()
    
    # Mock request and response
    request = AsyncMock()
    request.method = "GET"
    request.path = "/test"
    
    response = AsyncMock()
    
    # Mock call_next
    async def mock_call_next():
        return response
    
    # Test middleware
    result = await middleware.process_request(request, response, mock_call_next)
    
    assert result == response
```

### Integration Testing

```python
from nexios.testing import TestClient

def test_middleware_integration():
    app = NexiosApp()
    
    # Add middleware
    app.add_middleware(LoggingMiddleware())
    
    @app.get("/test")
    async def test_route(request, response):
        return response.json({"message": "test"})
    
    client = TestClient(app)
    response = client.get("/test")
    
    assert response.status_code == 200
    assert "X-Processing-Time" in response.headers
```

## ⚡ Performance Considerations

### Lightweight Middleware

```python
class FastMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        # Keep processing minimal
        if request.path == "/health":
            return response.json({"status": "ok"})
        
        return await call_next()
```

### Async Operations

```python
class AsyncMiddleware(BaseMiddleware):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = aiohttp.ClientSession()

    async def process_request(self, request, response, call_next):
        # Perform async operations efficiently
        async with self.session.get("http://external-api.com/validate") as resp:
            if resp.status != 200:
                return response.status(503).json({"error": "Service unavailable"})
        
        return await call_next()

    async def cleanup(self):
        await self.session.close()
```

## 📦 Built-in Middleware

Nexios provides several built-in middleware classes:

### CORS Middleware

```python
from nexios.middleware import CORSMiddleware

app.add_middleware(CORSMiddleware(
    allow_origins=["https://example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
))
```

### CSRF Middleware

```python
from nexios.middleware import CSRFMiddleware

app.add_middleware(CSRFMiddleware(
    secret_key="your-csrf-secret"
))
```

### Session Middleware

```python
from nexios.middleware import SessionMiddleware

app.add_middleware(SessionMiddleware(
    secret_key="session-secret",
    max_age=86400  # 24 hours
))
```

### Security Middleware

```python
from nexios.middleware import SecurityMiddleware

app.add_middleware(SecurityMiddleware(
    force_https=True,
    hsts_max_age=31536000,
    content_type_nosniff=True
))
```

## ✨ Best Practices

1. **Keep middleware focused** - Each middleware should have a single responsibility
2. **Handle errors gracefully** - Always include proper error handling
3. **Minimize performance impact** - Keep processing lightweight
4. **Use async/await properly** - Ensure all async operations are awaited
5. **Test thoroughly** - Write comprehensive tests for middleware logic
6. **Document behavior** - Clearly document what each middleware does
7. **Consider order** - Middleware execution order matters
8. **Clean up resources** - Properly close connections and clean up
9. **Use type hints** - Provide clear type annotations
10. **Monitor performance** - Profile middleware for bottlenecks

## 💡 Common Use Cases

### API Versioning

```python
class APIVersionMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        # Extract version from header or URL
        version = request.headers.get("API-Version", "v1")
        request.state.api_version = version
        
        # Route to appropriate handler based on version
        if version == "v2" and request.path.startswith("/api/v1/"):
            # Redirect v1 requests to v2 if needed
            new_path = request.path.replace("/api/v1/", "/api/v2/")
            return response.redirect(new_path)
        
        return await call_next()
```

### Request ID Tracking

```python
import uuid

class RequestIDMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        result = await call_next()
        return result

    async def process_response(self, request, response):
        # Add request ID to response
        request_id = getattr(request.state, "request_id", "unknown")
        response.set_header("X-Request-ID", request_id)
        return response
```

### Content Compression

```python
import gzip

class CompressionMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        result = await call_next()
        return result

    async def process_response(self, request, response):
        # Check if client accepts gzip
        accept_encoding = request.headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding:
            return response

        # Compress response body if it's large enough
        if hasattr(response, '_body') and len(response._body) > 1024:
            compressed_body = gzip.compress(response._body)
            response.set_body(compressed_body)
            response.set_header("Content-Encoding", "gzip")
            response.set_header("Content-Length", str(len(compressed_body)))

        return response
```

## 🔍 See Also

- [CORS Middleware](./cors.md) - Cross-origin resource sharing
- [CSRF Middleware](./csrf.md) - Cross-site request forgery protection
- [Session Middleware](./session.md) - Session management
- [Security Middleware](./security.md) - Security headers and protection
- [Application](../application/nexios-app.md) - Application middleware setup
- [Router](../routing/router.md) - Router-level middleware