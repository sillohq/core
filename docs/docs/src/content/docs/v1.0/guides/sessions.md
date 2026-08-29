---
title: Session Management
description: Session management is a critical component of web applications, allowing you to store and retrieve user data across multiple requests. sillo provides a robust, flexible session management
  system that's easy to configure yet powerful enough for complex applications.
head:
- tag: meta
  attrs:
    property: og:title
    content: Session Management
- tag: meta
  attrs:
    property: og:description
    content: Session management is a critical component of web applications, allowing you to store and retrieve user data across multiple requests. sillo provides a robust, flexible session management
      system that's easy to configure yet powerful enough for complex applications.
---

Session management is a critical component of web applications, allowing you to store and retrieve user data across multiple requests. sillo provides a robust, flexible session management system that's easy to configure yet powerful enough for complex applications.

##  Basic Session Setup

Setting up sessions in your sillo application is straightforward:

```python [Recommended Approach]
from sillo import SilloApp
from sillo.session.middleware import SessionMiddleware

app = SilloApp()

app.use(
    SessionMiddleware(
        secret_key="your-secure-secret-key",
        session_cookie_name="sillo_session",
        session_cookie_path="/",
        session_cookie_domain=None,
        session_cookie_secure=True,
        session_cookie_httponly=True,
        session_cookie_samesite="lax",
        session_expiration_time=86400,  # 24 hours
    )
)
```

Every setting is prefixed `session_`. A name that is not one raises a
`TypeError` naming the closest real setting, rather than being accepted and
ignored:

```python
SessionMiddleware(secret_key=..., cookie_secure=False)
# TypeError: SessionMiddleware() got a setting it does not understand:
#   'cookie_secure' — did you mean 'session_cookie_secure'?
```

With this minimal setup, sillo will use the default cookie-based session backend. Your routes can now access the session through the request object:

```python
from sillo import HttpContext, text

@app.get("/")
async def index(ctx: HttpContext):
    # Access the session
    counter = ctx.session.get("counter", 0)
    counter += 1
    ctx.session["counter"] = counter
    
    return text(f"You've visited this page {counter} times")
```

##  Session Configuration Options

For anything more than a handful of settings, or to share one configuration
between applications, build a `SessionConfig` and pass it as `config`:

```python title="Recommended Approach"
from sillo import SilloApp
from sillo.session import SessionConfig
from sillo.session.middleware import SessionMiddleware
from sillo.session.file import FileSessionManager

app = SilloApp()

session_config = SessionConfig(
    session_cookie_name="sillo_session",
    session_cookie_path="/",
    session_cookie_domain=None,
    session_cookie_secure=True,
    session_cookie_httponly=True,
    session_cookie_samesite="lax",
    session_expiration_time=86400,  # 24 hours
    session_file_storage_path="sessions",
)

app.use(
    SessionMiddleware(
        config=session_config,
        manager=FileSessionManager(session_config),
        secret_key="secret-key",
    )
)
```

`manager` takes an instance, not the class. The backend needs the same
configuration to know where to write.

`config` and individual settings cannot be combined. Passing both raises,
because one of the two would otherwise have to win silently.

##  Configuration Options Reference

| Option                          | Description                                            | Default                |
| ------------------------------- | ------------------------------------------------------ | ---------------------- |
| `session_cookie_name`           | Name of the cookie storing the session ID              | `"session_id"`         |
| `session_cookie_path`           | Path for which the cookie is valid                     | `"/"`                  |
| `session_cookie_domain`         | Domain for which the cookie is valid                   | `None`                 |
| `session_cookie_secure`         | Send the cookie over HTTPS only                        | `True`                 |
| `session_cookie_httponly`       | Keep the cookie out of reach of JavaScript             | `True`                 |
| `session_cookie_samesite`       | SameSite attribute (`"lax"`, `"strict"`, or `"none"`)  | `"lax"`                |
| `session_expiration_time`       | Session lifetime in seconds, enforced in the signature  | `86400` (24 hours)     |
| `session_permanent`             | Whether the cookie carries an expiry at all            | `True`                 |
| `session_refresh_each_request`  | Re-send the cookie on every response, sliding expiry   | `True`                 |
| `session_file_storage_path`     | Directory the file backend writes to                   | `None`                 |
| `manager`                       | A session backend instance                             | `SignedSessionManager` |

:::caution[The signed cookie is signed, not encrypted]
With the default backend the session's contents travel in the cookie. Anyone
holding it can base64-decode it and read every key — put identifiers in a
session, not secrets.

