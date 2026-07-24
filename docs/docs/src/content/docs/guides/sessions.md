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
from sillo import silloApp
from sillo.session.middleware import SessionMiddleware

app = silloApp()

# Add the session middleware with secret_key passed directly
app.use(
    SessionMiddleware(
        secret_key="your-secure-secret-key",
        session_cookie_name="sillo_session",
        cookie_path="/",
        cookie_domain=None,
        cookie_secure=True,
        cookie_httponly=True,
        cookie_samesite="lax",
        session_expiration_time=86400  # 24 hours
    )
)
```

With this minimal setup, sillo will use the default cookie-based session backend. Your routes can now access the session through the request object:

```python
@app.get("/")
async def index(request, response):
    # Access the session
    counter = request.session.get("counter", 0)
    counter += 1
    request.session["counter"] = counter
    
    return response.text(f"You've visited this page {counter} times")
```

##  Session Configuration Options

sillo offers various configuration options for customizing session behavior:
```python title="Recommended Approach"
from sillo import silloApp
from sillo.session import SessionConfig
from sillo.session.middleware import SessionMiddleware
from sillo.session.file import FileSessionManager

app = silloApp()

session_config = SessionConfig(
    session_cookie_name="sillo_session",
    cookie_path="/",
    cookie_domain=None,
    cookie_secure=True,
    cookie_httponly=True,
    cookie_samesite="lax",
    session_expiration_time=86400,  # 24 hours
    manager=FileSessionManager,
    session_file_storage_path="sessions",
    session_file_name="session_"
)

app.use(SessionMiddleware(config=session_config, secret_key="secret-key"))

```

##  Configuration Options Reference

| Option                | Description                                           | Default                |
| --------------------- | ----------------------------------------------------- | ---------------------- |
| `session_cookie_name` | Name of the cookie storing the session ID             | `"session_id"`         |
| `cookie_path`         | Path for which the cookie is valid                    | `"/"`                  |
| `cookie_domain`       | Domain for which the cookie is valid                  | `None`                 |
| `cookie_secure`       | Whether cookie should only be sent over HTTPS         | `False`                |
| `cookie_httponly`     | Whether cookie should be accessible via JavaScript    | `True`                 |
| `cookie_samesite`     | SameSite attribute (`"lax"`, `"strict"`, or `"none"`) | `"lax"`                |
| `expiry`              | Session lifetime in seconds                           | `86400` (24 hours)     |
| `manager`             | Session backend class                                 | `SignedSessionManager` |

##  Basic Session Operations

```python
@app.get("/session-demo")
async def session_demo(request, response):
    # Get a value with default if not present
    user_id = request.session.get("user_id", None)
    
    # Set a value
    request.session["last_visit"] = time.time()
    
    # Check if a key exists
    if "preferences" in request.session:
        preferences = request.session["preferences"]
    
    # Remove a key
    if "temporary_data" in request.session:
        del request.session["temporary_data"]
    
    # Clear the entire session
    # request.session.clear()
    
    return response.json({
        "user_id": user_id,
        "session_keys": list(request.session.keys())
    })
```

#### Session Properties and Methods

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

#### Session Expiration

By default, sessions expire after 24 hours (86400 seconds). You can customize this:

```python
# Set global session expiration time using recommended approach
session_config = SessionConfig(
    session_expiration_time=3600  # 1 hour
)
app.use(SessionMiddleware(config=session_config))

# Or set per-session expiration time
@app.post("/login")
async def login(request, response):
    # Authenticate user...
    request.session["user_id"] = user.id
    
    # Set this specific session to expire in 30 minutes
    request.session.set_expiry(1800)
    
    return response.json({"success": True})
```

##  Session Backends

sillo supports multiple session backends to store session data. Each backend has different characteristics suitable for various use cases.

##  Signed Cookie Sessions (Default)

The simplest session backend, storing the session data directly in a signed cookie:

```python
# Using recommended approach for signed cookie sessions
session_config = SessionConfig(
    manager=SignedSessionManager
)
app.use(SessionMiddleware(config=session_config))
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
# Using recommended approach for file-based sessions
session_config = SessionConfig(
    manager=FileSessionInterface,
    session_file_storage_path="sessions",  # Directory to store session files
    session_file_name="session_"           # Prefix for session files
)
app.use(SessionMiddleware(config=session_config))
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

