---
title: Session Management
description: Session management is a critical component of web applications, allowing you to store and retrieve user data across multiple requests. Nexios provides a robust, flexible session management system that's easy to configure yet powerful enough for complex applications.
head:
  - - meta
    - property: og:title
      content: Session Management
  - - meta
    - property: og:description
      content: Session management is a critical component of web applications, allowing you to store and retrieve user data across multiple requests. Nexios provides a robust, flexible session management system that's easy to configure yet powerful enough for complex applications.
---

Session management is a critical component of web applications, allowing you to store and retrieve user data across multiple requests. Nexios provides a robust, flexible session management system that's easy to configure yet powerful enough for complex applications.

## 🚀 Basic Session Setup

Setting up sessions in your Nexios application is straightforward:

```python
from nexios import NexiosApp
from nexios.session.middleware import SessionMiddleware

app = NexiosApp()

# Required: Configure a secret key for signing sessions
app.config.secret_key = "your-secure-secret-key"

# Add the session middleware
app.add_middleware(SessionMiddleware())
```

With this minimal setup, Nexios will use the default cookie-based session backend. Your routes can now access the session through the request object:

```python
@app.get("/")
async def index(req, res):
    # Access the session
    counter = req.session.get("counter", 0)
    counter += 1
    req.session["counter"] = counter
    
    return res.text(f"You've visited this page {counter} times")
```

## ⚙️ Session Configuration Options

Nexios offers various configuration options for customizing session behavior:

```python
from nexios import NexiosApp, MakeConfig
from nexios.session import SessionConfig
from nexios.session.middleware import SessionMiddleware
from nexios.session.file import FileSessionInterface

config = MakeConfig(
    secret_key="your-secure-secret-key",
    session=SessionConfig(
        session_cookie_name="nexios_session",
        cookie_path="/",
        cookie_domain=None,
        cookie_secure=True,
        cookie_httponly=True,
        cookie_samesite="lax",
        session_expiration_time=86400,  # 24 hours
        manager=FileSessionInterface,
        session_file_storage_path="sessions",
        session_file_name="session_"
    )
)

app = NexiosApp(config=config)
app.add_middleware(SessionMiddleware())
```

## 📊 Configuration Options Reference

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

## 🛠️ Basic Session Operations

```python
@app.get("/session-demo")
async def session_demo(req, res):
    # Get a value with default if not present
    user_id = req.session.get("user_id", None)
    
    # Set a value
    req.session["last_visit"] = time.time()
    
    # Check if a key exists
    if "preferences" in req.session:
        preferences = req.session["preferences"]
    
    # Remove a key
    if "temporary_data" in req.session:
        del req.session["temporary_data"]
    
    # Clear the entire session
    # req.session.clear()
    
    return res.json({
        "user_id": user_id,
        "session_keys": list(req.session.keys())
    })
```

#### Session Properties and Methods

Sessions in Nexios behave similar to dictionaries but with additional methods:

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
from nexios import MakeConfig
from nexios.session import SessionConfig

# Set global session expiration time
config = MakeConfig(
    session=SessionConfig(
        session_expiration_time=3600  # 1 hour
    )
)

# Or set per-session expiration time
@app.post("/login")
async def login(req, res):
    # Authenticate user...
    req.session["user_id"] = user.id
    
    # Set this specific session to expire in 30 minutes
    req.session.set_expiry(1800)
    
    return res.json({"success": True})
```

## 🔄 Session Backends

Nexios supports multiple session backends to store session data. Each backend has different characteristics suitable for various use cases.

## 🍪 Signed Cookie Sessions (Default)

The simplest session backend, storing the session data directly in a signed cookie:

```python
from nexios import MakeConfig
from nexios.session import SessionConfig
from nexios.session.signed_cookies import SignedSessionManager

config = MakeConfig(
    session=SessionConfig(
        manager=SignedSessionManager
    )
)
```

**Pros**:

* No server-side storage required
* Works well in distributed environments
* Simple setup

**Cons**:

* Limited storage size (4KB cookie limit)
* Session data sent with every request
* Cannot be invalidated server-side

## 📁 File-based Sessions

Stores session data in files on the server filesystem:

```python
from nexios import MakeConfig
from nexios.session import SessionConfig
from nexios.session.file import FileSessionInterface

