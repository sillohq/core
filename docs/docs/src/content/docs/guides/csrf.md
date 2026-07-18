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

# Understanding CSRF Protection in sillo

## What is CSRF?

Cross-Site Request Forgery (CSRF) is a security vulnerability that tricks users into performing unwanted actions on web applications where they're authenticated. Attackers can force users to execute state-changing requests (like changing passwords, making purchases, or transferring funds) without their knowledge.

## ⚠️ Why CSRF Protection Matters

Imagine this scenario:

1. You're logged into your bank's website
2. You visit a malicious website in another tab
3. That site contains hidden forms or scripts that submit requests to your bank
4. Because you're already authenticated, these requests appear legitimate

Without CSRF protection, these malicious requests could perform harmful actions on your behalf.

## How CSRF Protection Works

sillo implements the "Synchronizer Token Pattern":

1. **Token Generation**: A unique, secure token is generated when a user visits your site
2. **Token Storage**: Stored in an HTTP-only cookie and server session
3. **Token Validation**: Required for state-changing requests (POST, PUT, DELETE, etc.)
4. **Request Verification**: Server verifies the token matches the session

## Basic Setup

```python
from sillo import silloApp
from sillo.security.csrf import CSRFConfig, CSRFMiddleware

csrf_config = CSRFConfig(
    enabled=True,
    secret_key="your-secret-key-here",  # Required: used to sign CSRF tokens
    required_urls=["*"],
    safe_methods=["GET", "HEAD", "OPTIONS"],
    cookie_name="csrftoken",
    header_name="X-CSRFToken"
)

app = silloApp()
app.use(CSRFMiddleware(config=csrf_config))
```

## Configuration Options

sillo provides flexible configuration to customize CSRF protection for your application's needs. Here's a detailed breakdown of each option:

### Core Settings

- **`enabled`** (boolean, default: `False`)
  - Enables or disables CSRF protection globally
  - **Recommended**: `True` in production environments
  - Example: `CSRFConfig(enabled=True)`

- **`secret_key`** (string, required)
  - Cryptographic key used to sign CSRF tokens
  - **Security Note**: Keep this secret and consistent across application restarts
  - Example: `CSRFConfig(secret_key="your-secure-key-123")`

### URL Configuration

- **`required_urls`** (list of strings, default: `["*"]`)
  - URL patterns that require CSRF protection
  - Supports wildcard `*` for matching multiple URLs
  - Example: `["/api/*", "/admin/*"]`

- **`exempt_urls`** (list of strings, default: `[]`)
  - URL patterns excluded from CSRF protection
  - Takes precedence over `required_urls`
  - Example: `["/api/public/*", "/webhooks/stripe"]`

### HTTP Methods

- **`safe_methods`** (list of strings, default: `["GET", "HEAD", "OPTIONS"]`)
  - HTTP methods that don't require CSRF tokens
  - These should be idempotent and have no side effects
  - Example: `["GET", "HEAD", "OPTIONS", "TRACE"]`

### Cookie Settings

- **`cookie_name`** (string, default: `"csrftoken"`)
  - Name of the cookie that stores the CSRF token
  - Change this if you need to avoid naming conflicts
  - Example: `CSRFConfig(cookie_name="myapp_csrf_token")`

- **`cookie_secure`** (boolean, default: `False`)
  - When `True`, the cookie is only sent over HTTPS
  - **Security Best Practice**: Set to `True` in production
  - Example: `CSRFConfig(cookie_secure=True)`

- **`cookie_httponly`** (boolean, default: `True`)
  - Prevents JavaScript from accessing the cookie
  - **Security Best Practice**: Keep this as `True`
  - Example: `CSRFConfig(cookie_httponly=True)`

- **`cookie_samesite`** (string, default: `"lax"`)
  - Controls when cookies are sent with cross-site requests
  - Options: `"lax"` (recommended), `"strict"`, or `"none"`
  - Note: `"none"` requires `secure=True`
  - Example: `CSRFConfig(cookie_samesite="lax")`

### Headers and Forms

- **`header_name`** (string, default: `"X-CSRFToken"`)
  - HTTP header name for sending CSRF tokens in AJAX requests
  - Example: `CSRFConfig(header_name="X-CSRF-TOKEN")`

- **`form_field`** (string, default: `"csrf_token"`)
  - Form field name for CSRF tokens in HTML forms
  - Must match your form field names
  - Example: `CSRFConfig(form_field="_csrf_token")`

- **`cookie_path`** (string, default: `"/"`)
  - Path for which the cookie is valid
  - Example: `CSRFConfig(cookie_path="/api")`

## Using CSRF with Templates

When working with sillo templates, you can easily include CSRF tokens in your forms. The CSRF token is automatically added to the request state and can be accessed in your templates.

### 1. Basic Form with CSRF Token

First, ensure you have a template file (e.g., `templates/login.html`):

```html
<!-- templates/login.html -->
<!DOCTYPE html>
<html>
  <head>
    <title>Login</title>
  </head>
  <body>
    <h1>Login</h1>
    <form method="post" action="/login">
      <input type="hidden" name="csrftoken" value="{{ csrf_token }}" />

      <div class="form-group">
        <label for="username">Username:</label>
        <input type="text" id="username" name="username" required />
      </div>

      <div class="form-group">
        <label for="password">Password:</label>
        <input type="password" id="password" name="password" required />
      </div>

      <button type="submit">Login</button>
    </form>
  </body>
</html>
```

### 2. Route Handler with Template Rendering

