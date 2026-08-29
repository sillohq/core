---
title: Request Information in sillo
description: sillo provides a comprehensive `HttpContext` object that gives you access to all the information about the incoming HTTP request. This object is automatically passed to your route handlers and
  contains methods and properties to access request data.
head:
- tag: meta
  attrs:
    property: og:title
    content: Request Information in sillo
- tag: meta
  attrs:
    property: og:description
    content: sillo provides a comprehensive `HttpContext` object that gives you access to all the information about the incoming HTTP request. This object is automatically passed to your route handlers and
      contains methods and properties to access request data.
---
#  Request Information

```python
from sillo import HttpContext

@app.get("/example")
async def example_handler(ctx: HttpContext):
    # Basic ctx information
    method = ctx.method        # HTTP method (GET, POST, etc.)
    url = ctx.url              # Full URL object
    path = ctx.path            # Request path (/example)
    headers = ctx.headers      # Headers dictionary
    client_ip = ctx.client     # Client address (IP, port)
```

##  Query Parameters

Access URL query parameters (after the `?` in the URL):

```python
from sillo import HttpContext

@app.get("/search")
async def search_handler(ctx: HttpContext):
    # For URL: /search?q=sillo&page=2
    query = ctx.query_params.get("q")       # "sillo"
    page = ctx.query_params.get("page")     # "2"
    all_params = dict(ctx.query_params)    # {'q': 'sillo', 'page': '2'}
```

##  Path Parameters

Access named parameters from the route path:

```python
from sillo import HttpContext

@app.get("/users/{user_id}")
async def user_handler(ctx: HttpContext):
    # For URL: /users/123
    user_id = ctx.path_params["user_id"]  # "123"
    # Or directly as function parameter (shown above)
```

##  Request Body

###  JSON Data

```python
from sillo import HttpContext

@app.post("/data")
async def data_handler(ctx: HttpContext):
    json_data = await ctx.json  # Parses JSON body
```

###  Form Data

```python
from sillo import HttpContext

@app.post("/submit")
async def submit_handler(ctx: HttpContext):
    form_data = await ctx.form  # Parses both URL-encoded and multipart forms
    username = form_data.get("username")
```

###  File Uploads

```python
from sillo import HttpContext

@app.post("/upload")
async def upload_handler(ctx: HttpContext):
    files = await ctx.files      # Dictionary of uploaded files
    file = files.get("document") # Access specific file
    if file:
        filename = file.filename
        content = await file.read()
```

###  Raw Body

```python
from sillo import HttpContext

@app.post("/raw")
async def raw_handler(ctx: HttpContext):
    body_bytes = await ctx.body  # Raw bytes
    body_text = await ctx.text  # Decoded text
```

##  Cookies

```python
from sillo import HttpContext

@app.get("/profile")
async def profile_handler(ctx: HttpContext):
    session_id = ctx.cookies.get("session_id")
```

##  Client Information

```python
from sillo import HttpContext

@app.get("/client-info")
async def client_info_handler(ctx: HttpContext):
    user_agent = ctx.user_agent
    client_ip = ctx.client.host if ctx.client else None
    origin = ctx.origin
```

##  State and Middleware Data

```python
from sillo import HttpContext

@app.get("/auth")
async def auth_handler(ctx: HttpContext):
    # Access data added by middleware
    user = ctx.user
    session = ctx.session  # Requires session middleware
    custom_data = ctx.state.get("custom_data")
```

##  URL Construction

```python
from sillo import HttpContext

@app.get("/links")
async def links_handler(ctx: HttpContext):
    absolute_url = ctx.build_absolute_uri("/api/resource")
    # Returns full URL like "https://example.com/api/resource"
```


##  Request Type Detection

sillo provides convenient properties to quickly check the type and characteristics of incoming requests:

###  Content Type Flags

```python
from sillo import HttpContext

@app.post("/api/endpoint")
async def handle_request(ctx: HttpContext):
    # Check content type
    if ctx.is_json:
        data = await ctx.json
        # Handle JSON data
    elif ctx.is_form:
        data = await ctx.form
        # Handle form data
    elif ctx.is_multipart:
        files = await ctx.files
        # Handle file uploads
    elif ctx.is_urlencoded:
        data = await ctx.form
        # Handle URL-encoded form data
```

###  Request State Flags

```python
from sillo import HttpContext, text

@app.post("/process")
async def process_request(ctx: HttpContext):
    # Check if ctx has various components
    if ctx.has_cookie:
        session_id = ctx.cookies.get("session")

    if ctx.has_files:
        files = await ctx.files
        # Process uploaded files

    if ctx.has_body:
        # The request carries a body
        if ctx.content_length > 1000000:  # 1MB
            return text("File too large").status(413)

    if ctx.is_authenticated:
        user_id = ctx.user.id
        # Handle authenticated ctx

    if ctx.has_session:
        session_data = ctx.session
        # Access session data
```

