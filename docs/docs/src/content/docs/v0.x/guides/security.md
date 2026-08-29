---
title: Security Headers (Shield)
description: Apply secure HTTP response headers (CSP, HSTS, frame options, and more) with the first-party sillo.security.Shield middleware.
---

#  Security Headers (Shield)

`sillo.security.Shield` is a first-party middleware that attaches defensive HTTP response headers to every response. It is the sillo equivalent of a "secure by default" header stack: Content-Security-Policy, HSTS, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, cross-origin policies, and more.

Use it to raise the browser-enforced baseline of your app without hand-writing header logic in every handler.

<aside type="caution" title="Shield is headers only">
Shield sets **response headers**. It does not handle CORS, CSRF, or
authentication. Those are separate middleware (`CORSMiddleware`,
`CSRFMiddleware`, and the auth/session modules). Docs that put
`cors_enabled`/`allowed_origins` on `Shield(...)` are wrong; configure CORS
with its own middleware (see [CORS](/v0.x/guides/cors/)).
</aside>

##  The smallest useful form

```python
from sillo import SilloApp
from sillo.security import Shield

app = SilloApp()
app.use(Shield())
```

With no arguments, `Shield` applies a strict default policy: CSP locked to `'self'`, HSTS enabled (`max-age=31536000`, include-subdomains), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and the cross-origin policies set to `same-origin`. Every response gets these headers automatically.

##  How Shield applies headers

`Shield` is a `BaseMiddleware`. In `process_response` it writes each configured
header onto the response before it leaves the stack. Because it runs late in
the chain, headers are present even on error responses and redirects, unless a
later middleware overrides them.

Defaults that are safe to change:

- `ssl_redirect=False`: off by default because it requires TLS termination in
  front of sillo. Enable only when HTTPS is enforced upstream or by sillo.
- `csp_report_only=False`: set `True` to emit CSP violations as reports without
  blocking, while you tune the policy.
- `hide_server=True`: strips the `Server` header so the stack isn't advertised.

##  Configuring the policy

```python
from sillo import SilloApp
from sillo.security import Shield

app = SilloApp()
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

##  A realistic scenario: a public API

An API server wants HSTS, a tight CSP, and CORS for one trusted web origin. CORS is a **separate** middleware layered alongside Shield:

```python
from sillo import SilloApp
from sillo.security import Shield
from sillo.security import CORSMiddleware, CorsConfig

app = SilloApp()

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

##  Header reference

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

##  Errors and edge cases

- **HSTS is hard to undo.** Once a browser caches `max-age` + `preload`,
  rolling back requires users to flush HSTS state. Only set `hsts_preload=True`
  after the host is permanently HTTPS.
- **CSP blocks assets.** A policy missing a needed source silently breaks
  scripts/styles/images in the browser console. Use `csp_report_only=True` in
  staging to collect violations before enforcing.
- **`ssl_redirect=True` without TLS**: redirects every request to HTTPS; if
  sillo itself serves plain HTTP (no proxy), clients loop or get refused. Keep
  it off unless HTTPS is terminated in front of sillo.
- **Server header.** `hide_server=True` removes `Server`; some observability
  stacks key on it, so disable if you rely on it.

##  Testing

Assert headers with `TestClient`; security headers are just response headers:

```python
from sillo import SilloApp
from sillo.security import Shield
from sillo.testclient import TestClient


def test_shield_sets_headers():
    app = SilloApp()
    app.use(Shield())

    @app.get("/")
    async def home(request, response):
        return {"ok": True}

    resp = TestClient(app).get("/")
    assert resp.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in resp.headers
    assert resp.headers["strict-transport-security"].startswith("max-age=")
```

##  Production considerations

- **HTTPS first**: enable `ssl_redirect` only when a proxy or sillo terminates
  TLS; otherwise enforce HTTPS at the edge.
- **CSP as a process**: start `csp_report_only=True`, collect violations, then
  enforce. A one-shot strict policy breaks real pages.
- **Preload carefully.** `hsts_preload=True` enters the browser preload list;
  it is effectively permanent for that host.
- **Layering.** Shield complements, not replaces, CSRF, CORS, and
  authentication. Keep each concern in its own middleware so behavior is
  auditable.
- **Don't hide everything.** `hide_server=True` is fine, but if your monitoring
  depends on the `Server` header, turn it off rather than lose telemetry.

##  Related topics

- [CORS](/v0.x/guides/cors/): cross-origin access as its own middleware
- [CSRF](/v0.x/guides/csrf/): synchronizer-token protection for state-changing
  requests
- [Authentication](/v0.x/guides/authentication/): verifying who the caller is
- [Rate Limiting](/v0.x/guides/rate-limiting/): throttling abuse


##  The checklist

Everything below has a page of its own; this is the short form to read
before a release.

###  Input

Every request input is attacker-controlled: body, query, headers, cookies,
path, and uploads. [Validate](/v0.x/guides/validation/) shape at the boundary, and
remember that shape is not meaning: a valid `user_id` is not an authorized one.

Never interpolate user input into SQL, a shell command, a filesystem
path, or a redirect target. Parameterised queries, allowlists, and
`Path.resolve()` containment checks respectively.

Bound everything: body size at the proxy, collection lengths in models,
upload sizes and counts, and string lengths.

###  Output

Escape by context. HTML escaping is not URL escaping is not JavaScript
escaping, and a value safe in one is dangerous in another. Templates autoescape
`.html` files. See [Templating](/v0.x/guides/templating/), and `|safe` disables it.

