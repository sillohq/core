---
title: Authentication in Nexios
description: A guide to authentication in Nexios
head:
  - - meta
    - property: og:title
      content: Authentication in Nexios
  - - meta
    - property: og:description
      content: Nexios makes authentication simple yet powerful. Learn how to secure your API with just one line of code, and discover the built-in features that make authentication a breeze.
---

# 🔐 Authentication in Nexios
Nexios provides a simple yet powerful authentication system that makes securing your API a breeze. With just one line of code, you can protect your routes with robust authentication logic.

By default, Nexios will try to authenticate users with a provided list of `backends`. This means that users can authenticate with either JSON Web Tokens (JWT) or session-based authentication. You can also add custom backends to support other authentication methods, such as API keys or OAuth.

## 🔑 The Basic Idea

Nexios uses a simple yet powerful authentication system that makes securing your API a breeze. With just one line of code, you can protect your routes with robust authentication logic.

```py
from nexios import NexiosApp
from nexios.config import MakeConfig
from nexios.http import Request, Response
from nexios.auth.middleware import AuthenticationMiddleware
from nexios.auth.backends.jwt import JWTAuthBackend
from nexios.auth import SimpleUser

app = NexiosApp(config=MakeConfig(
    secret_key="your-secret-key",
    
))
app.add_middleware(AuthenticationMiddleware(
    user_model=SimpleUser,
    backend=JWTAuthBackend()
))

@app.get("/profile")
@auth()
async def user_profile(request: Request, response: Response):
    return {
        "message": f"Welcome back, {request.user.display_name}!",
        "user_id": request.user.identity,
        "is_authenticated": request.user.is_authenticated
    }
```

::: tip 💡 User Model Basics
The `user_model` is the model that will be used to load the user from the authentication backend.
:::

## 🛡️ Authentication Middleware
The `AuthenticationMiddleware` takes the following arguments:

- `user_model`: The user model class that will be used to load the user from the authentication backend.
- `backend`: The authentication backend class that will be used to authenticate the user.
- `backends`: A list of authentication backend classes that will be used to authenticate the user. The first backend that successfully authenticates the user will be used.

The middleware will then attach the user to the request object under the `request.user` attribute. If the user is not authenticated, the middleware will attach an `UnauthenticatedUser` to the request object.

The middleware will also attach the authentication type to the request object under the `request.scope["auth"]` attribute. This allows you to check the authentication type in your route handlers.

::: tip ✨ Built-in SimpleUser
Nexios provides a built-in `SimpleUser` class that you can use as the `user_model` argument.
:::


## 👤 User Model

The user model is responsible for loading the user from the authentication backend. Nexios provides a simple `BaseUser` class that you can extend to create your own user model.

Here's an example of how to extend the `BaseUser` class to include a `last_login_ip` field:

```python
from nexios.auth.base import BaseUser

class User(BaseUser):
   def __init__(self, identity: str, display_name: str, last_login_ip: str):
       self.identity = identity
       self.display_name = display_name
       self.last_login_ip = last_login_ip

   @property
   def is_authenticated(self) -> bool:
       return True

   @property
   def display_name(self) -> str:
       return self.display_name

   @property
   def identity(self) -> str:
       return self.identity

   @property
   def last_login_ip(self) -> str:
       return self.last_login_ip


    @classmethod
    async def load_user(cls, identity: str) -> User:
        
        user = db.get_user_by_id(identity)
        if user:
            return cls(
                identity=user.id,
                display_name=user.display_name,
                last_login_ip=user.last_login_ip
            )
        return None

app.add_middleware(AuthenticationMiddleware(
    user_model=User,
    backend=JWTAuthBackend()
))

```

- `load_user` is a class method that is responsible for loading the user from the authentication backend it can be from a database or any other source.
now you can access the user via `request.user` and the authentication type via `request.scope["auth"]` if the user is authenticated.

## ✅ Checking Authentication Status

Once authentication middleware is set up, you can check if a user is authenticated using the `is_authenticated` property on the request user object:

```python
@app.get("/profile")
@auth()
async def user_profile(request: Request, response: Response):
    return {
        "message": f"Welcome back, {request.user.display_name}!",
        "user_id": request.user.identity,
        "is_authenticated": request.user.is_authenticated
    }
```

