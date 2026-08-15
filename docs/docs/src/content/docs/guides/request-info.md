---
title: Request Information in sillo
description: sillo provides a comprehensive `Request` object that gives you access to all the information about the incoming HTTP request. This object is automatically passed to your route handlers and
  contains methods and properties to access request data.
head:
- tag: meta
  attrs:
    property: og:title
    content: Request Information in sillo
- tag: meta
  attrs:
    property: og:description
    content: sillo provides a comprehensive `Request` object that gives you access to all the information about the incoming HTTP request. This object is automatically passed to your route handlers and
      contains methods and properties to access request data.
---
#  Request Information

```python
@app.get("/example")
async def example_handler(request: Request, response):
    # Basic request information
    method = request.method        # HTTP method (GET, POST, etc.)
    url = request.url              # Full URL object
    path = request.path            # Request path (/example)
    headers = request.headers      # Headers dictionary
    client_ip = request.client     # Client address (IP, port)
```

##  Query Parameters

Access URL query parameters (after the `?` in the URL):

```python
@app.get("/search")
async def search_handler(request: Request, response):
    # For URL: /search?q=sillo&page=2
    query = request.query_params.get("q")       # "sillo"
    page = request.query_params.get("page")     # "2"
    all_params = dict(request.query_params)    # {'q': 'sillo', 'page': '2'}
```

##  Path Parameters

Access named parameters from the route path:

```python
@app.get("/users/{user_id}")
async def user_handler(request: Request, response):
    # For URL: /users/123
    user_id = request.path_params["user_id"]  # "123"
    # Or directly as function parameter (shown above)
```

##  Request Body

###  JSON Data

```python
@app.post("/data")
async def data_handler(request: Request, response):
    json_data = await request.json  # Parses JSON body
```

###  Form Data

```python
@app.post("/submit")
async def submit_handler(request: Request, response):
    form_data = await request.form  # Parses both URL-encoded and multipart forms
    username = form_data.get("username")
```

###  File Uploads

```python
@app.post("/upload")
async def upload_handler(request: Request, response):
    files = await request.files      # Dictionary of uploaded files
    file = files.get("document") # Access specific file
    if file:
        filename = file.filename
        content = await file.read()
```

###  Raw Body

```python
@app.post("/raw")
async def raw_handler(request: Request, response):
    body_bytes = await request.body  # Raw bytes
    body_text = await request.text  # Decoded text
```

##  Cookies

```python
@app.get("/profile")
async def profile_handler(request: Request, response):
    session_id = request.cookies.get("session_id")
```

##  Client Information

```python
@app.get("/client-info")
async def client_info_handler(request: Request, response):
    user_agent = request.user_agent
    client_ip = request.client.host if request.client else None
    origin = request.origin
```

##  State and Middleware Data

```python
@app.get("/auth")
async def auth_handler(request: Request, response):
    # Access data added by middleware
    user = request.user
    session = request.session  # Requires session middleware
    custom_data = request.state.get("custom_data")
```

##  URL Construction

```python
@app.get("/links")
async def links_handler(request: Request, response):
    absolute_url = request.build_absolute_uri("/api/resource")
    # Returns full URL like "https://example.com/api/resource"
```


##  Request Type Detection

sillo provides convenient properties to quickly check the type and characteristics of incoming requests:

###  Content Type Flags

```python
@app.post("/api/endpoint")
async def handle_request(request: Request, response):
    # Check content type
    if request.is_json:
        data = await request.json
        # Handle JSON data
    elif request.is_form:
        data = await request.form
        # Handle form data
    elif request.is_multipart:
        files = await request.files
        # Handle file uploads
    elif request.is_urlencoded:
        data = await request.form
        # Handle URL-encoded form data
```

###  Request State Flags

```python
@app.post("/process")
async def process_request(request: Request, response):
    # Check if request has various components
    if request.has_cookie:
        session_id = request.cookies.get("session")

    if request.has_files:
        files = await request.files
        # Process uploaded files

    if request.has_body:
        # Request contains body data
        if request.content_length > 1000000:  # 1MB
            return response.status(413).text("File too large")

    if request.is_authenticated:
        user_id = request.user.id
        # Handle authenticated request

    if request.has_session:
        session_data = request.session
        # Access session data
```

###  Request Type Properties