###  Request Type Properties

| Property | Description | Example |
|----------|-------------|---------|
| `ctx.is_json` | True if Content-Type is `application/json` | JSON API requests |
| `ctx.is_form` | True if Content-Type is form data (URL-encoded or multipart) | HTML forms |
| `ctx.is_multipart` | True if Content-Type is `multipart/form-data` | File uploads |
| `ctx.is_urlencoded` | True if Content-Type is `application/x-www-form-urlencoded` | Simple forms |
| `ctx.has_cookie` | True if request contains cookies | Session management |
| `ctx.has_files` | True if request contains uploaded files | File upload detection |
| `ctx.has_body` | True if request has a body | POST/PUT/PATCH requests |
| `ctx.is_authenticated` | True if user is authenticated | Authenticated requests |
| `ctx.has_session` | True if session middleware is available | Session-enabled requests |

###  Existing Request Flags

sillo also provides additional request detection properties:

```python
from sillo import HttpContext, json, html

@app.get("/responsive")
async def responsive_handler(ctx: HttpContext):
    # Check ctx characteristics
    if ctx.is_ajax:
        return json({"message": "AJAX request"})

    if ctx.is_secure:
        return json({"protocol": "HTTPS"})

    if ctx.accepts_json:
        return json({"format": "JSON preferred"})

    if ctx.accepts_html:
        return html("<h1>HTML BaseResponse</h1>")
```

###  Header Utilities

```python
from sillo import HttpContext

@app.get("/headers")
async def header_handler(ctx: HttpContext):
    # Check for specific headers
    if ctx.has_header("authorization"):
        token = ctx.get_header("authorization")

    # Get header with default value
    api_version = ctx.get_header("x-api-version", "v1")

    # Check if header exists
    if ctx.has_header("x-custom-header"):
        custom_value = ctx.get_header("x-custom-header")
```

| Method/Property | Description | Example |
|----------------|-------------|---------|
| `ctx.has_header(name)` | Check if header exists (case-insensitive) | `ctx.has_header("content-type")` |
| `ctx.get_header(name, default)` | Get header value with default | `ctx.get_header("x-api-key", "none")` |
| `ctx.is_ajax` | True if X-Requested-With is XMLHttpRequest | AJAX requests |
| `ctx.is_secure` | True if request uses HTTPS | Secure connections |
| `ctx.accepts_json` | True if client accepts JSON | API responses |
| `ctx.accepts_html` | True if client accepts HTML | Web page responses |

##  Advanced Features

###  Streaming Requests

For handling large uploads:

```python
from sillo import HttpContext

@app.post("/stream")
async def stream_handler(ctx: HttpContext):
    async for chunk in ctx.stream:
        # Process each chunk of the ctx body
        process_chunk(chunk)
```

###  Server Push

```python
from sillo import HttpContext

@app.get("/push")
async def push_handler(ctx: HttpContext):
    await ctx.send_push_promise("/static/style.css")
```

The sillo `HttpContext` object provides a rich interface for working with incoming HTTP requests, with support for all common web standards and convenient access to request data. 

##  What the request tells you, and how much to trust it

Everything on a request comes from the client except the connection
address, and even that is unreliable behind a proxy. A short trust
ranking, most trustworthy first.

**The transport peer address**: who actually connected. Correct, and behind a
load balancer it is the balancer, not the user.

**Path and method**. Set by the client but validated by routing, so by the time
your handler runs they match a route you declared.

**Headers**: entirely client-controlled. `User-Agent`, `Referer`, `Origin`, and
every `X-` header are whatever the caller typed. Useful for analytics, never
for authorization.

**Forwarded headers**: `X-Forwarded-For`, `X-Real-IP`, `X-Forwarded-Proto`.
Trustworthy only if a proxy you control sets them and strips any the client
sent. Otherwise a client can claim any address. See [Network
helpers](/v1.0/guides/helpers/network/) for the trusted-proxy handling this needs.

**The body**, client-controlled, and the reason
[validation](/v1.0/guides/validation/) exists.

##  Identifying a client

The three things people reach for and what each is actually worth.

**IP address** identifies a network path, not a person. Mobile networks
share addresses across thousands of users; corporate NAT does the same;
a user moving between wifi and cellular changes address mid-session.
Adequate for coarse rate limiting, useless for identity.

**`User-Agent`** is a string the client chooses. Fine for
"which browsers do our users have"; worthless as a control, because
anything can send anything.

**A session or token** is the only real answer. If a decision depends on
who the caller is, it depends on authentication.

##  Correlating requests

A request id threaded through logs is the difference between debugging a
production issue in minutes and in hours. Accept one from the caller if
present, generate one if not, put it in `ctx.state`, log it
everywhere, and return it in the response.

