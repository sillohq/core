---
title: Handling Cookies in Nexios
description: Learn how to work with cookies in Nexios
head:
  - - meta
    - property: og:title
      content: Handling Cookies in Nexios
  - - meta
    - property: og:description
      content: Learn how to work with cookies in Nexios
---
# Handling Cookies in Nexios

Cookies are an essential part of web development, allowing you to store small pieces of data on the client's browser. Nexios provides comprehensive support for working with cookies in both requests and responses.

##  Receiving Cookies

When a client makes a request to your Nexios application, any cookies sent by the browser are automatically parsed and made available through the `request.cookies` property.

```python
from nexios import NexiosApp

app = NexiosApp()

@app.get("/")
async def read_cookie(request, response):
    auth_token = request.cookies.get("auth_token")
    return {"token": auth_token}
```

::: tip 💡 Tip
The `request.cookies` property returns a dictionary where keys are cookie names and values are the corresponding cookie values.
:::

## Sending Cookies

You can set cookies in responses using the `response.set_cookie()` method:

```python
@app.get("/set-cookie")
async def set_cookie(request, response):
    return response.set_cookie(
        key="user_id",
        value="12345",
        max_age=3600,  # Expires in 1 hour (in seconds)
        httponly=True,
        secure=True
    ).json({"status": "Cookie set"})
```

### Cookie Options

Nexios supports all standard cookie attributes:

| Parameter             | Description                                                                 | Default |
|-----------------------|-----------------------------------------------------------------------------|---------|
| `key`                 | The name of the cookie                                                      | -       |
| `value`               | The value of the cookie                                                     | ""      |
| `max_age`             | Number of seconds until the cookie expires                                  | None    |
| `expires`             | Expiration date (datetime or timestamp)                                     | None    |
| `path`                | The path the cookie is valid for                                            | "/"     |
| `domain`              | The domain the cookie is valid for                                          | None    |
| `secure`              | Only send cookie over HTTPS                                                 | False   |
| `httponly`            | Prevent JavaScript access                                                   | False   |
| `samesite`            | Control cross-site requests ("lax", "strict", or "none")                    | "lax"   |

::: warning ⚠️ Security Best Practices
- Always set `secure=True` in production to ensure cookies are only sent over HTTPS
- Use `httponly=True` for sensitive cookies to prevent XSS attacks
- Consider `samesite='strict'` for authentication cookies
:::

## Deleting Cookies

To delete a cookie, set an expired cookie with the same name:

```python
@app.get("/logout")
async def logout(request, response):
    return response.delete_cookie("auth_token").json({"status": "Logged out"})
```

## Permanent Cookies

For long-lived cookies (like "remember me" functionality), use `set_permanent_cookie()`:

```python
@app.get("/remember-me")
async def remember_me(request, response):
    return response.set_permanent_cookie(
        key="remember_me",
        value="true"
    ).text("Cookie set for 10 years")
```

## Multiple Cookies

You can set multiple cookies at once:

```python
@app.get("/multi-cookie")
async def multi_cookie(request, response):
    cookies = [
        {"key": "user", "value": "john", "max_age": 3600},
        {"key": "theme", "value": "dark", "max_age": 86400}
    ]
    return response.set_cookies(cookies).json({"status": "Cookies set"})
```

## Cookie Security Considerations

::: danger 🚨 Critical Warning
Improper cookie handling can lead to serious security vulnerabilities:
- Never store sensitive data directly in cookies
- Always validate and sanitize cookie values from requests
- Use proper SameSite policies to prevent CSRF attacks
- Regenerate session tokens after login
:::

## Practical Example

Here's a complete authentication flow using cookies:

```python
from datetime import datetime, timedelta
from nexios import NexiosApp

app = NexiosApp()

@app.post("/login")
async def login(request, response):
    data = await request.json
    # Validate credentials (pseudo-code)
    if validate_credentials(data["username"], data["password"]):
        return response.set_cookie(
            key="auth_token",
            value=generate_token(data["username"]),
            max_age=3600 * 24,  # 1 day
            httponly=True,
            secure=True,
            samesite="strict"
        ).json({"status": "Login successful"})
    else:
        return response.status(401).json({"error": "Invalid credentials"})

@app.get("/protected")
async def protected_route(request, response):
    if not request.cookies.get("auth_token"):
        return response.status(401).json({"error": "Unauthorized"})
    
    # Verify token (pseudo-code)
    user = verify_token(request.cookies["auth_token"])
    if not user:
        return response.delete_cookie("auth_token").status(401).json({"error": "Invalid token"})
    
    return response.json({"message": f"Welcome {user}"})

@app.get("/logout")
async def logout(request, response):
    return response.delete_cookie("auth_token").json({"status": "Logged out"})
```

## Best Practices

1. **Size Limits**: Keep cookies small (typically under 4KB)
2. **Essential Data Only**: Store only what's necessary
3. **Expiration**: Set reasonable expiration times
4. **Validation**: Always validate cookie data before use
5. **HTTPS**: Always use secure cookies in production
6. **Prefixes**: Consider using `__Host-` or `__Secure-` prefixes for added security

Nexios makes cookie handling simple while providing all the tools you need to implement secure, production-ready cookie-based functionality in your web applications.