---
title: Security Headers (Shield)
description: Apply secure HTTP response headers — CSP, HSTS, frame options, and more — with the first-party sillo.security.Shield middleware.
---

# Security Headers (Shield)

`sillo.security.Shield` is a first-party middleware that attaches defensive HTTP response headers to every response. It is the sillo equivalent of a "secure by default" header stack: Content-Security-Policy, HSTS, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, cross-origin policies, and more.

Use it to raise the browser-enforced baseline of your app without hand-writing header logic in every handler.

<aside type="caution" title="Shield is headers only">
Shield sets **response headers**. It does not handle CORS, CSRF, or authentication — those are separate middleware (`CORSMiddleware`, `CSRFMiddleware`, and the auth/session modules). Docs that put `cors_enabled`/`allowed_origins` on `Shield(...)` are wrong; configure CORS with its own middleware (see [CORS](/guides/cors/)).
</aside>

## The smallest useful form

```python
from sillo import silloApp
from sillo.security import Shield

app = silloApp()
app.use(Shield())
```

With no arguments, `Shield` applies a strict default policy: CSP locked to `'self'`, HSTS enabled (`max-age=31536000`, include-subdomains), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and the cross-origin policies set to `same-origin`. Every response gets these headers automatically.

## How Shield applies headers

`Shield` is a `BaseMiddleware`. In `process_response` it writes each configured header onto the response before it leaves the stack. Because it runs late in the chain, headers are present even on error responses and redirects — unless a later middleware overrides them.

Defaults that are safe to change:

- `ssl_redirect=False` — off by default because it requires TLS termination in front of sillo. Enable only when HTTPS is enforced upstream or by sillo.
- `csp_report_only=False` — set `True` to emit CSP violations as reports without blocking, while you tune the policy.
- `hide_server=True` — strips the `Server` header so the stack isn't advertised.

## Configuring the policy

```python
from sillo import silloApp
from sillo.security import Shield

app = silloApp()
app.use(
    Shield(
        csp_enabled=True,
        csp_policy={
            "default-src": ["'self'"],
            "script-src": ["'self'"],
            "style-src": ["'self'", "https://fonts.googleapis.com"],
            "img-src": ["'self'", "data:", "https:"],
            "connect-src": ["'self'", "https://api.example.com"],
        },
        hsts_enabled=True,
        hsts_max_age=31536000,
        hsts_include_subdomains=True,
        hsts_preload=True,
        frame_options="DENY",
        referrer_policy="strict-origin-when-cross-origin",
    )
)
```

`csp_policy` accepts a dict of directive → list of sources. When omitted, Shield uses a restrictive same-origin default (`object-src: 'none'`, `frame-ancestors: 'none'`, `base-uri: 'self'`). Validate CSP in `csp_report_only=True` mode first; a too-strict policy will block legitimate assets.

## A realistic scenario: a public API

An API server wants HSTS, a tight CSP, and CORS for one trusted web origin. CORS is a **separate** middleware layered alongside Shield:

```python
from sillo import silloApp
from sillo.security import Shield
from sillo.security import CORSMiddleware, CorsConfig

app = silloApp()

# Headers
app.use(Shield(hsts_enabled=True, csp_enabled=True))

# Cross-origin access — its own middleware, not a Shield argument
app.use(
    CORSMiddleware(
        CorsConfig(
            allow_origins=["https://app.example.com"],
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            expose_headers=["X-Request-ID"],
            allow_credentials=True,
        )
    )
)
```

Shield and CORS are independent: Shield owns the security headers, `CORSMiddleware` owns the `Access-Control-*` headers. Ordering between them does not matter for the headers themselves, but both should run before routing so error responses carry them.

## Header reference

| Header | Purpose | Shield default |
| --- | --- | --- |
| `Content-Security-Policy` | Controls loadable resources | `'self'` for scripts/styles/img/connect/font; `none` for object/frame |
| `Strict-Transport-Security` | Forces HTTPS | `max-age=31536000; includeSubDomains` |
| `X-Frame-Options` | Clickjacking protection | `DENY` |
| `X-Content-Type-Options` | MIME sniffing protection | `nosniff` |
| `Referrer-Policy` | Referrer leakage control | `strict-origin-when-cross-origin` |
| `Cross-Origin-Opener-Policy` | Cross-origin isolation | `same-origin` |
| `Cross-Origin-Embedder-Policy` | Cross-origin isolation | `require-corp` |
| `Cross-Origin-Resource-Policy` | Resource sharing | `same-origin` |
| `Permissions-Policy` | Browser feature gating | none unless configured |

## Errors and edge cases

- **HSTS is hard to undo** — once a browser caches `max-age` + `preload`, rolling back requires users to flush HSTS state. Only set `hsts_preload=True` after the host is permanently HTTPS.
- **CSP blocks assets** — a policy missing a needed source silently breaks scripts/styles/images in the browser console. Use `csp_report_only=True` in staging to collect violations before enforcing.
- **`ssl_redirect=True` without TLS** — redirects every request to HTTPS; if sillo itself serves plain HTTP (no proxy), clients loop or get refused. Keep it off unless HTTPS is terminated in front of sillo.
- **Server header** — `hide_server=True` removes `Server`; some observability stacks key on it, so disable if you rely on it.

## Testing

Assert headers with `TestClient`; security headers are just response headers:

```python
from sillo import silloApp
from sillo.security import Shield
from sillo.testclient import TestClient


def test_shield_sets_headers():
    app = silloApp()
    app.use(Shield())

    @app.get("/")
    async def home(request, response):
        return {"ok": True}

    resp = TestClient(app).get("/")
    assert resp.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in resp.headers
    assert resp.headers["strict-transport-security"].startswith("max-age=")
```

## Production considerations

- **HTTPS first** — enable `ssl_redirect` only when a proxy or sillo terminates TLS; otherwise enforce HTTPS at the edge.
- **CSP as a process** — start `csp_report_only=True`, collect violations, then enforce. A one-shot strict policy breaks real pages.
- **Preload carefully** — `hsts_preload=True` enters the browser preload list; it is effectively permanent for that host.
- **Layering** — Shield complements, not replaces, CSRF, CORS, and authentication. Keep each concern in its own middleware so behavior is auditable.
- **Don't hide everything** — `hide_server=True` is fine, but if your monitoring depends on the `Server` header, turn it off rather than lose telemetry.

## Related topics

- [CORS](/guides/cors/) — cross-origin access as its own middleware
- [CSRF](/guides/csrf/) — synchronizer-token protection for state-changing requests
- [Authentication](/guides/authentication/) — verifying who the caller is
- [Rate Limiting](/guides/rate-limiting/) — throttling abuse