| Property | Description | Example |
|----------|-------------|---------|
| `request.is_json` | True if Content-Type is `application/json` | JSON API requests |
| `request.is_form` | True if Content-Type is form data (URL-encoded or multipart) | HTML forms |
| `request.is_multipart` | True if Content-Type is `multipart/form-data` | File uploads |
| `request.is_urlencoded` | True if Content-Type is `application/x-www-form-urlencoded` | Simple forms |
| `request.has_cookie` | True if request contains cookies | Session management |
| `request.has_files` | True if request contains uploaded files | File upload detection |
| `request.has_body` | True if request has a body | POST/PUT/PATCH requests |
| `request.is_authenticated` | True if user is authenticated | Authenticated requests |
| `request.has_session` | True if session middleware is available | Session-enabled requests |

###  Existing Request Flags

sillo also provides additional request detection properties:

```python
@app.get("/responsive")
async def responsive_handler(request: Request, response):
    # Check request characteristics
    if request.is_ajax:
        return response.json({"message": "AJAX request"})

    if request.is_secure:
        return response.json({"protocol": "HTTPS"})

    if request.accepts_json:
        return response.json({"format": "JSON preferred"})

    if request.accepts_html:
        return response.html("<h1>HTML Response</h1>")
```

###  Header Utilities

```python
@app.get("/headers")
async def header_handler(request: Request, response):
    # Check for specific headers
    if request.has_header("authorization"):
        token = request.get_header("authorization")

    # Get header with default value
    api_version = request.get_header("x-api-version", "v1")

    # Check if header exists
    if request.has_header("x-custom-header"):
        custom_value = request.get_header("x-custom-header")
```

| Method/Property | Description | Example |
|----------------|-------------|---------|
| `request.has_header(name)` | Check if header exists (case-insensitive) | `request.has_header("content-type")` |
| `request.get_header(name, default)` | Get header value with default | `request.get_header("x-api-key", "none")` |
| `request.is_ajax` | True if X-Requested-With is XMLHttpRequest | AJAX requests |
| `request.is_secure` | True if request uses HTTPS | Secure connections |
| `request.accepts_json` | True if client accepts JSON | API responses |
| `request.accepts_html` | True if client accepts HTML | Web page responses |

##  Advanced Features

###  Streaming Requests

For handling large uploads:

```python
@app.post("/stream")
async def stream_handler(request: Request, response):
    async for chunk in request.stream:
        # Process each chunk of the request body
        process_chunk(chunk)
```

###  Server Push

```python
@app.get("/push")
async def push_handler(request: Request, response):
    await request.send_push_promise("/static/style.css")
```

The sillo `Request` object provides a rich interface for working with incoming HTTP requests, with support for all common web standards and convenient access to request data. 

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
helpers](/guides/helpers/network/) for the trusted-proxy handling this needs.

**The body**, client-controlled, and the reason
[validation](/guides/validation/) exists.

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
present, generate one if not, put it in `request.state`, log it
everywhere, and return it in the response.

```python title="request correlation"
import uuid


async def request_id_middleware(request, response, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = rid
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

`request.body`, `request.json`, `request.form`, and `request.files` each
consume the request stream. Reading one and then another may give you
nothing, because the bytes are gone.

Where middleware needs the body (logging, signature verification) read it once,
cache it on `request.state`, and have downstream code use the cached copy. And
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

- [Headers](/guides/headers/): reading and setting them safely
- [Network helpers](/guides/helpers/network/): client IP resolution and trusted
  proxies
- [Middleware](/guides/middleware/): where request correlation belongs
- [Request Lifecycle](/guides/request-lifecycle/): when each of these values
  becomes available
- [Security](/guides/security/): what not to trust from a request


##  Content negotiation inputs

`Accept`, `Accept-Language`, and `Accept-Encoding` are the headers a client
uses to state preferences, each a weighted list rather than a single value.
Parsing them naively (taking the first entry, or substring-matching) produces
wrong answers for any client that sends real quality values.

Anything whose response varies by one of these must set `Vary` naming it,
or a shared cache will serve one representation to everyone. See
[Content Negotiation](/guides/content-negotiation/).


##  Debugging what actually arrived

When behaviour depends on a header you cannot see, dump the raw picture
once rather than guessing:

```python title="a temporary diagnostic endpoint"
@app.get("/_debug/echo")
async def echo(request, response):
    return response.json({
        "method": request.method,
        "path": request.url.path,
        "query": dict(request.query_params),
        "headers": dict(request.headers),
        "client": request.client,
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
| `request.method` / `request.url` | Request line | Validated by routing |
| `request.path_params` | Route match | Validated by convertors |
| `request.query_params` | Query string | Client-controlled |
| `request.headers` | Headers | Client-controlled |
| `request.cookies` | `Cookie` header | Client-controlled |
| `request.client` | Transport peer | The proxy, behind one |
| `request.state` | Middleware | Yours |