In your route handler, use the `render` function to render the template with the CSRF token:

```python
from sillo.templating import render

@app.get("/login")
async def login_get(request, response):
    # The CSRF token is automatically available in the template context
    return await render("login.html", request=request)

@app.post("/login")
async def login_post(request, response):
    form = await request.form
    # CSRF validation happens automatically via the middleware

    # Your login logic here
    if form.get("username") == "admin" and form.get("password") == "password":
        return "Login successful!"
    return "Invalid credentials"
```

### 3. Using Template Context Middleware (Recommended)

For better organization, use the `TemplateContextMiddleware` to automatically inject the CSRF token into all your templates:

```python
from sillo.templating.middleware import TemplateContextMiddleware

# Add this before your route definitions
app.use(TemplateContextMiddleware())

# Now all templates will have access to the CSRF token as `{{ csrf_token }}`
```

### 4. AJAX Requests with CSRF

For AJAX requests, include the CSRF token in your JavaScript:

```javascript
// Include this in your base template
<script>
    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // Example AJAX request
    async function submitForm() {
        const response = await fetch('/api/endpoint', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ data: 'example' })
        });
        return await response.json();
    }
</script>
```

### 5. Customizing the CSRF Field Name

If you need to use a different field name for the CSRF token in your forms, you can customize it in your configuration:

```python
csrf_config = CSRFConfig(
    # ... other config
    form_field="custom_csrf_field",  # Default is "csrftoken"
)
app.use(CSRFMiddleware(config=csrf_config))
```

Then update your form to use the custom field name:

```html
<form method="post">
  <input type="hidden" name="custom_csrf_field" value="{{ csrf_token }}" />
  <!-- form fields -->
</form>
```

## Best Practices

1. **Always use HTTPS** in production to protect the CSRF token in transit.
2. **Don't expose the CSRF token** in logs or error messages.
3. **Use the TemplateContextMiddleware** to automatically include the CSRF token in all templates.
4. **Protect all state-changing endpoints** (POST, PUT, DELETE, PATCH) with CSRF tokens.
5. **Use the same-site cookie attribute** to provide additional protection against CSRF attacks.

## Client-Side Implementation

### 1. HTML Forms

For traditional form submissions, include the CSRF token in a hidden field. The token should be included in every form that performs state-changing operations (POST, PUT, DELETE, etc.).

```html
<!-- Example: User Profile Update Form -->
<form method="post" action="/profile/update">
  <div class="form-group">
    <label for="username">Username</label>
    <input
      type="text"
      id="username"
      name="username"
      value="{{ current_user.username }}"
      required
    />
  </div>

  <div class="form-group">
    <label for="email">Email</label>
    <input
      type="email"
      id="email"
      name="email"
      value="{{ current_user.email }}"
      required
    />
  </div>

  <button type="submit" class="btn btn-primary">Update Profile</button>
</form>
```

### 2. JavaScript (AJAX) Requests

For AJAX requests, you'll need to:

1. Extract the CSRF token from cookies
2. Include it in the request headers

```javascript
// Example AJAX request
async function submitForm() {
  const csrfToken = document.cookie.match(/csrftoken=([^\s]*)/)[1];
  const response = await fetch("/api/endpoint", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify({ data: "example" }),
  });
  return await response.json();
}
```

## How a request is checked

`CSRFMiddleware.process_request` runs this sequence for every request (only when `enabled=True`):

1. Generate a fresh signed token and stash it on `request.state.csrf_token`.
2. If the method is in `safe_methods` (`GET`, `HEAD`, `OPTIONS` by default), allow the request through.
3. Otherwise, if the path matches `required_urls` — or matches `exempt_urls` **and** carries a sensitive cookie — validation runs:
   - The token cookie (`cookie_name`) must be present.
   - A submitted token must be present, read from the `X-CSRFToken` header, or (for form-urlencoded bodies) the `csrftoken` form field.
   - The submitted token must match the cookie token.
4. Any failure (missing cookie, missing token, mismatch) returns **`403`** and clears the CSRF cookie.

On the way out, `process_response` sets the `csrftoken` cookie so the next request can present a matching header. The cookie is `HttpOnly` by default, so JavaScript cannot read it — the token must travel in the header (or form field), which is what makes the pattern resistant to cross-site forgery.

## Testing

Drive CSRF through `TestClient`: fetch a token-bearing response, then replay the cookie + header on a `POST`.

```python
from sillo import silloApp
from sillo.security import CSRFMiddleware, CSRFConfig
from sillo.testclient import TestClient


def test_valid_token_passes():
    app = silloApp()
    app.use(CSRFMiddleware(CSRFConfig(enabled=True, secret_key="secret")))

    @app.post("/transfer")
    async def transfer(request, response):
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
    app = silloApp()
    app.use(CSRFMiddleware(CSRFConfig(enabled=True, secret_key="secret")))

    @app.post("/transfer")
    async def transfer(request, response):
        return {"ok": True}

    resp = TestClient(app).post("/transfer")
    assert resp.status_code == 403
```

<aside type="caution" title="secret_key is mandatory">
`CSRFConfig(enabled=True)` without `secret_key` leaves `self.secret` as `None`, so token signing has no key and protection is broken. Set `secret_key` to a stable secret (env var, not a literal in source) and keep it identical across restarts — rotating it invalidates every outstanding token at once.
</aside>

## Related topics

- [Security Headers (Shield)](/guides/security/) — defensive response headers
- [CORS](/guides/cors/) — cross-origin access control
- [Authentication](/guides/authentication/) — who the caller is