#### Generate a Strong Secret Key

```python
import secrets

# Generate a secure random key
secret_key = secrets.token_hex(32)

# For production, store this in environment variables
secret_key = os.environ.get("SECRET_KEY")

app.use(SessionMiddleware(secret_key=secret_key))
```

#### Enable Secure Cookies

```python
# Using recommended approach for secure cookies
session_config = SessionConfig(
    cookie_secure=True,      # Only send cookies over HTTPS
    cookie_httponly=True,    # Prevent JavaScript access
    cookie_samesite="lax"    # Mitigate CSRF attacks
)
app.use(SessionMiddleware(config=session_config))
```

#### Use Appropriate Session Expiration

```python
# Short expiration for sensitive operations
@app.post("/banking/transfer")
async def transfer(request, response):
    # Verify authentication is recent
    auth_time = request.session.get("auth_time", 0)
    if time.time() - auth_time > 300:  # 5 minutes
        return response.redirect("/re-authenticate")
    
    # Process transfer...
```

#### Implement Session Invalidation

```python
@app.post("/logout")
async def logout(request, response):
    # Clear session and remove cookie
    request.session.clear()
    
    return response.redirect("/login")
```

##  Practical Examples

#### Example 1: User Authentication Flow

```python
@app.post("/login")
async def login(request, response):
    data = await request.form
    username = data.get("username")
    password = data.get("password")
    
    # Authenticate user (pseudo-code)
    user = authenticate_user(username, password)
    if not user:
        return response.redirect("/login?error=invalid_credentials")
    
    # Store user info in session
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["auth_time"] = time.time()
    request.session["is_admin"] = user.is_admin
    
    
    
    return response.redirect("/dashboard")

@app.get("/dashboard")
async def dashboard(request, response):
    # Check if user is logged in
    if "user_id" not in request.session:
        return response.redirect("/login")
    
    username = request.session["username"]
    return response.html(f"<h1>Welcome, {username}!</h1>")

@app.post("/logout")
async def logout(request, response):
    request.session.clear()
    return response.redirect("/login?message=logged_out")
```

#### Example 2: Shopping Cart

```python
@app.get("/cart")
async def view_cart(request, response):
    # Initialize cart if it doesn't exist
    cart = request.session.get("cart", {})
    
    # Calculate total
    total = sum(item["price"] * item["quantity"] for item in cart.values())
    
    return response.json({
        "items": cart,
        "total": total
    })

@app.post("/cart/add/{product_id}")
async def add_to_cart(request, response):
    product_id = request.path_params.product_id
    quantity = int(request.query_params.get("quantity", 1))
    
    # Get product details (pseudo-code)
    product = get_product(product_id)
    if not product:
        return response.json({"error": "Product not found"}, status_code=404)
    
    # Get or initialize cart
    cart = request.session.get("cart", {})
    
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
    request.session["cart"] = cart
    
    return response.json({"success": True, "cart": cart})

@app.post("/cart/clear")
async def clear_cart(request, response):
    if "cart" in request.session:
        del request.session["cart"]
    
    return response.json({"success": True})
```

#### Example 3: Multi-step Form with Session Data

```python
@app.get("/wizard/step1")
async def wizard_step1(request, response):
    # Initialize or get form data
    form_data = request.session.get("wizard_data", {})
    
    return response.html_template("wizard/step1.html", form_data=form_data)

@app.post("/wizard/step1")
async def wizard_step1_post(request, response):
    form_data = await request.form
    
    # Validate form (pseudo-code)
    if not validate_step1(form_data):
        return response.redirect("/wizard/step1?error=invalid_data")
    
    # Initialize wizard data if not exists
    wizard_data = request.session.get("wizard_data", {})
    
    # Update with step 1 data
    wizard_data.update({
        "name": form_data.get("name"),
        "email": form_data.get("email")
    })
    
    # Save back to session
    request.session["wizard_data"] = wizard_data
    
    # Proceed to next step
    return response.redirect("/wizard/step2")

@app.post("/wizard/complete")
async def wizard_complete(request, response):
    # Get all wizard data
    wizard_data = request.session.get("wizard_data", {})
    
    # Process the complete submission
    result = process_wizard_submission(wizard_data)
    
    # Clear wizard data from session
    del request.session["wizard_data"]
    
    return response.redirect(f"/wizard/success?id={result.id}")
```