### Implementing is_authenticated in Custom User Models

When creating custom user models, you need to implement the `is_authenticated` property:

```python
from nexios.auth.base import BaseUser

class User(BaseUser):
    def __init__(self, identity: str, display_name: str, last_login_ip: str):
        self.identity = identity
        self.display_name = display_name
        self.last_login_ip = last_login_ip

    @property
    def is_authenticated(self) -> bool:
        return True  # Return True for authenticated users

    @property
    def display_name(self) -> str:
        return self.display_name

    @property
    def identity(self) -> str:
        return self.identity

    @property
    def last_login_ip(self) -> str:
        return self.last_login_ip

    @classmethod
    async def load_user(cls, identity: str) -> User:
        user = db.get_user_by_id(identity)
        if user:
            return cls(
                identity=user.id,
                display_name=user.display_name,
                last_login_ip=user.last_login_ip
            )
        return None
```

### 🔑 Key Points:

- **`is_authenticated` is a property**, not a method - access it without parentheses
- **Return `True`** for authenticated users, `False` for unauthenticated users
- The authentication middleware automatically handles attaching the user to `request.user`
- If authentication fails, an `UnauthenticatedUser` instance is attached instead
- The property should always return a boolean value

This allows you to easily check authentication status in your route handlers and implement proper access control.

:::

## 🎫 JWT Authentication Backend
Nexios provides a built-in `JWTAuthBackend` that you can use to authenticate users with JSON Web Tokens (JWT).

The `JWTAuthBackend` takes the following arguments:
- `identifier`: The identifier to use for the user.


### 🚀 Basic Usage

```python
from nexios.auth.backends.jwt import JWTAuthBackend

backend = JWTAuthBackend(identifier="id")

app.add_middleware(AuthenticationMiddleware(
    user_model=User,
    backend=backend
))

@app.get("/")
async def index(request: Request, response: Response):
    return {"message": "Hello, world!"}
```

### 🔑 Issuing a JWT
Nexios provides a simple way to issue a JWT token.

```python
from nexios.auth.backends.jwt import create_jwt

jwt = create_jwt(payload={"id": "123"})
```
- **payload** is the data to include in the token.

**with expires_in**
jwt = create_jwt(payload={"id": "123"}, expires_in=timedelta(minutes=30))
```
- **payload** is the data to include in the token.
- **expires_in** is the time in minutes until the token expires.

```python
from nexios.auth.backends.jwt import JWTAuthBackend
from nexios.config import MakeConfig
app = NexiosApp(config=MakeConfig(
    secret_key="your-secret-key",
    jwt_algorithms=["HS256"],
    
))
backend = JWTAuthBackend(identifier="id")

app.add_middleware(AuthenticationMiddleware(
    user_model=User,
    backend=backend
))
```

## 🍪 Session Authentication Backend
Nexios provides a built-in `SessionAuthBackend` that you can use to authenticate users with session-based authentication.


### Basic Usage

```python
from nexios.auth.backends.session import SessionAuthBackend
from nexios.config import MakeConfig
from nexios.session import SessionMiddleware
app = NexiosApp(config=MakeConfig(
    secret_key="your-secret-key",
    
))
app.add_middleware(SessionMiddleware())
backend = SessionAuthBackend()

app.add_middleware(AuthenticationMiddleware(
    user_model=User,
    backend=backend
))
```
The `SessionAuthBackend` takes the following arguments:
- `session_key`: The key used to store user data in the session (default: "user")
- `identifier`: The identifier to use for the user.

::: tip 📝 Session Setup Note
- Ensure a session middleware is added to the app.
:::


### 🔑 Login & Logout

```python
from nexios.auth.backends.session import login, logout

login(request, user)
logout(request)
```
the `login` function takes the following arguments:
- `request`: The HTTP request containing the session
- `user`: The user to login (should be an instance of `BaseUser`)

## 🔑 API Key Authentication Backend

::: warning API key authentication is a little bit complex
API key authentication requires careful management of keys, proper storage of hashed keys, and secure transmission. Make sure to follow security best practices when implementing API key authentication.
:::

Nexios provides a built-in `APIKeyAuthBackend` that you can use to authenticate users with API keys. API keys are useful for server-to-server authentication or when you need to authenticate requests from external services.

### Basic Usage

```python
from nexios.auth.backends.apikey import APIKeyAuthBackend
from nexios.auth.base import SimpleUser

