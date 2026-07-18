---
title: Content Negotiation
description: Negotiate Accept headers with the sillo.helpers.accepts module.
---

# Content Negotiation

A comprehensive content negotiation middleware for sillo, shipped as the first‑party `sillo.helpers.accepts` module. It parses `Accept`, `Accept-Language`, `Accept-Charset`, and `Accept-Encoding` headers and performs RFC 7231 content negotiation.

It automatically:

- Parses and processes `Accept`, `Accept-Language`, `Accept-Charset`, and `Accept-Encoding` headers
- Performs intelligent content negotiation based on client preferences
- Sets appropriate `Vary` headers for proper caching
- Provides utilities for manual content negotiation
- Supports strict negotiation with `406 Not Acceptable` responses

## Quick Start

```python
from sillo import silloApp
from sillo.helpers.accepts import Accepts

app = silloApp()

app.use(Accepts())

@app.get("/")
async def home(request, response):
    accepts_info = getattr(request.state, "accepts", {})
    return {
        "message": "Hello with Content Negotiation!",
        "accepts": accepts_info.get("raw_accept", ""),
    }
```

## Content Negotiation Examples

### Basic Usage

```python
from sillo import silloApp
from sillo.helpers.accepts import Accepts

app = silloApp()
app.use(Accepts())

@app.get("/api/data")
async def get_data(request, response):
    data = {"message": "API data", "items": [1, 2, 3]}
    # Client sends: Accept: application/json
    # Response will be: Content-Type: application/json
    return data
```

### Manual Content Negotiation

```python
from sillo import silloApp
from sillo.helpers.accepts import ContentNegotiationMiddleware, negotiate_content_type

app = silloApp()
app.use(ContentNegotiationMiddleware())

@app.get("/api/content")
async def get_content(request, response):
    available_types = ["application/json", "application/xml", "text/html"]
    best_type = negotiate_content_type(
        request.headers.get("Accept", ""),
        available_types,
    )
    response.headers["Content-Type"] = best_type
    if best_type == "application/json":
        return {"data": "JSON format"}
    elif best_type == "application/xml":
        return "<data>XML format</data>"
    else:
        return "<h1>HTML format</h1>"
```

### Language Negotiation

```python
from sillo import silloApp
from sillo.helpers.accepts import ContentNegotiationMiddleware, negotiate_language

app = silloApp()
app.use(ContentNegotiationMiddleware())

@app.get("/greetings")
async def get_greetings(request, response):
    available_languages = ["en", "es", "fr", "de"]
    best_language = negotiate_language(
        request.headers.get("Accept-Language", ""),
        available_languages,
    )
    greetings = {"en": "Hello", "es": "Hola", "fr": "Bonjour", "de": "Guten Tag"}
    return {
        "greeting": greetings.get(best_language, greetings["en"]),
        "language": best_language,
    }
```

### Strict Content Negotiation

```python
from sillo import silloApp
from sillo.helpers.accepts import StrictContentNegotiationMiddleware

app = silloApp()
app.use(
    StrictContentNegotiationMiddleware(
        available_types=["application/json", "application/xml"],
        available_languages=["en", "es"],
    )
)

@app.get("/api/strict")
async def strict_api(request, response):
    # Returns 406 Not Acceptable if the client doesn't accept JSON/XML
    # or doesn't accept English/Spanish
    negotiated_type = getattr(request, "negotiated_content_type", "application/json")
    negotiated_lang = getattr(request, "negotiated_language", "en")
    return {
        "data": "Strict API response",
        "content_type": negotiated_type,
        "language": negotiated_lang,
    }
```

## Configuration Options

### AcceptsMiddleware Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `default_content_type` | `str` | `"application/json"` | Default content type when no match found |
| `default_language` | `str` | `"en"` | Default language when no match found |
| `default_charset` | `str` | `"utf-8"` | Default charset when no match found |
| `set_vary_header` | `bool` | `True` | Automatically set `Vary` headers |
| `store_accepts_info` | `bool` | `True` | Store parsed accepts info in request object |

### StrictContentNegotiationMiddleware Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `available_types` | `List[str]` | Required | Content types this application can serve |
| `available_languages` | `List[str]` | `["en"]` | Languages this application supports |

## Usage Examples

