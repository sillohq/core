---
title: Cors in sillo
description: Learn how to use cors utilities in sillo
head:
- tag: meta
  attrs:
    property: og:title
    content: Cors in sillo
- tag: meta
  attrs:
    property: og:description
    content: Learn how to use cors utilities in sillo
---
#  CORS in sillo

Got it! I'll go through each CORS configuration setting in **sillo**, explaining what it does and how it impacts requests.

***

###  Basic CORS Configuration in sillo

Before diving into individual settings, here's a simple CORS setup using `CorsConfig`:
```python title="Recommended Approach"
from sillo import silloApp
from sillo.security.cors import CorsConfig
from sillo.security.cors import CORSMiddleware

cors_config = CorsConfig(
    allow_origins=["https://example.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "X-Requested-With"],
    allow_credentials=True,
    max_age=600,
    debug=True
)
app = silloApp()
app.use(CORSMiddleware(config=cors_config))
```

we can break it down further:

***

###  allow_origins

* **Purpose:** Specifies which domains can access the API.
* **Example:**

```python
# Using CorsConfig with recommended approach
cors_config = CorsConfig(
    allow_origins=["https://example.com", "https://another-site.com"]
)
app.use(CORSMiddleware(config=cors_config))
```

* **Special cases:**
  * Use `["*"]` to allow requests from **any** origin (not safe if credentials are enabled).
  * If an origin is not listed here, the request will be blocked.

***

###  blacklist_origins

* **Purpose:** Specifies which origins should be**blocked**, even if they match `allow_origins`.
* **Example:**

```python
cors_config = CorsConfig(
        blacklist_origins=["https://bad-actor.com"]
    )
app.use(CORSMiddleware(config=cors_config))
```

* **Use case:** If you allow all origins (`["*"]`), but want to exclude specific ones.

***

###  allow_methods

* **Purpose:** Defines which HTTP methods (GET, POST, etc.) are allowed in cross-origin requests.
* **Example:**

```python
cors_config = CorsConfig(
    allow_methods=["GET", "POST", "PUT"]
)
app.use(CORSMiddleware(config=cors_config))
```

* **Default:** All methods (`["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]`) are allowed.

***

###  allow_headers

* **Purpose:** Specifies which request headers are permitted in cross-origin requests.
* **Example:**

```python
cors_config = CorsConfig(
        allow_headers=["Authorization", "X-Custom-Header"]
    )
app.use(CORSMiddleware(config=cors_config))
```

* **Default:** Basic headers like `Accept`, `Content-Type`, etc., are always allowed.

***

###  blacklist_headers

* **Purpose:** Defines headers that should**not** be allowed in requests.
* **Example:**

```python
cors_config = CorsConfig(
    blacklist_headers=["X-Disallowed-Header"]
)
app.use(CORSMiddleware(config=cors_config))
```

* **Use case:** If you allow most headers but want to restrict specific ones.

***

###  allow_credentials

* **Purpose:** Determines whether credentials (cookies, authorization headers) are allowed in requests.
* **Example:**

```python
cors_config = CorsConfig(
        allow_credentials=True
    )
app.use(CORSMiddleware(config=cors_config))
```

* **Important:**
  * If `True`, the browser allows requests with credentials (e.g., session cookies).
  * If `True`, `allow_origins` **cannot** be `"*"` (security restriction).
  * If `False`, credentials are blocked.

***

###  allow_origin_regex

* **Purpose:** Uses a regex pattern to match allowed origins dynamically.
* **Example:**

```python
cors_config = CorsConfig(
        allow_origin_regex=r"https://.*\.trusted-site\.com"
    )
app.use(CORSMiddleware(config=cors_config))
```

* **Use case:** When you want to allow multiple subdomains without listing them individually.

***

###  👁️ expose_headers

* **Purpose:** Specifies which response headers the client is allowed to access.
* **Example:**

```python
cors_config = CorsConfig(
        expose_headers=["X-Response-Time"]
    )
app.use(CORSMiddleware(config=cors_config))
```

* **Default:** Only basic headers are exposed unless configured.

***

###  ⏱️ max_age

* **Purpose:** Defines how long the preflight (OPTIONS) response can be cached.
* **Example:**

```python
cors_config = CorsConfig(
        max_age=600  # Cache for 10 minutes
    )
app.use(CORSMiddleware(config=cors_config))
```

* **Impact:** Reduces unnecessary preflight requests for frequent API calls.

***

###  strict_origin_checking

* **Purpose:** If enabled, requests**must** include an `Origin` header.
* **Example:**

```python
cors_config = CorsConfig(
        strict_origin_checking=True
    )
app.use(CORSMiddleware(config=cors_config))
```

* **Use case:** When you want to strictly enforce CORS checks, especially for security.

***

###  debug

* **Purpose:** Enables logging to troubleshoot CORS issues.
* **Example:**