`session_expiration_time` is checked against a timestamp inside the signature,
not just written to the cookie's `Expires`, so a captured cookie stops working
once it lapses. Nothing else revokes one: there is no server-side record to
delete, so signing out clears the browser's copy but cannot invalidate a copy
someone else kept. Use a server-side backend where that matters.

Browsers cap a cookie at about 4096 bytes and drop larger ones without saying
so. Sillo warns when a session cookie crosses that line.
:::

:::caution
**`session_cookie_secure` in local development.** It defaults to `True`, and a
browser will not return a `Secure` cookie over plain `http://`. Serving over
HTTP without turning it off means the cookie is set and never sent back, so
every request starts a new empty session and nothing appears to work. Set it
from your environment:

```python
session_cookie_secure=config.app_env != "local"
```
:::

##  Basic Session Operations

```python
from sillo import HttpContext, json

@app.get("/session-demo")
async def session_demo(ctx: HttpContext):
    # Get a value with default if not present
    user_id = ctx.session.get("user_id", None)
    
    # Set a value
    ctx.session["last_visit"] = time.time()
    
    # Check if a key exists
    if "preferences" in ctx.session:
        preferences = ctx.session["preferences"]
    
    # Remove a key
    if "temporary_data" in ctx.session:
        del ctx.session["temporary_data"]
    
    # Clear the entire session
    # ctx.session.clear()
    
    return json({
        "user_id": user_id,
        "session_keys": list(ctx.session.keys())
    })
```

####  Session Properties and Methods

Sessions in sillo behave similar to dictionaries but with additional methods:

| Method/Property                  | Description                                            |
| -------------------------------- | ------------------------------------------------------ |
| `session.get(key, default=None)` | Get a value, returning default if not present          |
| `session[key] = value`           | Set a session value                                    |
| `key in session`                 | Check if key exists in the session                     |
| `del session[key]`               | Delete a key from the session                          |
| `session.clear()`                | Remove all keys from the session                       |
| `session.keys()`                 | Get all keys in the session                            |
| `session.items()`                | Get all key-value pairs in the session                 |
| `session.pop(key, default=None)` | Get and remove a key, returning default if not present |
| `session.is_empty()`             | Check if session has no data                           |
| `session.modified`               | Whether session has been modified                      |

####  Session Expiration

By default, sessions expire after 24 hours (86400 seconds). You can customize this:

```python
# Set global session expiration time
from sillo import HttpContext, json

app.use(SessionMiddleware(secret_key=secret_key, session_expiration_time=3600))  # 1 hour

# Or set per-session expiration time
@app.post("/login")
async def login(ctx: HttpContext):
    # Authenticate user...
    ctx.session["user_id"] = user.id
    
    # Set this specific session to expire in 30 minutes
    ctx.session.set_expiry(1800)
    
    return json({"success": True})
```

##  Session Backends

sillo supports multiple session backends to store session data. Each backend has different characteristics suitable for various use cases.

##  Signed Cookie Sessions (Default)

The simplest session backend, storing the session data directly in a signed cookie:

```python
# The default: nothing to configure beyond the key it signs with.
app.use(SessionMiddleware(secret_key=secret_key))
```

**Pros**:

* No server-side storage required
* Works well in distributed environments
* Simple setup

**Cons**:

* Limited storage size (4KB cookie limit)
* Session data sent with every request
* Cannot be invalidated server-side

##  File-based Sessions

Stores session data in files on the server filesystem:

```python
from sillo.session.file import FileSessionManager

session_config = SessionConfig(
    session_file_storage_path="sessions",  # Directory to store session files
)
app.use(
    SessionMiddleware(
        config=session_config,
        manager=FileSessionManager(session_config),
        secret_key=secret_key,
    )
)
```

**Pros**:

* Unlimited session data size
* Sessions can be invalidated server-side
* Simple setup for single-server environments

**Cons**:

* Not suitable for distributed environments
* Requires filesystem access
* Needs cleanup of expired session files

##  Building Custom Session Backends

You can create custom session backends by implementing the `BaseSessionInterface`:

