---
title: CSRF in sillo
description: Learn how to use csrf utilities in sillo
head:
- tag: meta
  attrs:
    property: og:title
    content: CSRF in sillo
- tag: meta
  attrs:
    property: og:description
    content: Learn how to use csrf utilities in sillo
---

#  Understanding CSRF Protection in sillo

##  What is CSRF?

Cross-Site Request Forgery (CSRF) is a security vulnerability that tricks users into performing unwanted actions on web applications where they're authenticated. Attackers can force users to execute state-changing requests (like changing passwords, making purchases, or transferring funds) without their knowledge.

##  ⚠️ Why CSRF Protection Matters

Imagine this scenario:

1. You're logged into your bank's website
2. You visit a malicious website in another tab
3. That site contains hidden forms or scripts that submit requests to your bank
4. Because you're already authenticated, these requests appear legitimate

Without CSRF protection, these malicious requests could perform harmful actions on your behalf.

##  How CSRF Protection Works

sillo implements the "Synchronizer Token Pattern":

1. **Token Generation**: A unique, secure token is generated when a user visits your site
2. **Token Storage**: Stored in an HTTP-only cookie and server session
3. **Token Validation**: Required for state-changing requests (POST, PUT, DELETE, etc.)
4. **Request Verification**: Server verifies the token matches the session

##  Basic Setup

```python
from sillo import SilloApp
from sillo.security.csrf import CSRFConfig, CSRFMiddleware

csrf_config = CSRFConfig(
    enabled=True,
    secret_key="your-secret-key-here",  # Required: used to sign CSRF tokens
    required_urls=["*"],
    safe_methods=["GET", "HEAD", "OPTIONS"],
    cookie_name="csrftoken",
    header_name="X-CSRFToken"
)

app = SilloApp()
app.use(CSRFMiddleware(config=csrf_config))
```

##  Configuration Options

sillo provides flexible configuration to customize CSRF protection for your application's needs. Here's a detailed breakdown of each option:

###  Core Settings

- **`enabled`** (boolean, default: `False`)
  - Enables or disables CSRF protection globally
  - **Recommended**: `True` in production environments
  - Example: `CSRFConfig(enabled=True)`

- **`secret_key`** (string, required when `enabled=True`)
  - Cryptographic key used to sign CSRF tokens
  - **Security Note**: Keep this secret and consistent across application restarts.
    Changing it invalidates every token in flight, so the next request from each
    open page is a 403 until it reloads.
  - Enabling CSRF without one raises `ValueError` at startup
  - Example: `CSRFConfig(secret_key="your-secure-key-123")`

###  URL Configuration

- **`required_urls`** (list of strings, default: `["*"]`)
  - URL patterns that require CSRF protection
  - Supports wildcard `*` for matching multiple URLs
  - Example: `["/api/*", "/admin/*"]`

- **`exempt_urls`** (list of strings, default: `[]`)
  - URL patterns excluded from CSRF protection
  - Takes precedence over `required_urls`
  - Patterns are regular expressions and must match the **whole** path, so
    `/webhooks` does not exempt `/webhooks/stripe` — write `/webhooks/.*`
  - Example: `["/api/public/.*", "/webhooks/stripe"]`

- **`sensitive_cookies`** (list of strings, default: `[]`)
  - Cookies that carry ambient authority, typically your session cookie
  - When set, only requests presenting one of them are checked — which is what
    lets an API authenticated by an `Authorization` header skip the token
  - Naming none keeps the safe default of treating every request as sensitive
  - Example: `CSRFConfig(sensitive_cookies=["session_id"])`

###  HTTP Methods

- **`safe_methods`** (list of strings, default: `["GET", "HEAD", "OPTIONS"]`)
  - HTTP methods that don't require CSRF tokens
  - These should be idempotent and have no side effects
  - Example: `["GET", "HEAD", "OPTIONS", "TRACE"]`

###  Cookie Settings

- **`cookie_name`** (string, default: `"csrftoken"`)
  - Name of the cookie that stores the CSRF token
  - Change this if you need to avoid naming conflicts
  - Example: `CSRFConfig(cookie_name="myapp_csrf_token")`

- **`cookie_secure`** (boolean, default: `False`)
  - When `True`, the cookie is only sent over HTTPS
  - **Security Best Practice**: Set to `True` in production
  - Example: `CSRFConfig(cookie_secure=True)`

- **`cookie_httponly`** (boolean, default: `False`)
  - Prevents JavaScript from accessing the cookie
  - **Leave this off.** The double-submit pattern requires the page to read
    this cookie and echo it back in `header_name`, which `HttpOnly` makes
    impossible — an `HttpOnly` CSRF cookie cannot be used by any JavaScript
    client. The token is not a credential: it is only useful to someone who
    can already read the page. Turn it on only if every form is rendered
    server-side with the token already in it and nothing submits over AJAX.
  - Example: `CSRFConfig(cookie_httponly=True)`

