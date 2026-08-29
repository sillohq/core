---
title: OAuth in OpenAPI
description: "What your API reference should say about an OAuth login: which credential to document, how sillo derives securitySchemes and per-route security from your backends and gates, and how to publish an OAuth2 flow for a Swagger authorize button."
head:
- tag: meta
  attrs:
    property: og:title
    content: Documenting OAuth in OpenAPI with sillo
- tag: meta
  attrs:
    property: og:description
    content: Declare backends with SilloApp(auth=[...]) and sillo derives securitySchemes and every route's security from the gate you already wrote.
---

#  OAuth in OpenAPI

The first thing to settle is *what* you are documenting, because it is easy to
document the wrong thing.

An OAuth login is how somebody **obtains** a credential. It is not the
credential your API checks on every subsequent request. That is the session
cookie or the JWT your callback issued. Those two are different, and your
reference should describe the second.

So in almost every application:

- The OAuth redirect and callback routes are **public browser endpoints**, and
  usually should not appear in the document at all.
- The protected routes are documented as `sessionCookie` or `bearerAuth`,
  whichever your callback issues.
- An `oauth2` security scheme is only needed if you want Swagger UI's
  **Authorize** button to run the flow, and that takes extra wiring, covered
  [at the end](#publishing-the-oauth2-flow-itself).

##  Declare backends on the application

This is the load-bearing step. Pass backends to `SilloApp(auth=[...])` rather
than installing `AuthenticationMiddleware` yourself:

```python
app = SilloApp(
    title="My API",
    auth=[
        JWTAuthBackend(
            secret_key=settings.jwt_secret,
            description="Issued by /auth/google/callback.",
        ),
        SessionAuthBackend(description="Set by /auth/google/callback."),
    ],
    auth_user_model=User,
    strict_security=True,
)
```

Doing so makes sillo publish each backend's own description of itself under
`components.securitySchemes`, keyed by the backend's `name`:

```json
{
  "bearerAuth": {
    "type": "http",
    "scheme": "bearer",
    "bearerFormat": "JWT",
    "description": "Issued by /auth/google/callback."
  },
  "sessionCookie": {
    "type": "apiKey",
    "in": "cookie",
    "name": "session_id",
    "description": "Set by /auth/google/callback."
  }
}
```

`description` is worth filling in. Where a token comes from is the one thing
OAuth makes non-obvious, and it is the only place in the reference you can say
so.

:::caution
**Installing the middleware by hand documents the wrong credential.** It
authenticates requests perfectly well, but registers no scheme, so the document
falls back to a legacy default that advertises `bearerAuth`.

A session-only application wired with `app.use(AuthenticationMiddleware(...))`
therefore publishes a bearer token it never reads, and stays silent about the
cookie it does. No test of the application's behaviour would catch that; only
a reader would, by failing to authenticate.

The same legacy default applies to an application that declares no backends at
all: its document claims `bearerAuth` regardless.
:::

The `sessionCookie` scheme names the cookie a caller must send, so keep it in
step with your session configuration:

```python
SessionAuthBackend(cookie_name="my_session")   # documented as name: "my_session"
```

##  Route security is derived, not written

You already declare what a route accepts when you write its gate. sillo turns
that into the document's `security`, so the two cannot drift:

```python
@app.get("/api/me", auth=useAuth(schemes=["bearerAuth"]))
```

| Gate | Documented `security` | Meaning |
| --- | --- | --- |
| no gate | *absent* | Public. |
| `useAuth()` | `[{"bearerAuth": []}, {"sessionCookie": []}]` | Every registered scheme. It rejects anonymous callers but names none, and documenting it as public is the more dangerous lie. |
| `useAuth(schemes=["bearerAuth"])` | `[{"bearerAuth": []}]` | That one credential. |
| `useAuth(schemes=["bearerAuth", "sessionCookie"])` | `[{"bearerAuth": []}, {"sessionCookie": []}]` | Separate objects mean **either**. |
| `useAuth(schemes=[...], all_of=True)` | `[{"bearerAuth": [], "sessionCookie": []}]` | One object with several keys means **both**. |
| `useAuth(required=False)` | `[{...}, {...}, {}]` | The trailing `{}` is OpenAPI's spelling of "authentication is optional". |
| `useAuth(permissions=["admin"])` | every registered scheme | Authorization has no OpenAPI field, so permissions never reach the document. |

You can still override it per route with `security=[...]`, but doing so
reintroduces exactly the drift this is designed to prevent.

##  Keep the OAuth routes out

```python
@app.get("/auth/google/redirect", exclude_from_schema=True)
@app.get("/auth/google/callback", exclude_from_schema=True)
```

They are browser redirects, not API operations. A callback documented as
callable is misleading. It only works with a live `code` and a matching state
cookie, so a reader trying it from Swagger UI gets `state_mismatch` and no
explanation.

If you do leave them in, leave them **ungated**. They document as public, which
is correct: the browser arrives at both without a credential.

##  Use scheme names, not the old scope labels

`useAuth` still accepts the legacy method labels `jwt`, `session` and `apikey`
as `schemes` values, and they still gate correctly at runtime. But they are not
scheme *names*, so they produce a document that references something it never
defines:

```python
@app.get("/legacy", auth=useAuth(schemes=["jwt"]))
```

```json
"security": [{ "jwt": [] }]
```

…while `components.securitySchemes` contains only `bearerAuth`. A viewer
renders an authorize box wired to nothing.

`strict_security=True` turns that from a silent lie into a startup error:

```
ValueError: These routes require security schemes that are not registered:
  /legacy requires 'jwt'
Registered schemes: bearerAuth.
```

Write `schemes=["bearerAuth"]` and it passes. Turning `strict_security` on is
the recommendation for exactly this reason: the whole point of deriving
`security` from the gate is that the two can be checked against each other.

##  Two backends of the same kind

Two JWT backends (a user token and an admin token on a different secret) both
call themselves `bearerAuth` by default. Rather than let one silently overwrite
the other's definition, sillo refuses:

```
ValueError: Two auth backends both claim the scheme 'bearerAuth' but describe
it differently. Give one of them a distinct name, e.g. JWTAuthBackend(name='...').
```

```python
auth=[
    JWTAuthBackend(secret_key=user_secret, description="User tokens."),
    JWTAuthBackend(secret_key=admin_secret, name="adminAuth", description="Admin tokens."),
]
```

Both now appear, and routes can require one or the other.

##  Publishing the OAuth2 flow itself

Only needed if you want Swagger UI's **Authorize** button to run the Google
flow. sillo has the models:

```python
from sillo.openapi.models import OAuth2, OAuthFlowAuthorizationCode, OAuthFlows

scheme = OAuth2(
    description="Sign in with Google.",
    flows=OAuthFlows(
        authorizationCode=OAuthFlowAuthorizationCode(
            authorizationUrl="https://accounts.google.com/o/oauth2/v2/auth",
            tokenUrl="https://oauth2.googleapis.com/token",
            scopes={"openid": "Sign in", "email": "Email address"},
        )
    ),
)
app.openapi_config.add_security_scheme("googleOAuth", scheme)
```

The mapping form of `schemes` carries OAuth2 scopes onto a route:

```python
@app.get("/scoped", auth=useAuth(schemes={"googleOAuth": ["openid", "email"]}))
```

```json
"security": [{ "googleOAuth": ["openid", "email"] }]
```

:::caution
**Registering the scheme does not make the gate accept it.** A scheme in the
document is prose. The gate matches on the name a backend *reports*, and no
shipped backend calls itself `googleOAuth`, so the route above refuses every
caller, including one holding a perfectly valid JWT.
:::

To make the gate and the document agree, the backend has to report that name
and describe itself as that scheme:

```python
class GoogleTokenBackend(JWTAuthBackend):
    name = "googleOAuth"

    def describe(self):
        return scheme


app = SilloApp(
    auth=[GoogleTokenBackend(secret_key=settings.jwt_secret)],
    strict_security=True,
)
```

Now `useAuth(schemes=["googleOAuth"])` both gates and documents correctly.

Unless you specifically want that authorize button, skip all of this. An
`oauth2` scheme claims your API accepts a Google token directly; it does not.
It accepts *your* token, and `bearerAuth` says so honestly.

##  Verifying your own document

Every output on this page is asserted against a generated document in
`sillo-oauth`'s test suite. The same check is worth having in yours:

```python
def test_document_has_no_dangling_security_references():
    doc = TestClient(app).get("/openapi.json").json()
    defined = set(doc["components"]["securitySchemes"])
    for path, item in doc["paths"].items():
        for operation in item.values():
            if not isinstance(operation, dict):
                continue  # a path item may hold `parameters` or `summary`
            for requirement in operation.get("security") or []:
                assert set(requirement) <= defined, f"{path} references an unknown scheme"
```

With `strict_security=True` the application refuses to build such a document at
all, which is the better place to catch it.
