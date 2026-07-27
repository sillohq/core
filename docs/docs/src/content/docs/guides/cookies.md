---
title: Handling Cookies in sillo
description: Learn how to work with cookies in sillo
head:
- tag: meta
  attrs:
    property: og:title
    content: Handling Cookies in sillo
- tag: meta
  attrs:
    property: og:description
    content: Learn how to work with cookies in sillo
---
#  Handling Cookies in sillo

Cookies are an essential part of web development, allowing you to store small pieces of data on the client's browser. sillo provides comprehensive support for working with cookies in both requests and responses.

##  Receiving Cookies

When a client makes a request to your sillo application, any cookies sent by the browser are automatically parsed and made available through the `request.cookies` property.

```python
from sillo import silloApp

app = silloApp()

@app.get("/")
async def read_cookie(request, response):
    auth_token = request.cookies.get("auth_token")
    return {"token": auth_token}
```

::: tip  Tip
The `request.cookies` property returns a dictionary where keys are cookie names and values are the corresponding cookie values.
:::

##  Sending Cookies

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

###  Cookie Options

sillo supports all standard cookie attributes:

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

:::caution ⚠️ Security Best Practices
- Always set `secure=True` in production to ensure cookies are only sent over HTTPS
- Use `httponly=True` for sensitive cookies to prevent XSS attacks
- Consider `samesite='strict'` for authentication cookies
:::

##  🗑️ Deleting Cookies

To delete a cookie, set an expired cookie with the same name:

```python
@app.get("/logout")
async def logout(request, response):
    return response.delete_cookie("auth_token").json({"status": "Logged out"})
```

##  Permanent Cookies

For long-lived cookies (like "remember me" functionality), use `set_permanent_cookie()`:

```python
@app.get("/remember-me")
async def remember_me(request, response):
    return response.set_permanent_cookie(
        key="remember_me",
        value="true"
    ).text("Cookie set for 10 years")
```

##  Multiple Cookies

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

##  Cookie Security Considerations

::: danger  Critical Warning
Improper cookie handling can lead to serious security vulnerabilities:
- Never store sensitive data directly in cookies
- Always validate and sanitize cookie values from requests
- Use proper SameSite policies to prevent CSRF attacks
- Regenerate session tokens after login
:::

##  Practical Example

Here's a complete authentication flow using cookies:

```python
from datetime import datetime, timedelta
from sillo import silloApp

app = silloApp()

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

##  Best Practices

1. **Size Limits**: Keep cookies small (typically under 4KB)
2. **Essential Data Only**: Store only what's necessary
3. **Expiration**: Set reasonable expiration times
4. **Validation**: Always validate cookie data before use
5. **HTTPS**: Always use secure cookies in production
6. **Prefixes**: Consider using `__Host-` or `__Secure-` prefixes for added security

sillo makes cookie handling simple while providing all the tools you need to implement secure, production-ready cookie-based functionality in your web applications.

##  Attributes decide everything

A cookie's security is entirely in its attributes, and the defaults are
the permissive ones.

`HttpOnly` keeps JavaScript from reading it. Set it on anything that is a
credential; the only cookies that need to be readable are ones your own
frontend genuinely reads, and those should not be credentials.

`Secure` keeps it off plaintext connections. There is no reason to omit
it outside local development, and even there a browser will accept it on
`localhost`.

`SameSite` controls whether the cookie is sent on cross-site requests.
`Lax` is the sensible default and blocks the cross-site POST case;
`Strict` also blocks inbound navigation, which breaks links from email
and other sites; `None` sends it everywhere and requires `Secure`.

`Max-Age` or `Expires` decides persistence. Without either, the cookie is
a session cookie and dies with the browser process — which, given modern
browsers restore sessions on restart, is less reliable than it sounds.

`Domain` and `Path` scope it. Setting `Domain` to a parent domain shares
the cookie with every subdomain, including any an attacker controls. Omit
it unless you need the sharing.

##  Size and count limits

Browsers allow roughly 4 KB per cookie and around 50 cookies per domain,
and total header size caps the practical number lower.

Every cookie for a domain is sent on **every request to that domain** —
images, stylesheets, API calls, all of them. Ten kilobytes of cookies is
ten kilobytes of upload per request, which on a mobile connection is
measurable latency on every asset.

Two consequences worth designing around. Serve static assets from a
cookieless domain or a CDN, so asset requests carry nothing. And keep an
identifier in the cookie rather than data, with the data server-side —
which is the same argument as for session storage, arriving from a
different direction.

##  Reading and writing

```python title="setting a cookie properly"
resp = response.json({"ok": True})
resp.set_cookie(
    "session",
    value=session_id,
    httponly=True,
    secure=True,
    samesite="lax",
    max_age=60 * 60 * 24,
    path="/",
)
return resp
```

Deleting requires matching attributes. A cookie set with `path="/app"`
is not removed by a delete on `path="/"` — the browser treats them as
different cookies, and the stale one keeps being sent.

Cookie values are client-controlled like any other input. A value that
came back from a browser may have been edited, so a cookie carrying
anything trusted must be signed, and a cookie carrying anything private
must be encrypted or replaced by a server-side lookup.

##  What not to do

**Do not put anything sensitive in a cookie.** They are stored in
plaintext on disk and readable by anything with filesystem access.

**Do not omit `HttpOnly` on credentials.** One XSS becomes total account
compromise.

**Do not set `Domain` to a parent domain** unless subdomain sharing is
required; it widens the blast radius to every subdomain.

**Do not exceed 4 KB.** The browser silently drops the cookie, and the
symptom is a feature that stops working for some users.

**Do not trust a cookie value.** Sign it, or use it only as a lookup key.

**Do not forget the attributes when deleting.** Path and domain must
match or the cookie survives.

##  Related

- [Sessions](/guides/sessions/) — what most cookies carry
- [Session Auth](/guides/session-auth/) — the authentication flow
- [CSRF](/guides/csrf/) — why cookies need `SameSite` and a token
- [Headers](/guides/headers/) — `Set-Cookie` and header size limits
- [Security](/guides/security/) — the wider checklist


##  Signed cookies

When a cookie must carry data rather than an identifier, sign it so
tampering is detectable:

```python title="signing and verifying"
from sillo.helpers.crypto import sign_value, unsign_value