```python
cors_config = CorsConfig(
        debug=True
    )
app.use(CORSMiddleware(config=cors_config))
```

* **Impact:**
  * Prints logs when a request is blocked due to CORS.
  * Useful for debugging in development.

***

###  custom_error_status &  custom_error_messages

* **Purpose:** Allows custom error handling for CORS failures.
* **Example:**

```python
cors_config = CorsConfig(
        custom_error_status=403,
        custom_error_messages={
            "disallowed_origin": "This origin is not allowed.",
            "missing_origin": "The request is missing an origin."
        }
    )
app.use(CORSMiddleware(config=cors_config))
```

* **Use case:** When you want meaningful error messages instead of generic CORS errors.

##  How CORS is enforced

`CORSMiddleware` runs in `process_request` for every request:

1. If there is no `Origin` header, the request is same-origin — the middleware does nothing and the request proceeds.
2. The `Origin` is checked against `allow_origins`, `allow_origin_regex`, and `blacklist_origins`. Unmatched origins are silently dropped (simple requests complete normally, just without `Access-Control-*` headers), so the browser blocks the cross-origin read.
3. **Preflight (`OPTIONS`)** — browsers send this before a non-simple request (custom headers, `PUT`/`DELETE`, `application/json` bodies). The middleware answers the preflight directly:
   - Reflects `Access-Control-Allow-Origin`
   - Echoes `Access-Control-Allow-Methods` (the method from `Access-Control-Request-Method`)
   - Echoes `Access-Control-Allow-Headers` (from `Access-Control-Request-Headers`)
   - Sets `Access-Control-Max-Age` from `max_age`
   - A disallowed origin, method, or header fails the preflight with a `400`/custom status and the actual handler never runs.
4. **Actual request** — after a passing preflight, the real request carries the same `Access-Control-Allow-Origin` (and, when `allow_credentials=True`, `Access-Control-Allow-Credentials: true`) so the browser permits the response.

<aside type="caution" title="Wildcard + credentials don't mix">
When `allow_credentials=True`, `allow_origins` cannot be `["*"]` — the spec forbids `Access-Control-Allow-Origin: *` together with `Access-Control-Allow-Credentials: true`. List explicit origins, or use `allow_origin_regex` to match a trusted set dynamically.
</aside>

##  Testing

Drive CORS through `TestClient`. A simple request reflects the allow-list; a preflight (`OPTIONS`) echoes the method/header policy.

```python
from sillo import silloApp
from sillo.security.cors import CorsConfig, CORSMiddleware
from sillo.testclient import TestClient


def test_simple_request_allowed_origin():
    app = silloApp()
    app.use(
        CORSMiddleware(
            CorsConfig(
                allow_origins=["http://example.com"],
                allow_methods=["GET", "POST"],
                allow_credentials=True,
            )
        )
    )

    @app.get("/data")
    async def data(request, response):
        return {"ok": True}

    resp = TestClient(app).get("/data", headers={"Origin": "http://example.com"})
    assert resp.headers["Access-Control-Allow-Origin"] == "http://example.com"
    assert resp.headers["Access-Control-Allow-Credentials"] == "true"


def test_preflight_reflects_methods():
    app = silloApp()
    app.use(
        CORSMiddleware(
            CorsConfig(
                allow_origins=["http://example.com"],
                allow_methods=["GET", "POST"],
                max_age=3600,
            )
        )
    )

    @app.post("/data")
    async def data(request, response):
        return {"ok": True}

    resp = TestClient(app).options(
        "/data",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 201
    assert "POST" in resp.headers["Access-Control-Allow-Methods"]
    assert resp.headers["Access-Control-Max-Age"] == "3600"


def test_disallowed_origin_gets_no_header():
    app = silloApp()
    app.use(CORSMiddleware(CorsConfig(allow_origins=["http://example.com"])))

    @app.get("/data")
    async def data(request, response):
        return {"ok": True}

    resp = TestClient(app).get("/data", headers={"Origin": "http://evil.com"})
    assert "Access-Control-Allow-Origin" not in resp.headers
```

##  Production considerations

- **List explicit origins** — never ship `allow_origins=["*"]` with cookies or auth. Use `allow_origin_regex` for subdomain sets.
- **Keep `max_age` high** in production (e.g. `600`+) to cut preflight chatter, but lower it while the policy is still changing.
- **Preflight is not auth** — CORS governs which origins may *read* responses in a browser. It does not authenticate the caller or stop non-browser clients. Pair it with CSRF for cookie-auth flows and with real auth for data.
- **`custom_error_status`** — returning a non-default status on preflight failure is cosmetic (the browser blocks the read regardless). Don't rely on it for security.

##  Related topics

- [Security Headers (Shield)](/guides/security/) — defensive response headers
- [CSRF](/guides/csrf/) — protect cookie-auth state-changing requests from cross-site forgery
- [Authentication](/guides/authentication/) — verifying who the caller is


##  What CORS actually protects

