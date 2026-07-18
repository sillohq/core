---
title: URL Normalization
description: Normalize URLs — trailing slashes, double slashes, and case — with the sillo.normalize module.
---

# URL Normalization

A production‑ready URL normalization middleware for sillo, shipped as the first‑party `sillo.normalize` module.

It automatically handles trailing slashes, double slashes, and other common URL normalization issues to keep consistent, clean URLs across your application.

## Quick Start

```python
from sillo import silloApp
from sillo.normalize import Normalize, SlashAction

app = silloApp()

app.use(Normalize(
    slash_action=SlashAction.REDIRECT_REMOVE,
    redirect_status_code=301,
))

@app.get("/users")
async def users(request, response):
    return {"users": ["alice", "bob", "charlie"]}

@app.get("/posts")
async def posts(request, response):
    return {"posts": ["post1", "post2", "post3"]}
```

Requests to `/users/` will redirect to `/users`, and URLs with double slashes like `/users//123` will be cleaned to `/users/123`.

## Configuration

### Slash Action Options

The middleware supports several modes for handling trailing slashes:

- **`SlashAction.REDIRECT_REMOVE`** (default): Redirect to remove trailing slashes
- **`SlashAction.REDIRECT_ADD`**: Redirect to add trailing slashes
- **`SlashAction.REMOVE`**: Remove trailing slashes without redirect
- **`SlashAction.ADD`**: Add trailing slashes without redirect
- **`SlashAction.IGNORE`**: Leave trailing slashes as-is (only clean double slashes)

### Parameters (`NormalizeMiddleware`)

- **`slash_action: SlashAction`** — How to handle trailing slashes (default: REDIRECT_REMOVE)
- **`auto_remove_double_slashes: bool`** — Remove double slashes automatically (default: True)
- **`redirect_status_code: int`** — HTTP status code for redirects (default: 301)
- **`normalize_case: bool`** — Lowercase the URL path (default: False)

## Examples

### SEO-Friendly Setup (Remove Trailing Slashes)

```python
from sillo.normalize import Normalize, SlashAction

app.use(Normalize(
    slash_action=SlashAction.REDIRECT_REMOVE,
    redirect_status_code=301
))
```

### Directory-Style URLs (Add Trailing Slashes)

```python
app.use(Normalize(
    slash_action=SlashAction.REDIRECT_ADD,
    redirect_status_code=301
))
```

### Silent Normalization (No Redirects)

```python
app.use(Normalize(
    slash_action=SlashAction.REMOVE,
    auto_remove_double_slashes=True
))
```

### Case-Insensitive Normalization

```python
app.use(Normalize(
    slash_action=SlashAction.IGNORE,
    normalize_case=True  # Lowercase all paths
))
```

### Programmatic URL Normalization

```python
from sillo.normalize import normalize_path, clean_url_path

clean_path = normalize_path("/api//users//123")  # "/api/users/123"
clean_url = clean_url_path("https://example.com/api//users")
```

## Advanced Usage

### Custom Skip Logic

```python
from sillo.normalize import NormalizeMiddleware, SlashAction

class CustomNormalizeMiddleware(NormalizeMiddleware):
    def _should_skip_processing(self, path: str) -> bool:
        if super()._should_skip_processing(path):
            return True
        if path.startswith("/api/v2/"):
            return True
        if "/webhook" in path:
            return True
        return False

app.use(CustomNormalizeMiddleware(
    slash_action=SlashAction.REDIRECT_REMOVE
))
```

### Conditional Processing

```python
from sillo.normalize import NormalizeMiddleware, SlashAction

class ConditionalNormalizeMiddleware(NormalizeMiddleware):
    async def process_request(self, request, response, call_next):
        host = request.headers.get("host", "")
        if host.startswith("api."):
            self.slash_action = SlashAction.REDIRECT_REMOVE
        elif host.startswith("blog."):
            self.slash_action = SlashAction.REDIRECT_ADD
        else:
            self.slash_action = SlashAction.IGNORE
        return await super().process_request(request, response, call_next)

app.use(ConditionalNormalizeMiddleware())
```

## Best Practices

- **Choose one slash behavior**: Be consistent across your application
- **Use 301 for permanent changes**: Better for SEO than 302
- **Test with your routing**: Ensure compatibility with your route definitions
- **Consider API endpoints**: May need different behavior for API vs pages
- **Monitor redirects**: Use appropriate redirect status codes
- **File serving**: Static files are automatically skipped from processing

## Migration Guide

If you're migrating from inconsistent URLs:

1. **Audit your URLs**: Check current URL patterns
2. **Choose a strategy**: Decide on trailing slash behavior
3. **Implement gradually**: Add middleware and monitor
4. **Update internal links**: Ensure all internal links follow the new pattern
5. **Update documentation**: Document the new URL conventions

### Example Migration

```python
from sillo.normalize import Normalize, SlashAction

# Phase 1: Log what would be changed
class AuditNormalizeMiddleware(NormalizeMiddleware):
    async def process_request(self, request, response, call_next):
        original_path = request.url.path
        result = await super().process_request(request, response, call_next)
        if hasattr(request, "_normalized_path"):
            print(f"Would normalize: {original_path} → {request._normalized_path}")
        return result

# Phase 2: Implement with redirects
app.use(Normalize(
    slash_action=SlashAction.REDIRECT_REMOVE,
    redirect_status_code=301,
))
```

## Performance Considerations

- **Minimal overhead**: Only processes paths that need normalization
- **Smart skipping**: Avoids processing static files and complex URLs
- **Efficient redirects**: Uses appropriate HTTP status codes
- **Cache-friendly**: Redirects are cacheable by browsers and CDNs

## Troubleshooting

### Common Issues

**Infinite redirects**
- Check that your route definitions match your slash action
- Ensure middleware is added before routing middleware

**Static files not loading**
- Verify file extensions are being skipped
- Check static file serving configuration

**API endpoints broken**
- Consider using `SlashAction.IGNORE` for API routes
- Use custom skip logic for specific endpoints

Built with ❤️ by the [@sillo-labs](https://github.com/sillo-labs) community.
