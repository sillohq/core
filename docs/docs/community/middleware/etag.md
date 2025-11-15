# ETag Middleware

A lightweight, production‑ready ETag middleware for the Nexios ASGI framework.

It automatically:

- Computes and sets an `ETag` header for responses that don't already have one
- Handles conditional `GET`/`HEAD` requests via `If-None-Match` and returns `304 Not Modified` when appropriate

## Installation

```bash
pip install nexios_contrib
```

## Quick Start

```python
from nexios import NexiosApp
import nexios_contrib.etag as etag

app = NexiosApp()

# Add the ETag middleware (defaults shown)
app.add_middleware(
    etag.ETag(
        weak=True,                 # Generate weak validators (W/ prefixes)
        methods=("GET", "HEAD"),  # Methods to apply to
        override=False             # Don't overwrite an existing ETag by default
    )
)

@app.get("/")
async def home(request, response):
    return {"message": "Hello with ETag!"}
```

That's it! Responses to `GET`/`HEAD` will carry an `ETag` header. Clients sending `If-None-Match` will receive `304` when the ETag matches.

## Configuration

### Parameters

- **`weak: bool = True`**  
  Use weak validators (e.g. `W/"abc"`). Set `False` for strong validators when you know the body bytes are stable across platforms and encodings.

- **`methods: Iterable[str] = ("GET", "HEAD")`**  
  Limit conditional handling to idempotent methods. You can add others, but it's not typical.

- **`override: bool = False`**  
  If `True`, overwrites an `ETag` already set by your handler.

## How It Works

1. If the handler doesn't set an `ETag`, the middleware computes one from the response body and sets it
2. If the request includes `If-None-Match` and it matches the response's `ETag` (weak compare by default), the middleware converts the response into `304 Not Modified` and removes the body, per RFC 9110

## Examples

### Basic Usage

```python
from nexios import NexiosApp
import nexios_contrib.etag as etag

app = NexiosApp()
app.add_middleware(etag.ETag())

@app.get("/api/data")
async def get_data(request, response):
    # This response will automatically get an ETag
    return {"data": "some content", "timestamp": "2024-01-01"}

# First request: Returns 200 with ETag: W/"abc123"
# Second request with If-None-Match: W/"abc123": Returns 304 Not Modified
```

### Strong ETags

```python
app.add_middleware(
    etag.ETag(
        weak=False,  # Use strong validators
        methods=("GET", "HEAD")
    )
)

@app.get("/api/file")
async def get_file(request, response):
    # Strong ETag will be generated: "abc123" (no W/ prefix)
    return {"file_content": "binary data"}
```

### Custom Methods

```python
app.add_middleware(
    etag.ETag(
        methods=("GET", "HEAD", "POST"),  # Include POST (not recommended)
        override=True  # Override existing ETags
    )
)
```

## Best Practices

- **Use for idempotent methods**: Apply by default to `GET` and `HEAD`. Avoid applying to mutating methods like `POST`/`PUT` unless you know what you're doing
- **Consider response size**: Streaming or extremely large bodies may benefit from precomputed/strong ETags at your handler or via a hash of a stable resource version
- **Weak vs Strong**: Use weak ETags (default) unless you need byte-for-byte identical responses
- **Cache-friendly**: ETags work great with HTTP caching - browsers and CDNs will use them automatically

## Advanced Usage

### Manual ETag Setting

```python
@app.get("/api/custom")
async def custom_etag(request, response):
    # Set your own ETag - middleware won't override by default
    response.headers['ETag'] = 'W/"custom-etag-123"'
    return {"data": "custom content"}
```

### Conditional Logic

```python
@app.get("/api/conditional")
async def conditional_response(request, response):
    # Check if client has current version
    if_none_match = request.headers.get('If-None-Match')
    current_etag = 'W/"version-456"'
    
    if if_none_match == current_etag:
        # Client has current version
        response.status_code = 304
        return None
    
    # Return new content
    response.headers['ETag'] = current_etag
    return {"data": "updated content"}
```

## Notes

- When returning `304`, the middleware ensures the body is empty and relies on the underlying response type to handle headers correctly
- ETags are computed from the response body, so identical content will have identical ETags
- The middleware respects existing ETags unless `override=True` is set

## Performance Considerations

- ETag computation adds minimal overhead for small responses
- For large responses, consider pre-computing ETags based on resource versions
- ETags enable efficient caching, reducing server load for repeated requests
- Use with appropriate `Cache-Control` headers for optimal caching behavior

Built with ❤️ by the [@nexios-labs](https://github.com/nexios-labs) community.