```python
from sillo.session.base import BaseSessionInterface

class RedisSessionInterface(BaseSessionInterface):
    """Redis-backed session interface"""
    
    def __init__(self, session_key=None):
        super().__init__(session_key)
        self.redis_client = redis.Redis()
    
    async def load(self):
        """Load the session data from Redis"""
        if not self.session_key:
            return
        
        data = self.redis_client.get(f"session:{self.session_key}")
        if data:
            self._data = json.loads(data)
    
    async def save(self):
        """Save the session data to Redis"""
        if not self.session_key:
            self.session_key = self.generate_sid()
        
        expiry = self.get_expiry_age()
        self.redis_client.setex(
            f"session:{self.session_key}",
            expiry,
            json.dumps(self._data)
        )
        self.modified = False
    
    def get_session_key(self):
        """Return the session key"""
        return self.session_key
```

##  Session Security Best Practices

Session management requires careful attention to security:

####  Generate a Strong Secret Key

```python
import secrets

# Generate a secure random key
secret_key = secrets.token_hex(32)

# For production, store this in environment variables
secret_key = os.environ.get("SECRET_KEY")

app.use(SessionMiddleware(secret_key=secret_key))
```

####  Enable Secure Cookies

```python
app.use(
    SessionMiddleware(
        secret_key=secret_key,
        session_cookie_secure=True,    # Only send cookies over HTTPS
        session_cookie_httponly=True,  # Keep them away from JavaScript
        session_cookie_samesite="lax",  # Mitigate CSRF
    )
)
```

All three are already the defaults. The one worth setting explicitly is
`session_cookie_secure`, turned *off* for local development over HTTP.

####  Use Appropriate Session Expiration

```python
# Short expiration for sensitive operations
from sillo import HttpContext, redirect

@app.post("/banking/transfer")
async def transfer(ctx: HttpContext):
    # Verify authentication is recent
    auth_time = ctx.session.get("auth_time", 0)
    if time.time() - auth_time > 300:  # 5 minutes
        return redirect("/re-authenticate")
    
    # Process transfer...
```

####  Implement Session Invalidation

```python
from sillo import HttpContext, redirect

@app.post("/logout")
async def logout(ctx: HttpContext):
    # Clear session and remove cookie
    ctx.session.clear()
    
    return redirect("/login")
```

##  Practical Examples

####  Example 1: User Authentication Flow

```python
from sillo import HttpContext, html, redirect

@app.post("/login")
async def login(ctx: HttpContext):
    data = await ctx.form
    username = data.get("username")
    password = data.get("password")
    
    # Authenticate user (pseudo-code)
    user = authenticate_user(username, password)
    if not user:
        return redirect("/login?error=invalid_credentials")
    
    # Store user info in session
    ctx.session["user_id"] = user.id
    ctx.session["username"] = user.username
    ctx.session["auth_time"] = time.time()
    ctx.session["is_admin"] = user.is_admin
    
    
    
    return redirect("/dashboard")

@app.get("/dashboard")
async def dashboard(ctx: HttpContext):
    # Check if user is logged in
    if "user_id" not in ctx.session:
        return redirect("/login")
    
    username = ctx.session["username"]
    return html(f"<h1>Welcome, {username}!</h1>")

@app.post("/logout")
async def logout(ctx: HttpContext):
    ctx.session.clear()
    return redirect("/login?message=logged_out")
```

####  Example 2: Shopping Cart

```python
from sillo import HttpContext, json

@app.get("/cart")
async def view_cart(ctx: HttpContext):
    # Initialize cart if it doesn't exist
    cart = ctx.session.get("cart", {})
    
    # Calculate total
    total = sum(item["price"] * item["quantity"] for item in cart.values())
    
    return json({
        "items": cart,
        "total": total
    })

@app.post("/cart/add/{product_id}")
async def add_to_cart(ctx: HttpContext):
    product_id = ctx.path_params.product_id
    quantity = int(ctx.query_params.get("quantity", 1))
    
    # Get product details (pseudo-code)
    product = get_product(product_id)
    if not product:
        return json({"error": "Product not found"}, status_code=404)
    
    # Get or initialize cart
    cart = ctx.session.get("cart", {})
    
    # Add or update product in cart
    if product_id in cart:
        cart[product_id]["quantity"] += quantity
    else:
        cart[product_id] = {
            "name": product.name,
            "price": product.price,
            "quantity": quantity
        }
    
    # Save cart to session
    ctx.session["cart"] = cart
    
    return json({"success": True, "cart": cart})

@app.post("/cart/clear")
async def clear_cart(ctx: HttpContext):
    if "cart" in ctx.session:
        del ctx.session["cart"]
    
    return json({"success": True})
```