class APIKeyUser(SimpleUser):
    def __init__(self, identity: str, display_name: str):
        self.identity = identity
        self.display_name = display_name

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.display_name

    @property
    def identity(self) -> str:
        return self.identity

    @classmethod
    async def load_user(cls, identity: str) -> APIKeyUser:
        # Verify the API key against your stored hash
        if db.verify_api_key(identity):
            return cls(identity=identity, display_name="API User")
        return None

backend = APIKeyAuthBackend()

app.add_middleware(AuthenticationMiddleware(
    user_model=APIKeyUser,
    backend=backend
))
```

The `APIKeyAuthBackend` takes the following arguments:
- `header_name`: The HTTP header used to pass the API key (default: "X-API-Key")
- `prefix`: The prefix for the API key (default: "key")

### Creating and Verifying API Keys

Nexios provides utility functions to create and verify API keys securely:

```python
from nexios.auth.backends.apikey import create_api_key, verify_key

# Create a new API key
api_key, hashed_key = create_api_key()
print(f"API Key: {api_key}")  # e.g., "key_abc123..."
print(f"Hashed Key: {hashed_key}")  # Store this in your database

# Verify an API key
is_valid = verify_key(api_key, stored_hash)
```

::: warning Important Security Notes
- Always store the **hashed** version of the API key in your database, never the raw key
- Use `verify_key()` to check incoming API keys against stored hashes
- API keys should be transmitted securely (HTTPS only)
- Consider implementing key rotation and expiration policies
:::

### Complete Example

Here's a complete example showing how to set up API key authentication:

```python
from nexios.auth.backends.apikey import APIKeyAuthBackend, create_api_key, verify_key
from nexios.auth.base import SimpleUser
from nexios.auth.decorators import auth

class APIKeyUser(SimpleUser):
    def __init__(self, identity: str, display_name: str, permissions: list = None):
        self.identity = identity
        self.display_name = display_name
        self.permissions = permissions or []

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.display_name

    @property
    def identity(self) -> str:
        return self.identity

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    @classmethod
    async def load_user(cls, identity: str) -> APIKeyUser:
        # This method should verify the API key and load user data
        user_data = db.get_user_by_api_key(identity)
        if user_data:
            return cls(
                identity=user_data["id"],
                display_name=user_data["name"],
                permissions=user_data["permissions"]
            )
        return None

# Set up the backend
backend = APIKeyAuthBackend(header_name="X-API-Key")

app.add_middleware(AuthenticationMiddleware(
    user_model=APIKeyUser,
    backend=backend
))

# Protected route - requires valid API key in X-API-Key header
@app.get("/api/data")
@auth(scope="apikey")
async def get_protected_data(request: Request, response: Response):
    return {
        "data": "This is protected data",
        "user": request.user.display_name,
        "permissions": request.user.permissions
    }

# Endpoint to create new API keys (protect this endpoint!)
@app.post("/api/keys")
@auth()  # Requires authentication to create keys
async def create_api_key_endpoint(request: Request, response: Response):
    user_id = request.user.identity

    # Create new API key for the user
    api_key, hashed_key = create_api_key()

    # Store the hashed key in your database
    db.store_api_key(user_id, hashed_key)

    # Return the raw API key to the user (they won't see it again!)
    return {"api_key": api_key}
```

### Configuration Options

You can customize the API key backend behavior:

```python
# Use a custom header name
backend = APIKeyAuthBackend(header_name="Authorization")

# Use a custom prefix
backend = APIKeyAuthBackend(prefix="myapp")

