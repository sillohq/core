# 🔄 Proxy Middleware

A production-ready proxy middleware for the Nexios ASGI framework that handles applications running behind proxy servers, load balancers, and CDNs.

It automatically:

- 🌐 Extracts real client IP addresses from `X-Forwarded-For` and `Forwarded` headers
- 🔒 Determines correct protocol from `X-Forwarded-Proto` headers
- 🏠 Handles `X-Forwarded-Host` for proper host resolution
- 🛡️ Provides security controls to prevent header spoofing
- 🎯 Supports trusted proxy configuration with CIDR ranges
- 🔐 Includes enhanced security middleware for stricter controls

## Installation

```bash
pip install nexios_contrib
```

## Quick Start

```python
from nexios import NexiosApp
from nexios_contrib.proxy import Proxy

app = NexiosApp()

# Add basic proxy middleware
app.add_middleware(
    Proxy(
        trusted_proxies=["192.168.1.0/24", "10.0.0.1"],
        trust_forwarded_headers=True
    )
)

@app.get("/")
async def home(request, response):
    # Get real client IP
    real_ip = getattr(request, 'client_ip', None)
    proxy_info = getattr(request, 'proxy_info', {})

    return {
        "message": "Hello from behind proxy!",
        "client_ip": real_ip,
        "behind_proxy": proxy_info.get('trusted_proxy', False)
    }
```

## Common Proxy Scenarios

### Behind Nginx

```python
from nexios import NexiosApp
from nexios_contrib.proxy import Proxy

app = NexiosApp()

# Nginx typically sets X-Forwarded-* headers
app.add_middleware(
    Proxy(
        trusted_proxies=["127.0.0.1", "::1"],  # Trust local proxy
        trust_forwarded_headers=True
    )
)
```

### Behind AWS ELB/ALB

```python
from nexios import NexiosApp
from nexios_contrib.proxy import Proxy

app = NexiosApp()

# AWS load balancers use specific IP ranges
app.add_middleware(
    Proxy(
        trusted_proxies=[
            "10.0.0.0/8",      # Private IP range
            "172.16.0.0/12",   # Docker bridge
            "192.168.0.0/16"   # Local networks
        ]
    )
)
```

### Behind Cloudflare

```python
from nexios import NexiosApp
from nexios_contrib.proxy import Proxy

app = NexiosApp()

# Cloudflare IPs are dynamic, use their ranges
app.add_middleware(
    Proxy(
        trusted_proxies=[
            "173.245.48.0/20",
            "103.21.244.0/22",
            "103.22.200.0/22",
            "103.31.4.0/22",
            "141.101.64.0/18",
            "108.162.192.0/18",
            "190.93.240.0/20",
            "188.114.96.0/20",
            "197.234.240.0/22",
            "198.41.128.0/17",
            "162.158.0.0/15",
            "104.16.0.0/13",
            "104.24.0.0/14",
            "172.64.0.0/13",
            "131.0.72.0/22"
        ]
    )
)
```

## Configuration Options

### ProxyMiddleware Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `trusted_proxies` | `List[str]` | `[]` | List of trusted proxy IP addresses/CIDRs |
| `trust_forwarded_headers` | `bool` | `True` | Whether to trust X-Forwarded-* headers |
| `trust_forwarded_header` | `bool` | `True` | Whether to trust Forwarded header |
| `preserve_host_header` | `bool` | `False` | Whether to preserve original Host header |
| `store_proxy_info` | `bool` | `True` | Store proxy information in request object |

### TrustedProxyMiddleware Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `trusted_proxies` | `List[str]` | Required | List of trusted proxy IP addresses/CIDRs |
| `require_https` | `bool` | `False` | Require HTTPS when behind proxy |
| `max_forwards` | `int` | `10` | Maximum number of proxy hops to allow |

## Usage Examples

### Basic Usage

```python
from nexios import NexiosApp
from nexios_contrib.proxy import Proxy

app = NexiosApp()

app.add_middleware(Proxy())
```

### Trusted Proxy Configuration