####  Example 3: Multi-step Form with Session Data

```python
from sillo import HttpContext, redirect

@app.get("/wizard/step1")
async def wizard_step1(ctx: HttpContext):
    # Initialize or get form data
    form_data = ctx.session.get("wizard_data", {})
    
    return await render("wizard/step1.html", form_data=form_data, request=ctx)

@app.post("/wizard/step1")
async def wizard_step1_post(ctx: HttpContext):
    form_data = await ctx.form
    
    # Validate form (pseudo-code)
    if not validate_step1(form_data):
        return redirect("/wizard/step1?error=invalid_data")
    
    # Initialize wizard data if not exists
    wizard_data = ctx.session.get("wizard_data", {})
    
    # Update with step 1 data
    wizard_data.update({
        "name": form_data.get("name"),
        "email": form_data.get("email")
    })
    
    # Save back to session
    ctx.session["wizard_data"] = wizard_data
    
    # Proceed to next step
    return redirect("/wizard/step2")

@app.post("/wizard/complete")
async def wizard_complete(ctx: HttpContext):
    # Get all wizard data
    wizard_data = ctx.session.get("wizard_data", {})
    
    # Process the complete submission
    result = process_wizard_submission(wizard_data)
    
    # Clear wizard data from session
    del ctx.session["wizard_data"]
    
    return redirect(f"/wizard/success?id={result.id}")
```


##  What belongs in a session

A session should hold identity and a small amount of state that is
genuinely per-user and per-browser: the user id, a CSRF token, a flash
message, a partially completed multi-step form.

It should not hold a shopping cart of arbitrary size, a cached user
object, search results, or anything you could re-derive from the
database. Every one of those grows the session, and where the session
lives decides what that growth costs.

**Cookie-backed sessions** put the data in the browser. There is no
server storage and no lookup, and the limit is hard: roughly 4 KB per
cookie including overhead, sent on *every request to the domain*. A 3 KB
session is 3 KB of upload on every image request too.

**Server-backed sessions** store data server-side and put only an
identifier in the cookie. Size is bounded by your storage, invalidation
is immediate, and every request costs a lookup.

The decision is usually made for you by one requirement: if you need to revoke
a session immediately (a logout that must take effect everywhere, or an admin
disabling an account) you need server-side storage. A signed cookie remains
valid until it expires no matter what you do.

##  Session security essentials

**Regenerate the session id on privilege change.** Logging in must issue a new
id. Without it, an attacker who can set a victim's session cookie before login
shares the session after it, session fixation, and it is still common.

**Set the cookie flags.** `HttpOnly` keeps JavaScript out, which contains
the damage from an XSS. `Secure` keeps it off plaintext connections.
`SameSite=Lax` blocks the cross-site POST case. All three, always.

**Expire on two clocks.** An idle timeout closes abandoned sessions on
shared machines; an absolute lifetime bounds how long a stolen session is
useful. Neither alone is sufficient.

**Never trust session contents to be current.** A permission cached in a
session at login is a permission the user keeps after you revoke it.
Store the identity in the session and look up authorization fresh.


##  Sessions and multiple processes

A cookie-backed session works identically across processes because the
data travels with the request. A server-backed session does not, unless
the store is shared.

An in-memory session backend is per-process: with four workers, a user
is logged in on one and logged out on the other three, and the symptom is
"login randomly does not work". Any deployment beyond a single process
needs Redis or a database behind the session store.

The same applies to invalidation. Clearing a session in one process does
nothing to the copy in another unless the store is shared.

##  Sessions versus tokens

A cookie session is convenient for a browser application: the browser
manages it, it survives navigation, and revocation is immediate with a
server-side store. It brings CSRF exposure with it, which is why the two
guides sit next to each other.

A bearer token suits API clients and mobile apps: nothing is automatic, which
removes CSRF entirely, and the client controls storage. Revocation is the hard
part. A stateless token stays valid until it expires unless you keep a
denylist, which puts the state back.

Most applications end up with both: sessions for the browser, tokens for
the API. That is fine, provided each endpoint is clear about which it
accepts. An endpoint accepting either is an endpoint whose CSRF exposure
depends on how the caller authenticated.


##  Rotating the signing key

A cookie-backed session is only as good as the key that signs it, and a leaked
key means forgeable sessions. Rotating requires accepting the old key for
verification while signing with the new one, for at least one session lifetime,
otherwise every logged-in user is logged out at once.