```python title="request correlation"
import uuid


from sillo import HttpContext

async def request_id_middleware(ctx: HttpContext, call_next):
    rid = ctx.headers.get("x-request-id") or uuid.uuid4().hex
    ctx.state.request_id = rid
    result = await call_next()
    result.headers["X-Request-ID"] = rid
    return result
```

Returning it matters as much as logging it: a user reporting a failure
can quote the id, and you can find the exact request.

Accepting a client-supplied id is convenient for tracing across services and
means the value is attacker-controlled, bound its length and strip anything
that is not alphanumeric before it reaches a log line.


##  Proxies change everything

Behind a load balancer, an ingress controller, or a CDN, several
properties of the request are no longer what they appear.

The peer address is the proxy's. The scheme may be `http` even though the
client used `https`, because TLS terminated upstream. The `Host` header
may be the internal service name rather than the public domain. Each has
a `X-Forwarded-*` header carrying the original value, and each of those
headers is forgeable unless the proxy overwrites it.

Two rules make this safe. Configure an explicit list of trusted proxy
addresses, and only read forwarded headers when the immediate peer is one of
them. And ensure the outermost proxy **replaces** rather than appends to
headers a client may have set. Otherwise a client can prepend a fake entry to
`X-Forwarded-For`.

Getting this wrong has concrete consequences: rate limits keyed on a
spoofable IP are trivially bypassed, and audit logs record whatever the
attacker chose.

##  Reading the body

`ctx.body`, `ctx.json`, `ctx.form`, and `ctx.files` each
consume the request stream. Reading one and then another may give you
nothing, because the bytes are gone.

Where middleware needs the body (logging, signature verification) read it once,
cache it on `ctx.state`, and have downstream code use the cached copy. And
bound it: a body read into memory is memory a client chose the size of, which
is why the size limit belongs at the proxy as well as in your code.


##  Practical checks

Three things worth asserting in a test, because they break silently
behind infrastructure changes.

That the client IP your code resolves matches the real client when the
expected forwarded headers are present, and does **not** follow a
client-supplied header when they are absent.

That the scheme resolves to `https` behind a TLS-terminating proxy, since
redirect URLs and secure-cookie decisions depend on it.

That reading the body twice in your middleware chain does not leave the
handler with an empty payload.


##  Related

- [Headers](/v1.0/guides/headers/): reading and setting them safely
- [Network helpers](/v1.0/guides/helpers/network/): client IP resolution and trusted
  proxies
- [Middleware](/v1.0/guides/middleware/): where request correlation belongs
- [Request Lifecycle](/v1.0/guides/request-lifecycle/): when each of these values
  becomes available
- [Security](/v1.0/guides/security/): what not to trust from a request


##  Content negotiation inputs

`Accept`, `Accept-Language`, and `Accept-Encoding` are the headers a client
uses to state preferences, each a weighted list rather than a single value.
Parsing them naively (taking the first entry, or substring-matching) produces
wrong answers for any client that sends real quality values.

Anything whose response varies by one of these must set `Vary` naming it,
or a shared cache will serve one representation to everyone. See
[Content Negotiation](/v1.0/guides/content-negotiation/).


##  Debugging what actually arrived

When behaviour depends on a header you cannot see, dump the raw picture
once rather than guessing:

```python title="a temporary diagnostic endpoint"
from sillo import HttpContext, json

@app.get("/_debug/echo")
async def echo(ctx: HttpContext):
    return json({
        "method": ctx.method,
        "path": ctx.url.path,
        "query": dict(ctx.query_params),
        "headers": dict(ctx.headers),
        "client": ctx.client,
    })
```

Remove it before shipping, or protect it. It reflects headers including
`Authorization` and `Cookie`, which is a credential-disclosure endpoint if it
survives into production.


##  Related reading in the standard specs

The behaviours on this page are defined outside sillo, and the specs are
short enough to be worth knowing about: forwarded headers are described
by RFC 7239, the `Forwarded` header being the standardised replacement
for the `X-Forwarded-*` family; content negotiation and `Vary` are in
RFC 9110. Where a proxy's behaviour surprises you, the answer is usually
there rather than in framework code.


##  Summary

Trust the transport peer, trust what routing validated, and treat
everything else as input. Forwarded headers are usable only with an
explicit trusted-proxy configuration; identity comes from a credential
rather than an address or a user agent; and a request id threaded through
your logs pays for itself the first time something goes wrong in
production.


##  Where each value comes from

| Value | Source | Trust |
|---|---|---|
| `ctx.method` / `ctx.url` | Request line | Validated by routing |
| `ctx.path_params` | Route match | Validated by convertors |
| `ctx.query_params` | Query string | Client-controlled |
| `ctx.headers` | Headers | Client-controlled |
| `ctx.cookies` | `Cookie` header | Client-controlled |
| `ctx.client` | Transport peer | The proxy, behind one |
| `ctx.state` | Middleware | Yours |