# Combine both options
backend = APIKeyAuthBackend(
    header_name="X-MyApp-API-Key",
    prefix="myapp"
)
```

::: tip Best Practices
- Use HTTPS for all API communications
- Implement rate limiting for API key endpoints
- Log API key usage for security monitoring
- Rotate API keys regularly
- Use different API keys for different environments (dev, staging, prod)
:::

## ⚙️ Custom Authentication Backend
You can create a custom authentication backend by implementing the `AuthenticationBackend` interface.  This interface has only one method: `authenticate`. this method should return an `AuthResult` object.

### Basic Example

```python
from nexios.auth.backends.base import AuthenticationBackend
from nexios.auth.model import AuthResult
from nexios.http import Request, Response
class CustomAuthBackend(AuthenticationBackend):
    async def authenticate(self, request: Request, response: Response) -> AuthResult:
        return AuthResult(success=True, identity="123", scope="custom")
```

`AuthResult` takes the following arguments:
- `success`: A boolean indicating whether the authentication was successful.
- `identity`: The unique identifier of the user.
- `scope`: The scope of the authentication (e.g., "jwt", "session").

### What is the scope?
the scope is used to identify the authentication backend that was used to authenticate the user.

### Simple Example

Let's create a simple example of a custom authentication backend. In this example, we will create an authentication backend that checks if the user is in a database.

```python
from nexios.auth.backends.base import AuthenticationBackend
from nexios.auth.base import SimpleUser
from nexios.auth.model import AuthResult
from nexios.http import Request, Response


class DatabaseAuthBackend(AuthenticationBackend):
    async def authenticate(self, request: Request, response: Response) -> AuthResult:
        header = request.headers.get("X-Key")
        if not header:
            return AuthResult(success=False, identity="", scope="database")
        
        return AuthResult(success=True, identity=header, scope="database")


class APIKeyUser(SimpleUser):
    def __init__(self, identity: str, display_name: str):
        self.identity = identity
        self.display_name = display_name

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.display_name

    @property
    def identity(self) -> str:
        return self.identity

    @classmethod
    async def load_user(cls, identity: str) -> APIKeyUser:
        if db.check_api_key(identity):
            return cls(identity=identity, display_name="API Key")
        return None


app.add_middleware(AuthenticationMiddleware(
    user_model=APIKeyUser,
    backend=DatabaseAuthBackend()
))

@app.get("/")
async def index(request: Request, response: Response):
    return {"message": "Hello, world!"}
```
This code defines a custom authentication backend for Nexios, which uses an API key as the identity. The `load_user` method checks if the provided API key exists in the database and returns an `APIKeyUser` instance if it does.

::: tip
- `load_user` is an async method.
:::

## 🛡️ Protected Route
Nexios provides a simple way to protect routes with authentication.

```python
from nexios.auth.decorators import auth

@app.get("/protected")
@auth()
async def protected_route(request: Request, response: Response):
    return {"message": "This is a protected route"}
```
the `auth` decorator protects the route from unauthenticated requests.


### Using Scope
You can use the `scope` argument to specify the scope of the authentication.

```python
from nexios.auth.decorators import auth

@app.get("/protected")
@auth(scope="jwt")
async def protected_route(request: Request, response: Response):
    return {"message": "This is a protected route"}
```
this will protect the route from unauthenticated requests and only allow requests with a valid JWT token.

### using multiple scopes
You can use the `scopes` argument to specify multiple scopes of the authentication.

```python
from nexios.auth.decorators import auth

@app.get("/protected")
@auth(scopes=["jwt", "session"])
async def protected_route(request: Request, response: Response):
    return {"message": "This is a protected route"}
```
this will protect the route from unauthenticated requests and only allow requests with a valid JWT token or session.




## 👑 Permissions (Role Based)
nexios provides a `has_permission` decorator to protect routes with permissions.

```python
from nexios.auth.decorators import has_permission

@app.get("/protected")
@has_permission("admin")
async def protected_route(request: Request, response: Response):
    return {"message": "This is a protected route"}
```

but the user should have the permission to access the route. you can override the `has_permission` method in the user model to check for permissions.

```python
class User(SimpleUser):
    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions
```

### Using multiple permissions
You can use the `permissions` argument to specify multiple permissions of the authentication.

```python
from nexios.auth.decorators import has_permission

@app.get("/protected")
@has_permission(permissions=["admin", "user"])
async def protected_route(request: Request, response: Response):
    return {"message": "This is a protected route"}
```