### Basic Setup

```python
from sillo import silloApp
from sillo.helpers.accepts import Accepts

app = silloApp()
app.use(Accepts())
```

### Custom Configuration

```python
from sillo import silloApp
from sillo.helpers.accepts import Accepts

app = silloApp()
app.use(
    Accepts(
        default_content_type="application/json",
        default_language="en",
        default_charset="utf-8",
        set_vary_header=True,
        store_accepts_info=True,
    )
)
```

### Accessing Accept Information

```python
@app.get("/debug/accepts")
async def debug_accepts(request, response):
    accepts = getattr(request, "accepts", {})
    return {
        "accept_header": accepts.get("raw_accept", ""),
        "accepted_types": [item.value for item in accepts.get("accept", [])],
        "accept_language": accepts.get("raw_accept_language", ""),
        "accepted_languages": [item.value for item in accepts.get("accept_language", [])],
        "accept_charset": accepts.get("raw_accept_charset", ""),
        "accept_encoding": accepts.get("raw_accept_encoding", ""),
    }
```

### Content Negotiation Utilities

```python
from sillo.helpers.accepts import get_best_match, negotiate_content_type

@app.get("/negotiate")
async def negotiate_example(request, response):
    best_type = get_best_match(
        request.headers.get("Accept", ""),
        ["application/json", "text/html", "application/xml"],
    )
    json_type = negotiate_content_type(
        request.headers.get("Accept", ""),
        ["application/json", "application/vnd.api+json"],
    )
    return {
        "best_match": best_type,
        "json_match": json_type,
        "accept_header": request.headers.get("Accept", ""),
    }
```

## Supported Headers

### Input Headers (Parsed)

- **`Accept`**: Media types (e.g., `text/html, application/json;q=0.9`)
- **`Accept-Language`**: Languages (e.g., `en-US, en;q=0.9, es;q=0.8`)
- **`Accept-Charset`**: Character sets (e.g., `utf-8, iso-8859-1;q=0.9`)
- **`Accept-Encoding`**: Content encodings (e.g., `gzip, deflate, br`)

### Output Headers (Set)

- **`Vary`**: Automatically set to include relevant Accept headers
- **`Content-Type`**: Automatically negotiated based on Accept header

## Content Negotiation Algorithm

### Media Type Matching

Follows RFC 7231 content negotiation rules:

1. **Exact Match**: `application/json` matches `application/json`
2. **Type Match**: `text/*` matches `text/html`, `text/plain`
3. **Wildcard Match**: `*/*` matches any media type
4. **Quality Factor**: Items are sorted by q-value (0.0 to 1.0)
5. **Specificity**: More specific types are preferred over generic ones

### Language Matching

1. **Exact Match**: `en-US` matches `en-US`
2. **Prefix Match**: `en` matches `en-US`, `en-GB`
3. **Fallback**: First available language if no match

## Helper Functions

### Parsing Accept Headers

```python
from sillo.helpers.accepts import parse_accept_header, parse_accept_language

accept_items = parse_accept_header("text/html, application/json;q=0.9")
# [AcceptItem("text/html", 1.0), AcceptItem("application/json", 0.9)]

lang_items = parse_accept_language("en-US, en;q=0.9, es;q=0.8")
# [AcceptItem("en-US", 1.0), AcceptItem("en", 0.9), AcceptItem("es", 0.8)]
```

### Content Negotiation

```python
from sillo.helpers.accepts import negotiate_content_type, negotiate_language

best_type = negotiate_content_type(
    "text/html, application/json;q=0.9",
    ["application/json", "text/html", "application/xml"],
)
# "text/html" (exact match wins over quality)

best_lang = negotiate_language("en-US, fr;q=0.8", ["en", "fr", "es"])
# "en" (prefix match)
```

### Best Match Selection

```python
from sillo.helpers.accepts import get_best_match

best = get_best_match(
    "application/json, text/html;q=0.9",
    ["text/html", "application/json", "application/xml"],
)
# "application/json"
```

## Advanced Usage

### Custom Content Negotiation

