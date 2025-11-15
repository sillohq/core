# Accepts Middleware

A comprehensive content negotiation middleware for the Nexios ASGI framework that handles Accept headers and provides intelligent content negotiation.

It automatically:

- Parses and processes Accept, Accept-Language, Accept-Charset, and Accept-Encoding headers
- Performs intelligent content negotiation based on client preferences
- Sets appropriate Vary headers for proper caching
- Provides utilities for manual content negotiation
- Supports strict content negotiation with 406 Not Acceptable responses

## Installation

```bash
pip install nexios_contrib
```

## Quick Start

```python
from nexios import NexiosApp
from nexios_contrib.accepts import Accepts

app = NexiosApp()

# Add accepts middleware
app.add_middleware(Accepts())

@app.get("/")
async def home(request, response):
    # Access parsed accept headers
    accepts_info = getattr(request, 'accepts', {})
    accept_header = accepts_info.get('raw_accept', '')

    return {
        "message": "Hello with Content Negotiation!",
        "accepts": accept_header
    }
```

## Content Negotiation Examples

### Basic Usage

```python
from nexios import NexiosApp
from nexios_contrib.accepts import Accepts

app = NexiosApp()

app.add_middleware(Accepts())

@app.get("/api/data")
async def get_data(request, response):
    # The middleware automatically handles content negotiation
    # Response content-type will be negotiated based on Accept header

    data = {"message": "API data", "items": [1, 2, 3]}

    # Client sends: Accept: application/json
    # Response will have: Content-Type: application/json

    return data
```

### Manual Content Negotiation

```python
from nexios import NexiosApp
from nexios_contrib.accepts import ContentNegotiationMiddleware, negotiate_content_type

app = NexiosApp()

app.add_middleware(ContentNegotiationMiddleware())

@app.get("/api/content")
async def get_content(request, response):
    # Manual content negotiation
    available_types = ["application/json", "application/xml", "text/html"]
    best_type = negotiate_content_type(
        request.headers.get('Accept', ''),
        available_types
    )

    response.headers['Content-Type'] = best_type

    if best_type == "application/json":
        return {"data": "JSON format"}
    elif best_type == "application/xml":
        return "<data>XML format</data>"
    else:
        return "<h1>HTML format</h1>"
```

### Language Negotiation

```python
from nexios import NexiosApp
from nexios_contrib.accepts import ContentNegotiationMiddleware, negotiate_language

app = NexiosApp()

app.add_middleware(ContentNegotiationMiddleware())

@app.get("/greetings")
async def get_greetings(request, response):
    available_languages = ["en", "es", "fr", "de"]
    best_language = negotiate_language(
        request.headers.get('Accept-Language', ''),
        available_languages
    )

    greetings = {
        "en": "Hello",
        "es": "Hola",
        "fr": "Bonjour",
        "de": "Guten Tag"
    }

    return {
        "greeting": greetings.get(best_language, greetings["en"]),
        "language": best_language
    }
```

### Strict Content Negotiation

```python
from nexios import NexiosApp
from nexios_contrib.accepts import StrictContentNegotiationMiddleware

app = NexiosApp()

app.add_middleware(
    StrictContentNegotiationMiddleware(
        available_types=["application/json", "application/xml"],
        available_languages=["en", "es"]
    )
)

@app.get("/api/strict")
async def strict_api(request, response):
    # Will return 406 Not Acceptable if client doesn't accept JSON or XML
    # and doesn't accept English or Spanish

    negotiated_type = getattr(request, 'negotiated_content_type', 'application/json')
    negotiated_lang = getattr(request, 'negotiated_language', 'en')

    return {
        "data": "Strict API response",
        "content_type": negotiated_type,
        "language": negotiated_lang
    }
```

## Configuration Options

### AcceptsMiddleware Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `default_content_type` | `str` | `"application/json"` | Default content type when no match found |
| `default_language` | `str` | `"en"` | Default language when no match found |
| `default_charset` | `str` | `"utf-8"` | Default charset when no match found |
| `set_vary_header` | `bool` | `True` | Automatically set Vary headers |
| `store_accepts_info` | `bool` | `True` | Store parsed accepts info in request object |

### StrictContentNegotiationMiddleware Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `available_types` | `List[str]` | Required | Content types this application can serve |
| `available_languages` | `List[str]` | `["en"]` | Languages this application supports |

## Usage Examples

### Basic Setup

```python
from nexios import NexiosApp
from nexios_contrib.accepts import Accepts

app = NexiosApp()

app.add_middleware(Accepts())
```

