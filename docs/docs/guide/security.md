---
title: Security Middleware
description: Nexios provides a comprehensive security middleware that implements various security headers and protections. This guide covers all available security options and best practices.
head:
  - - meta
    - property: og:title
      content: Security Middleware
  - - meta
    - property: og:description
      content: Nexios provides a comprehensive security middleware that implements various security headers and protections. This guide covers all available security options and best practices.
---
# 🛡️ Security Middleware

```python
from nexios import NexiosApp
from nexios.middleware.security import SecurityMiddleware

app = NexiosApp()

# Basic usage with defaults
app.add_middleware(SecurityMiddleware())

# Advanced configuration
app.add_middleware(
    SecurityMiddleware(
        csp_enabled=True,
        hsts_enabled=True,
        ssl_redirect=True,
        frame_options="DENY"
    )
)
```

## 🔒 Security Features

### 1. Content Security Policy (CSP)

::: tip CSP
Content Security Policy is a powerful security feature that helps prevent XSS attacks by controlling which resources can be loaded.
:::

```python
security = SecurityMiddleware(
    csp_enabled=True,
    csp_policy={
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'"],
        'style-src': ["'self'", 'https://fonts.googleapis.com'],
        'img-src': ["'self'", 'data:', 'https:'],
        'font-src': ["'self'", 'https://fonts.gstatic.com'],
        'connect-src': ["'self'", 'https://api.example.com']
    },
    csp_report_only=False  # Set to True for testing
)
```



### 2. HTTP Strict Transport Security (HSTS)

```python
security = SecurityMiddleware(
    hsts_enabled=True,
    hsts_max_age=31536000,  # 1 year
    hsts_include_subdomains=True,
    hsts_preload=True
)
```

### 3. XSS Protection

```python
security = SecurityMiddleware(
    xss_protection=True,
    xss_mode="block"  # or "filter"
)
```

### 4. Frame Options

```python
security = SecurityMiddleware(
    frame_options="DENY",  # or "SAMEORIGIN"
    # Or allow specific origin:
    frame_options_allow_from="https://trusted.com"
)
```

### 5. SSL/HTTPS Redirect

```python
security = SecurityMiddleware(
    ssl_redirect=True,
    ssl_host="secure.example.com",
    ssl_permanent=True  # 301 redirect
)
```

### 6. Cross-Origin Policies

```python
security = SecurityMiddleware(
    cross_origin_opener_policy="same-origin",
    cross_origin_embedder_policy="require-corp",
    cross_origin_resource_policy="same-origin"
)
```

### 7. Permissions Policy

```python
security = SecurityMiddleware(
    permissions_policy={
        'camera': "'none'",
        'microphone': "'self'",
        'geolocation': ["'self'", "https://maps.example.com"],
        'payment': "'self'"
    }
)
```

### 8. Cache Control

```python
security = SecurityMiddleware(
    cache_control="no-store, no-cache, must-revalidate, proxy-revalidate",
    clear_site_data=["cache", "cookies", "storage"]
)
```

### 9. Expect-CT

```python
security = SecurityMiddleware(
    expect_ct=True,
    expect_ct_max_age=86400,
    expect_ct_enforce=True,
    expect_ct_report_uri="https://example.com/report"
)
```

## ⚙️ Complete Configuration Example

::: details Full Configuration
```python
from nexios import NexiosApp
from nexios.middleware import SecurityMiddleware

app = NexiosApp()

security = SecurityMiddleware(
    # Content Security Policy
    csp_enabled=True,
    csp_policy={
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'"],
        'style-src': ["'self'", 'https://fonts.googleapis.com'],
        'img-src': ["'self'", 'data:', 'https:'],
        'connect-src': ["'self'", 'https://api.example.com']
    },
    csp_report_only=False,

    # CORS
    cors_enabled=True,
    allowed_origins=["https://example.com"],
    allowed_methods=["GET", "POST", "PUT", "DELETE"],
    allowed_headers=["*"],
    expose_headers=["X-Custom-Header"],
    max_age=3600,
    allow_credentials=True,

    # HSTS
    hsts_enabled=True,
    hsts_max_age=31536000,
    hsts_include_subdomains=True,
    hsts_preload=True,

    # XSS Protection
    xss_protection=True,
    xss_mode="block",

    # Frame Options
    frame_options="DENY",

    # Content Type Options
    content_type_options=True,

    # Referrer Policy
    referrer_policy="strict-origin-when-cross-origin",

    # SSL/HTTPS
    ssl_redirect=True,
    ssl_host="secure.example.com",
    ssl_permanent=True,

    # Cache Control
    cache_control="no-store, no-cache",
    clear_site_data=["cache", "cookies"],

    # Cross-Origin Policies
    cross_origin_opener_policy="same-origin",
    cross_origin_embedder_policy="require-corp",
    cross_origin_resource_policy="same-origin",

    # Expect-CT
    expect_ct=True,
    expect_ct_max_age=86400,
    expect_ct_enforce=True,

    # Trusted Types
    trusted_types=True,
    trusted_types_policies=["default", "escape"],

    # Server
    hide_server=True
)

app.add_middleware(security)
```
:::

