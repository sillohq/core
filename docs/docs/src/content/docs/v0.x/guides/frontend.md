---
title: Frontend (SPA)
description: Serving static files and SPAs with Sillo.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Frontend (SPA)
  - tag: meta
    attrs:
      property: og:description
      content: Serving static files and SPAs with Sillo.
---

#  Frontend (SPA)

Sillo no longer includes a built-in `FrontendApp` or `app.frontend()` helper.

For serving static files and single-page applications, use one of the following approaches:

##  Using a reverse proxy

The recommended production setup is to serve static assets from a reverse proxy
or CDN in front of the Sillo application:

```bash
# nginx example
location / {
    proxy_pass http://127.0.0.1:8000;
}

location /static/ {
    alias /path/to/dist/;
    expires 1y;
}
```

##  Using `StaticFiles`

For development or simple deployments, mount Starlette's `StaticFiles` directly:

```python
from starlette.staticfiles import StaticFiles

app = SilloApp()
app.mount("/static", StaticFiles(directory="dist"), name="static")
```

##  Custom ASGI middleware

For SPA fallback routing, write a small ASGI middleware or mount a custom
`BaseRouter` subclass. This gives you full control over caching, fallback
behaviour, and security headers.