### Custom Configuration

```python
from nexios import NexiosApp
from nexios_contrib.accepts import Accepts

app = NexiosApp()

app.add_middleware(
    Accepts(
        default_content_type="application/json",
        default_language="en",
        default_charset="utf-8",
        set_vary_header=True,
        store_accepts_info=True
    )
)
```

### Accessing Accept Information

```python
@app.get("/debug/accepts")
async def debug_accepts(request, response):
    accepts = getattr(request, 'accepts', {})

    return {
        "accept_header": accepts.get('raw_accept', ''),
        "accepted_types": [item.value for item in accepts.get('accept', [])],
        "accept_language": accepts.get('raw_accept_language', ''),
        "accepted_languages": [item.value for item in accepts.get('accept_language', [])],
        "accept_charset": accepts.get('raw_accept_charset', ''),
        "accept_encoding": accepts.get('raw_accept_encoding', ''),
    }
```

### Content Negotiation Utilities

```python
from nexios_contrib.accepts import get_best_match, negotiate_content_type

@app.get("/negotiate")
async def negotiate_example(request, response):
    # Get best match from options
    best_type = get_best_match(
        request.headers.get('Accept', ''),
        ["application/json", "text/html", "application/xml"]
    )

    # Or use specific negotiation
    json_type = negotiate_content_type(
        request.headers.get('Accept', ''),
        ["application/json", "application/vnd.api+json"]
    )

    return {
        "best_match": best_type,
        "json_match": json_type,
        "accept_header": request.headers.get('Accept', '')
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

The middleware follows RFC 7231 content negotiation rules:

1. **Exact Match**: `application/json` matches `application/json`
2. **Type Match**: `text/*` matches `text/html`, `text/plain`
3. **Wildcard Match**: `*/*` matches any media type
4. **Quality Factor**: Items are sorted by q-value (0.0 to 1.0)
5. **Specificity**: More specific types are preferred over generic ones

### Language Matching

Language negotiation follows RFC 7231:

1. **Exact Match**: `en-US` matches `en-US`
2. **Prefix Match**: `en` matches `en-US`, `en-GB`
3. **Fallback**: First available language if no match

## Helper Functions

### Parsing Accept Headers

```python
from nexios_contrib.accepts import parse_accept_header, parse_accept_language

# Parse Accept header
accept_items = parse_accept_header("text/html, application/json;q=0.9")
# Returns: [AcceptItem("text/html", 1.0), AcceptItem("application/json", 0.9)]

# Parse Accept-Language header
lang_items = parse_accept_language("en-US, en;q=0.9, es;q=0.8")
# Returns: [AcceptItem("en-US", 1.0), AcceptItem("en", 0.9), AcceptItem("es", 0.8)]
```

### Content Negotiation

```python
from nexios_contrib.accepts import negotiate_content_type, negotiate_language

# Content type negotiation
best_type = negotiate_content_type(
    "text/html, application/json;q=0.9",
    ["application/json", "text/html", "application/xml"]
)
# Returns: "text/html" (exact match wins over quality)

# Language negotiation
best_lang = negotiate_language(
    "en-US, fr;q=0.8",
    ["en", "fr", "es"]
)
# Returns: "en" (prefix match)
```

### Best Match Selection

```python
from nexios_contrib.accepts import get_best_match

# Get best match from options
best = get_best_match(
    "application/json, text/html;q=0.9",
    ["text/html", "application/json", "application/xml"]
)
# Returns: "application/json" (first in list with highest quality)
```

## Advanced Usage

### Custom Content Negotiation

```python
from nexios import NexiosApp
from nexios_contrib.accepts import ContentNegotiationMiddleware

class CustomNegotiationMiddleware(ContentNegotiationMiddleware):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_types = {
            "application/vnd.api.v1+json": ["application/json"],
            "application/vnd.api.v2+json": ["application/json", "application/vnd.api.v1+json"]
        }

    def negotiate_content_type(self, request, available_types, default_type=None):
        accept_header = request.headers.get('Accept', '')

        # Check for custom vendor types
        for custom_type, fallback_types in self.custom_types.items():
            if custom_type in accept_header:
                for fallback in fallback_types:
                    if fallback in available_types:
                        return fallback

        # Fall back to standard negotiation
        return super().negotiate_content_type(request, available_types, default_type)

app = NexiosApp()
app.add_middleware(CustomNegotiationMiddleware())
```

### API Versioning with Content Negotiation

```python
from nexios import NexiosApp
from nexios_contrib.accepts import ContentNegotiationMiddleware