```python
from nexios import NexiosApp
from nexios_contrib.proxy import Proxy

app = NexiosApp()

app.add_middleware(
    Proxy(
        trusted_proxies=[
            "192.168.1.0/24",  # Local network
            "10.0.0.1",        # Specific proxy
            "2001:db8::1"      # IPv6 proxy
        ],
        trust_forwarded_headers=True,
        store_proxy_info=True
    )
)
```

### Enhanced Security

```python
from nexios import NexiosApp
from nexios_contrib.proxy import TrustedProxyMiddleware

app = NexiosApp()

app.add_middleware(
    TrustedProxyMiddleware(
        trusted_proxies=["192.168.1.0/24"],
        require_https=True,      # Require HTTPS when behind proxy
        max_forwards=5          # Limit proxy hops
    )
)
```

### Accessing Proxy Information

```python
@app.get("/debug")
async def debug_info(request, response):
    proxy_info = getattr(request, 'proxy_info', {})
    forwarded_for = getattr(request, 'x_forwarded_for', [])
    forwarded_header = getattr(request, 'forwarded_header', {})

    return {
        "client_ip": getattr(request, 'client_ip', None),
        "proxy_info": proxy_info,
        "x_forwarded_for": forwarded_for,
        "forwarded_header": forwarded_header,
        "headers": dict(request.headers)
    }
```

## Supported Headers

### Input Headers (Parsed)

- **`X-Forwarded-For`**: Client IP addresses (comma-separated)
- **`X-Forwarded-Proto`**: Original protocol (http/https)
- **`X-Forwarded-Host`**: Original host
- **`X-Forwarded-Port`**: Original port
- **`Forwarded`**: RFC 7239 compliant header

### Output Headers (Added)

- **`X-Client-IP`**: Real client IP (added to response if different)

## Security Considerations

### Trusted Proxies

Always specify your trusted proxies explicitly:

```python
# Good - explicit trusted proxies
app.add_middleware(Proxy(trusted_proxies=["192.168.1.0/24"]))

# Bad - trusts all proxies (security risk)
app.add_middleware(Proxy(trusted_proxies=[]))  # Don't do this!
```

### Header Spoofing Prevention

The middleware only processes proxy headers when the request comes from a trusted proxy IP, preventing header spoofing attacks.

```python
# Example: Untrusted request with spoofed headers
# Request from 203.0.113.1 (not in trusted_proxies)
# Headers: X-Forwarded-For: 192.168.1.100
# Result: Headers are ignored, client_ip = 203.0.113.1
```

### HTTPS Enforcement

```python
# Enforce HTTPS when behind proxy
app.add_middleware(
    TrustedProxyMiddleware(
        trusted_proxies=["10.0.0.0/8"],
        require_https=True
    )
)
```

## Helper Functions

### Parsing Headers

```python
from nexios_contrib.proxy import (
    parse_x_forwarded_for,
    parse_forwarded_header,
    parse_x_forwarded_proto
)

# Parse X-Forwarded-For
ips = parse_x_forwarded_for("192.168.1.1, 10.0.0.1")
# Returns: ["192.168.1.1", "10.0.0.1"]

# Parse Forwarded header
info = parse_forwarded_header('for=192.168.1.1; proto=https; host=example.com')
# Returns: {"for": "192.168.1.1", "proto": "https", "host": "example.com"}
```

### IP Validation

```python
from nexios_contrib.proxy import is_trusted_proxy

# Check if IP is trusted
is_trusted = is_trusted_proxy("192.168.1.100", ["192.168.1.0/24"])
# Returns: True

# Check with multiple ranges
is_trusted = is_trusted_proxy(
    "10.0.0.1",
    ["192.168.1.0/24", "10.0.0.0/8", "172.16.0.1"]
)
```

## Advanced Usage

### Custom Proxy Detection