Return only declared fields. A
[response model](/v0.x/guides/validation/response-models/) drops everything
undeclared, which is the only approach that stays correct when someone
adds a column.

Never return internal detail in an error. Stack traces, SQL fragments,
and file paths are reconnaissance. See
[Error Handling](/v0.x/guides/error-handling/).

###  Authentication and authorization

Hash passwords with a password hash (bcrypt, scrypt, Argon2) never a
general-purpose one. See [Hashing helpers](/v0.x/guides/helpers/hashing/).

Rate limit the login path by IP and by account. Credential stuffing is
the most common attack any application faces.

Scope queries by the authenticated principal rather than checking after
fetching. See [Protecting Routes](/v0.x/guides/protecting-routes/).

Fail closed on every branch that cannot decide.

###  Transport and headers

HTTPS everywhere, with `Strict-Transport-Security`. `Secure`, `HttpOnly`,
and `SameSite` on every session cookie. The security header set applied
in middleware so it covers errors and static files.

###  Dependencies and secrets

Secrets from the environment, never the repository, and rotate anything that
has ever been committed, because history is forever.

Pin dependencies and scan them. Most vulnerabilities in a Python
application are in code nobody on your team wrote.

##  Threats worth understanding, not just checking

**Injection** is what happens when data becomes code. The defence is never
escaping. It is never mixing the two: parameterised queries, argument lists
rather than shell strings, allowlists for anything that selects a column or a
table.

**Broken access control** is the most common serious finding in real
applications, and it never shows up in a happy-path test. The specific
shape is an authenticated user changing an identifier and reading
something that is not theirs.

**Cross-site scripting** turns your origin into the attacker's. It is why
`HttpOnly` matters, why autoescaping matters, and why a Content Security
Policy is worth the adoption cost.

**Cross-site request forgery** exploits the browser sending cookies
automatically. It applies to cookie sessions and largely not to header
credentials. See [CSRF](/v0.x/guides/csrf/).

**Server-side request forgery** is your server fetching a URL an attacker
chose, including internal addresses and cloud metadata endpoints. Any feature
that fetches a user-supplied URL needs an allowlist and a check that the
resolved address is not private.

**Denial of service** rarely needs a botnet. An unbounded page size, an
unbounded upload, a regex with catastrophic backtracking, or a
password-hash endpoint with no rate limit will each do it from one
laptop.

##  What not to do

**Do not roll your own crypto.** Use the [helpers](/v0.x/guides/helpers/crypto/),
and read their warnings about what is not real encryption.

**Do not trust anything the client sent**, including headers that look
infrastructural.

**Do not return different responses for "no such user" and "wrong
password".**

**Do not log credentials**, in any form, at any level.

**Do not put secrets in the repository.**

**Do not disable a security control to make a test pass.** The test is
telling you something.

**Do not treat a passing test suite as a security review.** Tests check
what you thought of.


##  Where sillo helps and where it does not

The framework provides mechanisms; it does not make decisions.

**Provided:** input validation with a clean 422 contract, template
autoescaping for `.html`, password hashing helpers, CSRF middleware,
session cookie attributes, CORS middleware, rate limiting, and exception
handlers that keep internals out of responses when you configure them to.

**Not provided:** authorization logic, a Content Security Policy, secret
management, dependency scanning, audit logging, or any decision about
what your application should permit.

The pages in these guides flag several places where a helper is weaker than its
name suggests. `sanitize_html` is a regex scanner with known bypasses, and `unsign_value`'s
`max_age` is not read. Each is
documented where it lives, with a working alternative. Read those warnings
before relying on a name.

##  Building a security review into the work

Three habits catch more than any single audit.

**Test the negative cases.** For every protected endpoint: anonymous,
wrong user, right user. The middle one finds real bugs and is the one
that gets skipped.

**Test structurally, not per endpoint.** A loop over `app.router.routes`
asserting that everything outside an explicit public allowlist requires
authentication means the route added next month fails the suite rather
than shipping open.

**Review the exemption lists.** Every CSRF exemption, every unprotected
route, every disabled check. Each was added for a reason that has
probably passed, and each is a hole that nobody is looking at.

##  Related

- [Validation](/v0.x/guides/validation/): bounding what you accept
- [Authentication](/v0.x/guides/authentication/): establishing identity
- [Permissions](/v0.x/guides/permissions/): deciding what is allowed
- [Protecting Routes](/v0.x/guides/protecting-routes/): enforcing it
- [CSRF](/v0.x/guides/csrf/) and [CORS](/v0.x/guides/cors/): cross-origin concerns
- [Headers](/v0.x/guides/headers/): the security header set
- [Error Handling](/v0.x/guides/error-handling/): not leaking internals
- [Crypto helpers](/v0.x/guides/helpers/crypto/) and [Hashing helpers](/v0.x/guides/helpers/hashing/)


##  A note on threat modelling

A checklist protects against what is on it. Thinking about your specific
application catches what is not.

Three questions are usually enough to find the gaps. What is the most valuable
thing an attacker could reach, and what stands between them and it? What would
an authenticated but hostile user do, given that they can change any identifier
they see? And what happens if one component is compromised: does an XSS in the
frontend, or a stolen worker credential, give them everything or something
bounded?

The answers tend to point at layers that do not exist yet: a missing
query-level scope, a service account with more permission than it needs, a
session that cannot be revoked. Those are cheaper to add before an incident
than during one.
