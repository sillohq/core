# Nexios Auth, State, And Security

Use this reference for login flows, protected routes, session state, cookie handling, and response hardening.

## Table of Contents

1. [Authentication Middleware](#authentication-middleware)
2. [Protected Routes](#protected-routes)
3. [Sessions](#sessions)
4. [Cookies](#cookies)
5. [Headers](#headers)
6. [CORS and Request Hardening](#cors-and-request-hardening)
7. [Security Middleware](#security-middleware)

## Authentication Middleware

The docs present authentication as middleware plus protected handlers.

```python
from nexios import NexiosApp
from nexios.auth import SimpleUser
from nexios.auth.decorators import auth
from nexios.auth.backends.jwt import JWTAuthBackend
from nexios.auth.middleware import AuthenticationMiddleware

app = NexiosApp()

app.add_middleware(AuthenticationMiddleware(
    user_model=SimpleUser,
    backend=JWTAuthBackend()
))
```

Key mental model:

- Authentication middleware attaches the current user to `request.user`
- The auth type is exposed through request scope metadata
- Route protection happens with decorators or auth-aware logic

## Protected Routes

```python
@app.get("/profile")
@auth()
async def profile(request, response):
    return response.json({
        "user": request.user.display_name,
        "authenticated": request.user.is_authenticated
    })


@app.get("/profile")
@auth(scope =["jwt"]) #for scoped auth
async def profile(request, response):
    return response.json({
        "user": request.user.display_name,
        "authenticated": request.user.is_authenticated
    })

```



## Auth Backends

```python
from nexios.auth.backends.session import SessionAuthBackend
from nexios.session import SessionConfig
from nexios.session.middleware import SessionMiddleware

app.add_middleware(AuthenticationMiddleware(
    user_model=SimpleUser,
    backend=JWTAuthBackend()
))

app.add_middleware(AuthenticationMiddleware(
    user_model=SimpleUser,
    backend=SessionAuthBackend() #require session middleware
))

app.add_middleware(AuthenticationMiddleware(
    user_model=SimpleUser,
    backend=APIKeyAuthBackend()
))
```

### Backend Explanations

- `JWTAuthBackend` accepts a token in the `Authorization` header and verifies it with a secret or public key
- `SessionAuthBackend` reads a session cookie and uses it to identify the user
- `APIKeyAuthBackend` expects an API key in the `Authorization` header


```python


class CustomAuthBackend(BaseAuthBackend):
    async def authenticate(self, request):
        # custom authentication logic here
        if request.headers.get("X-API-Key") == "your-super-secret-key":
            return CustomUser(request, "Super User")

class CustomUser(BaseUser):
    def __init__(self, request, name):
        self.request = request
        self.name = name

    @property
    def display_name(self):
        return self.name

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def auth_type(self):
        return "custom"

app.add_middleware(AuthenticationMiddleware(
    user_model=CustomUser,
    backend=CustomAuthBackend()
))
```

The above code snippet demonstrates how to add a custom authentication backend to Nexios. It defines a custom authentication backend by subclassing `BaseAuthBackend` and implementing the `authenticate` method. The `authenticate` method is responsible for verifying the user's credentials and returning a `BaseUser` subclass instance if authentication is successful. In the example, the custom authentication backend checks for the presence of a specific API key in the request headers. If the API key is present and matches a hard-coded value, a `CustomUser` instance is returned.

The `CustomUser` class is a subclass of `BaseUser` and implements the user properties required by Nexios. It stores a reference to the request and the user's name. The `display_name` property returns the user's name, the `is_authenticated` property returns `True` to indicate that the user is authenticated, and the `auth_type` property returns the string "custom" to indicate the type of authentication.

Finally, the custom authentication backend is added as middleware to the Nexios app using the `add_middleware` method.

This code is provided as a starting point for implementing custom authentication in Nexios.


Teach this as the default secured-endpoint shape.

## Sessions

Basic documented setup:

```python
from nexios.session import SessionConfig
from nexios.session.middleware import SessionMiddleware

app.config.secret_key = "your-secure-secret-key"

session_config = SessionConfig(
    session_cookie_name="nexios_session",
    cookie_secure=True,
    cookie_httponly=True,
    cookie_samesite="lax",
    session_expiration_time=86400
)

app.add_middleware(SessionMiddleware(config=session_config))
```

Session usage:

```python
@app.get("/counter")
async def counter(request, response):
    count = request.session.get("count", 0) + 1
    request.session["count"] = count
    return response.json({"count": count})
```

Teaching notes:

- `request.session` behaves a lot like a dictionary
- Session middleware depends on a configured secret key

## Cookies

### Read Cookies

```python
@app.get("/whoami")
async def whoami(request, response):
    token = request.cookies.get("auth_token")
    return response.json({"token": token})
```

### Set Cookies

```python
@app.get("/set-cookie")
async def set_cookie(request, response):
    return (
        response
        .json({"status": "ok"})
        .set_cookie(
            key="auth_token",
            value="abc123",
            max_age=3600,
            httponly=True,
            secure=True,
            samesite="strict"
        )
    )
```

### Delete Cookies

```python
@app.get("/logout")
async def logout(request, response):
    return response.json({"status": "logged out"}).delete_cookie("auth_token")
```

Teach these best practices:

- Use `secure=True` in production
- Use `httponly=True` for sensitive cookies
- Prefer strict or appropriate `samesite` settings for auth cookies

## Headers

### Read Request Headers

```python
@app.get("/headers")
async def show_headers(request, response):
    return response.json({
        "user_agent": request.headers.get("user-agent"),
        "accept_language": request.headers.get("accept-language")
    })
```

### Set Response Headers

```python
@app.get("/custom")
async def custom(request, response):
    return response.text("ok",headers = {"X-Content-Type-Options": "nosniff",
                                        "X-Frame-Options": "DENY",
                                        "X-XSS-Protection": "1; mode=block"})
    # another way to set headers after setting response type
    # response = response.text("ok")
    # response.set_header("X-Frame-Options", "DENY")
    # response.set_header("X-XSS-Protection", "1; mode=block")
    # return response
    
```

In middleware, set headers after `await next()` or the equivalent response-producing step.


### Example: Setting Headers After Middleware


### Example: Setting Headers After Middleware

```py
async def set_headers_after_middleware(request, response, next):
    strem = await next()
    response.set_header("X-Frame-Options", "DENY")
    response.set_header("X-XSS-Protection", "1; mode=block")
    return stream 
app.add_middleware(set_headers_after_middleware)
```

## CORS And Request Hardening

Nexios docs also cover cross-origin and browser-safety concerns.

```python
from nexios.middleware import CORSMiddleware

app.add_middleware(CORSMiddleware())
```

Use this concept bucket for:

- Cross-origin policies
- Credentialed browser requests
- Request and response header shaping
- CSRF discussions when the user is working with browser sessions or forms

## Security Middleware

The docs present a configurable security middleware:

```python
from nexios.middleware.security import SecurityMiddleware

app.add_middleware(SecurityMiddleware(
    csp_enabled=True,
    hsts_enabled=True,
    ssl_redirect=True,
    frame_options="DENY"
))
```

This is the right concept cluster for:

- Content Security Policy
- HSTS
- SSL redirects
- Frame protection
- Cross-origin response policies
- Cache and header hardening

Good teaching summary:

"Nexios treats security as middleware-driven response hardening plus authentication and session management. Use dedicated middleware for broad protections, and route-level logic for application-specific access control."