config = MakeConfig(
    session=SessionConfig(
        manager=FileSessionInterface,
        session_file_storage_path="sessions",  # Directory to store session files
        session_file_name="session_"           # Prefix for session files
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

## 🏗️ Building Custom Session Backends

You can create custom session backends by implementing the `BaseSessionInterface`:

```python
from nexios.session.base import BaseSessionInterface

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

## 🔐 Session Security Best Practices

Session management requires careful attention to security:

#### Generate a Strong Secret Key

```python
import secrets

# Generate a secure random key
app.config.secret_key = secrets.token_hex(32)

# For production, store this in environment variables
app.config.secret_key = os.environ.get("SECRET_KEY")
```

#### Enable Secure Cookies

```python
from nexios import MakeConfig
from nexios.session import SessionConfig

config = MakeConfig(
    session=SessionConfig(
        cookie_secure=True,      # Only send cookies over HTTPS
        cookie_httponly=True,    # Prevent JavaScript access
        cookie_samesite="lax"    # Mitigate CSRF attacks
    )
)
```

#### Use Appropriate Session Expiration

```python
# Short expiration for sensitive operations
@app.post("/banking/transfer")
async def transfer(req, res):
    # Verify authentication is recent
    auth_time = req.session.get("auth_time", 0)
    if time.time() - auth_time > 300:  # 5 minutes
        return res.redirect("/re-authenticate")
    
    # Process transfer...
```

#### Implement Session Invalidation

```python
@app.post("/logout")
async def logout(req, res):
    # Clear session and remove cookie
    req.session.clear()
    
    return res.redirect("/login")
```

## 💡 Practical Examples

#### Example 1: User Authentication Flow

```python
@app.post("/login")
async def login(req, res):
    data = await req.form
    username = data.get("username")
    password = data.get("password")
    
    # Authenticate user (pseudo-code)
    user = authenticate_user(username, password)
    if not user:
        return res.redirect("/login?error=invalid_credentials")
    
    # Store user info in session
    req.session["user_id"] = user.id
    req.session["username"] = user.username
    req.session["auth_time"] = time.time()
    req.session["is_admin"] = user.is_admin
    
    
    
    return res.redirect("/dashboard")

@app.get("/dashboard")
async def dashboard(req, res):
    # Check if user is logged in
    if "user_id" not in req.session:
        return res.redirect("/login")
    
    username = req.session["username"]
    return res.html(f"<h1>Welcome, {username}!</h1>")

@app.post("/logout")
async def logout(req, res):
    req.session.clear()
    return res.redirect("/login?message=logged_out")
```

#### Example 2: Shopping Cart

```python
@app.get("/cart")
async def view_cart(req, res):
    # Initialize cart if it doesn't exist
    cart = req.session.get("cart", {})
    
    # Calculate total
    total = sum(item["price"] * item["quantity"] for item in cart.values())
    
    return res.json({
        "items": cart,
        "total": total
    })

@app.post("/cart/add/{product_id}")
async def add_to_cart(req, res):
    product_id = req.path_params.product_id
    quantity = int(req.query_params.get("quantity", 1))
    
    # Get product details (pseudo-code)
    product = get_product(product_id)
    if not product:
        return res.json({"error": "Product not found"}, status_code=404)
    
    # Get or initialize cart
    cart = req.session.get("cart", {})
    
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
    req.session["cart"] = cart
    
    return res.json({"success": True, "cart": cart})

@app.post("/cart/clear")
async def clear_cart(req, res):
    if "cart" in req.session:
        del req.session["cart"]
    
    return res.json({"success": True})
```

#### Example 3: Multi-step Form with Session Data

```python
@app.get("/wizard/step1")
async def wizard_step1(req, res):
    # Initialize or get form data
    form_data = req.session.get("wizard_data", {})
    
    return res.html_template("wizard/step1.html", form_data=form_data)

@app.post("/wizard/step1")
async def wizard_step1_post(req, res):
    form_data = await req.form
    
    # Validate form (pseudo-code)
    if not validate_step1(form_data):
        return res.redirect("/wizard/step1?error=invalid_data")
    
    # Initialize wizard data if not exists
    wizard_data = req.session.get("wizard_data", {})
    
    # Update with step 1 data
    wizard_data.update({
        "name": form_data.get("name"),
        "email": form_data.get("email")
    })
    
    # Save back to session
    req.session["wizard_data"] = wizard_data
    
    # Proceed to next step
    return res.redirect("/wizard/step2")

@app.post("/wizard/complete")
async def wizard_complete(req, res):
    # Get all wizard data
    wizard_data = req.session.get("wizard_data", {})
    
    # Process the complete submission
    result = process_wizard_submission(wizard_data)
    
    # Clear wizard data from session
    del req.session["wizard_data"]
    
    return res.redirect(f"/wizard/success?id={result.id}")
```