app = NexiosApp()
app.add_middleware(ContentNegotiationMiddleware())

@app.get("/api/users")
async def get_users(request, response):
    # Support API versioning through Accept header
    accept_header = request.headers.get('Accept', '')

    if 'application/vnd.myapi.v2+json' in accept_header:
        response.headers['Content-Type'] = 'application/vnd.myapi.v2+json'
        return {"users": [], "version": "v2", "features": ["new_field"]}
    else:
        response.headers['Content-Type'] = 'application/vnd.myapi.v1+json'
        return {"users": [], "version": "v1"}
```

### Internationalization (i18n)

```python
from nexios import NexiosApp
from nexios_contrib.accepts import ContentNegotiationMiddleware, negotiate_language

app = NexiosApp()
app.add_middleware(ContentNegotiationMiddleware())

@app.get("/messages")
async def get_messages(request, response):
    available_messages = {
        "en": {"greeting": "Hello", "farewell": "Goodbye"},
        "es": {"greeting": "Hola", "farewell": "Adiós"},
        "fr": {"greeting": "Bonjour", "farewell": "Au revoir"}
    }

    best_lang = negotiate_language(
        request.headers.get('Accept-Language', ''),
        list(available_messages.keys())
    )

    messages = available_messages.get(best_lang, available_messages["en"])
    response.headers['Content-Language'] = best_lang

    return messages
```

## Best Practices

1. **Always set Vary headers** when using content negotiation for proper caching
2. **Provide sensible defaults** for content type and language
3. **Test with real browsers** - different browsers send different Accept headers
4. **Use strict negotiation** for APIs that only support specific content types
5. **Cache negotiated responses** - use Vary headers to ensure proper cache keys
6. **Support multiple formats** for better API compatibility

### Example Production Configuration

```python
from nexios import NexiosApp
from nexios_contrib.accepts import StrictContentNegotiationMiddleware

app = NexiosApp()

app.add_middleware(
    StrictContentNegotiationMiddleware(
        available_types=[
            "application/json",
            "application/vnd.api.v1+json",
            "application/vnd.api.v2+json"
        ],
        available_languages=["en", "es", "fr", "de"],
        default_content_type="application/json",
        default_language="en"
    )
)

@app.middleware
async def content_negotiation_logger(request, response, call_next):
    negotiated_type = getattr(request, 'negotiated_content_type', 'unknown')
    negotiated_lang = getattr(request, 'negotiated_language', 'unknown')

    print(f"Content-Type: {negotiated_type}, Language: {negotiated_lang}")

    return await call_next()
```

## Common Issues

### Content-Type Not Being Set

If Content-Type headers aren't being set automatically:

1. Check that Accepts middleware is added to your app
2. Verify the Accept header is being sent by the client
3. Ensure `default_content_type` is set correctly

### Vary Headers Too Broad

If Vary headers include too many fields:

1. Set `set_vary_header=False` if you don't need automatic Vary headers
2. Manually set specific Vary headers as needed
3. Consider caching implications when using content negotiation

### Language Fallback Issues

If language negotiation isn't working as expected:

1. Verify Accept-Language header is being sent
2. Check that your available languages list is correct
3. Ensure proper language codes (e.g., "en-US", not "en_US")

## Troubleshooting

### Debug Accept Headers

```python
@app.get("/debug/headers")
async def debug_headers(request, response):
    return {
        "accept": request.headers.get('Accept'),
        "accept_language": request.headers.get('Accept-Language'),
        "accept_charset": request.headers.get('Accept-Charset'),
        "accept_encoding": request.headers.get('Accept-Encoding'),
        "user_agent": request.headers.get('User-Agent')
    }
```

### Test Content Negotiation

```python
# Test script to verify content negotiation
import requests

# Test different Accept headers
headers_tests = [
    {"Accept": "application/json"},
    {"Accept": "text/html"},
    {"Accept": "application/xml"},
    {"Accept": "text/html, application/json;q=0.9"},
    {"Accept-Language": "en-US, fr;q=0.8"}
]

for headers in headers_tests:
    response = requests.get("http://localhost:8000/api/content", headers=headers)
    print(f"Headers: {headers}")
    print(f"Response Content-Type: {response.headers.get('Content-Type')}")
    print(f"Response: {response.text}\n")
```

Built with ❤️ by the [@nexios-labs](https://github.com/nexios-labs) community.