# Trusted Host Middleware

A lightweight, production‑ready trusted host middleware for the Nexios ASGI framework.

It automatically validates the `Host` header of incoming requests against a configurable list of allowed hosts to prevent Host header attacks and ensure requests only come from trusted domains.

## Installation

```bash
pip install nexios_contrib
```

## Quick Start

```python
from nexios import NexiosApp
import nexios_contrib.trusted as trusted

app = NexiosApp()

# Add the Trusted Host middleware
app.add_middleware(
    trusted.TrustedHost(
        allowed_hosts=[
            "example.com",
            "api.example.com",
            "*.example.com",  # Wildcard support
            "127.0.0.1",
            "localhost"
        ],
        allowed_ports=[80, 443, 8000],  # Optional: restrict ports
        www_redirect=True               # Redirect www.example.com to example.com
    )
)

@app.get("/")
async def home(request, response):
    return {"message": "Hello from trusted host!"}
```

## Configuration

### Required Parameters

- **`allowed_hosts: List[str]`**  
  List of allowed hostnames, IP addresses, or patterns. Supports wildcards (e.g., `"*.example.com"`)

### Optional Parameters

- **`allowed_ports: Optional[List[int]] = None`**  
  List of allowed ports. If specified, only requests to these ports will be allowed. If `None`, all ports are allowed.

- **`www_redirect: bool = True`**  
  If `True`, automatically allows requests from `www.domain.com` if `domain.com` is in the allowed hosts list.

## Host Patterns

The middleware supports several types of host patterns:

### Exact Hosts
```python
allowed_hosts = ["example.com", "api.example.com"]
```

### IP Addresses
```python
allowed_hosts = ["127.0.0.1", "192.168.1.100"]
```

### Wildcard Patterns
```python
allowed_hosts = ["*.example.com", "*.api.example.com"]
```

### Port Restrictions
```python
allowed_hosts = ["example.com"]
allowed_ports = [80, 443]  # Only HTTP and HTTPS
```

## How It Works

1. **Host Extraction**: Extracts the host from request headers with proper precedence:
   - `X-Forwarded-Host` (for proxies/load balancers)
   - `X-Host` (some proxies)
   - `Host` header (standard)

2. **Validation**: Checks the extracted host against the allowed patterns:
   - Normalizes hosts to lowercase
   - Validates against exact matches and wildcard patterns
   - Checks port restrictions if specified

3. **Security**: Rejects requests with untrusted hosts using `400 Bad Request`

4. **WWW Handling**: Optionally allows `www.domain.com` if `domain.com` is trusted

## Security Features

- **Host Header Attack Prevention**: Blocks requests with malicious Host headers
- **Proxy Support**: Properly handles forwarded headers from reverse proxies
- **Port Security**: Optional port restrictions for additional security
- **Case Insensitive**: All host validation is case insensitive
- **Wildcard Support**: Flexible pattern matching for subdomains

## Examples

### Basic Setup
```python
trusted.TrustedHost(allowed_hosts=["example.com", "api.example.com"])
```

### Development Environment
```python
trusted.TrustedHost(
    allowed_hosts=["localhost", "127.0.0.1", "*.local"],
    allowed_ports=[3000, 8000, 8080]
)
```

### Production with CDN
```python
trusted.TrustedHost(
    allowed_hosts=[
        "example.com",
        "www.example.com",
        "*.example.com",
        "cdn.example.com"
    ],
    allowed_ports=[80, 443]
)
```

### Multiple Domains
```python
trusted.TrustedHost(
    allowed_hosts=[
        "example.com",
        "myapp.com",
        "staging.example.com",
        "api.myapp.com"
    ]
)
```

## Error Handling

When a request comes from an untrusted host, the middleware raises:
- `BadRequest` exception with a descriptive message
- HTTP 400 status code is returned to the client

```python
# Example error response
{
    "error": "Untrusted host",
    "detail": "Host 'malicious.com' is not allowed"
}
```

## Advanced Usage

### Custom Error Handling

```python
from nexios import NexiosApp
from nexios.exceptions import BadRequest

app = NexiosApp()

@app.exception_handler(BadRequest)
async def handle_bad_request(request, exc):
    if "Untrusted host" in str(exc):
        # Custom response for untrusted hosts
        return {
            "error": "Access Denied",
            "message": "This domain is not authorized to access this service"
        }, 403
    
    # Default handling for other BadRequest exceptions
    return {"error": str(exc)}, 400
```

### Dynamic Host Configuration

```python
import os
from nexios_contrib.trusted import TrustedHost

# Load allowed hosts from environment
allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

app.add_middleware(
    TrustedHost(
        allowed_hosts=allowed_hosts,
        allowed_ports=[80, 443] if os.getenv("PRODUCTION") else None
    )
)
```

### Health Check Bypass

```python
from nexios_contrib.trusted import TrustedHostMiddleware

class HealthCheckTrustedHost(TrustedHostMiddleware):
    def __init__(self, health_check_path="/health", **kwargs):
        super().__init__(**kwargs)
        self.health_check_path = health_check_path
    
    async def __call__(self, request, response, call_next):
        # Skip host validation for health checks
        if request.url.path == self.health_check_path:
            return await call_next()
        
        return await super().__call__(request, response, call_next)

app.add_middleware(
    HealthCheckTrustedHost(
        allowed_hosts=["example.com"],
        health_check_path="/health"
    )
)
```

## Best Practices

- **Always specify allowed_hosts**: Never leave this empty or use wildcards like `["*"]` in production
- **Use HTTPS ports**: In production, typically restrict to ports 80 and 443
- **Consider your deployment**: Behind load balancers? Use `X-Forwarded-Host` support
- **Environment specific**: Use different configurations for development vs production
- **Subdomain handling**: Use wildcards for flexible subdomain support
- **IP restrictions**: Include your server's IP addresses in allowed hosts for health checks

## Common Scenarios

### Behind Nginx Proxy

```python
# Nginx sets X-Forwarded-Host header
trusted.TrustedHost(
    allowed_hosts=["example.com", "www.example.com"],
    allowed_ports=[80, 443]
)
```

### Kubernetes Ingress

```python
# Multiple ingress domains
trusted.TrustedHost(
    allowed_hosts=[
        "api.example.com",
        "*.staging.example.com",
        "internal.cluster.local"
    ]
)
```

### Microservices

```python
# Allow internal service communication
trusted.TrustedHost(
    allowed_hosts=[
        "service-a.internal",
        "service-b.internal",
        "*.example.com"  # External traffic
    ]
)
```

## Troubleshooting

### Common Issues

**Host header not found**
- Check if your proxy is forwarding the Host header correctly
- Verify X-Forwarded-Host is set if behind a proxy

**Wildcard not matching**
- Ensure wildcard patterns use `*` not regex syntax
- `*.example.com` matches `api.example.com` but not `example.com`

**Port restrictions too strict**
- Include all ports your application runs on
- Consider load balancer port forwarding

Built with ❤️ by the [@nexios-labs](https://github.com/nexios-labs) community.