```python
from nexios_contrib.proxy import ProxyMiddleware

class CustomProxyMiddleware(ProxyMiddleware):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def extract_client_ip(self, request):
        # Custom logic for extracting client IP
        custom_header = request.headers.get('X-Real-IP')
        if custom_header and self.is_trusted_proxy(request.client.host):
            return custom_header
        
        return super().extract_client_ip(request)

app.add_middleware(CustomProxyMiddleware(
    trusted_proxies=["192.168.1.0/24"]
))
```

### Logging Proxy Information

```python
import logging

@app.middleware
async def log_proxy_info(request, response, call_next):
    proxy_info = getattr(request, 'proxy_info', {})
    client_ip = getattr(request, 'client_ip', 'unknown')
    
    if proxy_info.get('trusted_proxy'):
        logging.info(f"Request from {client_ip} via trusted proxy")
    else:
        logging.info(f"Direct request from {client_ip}")
    
    return await call_next()
```

## Best Practices

1. **Always specify trusted proxies** - Never trust proxy headers from unknown sources
2. **Use CIDR ranges** for better security than individual IPs
3. **Enable HTTPS enforcement** when behind load balancers that terminate TLS
4. **Log proxy information** for debugging and security monitoring
5. **Test with real proxy setups** - Different proxies set different headers
6. **Monitor for header spoofing** attempts in your logs

### Example Production Configuration

```python
from nexios import NexiosApp
from nexios_contrib.proxy import TrustedProxyMiddleware

app = NexiosApp()

app.add_middleware(
    TrustedProxyMiddleware(
        trusted_proxies=[
            "10.0.0.0/8",      # Private networks
            "172.16.0.0/12",   # Docker networks
            "192.168.0.0/16",  # Local networks
            "127.0.0.1",       # Localhost
            "::1"              # IPv6 localhost
        ],
        require_https=True,
        max_forwards=3,
        store_proxy_info=True
    )
)

# Add logging middleware to capture proxy info
@app.middleware
async def log_proxy_info(request, response, call_next):
    proxy_info = getattr(request, 'proxy_info', {})
    if proxy_info.get('trusted_proxy'):
        logger.info(f"Request from {request.client_ip} via proxy")

    return await call_next()
```

## Common Issues

### Incorrect Client IP

If you're seeing proxy IPs instead of real client IPs:

1. Check that your proxy is sending the correct headers
2. Verify your trusted_proxies configuration
3. Ensure the middleware is added early in the chain

### HTTPS/SSL Issues

If your app thinks it's on HTTP when behind a TLS-terminating proxy:

1. Ensure the proxy sets `X-Forwarded-Proto: https`
2. Use `require_https=True` in TrustedProxyMiddleware
3. Check that the proxy is correctly configured

### Host Header Issues

If your app is getting the wrong host:

1. Check `X-Forwarded-Host` header from proxy
2. Consider setting `preserve_host_header=True` if needed
3. Verify proxy configuration

## Troubleshooting

### Debug Proxy Headers

```python
@app.get("/debug/headers")
async def debug_headers(request, response):
    return {
        "all_headers": dict(request.headers),
        "client_host": request.client.host,
        "client_ip": getattr(request, 'client_ip', None),
        "proxy_info": getattr(request, 'proxy_info', {}),
        "x_forwarded_for": request.headers.get('X-Forwarded-For'),
        "x_forwarded_proto": request.headers.get('X-Forwarded-Proto'),
        "x_forwarded_host": request.headers.get('X-Forwarded-Host'),
        "forwarded": request.headers.get('Forwarded')
    }
```

### Test Proxy Configuration

```python
# Test script to verify proxy configuration
import requests

# Test direct request
response = requests.get("http://localhost:8000/debug/headers")
print("Direct:", response.json())

# Test with proxy headers
headers = {
    "X-Forwarded-For": "203.0.113.1, 192.168.1.1",
    "X-Forwarded-Proto": "https",
    "X-Forwarded-Host": "example.com"
}
response = requests.get("http://localhost:8000/debug/headers", headers=headers)
print("With headers:", response.json())
```

Built with ❤️ by the [@nexios-labs](https://github.com/nexios-labs) community.