resp.set_cookie("prefs", sign_value("theme=dark", secret), httponly=True)

raw = request.cookies.get("prefs")
value = unsign_value(raw, secret) if raw else None
if value is None:
    ...   # tampered or absent — treat as no preference
```

Two things to be clear about. Signing proves the value came from you; it
does not hide it, so the contents remain readable by the user and by
anything with access to their disk. And a signed cookie has no built-in
expiry — see the note on `max_age` in
[Crypto helpers](/guides/helpers/crypto/) — so if the value should stop
being valid, put a timestamp inside it and check that yourself.

##  Third-party cookie deprecation

Browsers have been restricting cookies sent to a domain other than the
one in the address bar, and the direction is toward blocking them
entirely. Anything relying on a cookie set by an embedded iframe, a
tracking pixel, or a cross-site API on a different registrable domain
should be treated as already broken in some browsers and eventually
broken in all of them.

First-party cookies — your domain, your page — are unaffected. If your
architecture requires cross-site cookies, moving the API to a subdomain
of the site that uses it converts the problem into a same-site one.


##  Debugging cookie problems

Cookies fail silently, which makes them frustrating. Four checks resolve
most cases.

**Is it being set at all?** Look for `Set-Cookie` in the response
headers. If it is absent, the code path did not run.

**Is the browser rejecting it?** A cookie with `Secure` on a plain HTTP
page is dropped without a visible error. So is one over 4 KB, and one
with `SameSite=None` but no `Secure`.

**Is it being sent back?** Check the request headers on the next call. A
mismatch in `Domain` or `Path` means it was stored and is not applicable
to the URL you are requesting.

**Is something else overwriting it?** Two `Set-Cookie` headers with the
same name in one response is a race you will lose intermittently.

Browser developer tools list stored cookies with every attribute, which
answers most of these faster than reading code.

##  Testing

Assert on the attributes, not just the value. A test checking that a
session cookie exists passes when `HttpOnly` was accidentally dropped;
a test checking `httponly=True, secure=True, samesite="lax"` catches it.

For deletion, assert that a subsequent request with the old cookie is
rejected — not merely that a `Set-Cookie` clearing it was sent, which is
true even when the server-side session survives.


##  Summary

The attributes are the security model, and the defaults are the
permissive ones. Set `HttpOnly` and `Secure` on anything that is a
credential, `SameSite=Lax` on everything, and scope `Domain` and `Path`
as narrowly as the application allows. Keep an identifier in the cookie
and the data on the server — it avoids the size limit, the per-request
upload cost, and the disclosure that comes from a value the user can
read.


##  Cookies and caching

A response carrying `Set-Cookie` must never be cached publicly. A shared
cache that stores it will hand the same cookie — and therefore the same
session — to the next person who requests that URL.

Set `Cache-Control: private, no-store` on anything that sets a cookie,
and be aware that some CDNs strip `Set-Cookie` from cacheable responses
rather than refusing to cache them, which produces a login that appears
to succeed and does nothing.


##  Cookie prefixes

Two prefixes are enforced by browsers and cost nothing to adopt.

`__Secure-` requires the cookie to be set with `Secure` from a secure
origin. `__Host-` additionally requires `Path=/` and forbids `Domain`,
which pins the cookie to exactly the host that set it and prevents a
subdomain from overwriting it.

`__Host-session` is a stronger session cookie than `session` for the
same effort, and the enforcement happens in the browser rather than
depending on your code being right.