- **`cookie_samesite`** (string, default: `"lax"`)
  - Controls when cookies are sent with cross-site requests
  - Options: `"lax"` (recommended), `"strict"`, or `"none"`
  - Note: `"none"` requires `secure=True`
  - Example: `CSRFConfig(cookie_samesite="lax")`

###  Headers and Forms

- **`header_name`** (string, default: `"X-CSRFToken"`)
  - HTTP header name for sending CSRF tokens in AJAX requests
  - Example: `CSRFConfig(header_name="X-CSRF-TOKEN")`

- **`form_field`** (string, default: `"csrftoken"`)
  - Form field name for CSRF tokens in HTML forms
  - Must match your form field names
  - Read for both `application/x-www-form-urlencoded` and
    `multipart/form-data` bodies, so file-upload forms — which cannot set a
    header — can submit a token too
  - Example: `CSRFConfig(form_field="_csrf_token")`

- **`cookie_path`** (string, default: `"/"`)
  - Path for which the cookie is valid
  - Example: `CSRFConfig(cookie_path="/api")`

##  Getting the token to the client

The middleware puts the token on `ctx.state.csrf_token` before your handler
runs, and sets it as a cookie on the way out. Every way of submitting it starts
from one of those two.

###  1. Read it in a handler

```python
from sillo import HttpContext
from sillo.responses import json


@app.get("/api/csrf")
async def csrf(ctx: HttpContext):
    return {"token": ctx.state.csrf_token}
```

That is the shape a single-page app wants: fetch it once, keep it, send it back
in the `X-CSRFToken` header on every mutating request.

###  2. Share it with an Inertia page

[Inertia](/v1.0/guides/inertia/) pages get it as a shared prop, so every page
component has it without asking:

```python
inertia.share("csrf_token", lambda ctx: ctx.state.csrf_token)
```

```jsx
router.post('/posts', data, {
    headers: { 'X-CSRFToken': props.csrf_token },
})
```

###  3. Read it from the cookie

The token is also in a cookie, readable from JavaScript by design — the
protection comes from the attacker's page being unable to *read* your cookies,
not from the token being secret from your own page:

```javascript
const token = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrftoken='))
    ?.split('=')[1];

await fetch('/posts', {
    method: 'POST',
    headers: { 'X-CSRFToken': token, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
});
```

###  4. Submit it as a form field

A plain HTML form cannot set a header, so the middleware also reads the token
out of the body, under `form_field` (default `csrftoken`). Both
`application/x-www-form-urlencoded` and `multipart/form-data` are read, so a
file-upload form can submit one too:

```html
<form method="post" action="/login">
    <input type="hidden" name="csrftoken" value="…" />
    <input type="text" name="username" required />
    <input type="password" name="password" required />
    <button type="submit">Log in</button>
</form>
```

Fill the hidden input from the cookie, or render the page from a handler that
has `ctx.state.csrf_token` to hand.

###  5. Customizing the CSRF field name

If your front end already posts a differently-named field, name it rather than
changing the front end:

```python
csrf_config = CSRFConfig(
    # ... other config
    form_field="custom_csrf_field",  # Default is "csrftoken"
    header_name="X-CSRF-TOKEN",      # Default is "X-CSRFToken"
)
app.use(CSRFMiddleware(config=csrf_config))
```

##  Best Practices

1. **Always use HTTPS** in production to protect the CSRF token in transit.
2. **Don't expose the CSRF token** in logs or error messages.
3. **Share the token once**, as an Inertia shared prop or a single endpoint, rather than fetching it per form.
4. **Protect all state-changing endpoints** (POST, PUT, DELETE, PATCH) with CSRF tokens.
5. **Use the same-site cookie attribute** to provide additional protection against CSRF attacks.

##  How a request is checked

`CSRFMiddleware.dispatch` runs this sequence before `call_next`, for every request (only when `enabled=True`):

1. Generate a fresh signed token and stash it on `ctx.state.csrf_token`.
2. If the method is in `safe_methods` (`GET`, `HEAD`, `OPTIONS` by default), allow the request through.
3. Otherwise, if the path matches `required_urls`, or matches `exempt_urls`
   **and** carries a sensitive cookie, validation runs:
   - The token cookie (`cookie_name`) must be present.
   - A submitted token must be present, read from the `X-CSRFToken` header, or (for form-urlencoded bodies) the `csrftoken` form field.
   - The submitted token must match the cookie token.