## 📋 Best Practices

### Production Settings

::: tip Production Security
For production environments, we recommend:
1. Enable HTTPS redirect
2. Enable HSTS
3. Set strict CSP rules
4. Enable all security headers
5. Configure proper CORS settings
:::

```python
security = SecurityMiddleware(
    # Force HTTPS
    ssl_redirect=True,
    ssl_permanent=True,
    
    # Strict CSP
    csp_enabled=True,
    csp_policy={
        'default-src': ["'self'"],
        'script-src': ["'self'"],
        'object-src': ["'none'"],
        'base-uri': ["'self'"],
        'frame-ancestors': ["'none'"]
    },
    
    # HSTS
    hsts_enabled=True,
    hsts_max_age=31536000,
    hsts_include_subdomains=True,
    
    # Other Security Headers
    frame_options="DENY",
    content_type_options=True,
    referrer_policy="strict-origin-when-cross-origin",
    
    # Hide Server Info
    hide_server=True
)
```

### Development Settings

::: tip Development Mode
For development, you might want to relax some settings:
:::

```python
security = SecurityMiddleware(
    # Disable HTTPS redirect
    ssl_redirect=False,
    
    # Relaxed CSP for development tools
    csp_policy={
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
        'style-src': ["'self'", "'unsafe-inline'"],
        'connect-src': ["'self'", "ws://localhost:*"]
    },
    
    # Allow all origins in development
    cors_enabled=True,
    allowed_origins=["*"],
    
    # Disable HSTS in development
    hsts_enabled=False
)
```

## 📊 Header Reference

| Header | Purpose | Default |
|--------|---------|---------|
| Content-Security-Policy | Control resource loading | self only |
| X-Frame-Options | Prevent clickjacking | DENY |
| X-XSS-Protection | XSS filter | 1; mode=block |
| Strict-Transport-Security | Force HTTPS | max-age=31536000 |
| X-Content-Type-Options | Prevent MIME sniffing | nosniff |
| Referrer-Policy | Control referrer info | strict-origin-when-cross-origin |
| Permissions-Policy | Control browser features | Various restrictions |
| Clear-Site-Data | Clear browser data | None |
| Cross-Origin-*-Policy | Cross-origin isolation | same-origin |

## 🎯 Common Scenarios

### API Server

```python
security = SecurityMiddleware(
    cors_enabled=True,
    allowed_origins=["https://api.example.com"],
    allowed_methods=["GET", "POST", "PUT", "DELETE"],
    allowed_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-ID"],
    allow_credentials=True
)
```

### Static Website

```python
security = SecurityMiddleware(
    csp_policy={
        'default-src': ["'self'"],
        'img-src': ["'self'", "data:", "https:"],
        'style-src': ["'self'", "https://fonts.googleapis.com"],
        'font-src': ["'self'", "https://fonts.gstatic.com"]
    },
    frame_options="DENY",
    cache_control="public, max-age=31536000"
)
```

### WebSocket Server

```python
security = SecurityMiddleware(
    cors_enabled=True,
    allowed_origins=["https://example.com"],
    csp_policy={
        'default-src': ["'self'"],
        'connect-src': ["'self'", "wss://ws.example.com"]
    }
)
```

## 🔧 Troubleshooting

::: warning Common Issues
1. **CSP Blocking Resources**: Check browser console for CSP violations
2. **CORS Issues**: Verify allowed origins and methods
3. **HSTS Problems**: Cannot be easily undone, use carefully
4. **Mixed Content**: Ensure all resources use HTTPS
:::

## More Information

- [MDN Web Security](https://developer.mozilla.org/en-US/docs/Web/Security)
- [OWASP Security Headers](https://owasp.org/www-project-secure-headers/)
- [Content Security Policy](https://content-security-policy.com/)
- [Report URI](https://report-uri.com/) 