```python
from sillo import silloApp
from sillo.helpers.accepts import ContentNegotiationMiddleware

class CustomNegotiationMiddleware(ContentNegotiationMiddleware):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_types = {
            "application/vnd.api.v1+json": ["application/json"],
            "application/vnd.api.v2+json": ["application/json", "application/vnd.api.v1+json"],
        }

    def negotiate_content_type(self, request, available_types, default_type=None):
        accept_header = request.headers.get("Accept", "")
        for custom_type, fallback_types in self.custom_types.items():
            if custom_type in accept_header:
                for fallback in fallback_types:
                    if fallback in available_types:
                        return fallback
        return super().negotiate_content_type(request, available_types, default_type)

app = silloApp()
app.use(CustomNegotiationMiddleware())
```

### API Versioning with Content Negotiation

```python
from sillo import silloApp
from sillo.helpers.accepts import ContentNegotiationMiddleware

app = silloApp()
app.use(ContentNegotiationMiddleware())

@app.get("/api/users")
async def get_users(request, response):
    accept_header = request.headers.get("Accept", "")
    if "application/vnd.myapi.v2+json" in accept_header:
        response.headers["Content-Type"] = "application/vnd.myapi.v2+json"
        return {"users": [], "version": "v2", "features": ["new_field"]}
    else:
        response.headers["Content-Type"] = "application/vnd.myapi.v1+json"
        return {"users": [], "version": "v1"}
```

### Internationalization (i18n)

```python
from sillo import silloApp
from sillo.helpers.accepts import ContentNegotiationMiddleware, negotiate_language

app = silloApp()
app.use(ContentNegotiationMiddleware())

@app.get("/messages")
async def get_messages(request, response):
    available_messages = {
        "en": {"greeting": "Hello", "farewell": "Goodbye"},
        "es": {"greeting": "Hola", "farewell": "Adiós"},
        "fr": {"greeting": "Bonjour", "farewell": "Au revoir"},
    }
    best_lang = negotiate_language(
        request.headers.get("Accept-Language", ""),
        list(available_messages.keys()),
    )
    messages = available_messages.get(best_lang, available_messages["en"])
    response.headers["Content-Language"] = best_lang
    return messages
```

## Best Practices

1. **Always set Vary headers** when using content negotiation for proper caching
2. **Provide sensible defaults** for content type and language
3. **Test with real browsers** — different browsers send different Accept headers
4. **Use strict negotiation** for APIs that only support specific content types
5. **Cache negotiated responses** — use Vary headers to ensure proper cache keys
6. **Support multiple formats** for better API compatibility

### Example Production Configuration

```python
from sillo import silloApp
from sillo.helpers.accepts import StrictContentNegotiationMiddleware

app = silloApp()
app.use(
    StrictContentNegotiationMiddleware(
        available_types=[
            "application/json",
            "application/vnd.api.v1+json",
            "application/vnd.api.v2+json",
        ],
        available_languages=["en", "es", "fr", "de"],
        default_content_type="application/json",
        default_language="en",
    )
)

@app.middleware
async def content_negotiation_logger(request, response, call_next):
    negotiated_type = getattr(request, "negotiated_content_type", "unknown")
    negotiated_lang = getattr(request, "negotiated_language", "unknown")
    print(f"Content-Type: {negotiated_type}, Language: {negotiated_lang}")
    return await call_next()
```

## Troubleshooting

### Content-Type Not Being Set

1. Check that Accepts middleware is added to your app
2. Verify the Accept header is being sent by the client
3. Ensure `default_content_type` is set correctly

### Vary Headers Too Broad

1. Set `set_vary_header=False` if you don't need automatic Vary headers
2. Manually set specific Vary headers as needed
3. Consider caching implications when using content negotiation

### Language Fallback Issues

1. Verify Accept-Language header is being sent
2. Check that your available languages list is correct
3. Ensure proper language codes (e.g., `"en-US"`, not `"en_US"`)

### Debug Accept Headers

```python
@app.get("/debug/headers")
async def debug_headers(request, response):
    return {
        "accept": request.headers.get("Accept"),
        "accept_language": request.headers.get("Accept-Language"),
        "accept_charset": request.headers.get("Accept-Charset"),
        "accept_encoding": request.headers.get("Accept-Encoding"),
        "user_agent": request.headers.get("User-Agent"),
    }
```

Built with ❤️ by the [@sillo-labs](https://github.com/sillo-labs) community.