4. Any failure (missing cookie, missing token, mismatch) returns **`403`** and clears the CSRF cookie.

On the way out, after `call_next` returns, it sets the `csrftoken` cookie so the next
request can present a matching header. The cookie is `HttpOnly` by default, so
JavaScript cannot read it. The token must travel in the header (or form field),
which is what makes the pattern resistant to cross-site forgery.

##  Testing

Drive CSRF through `TestClient`: fetch a token-bearing response, then replay the cookie + header on a `POST`.

```python
from sillo import SilloApp, HttpContext
from sillo.security import CSRFMiddleware, CSRFConfig
from sillo.testclient import TestClient


def test_valid_token_passes():
    app = SilloApp()
    app.use(CSRFMiddleware(CSRFConfig(enabled=True, secret_key="secret")))

    @app.post("/transfer")
    async def transfer(ctx: HttpContext):
        return {"ok": True}

    client = TestClient(app)
    token_resp = client.get("/")  # any GET primes the cookie
    cookie = token_resp.cookies["csrftoken"]

    resp = client.post(
        "/transfer",
        headers={"X-CSRFToken": cookie},
        cookies={"csrftoken": cookie},
    )
    assert resp.status_code == 200


def test_missing_token_rejected():
    app = SilloApp()
    app.use(CSRFMiddleware(CSRFConfig(enabled=True, secret_key="secret")))

    @app.post("/transfer")
    async def transfer(ctx: HttpContext):
        return {"ok": True}

    resp = TestClient(app).post("/transfer")
    assert resp.status_code == 403
```

<aside type="caution" title="secret_key is mandatory">
`CSRFConfig(enabled=True)` without `secret_key` leaves `self.secret` as `None`,
so token signing has no key and protection is broken. Set `secret_key` to a
stable secret (env var, not a literal in source) and keep it identical across
restarts, rotating it invalidates every outstanding token at once.
</aside>

##  Related topics

- [Security Headers (Shield)](/v1.0/guides/security/): defensive response headers
- [CORS](/v1.0/guides/cors/): cross-origin access control
- [Authentication](/v1.0/guides/authentication/): who the caller is


##  Why CSRF exists, precisely

A browser attaches cookies to a request based on its destination, not its
origin. A form on `evil.example` that posts to `bank.example/transfer`
carries the user's `bank.example` session cookie, and from the server's
perspective the request is indistinguishable from a legitimate one.

That is the entire attack. The defence is to require something the
attacker's page cannot read or guess.

Two properties make CSRF specifically a *cookie* problem. A form POST
needs no JavaScript, so no CORS preflight blocks it. And cookies are sent
automatically, so the attacker never needs to steal one.

An API authenticating with an `Authorization` header is not vulnerable in the
same way. The attacker's page cannot set that header cross-origin, and
attempting to triggers a preflight that CORS refuses. **If your session lives
in a cookie, you need CSRF protection. If it lives in a header, you largely do
not.**

##  `SameSite` is a strong defence, not a complete one

`SameSite=Lax` stops cookies riding along on cross-site POSTs, which
removes the classic attack. It is a genuine improvement and worth setting
on every session cookie.

It is not a replacement for tokens. `Lax` still sends cookies on top-level
`GET` navigations, so any state-changing `GET` remains exposed, which is one
more reason `GET` must never change state. Browser support is universal now but
the enforcement details vary, and a subdomain you do not control is same-site
for cookie purposes.

Defence in depth: set `SameSite=Lax` (or `Strict` where the UX allows),
**and** validate a token on every state-changing request.

##  Where the token has to appear

The token must be somewhere the attacker cannot read: a form field, or a
request header. It must **not** be in a cookie alone, because the
attacker's page causes that cookie to be sent without ever seeing it.

The double-submit pattern (token in a cookie *and* in a header, compared
server-side) works because reading the cookie to copy it into the header
requires same-origin JavaScript. It is weaker than a server-side session token
when subdomains are involved, since a compromised subdomain can write cookies
for the parent domain.

Three things that must be exempt or handled specially: webhook endpoints,
which have no browser and no token; login itself, where no session exists
yet; and anything authenticating by header rather than cookie.


##  Failure modes

Two things go wrong with CSRF protection, in opposite directions.

**Too strict** breaks legitimate flows: a token that expires with a short
session means a user who leaves a form open gets an error on submit. Give the
token the session's lifetime, and return a clear, specific message ("your
session expired, reload and try again") rather than a bare 403, which users
read as "you are not allowed".

**Too permissive** is the exemption list. Every exempt endpoint is an
endpoint without protection, and exemptions accumulate: one for a
webhook, one for a legacy client, one added during an incident. Review
the list periodically and require a reason for each entry.