CORS is a browser mechanism, and understanding what it does and does not
do prevents both over- and under-configuration.

It stops **a page on one origin from reading a response from another
origin**. It does not stop the request being sent, and it does not
protect your server from anything. A non-browser client — curl, a script,
a mobile app — ignores CORS entirely, because the enforcement lives in
the browser, not in your response.

That single fact resolves the two most common misunderstandings. CORS is
not a security control for your API; authentication and authorization
are. And a "CORS error" in a console is usually the browser refusing to
show the response to a request your server already processed — including
one that already had side effects.

##  Simple requests and preflights

A request qualifies as *simple* — sent directly, no preflight — when the
method is `GET`, `HEAD`, or `POST`, the content type is one of
`text/plain`, `application/x-www-form-urlencoded`, or
`multipart/form-data`, and no custom headers are set.

Anything else triggers an `OPTIONS` preflight first. Sending
`Content-Type: application/json`, or an `Authorization` header, is enough
to require one — which is why almost every real API call is preflighted.

This is why a form POST is a [CSRF](/guides/csrf/) concern while a JSON
POST largely is not: the form request is simple, so it is sent without
permission being asked.

##  Configuring it correctly

Three rules cover most mistakes.

**Never use `*` with credentials.** The specification forbids the
combination and browsers enforce it, but the pattern of reflecting the
request's `Origin` header back to work around it is the dangerous
version: it means *any* origin is allowed. If you reflect an origin,
check it against an allowlist first.

**List origins explicitly.** Including the scheme and the port, since
`http://example.com` and `https://example.com` are different origins and
so is `:3000`.

**Set `Access-Control-Max-Age`.** Without it, a preflight happens before
every request, doubling the round trips on your entire API. A few hours
is a reasonable value.

Remember that error responses need CORS headers too. A 401 without them
appears to the browser as a CORS failure, and the developer debugging it
sees the wrong problem entirely — which is why CORS middleware belongs
near the outside of the stack, where it wraps the error handler rather
than sitting inside it.


##  Debugging a CORS failure

The browser console message names the missing header, and reading it
literally saves most of the time.

"No `Access-Control-Allow-Origin` header" usually means the request never
reached your CORS middleware — an exception in an outer layer, or a route
that 404'd before it. Check whether the request appears in your access
log at all.

"Origin not allowed" means it reached the middleware and your allowlist
does not include that origin. Compare scheme, host, and port exactly.

"Method not allowed" or "header not allowed" refers to the *preflight*
response, not your route. The `OPTIONS` handler has to advertise the
method and headers the real request will use.

"Credentials flag is true but `Access-Control-Allow-Origin` is `*`" is
the specification refusing the unsafe combination. Name the origin.

The one that misleads people: a CORS error on a request that *worked*.
The server processed it and the browser refused to hand you the response
— so any side effect already happened. That distinction matters when the
request was a `POST`.

##  Related

- [Middleware](/guides/middleware/) — where CORS belongs in the stack
- [CSRF](/guides/csrf/) — the other cross-origin concern, and a different one
- [Headers](/guides/headers/) — the response headers involved
- [Security](/guides/security/) — the wider checklist


##  Summary

CORS is a browser policy about reading responses, not a server-side
security control. Preflights happen for anything that is not a simple
request, which is nearly every real API call. Never combine wildcard
origins with credentials, never reflect an unvalidated origin, set a
`Max-Age` so preflights are not paid on every request, and make sure
error responses carry the headers too — otherwise the browser reports a
CORS failure where the real answer was a 401.


##  Configuring it in sillo

CORS is middleware, and it belongs near the outside of the stack so that
error responses — including the 401 from an auth layer inside it — carry
the headers.

```python title="a configuration that is not too permissive"
app.use(
    CORSMiddleware(
        allow_origins=["https://app.example.com", "https://admin.example.com"],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=True,
        max_age=3600,
    )
)
```

Four things to note. Origins are listed exactly, with scheme and without
a trailing slash. Methods list what you actually accept rather than `*`,
so an unexpected `PUT` is refused at the preflight. Headers list what
clients genuinely send — `Authorization` and `Content-Type` cover most
APIs. And `allow_credentials=True` requires named origins, never a
wildcard.

For a public, unauthenticated API the calculus changes: `allow_origins=["*"]`
with `allow_credentials=False` is correct and simple, because there is no
session for a malicious origin to ride on.

Development origins belong in configuration, not in the code. A
`http://localhost:3000` entry that ships to production is an origin an
attacker can serve from.


##  CORS and WebSockets

The WebSocket handshake is not subject to CORS. A browser will open a
WebSocket to any origin, and the server sees an `Origin` header it is
expected to check itself.

That check is not optional for an authenticated socket: cookies are sent
on the handshake, so an attacker's page can open an authenticated
connection to your server unless you validate `Origin` and reject
unknown ones. It is the WebSocket equivalent of CSRF, and there is no
browser-side protection to fall back on.
