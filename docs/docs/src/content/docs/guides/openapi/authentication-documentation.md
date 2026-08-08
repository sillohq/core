---
title: Documenting Authentication
description: >
    Securing your API is crucial for protecting user data and enabling safe integrations. sillo provides comprehensive OpenAPI documentation for multiple authentication schemes, making it easy for API consumers to understand and implement proper authentication.
---

#  Documenting Authentication

Securing your API is crucial for protecting user data and enabling safe integrations. sillo provides comprehensive OpenAPI documentation for multiple authentication schemes, making it easy for API consumers to understand and implement proper authentication.

##  Declare it once

An authentication backend already knows which credential it reads.
`JWTAuthBackend` reads `Authorization: Bearer <token>` — which *is*
`HTTPBearer(scheme="bearer", bearerFormat="JWT")`. So pass your backends to
`silloApp(auth=...)` and the document follows from them:

```python
from sillo import silloApp
from sillo.auth import JWTAuthBackend, APIKeyAuthBackend, SessionAuthBackend, useAuth

app = silloApp(
    auth=[
        JWTAuthBackend(secret_key=SECRET, description="A JWT from `POST /login`."),
        APIKeyAuthBackend(header_name="X-API-Key"),
        SessionAuthBackend(),
    ],
)
```

That one argument does two jobs: it mounts `AuthenticationMiddleware` with
those backends, and it publishes each one under
`components.securitySchemes` as `bearerAuth`, `apiKeyHeader` and
`sessionCookie`.

A route then names a scheme **once**, on its gate, and its documented
`security` is derived:

```python
@app.get("/me", auth=useAuth(schemes=["bearerAuth", "sessionCookie"]))
async def me(request, response): ...
```

```json
"security": [{"bearerAuth": []}, {"sessionCookie": []}]
```

| Gate | Generated `security` | Meaning |
| --- | --- | --- |
| `schemes=["a"]` | `[{"a": []}]` | requires `a` |
| `schemes=["a", "b"]` | `[{"a": []}, {"b": []}]` | either one |
| `schemes=["a", "b"], all_of=True` | `[{"a": [], "b": []}]` | both |
| `schemes=["a"], required=False` | `[{"a": []}, {}]` | optional |
| `schemes={"oauth2": ["read:widgets"]}` | `[{"oauth2": ["read:widgets"]}]` | with OAuth2 scopes |
| `useAuth()` — no `schemes` | every registered scheme, as alternatives | any credential |
| no gate at all | absent | public |

The `{}` in that fourth row is how OpenAPI spells "authentication is
optional" — an empty requirement object alongside the real ones. Almost
nobody writes it by hand, which is why optional-auth routes are so often
documented as mandatory.

The second-to-last row is the one that catches people out. A bare
`useAuth()` names no scheme but still rejects anonymous callers, and any
registered backend satisfies it — so the document lists them all as
alternatives rather than leaving the route looking public. The same applies
to `useAuth(permissions=[...])`: needing a permission implies needing an
identity.

<aside>

A route documented as public that answers **401** is worse than one
documented as protected that answers 200 — the reader has no reason to
suspect their client, and nothing in the reference suggests a credential is
wanted. That is why the fallback exists rather than leaving `security`
absent.

</aside>

###  Why this matters more than the shorter syntax

Before this, a route said its auth twice — once as a gate that enforced it,
once as a `security=` list that documented it — and nothing checked the two
against each other. A document could advertise bearer auth while the gate
accepted an API key, forever, with no test failing.

Turn that into an error:

```python
app = silloApp(auth=[JWTAuthBackend(secret_key=SECRET)], strict_security=True)
```

Building the document now fails if a route requires a scheme nothing
registered:

```
ValueError: These routes require security schemes that are not registered:
  /me requires 'sessionCookie'
Registered schemes: bearerAuth.
```

Without it, that route renders an authorize box in every viewer wired to a
scheme no backend implements, and the first sign of trouble is a 401 the
document says is impossible.

`strict_security` is off by default so existing applications keep building.

###  `scopes=` is gone — `schemes=` is the only spelling

There used to be two identifiers for one fact: a backend reported a *method
label* on `AuthResult.scope` (`"jwt"`), while the document named a *scheme*
(`"bearerAuth"`), and a route had to know both. They are now one — a backend
reports its own scheme name, and `request.scope["auth"]` and
`["auth_scheme"]` carry the same value.

The old `scopes=` parameter, which matched the method label, has been
removed — passing it raises `TypeError`. Gates name schemes:

| Old | New |
| --- | --- |
| `scopes=["jwt"]` | `schemes=["bearerAuth"]` |
| `scopes=["session"]` | `schemes=["sessionCookie"]` |
| `scopes=["apikey"]` | `schemes=["apiKeyHeader"]` |

The legacy `@auth("jwt")` decorator still matches method labels.

<aside>

OpenAPI also says "scopes", meaning OAuth2 permission strings — a third
thing again. Those live inside `schemes` as the mapping form:
`schemes={"oauth2": ["read:widgets"]}`.

</aside>

###  Naming two backends of the same kind

Two JWT secrets — a user token and an admin token — are two schemes:

```python
auth=[
    JWTAuthBackend(secret_key=USER_SECRET),
    JWTAuthBackend(secret_key=ADMIN_SECRET, name="adminBearer",
                   description="Issued only to staff accounts."),
]
```

Leave the second unnamed and sillo raises rather than letting one silently
overwrite the other — which would document a credential the losing backend
never reads.

###  Opting out

A backend whose `describe()` returns `None` still authenticates; it is just
left out of the document. That is the default for a custom
`AuthenticationBackend`, so subclasses keep working unchanged:

```python
class InternalBackend(AuthenticationBackend):
    name = "internal"

    def describe(self):
        return None            # enforced, undocumented

    async def authenticate(self, request): ...
```

An explicit `security=` on a route always wins over the derived value. You
need that when a gateway terminates auth ahead of the application and the
document has to describe something this process does not enforce.

###  When you still register schemes by hand

`config.add_security_scheme` remains the way to document a scheme sillo has
no backend for — `openIdConnect`, an OAuth2 flow handled by an identity
provider, or mutual TLS terminated at a load balancer. The rest of this page
covers that path.

<aside>

**An application that declares no backends still advertises `bearerAuth`.**
`silloApp()` has always registered that scheme unconditionally, whether or
not the app has any JWT anywhere. Passing `auth=` is the opt-out; it is left
in place otherwise so existing `security=[{"bearerAuth": []}]` declarations
keep resolving.

</aside>

##  Why Document Authentication?

Proper authentication documentation provides several benefits:

- **Security Clarity**: API consumers understand exactly how to authenticate
- **Integration Speed**: Clear auth docs reduce integration time and support requests
- **Testing Support**: Interactive docs allow testing with real authentication
- **Compliance**: Proper documentation helps meet security audit requirements
- **Developer Experience**: Clear auth flows improve API adoption

##  Bearer Token Authentication

Bearer token authentication (typically JWT) is the most common modern authentication method. sillo includes built-in support with automatic documentation:

```python
from sillo import silloApp

app = silloApp()

# Basic bearer authentication
@app.get(
    "/profile",
    security=[{"bearerAuth": []}],
    summary="Get user profile",
    description="Retrieves the authenticated user's profile information"
)
async def get_profile(request, response):
    # Access authenticated user info
    # request.user is available after authentication middleware
    return response.json({
        "id": 123,
        "username": "johndoe",
        "email": "john@example.com"
    })

# Multiple protected endpoints
@app.get("/settings", security=[{"bearerAuth": []}])
async def get_settings(request, response):
    return response.json({"theme": "dark", "notifications": True})

@app.post("/posts", security=[{"bearerAuth": []}])
async def create_post(request, response):
    return response.json({"id": 456, "title": "New Post"}, status=201)

@app.delete("/posts/{post_id}", security=[{"bearerAuth": []}])
async def delete_post(request, response, post_id: int):
    return response.json({"deleted": True}, status=204)
```

###  Custom Bearer Token Configuration

Customize the bearer token scheme for specific requirements:

```python
from sillo.openapi.models import HTTPBearer

# Add custom JWT authentication scheme
app.openapi_config.add_security_scheme(
    "JWTAuth",
    HTTPBearer(
        type="http",
        scheme="bearer",
        bearerFormat="JWT",
        description="JWT token required in Authorization header. Format: 'Bearer <token>'"
    )
)

@app.get(
    "/admin/users",
    security=[{"JWTAuth": []}],
    summary="List all users (Admin only)",
    description="Requires valid JWT token with admin privileges"
)
async def admin_list_users(request, response):
    # Verify admin role in middleware
    return response.json({"users": []})
```

##  🗝️ API Key Authentication

API keys provide simple authentication for programmatic access. They can be passed in headers, query parameters, or cookies:

###  Header-Based API Keys

```python
from sillo.openapi.models import APIKey

# Register API key scheme
app.openapi_config.add_security_scheme(
    "ApiKeyAuth",
    APIKey(
        type="apiKey",
        name="X-API-Key",
        in_="header",
        description="API key for programmatic access. Contact support to obtain your key."
    )
)

@app.get(
    "/api/data",
    security=[{"ApiKeyAuth": []}],
    summary="Get data via API key",
    description="Retrieve data using API key authentication"
)
async def get_api_data(request, response):
    api_key = request.headers.get('X-API-Key')
    # Validate API key
    return response.json({"data": "sensitive information"})

# Multiple API key schemes for different purposes
app.openapi_config.add_security_scheme(
    "AdminApiKey",
    APIKey(
        type="apiKey",
        name="X-Admin-Key",
        in_="header",
        description="Admin API key for elevated privileges"
    )
)

@app.delete(
    "/admin/cleanup",
    security=[{"AdminApiKey": []}],
    summary="Admin cleanup operation"
)
async def admin_cleanup(request, response):
    admin_key = request.headers.get('X-Admin-Key')
    # Validate admin key and perform cleanup
    return response.json({"cleaned": True})
```

###  Query Parameter API Keys

```python
# API key in query parameter
app.openapi_config.add_security_scheme(
    "QueryApiKey",
    APIKey(
        type="apiKey",
        name="api_key",
        in_="query",
        description="API key passed as query parameter. Example: ?api_key=your_key_here"
    )
)

@app.get(
    "/public-api/stats",
    security=[{"QueryApiKey": []}],
    summary="Get public statistics"
)
async def get_public_stats(request, response):
    api_key = request.query_params.get('api_key')
    # Validate and return stats
    return response.json({"stats": {"users": 1000, "posts": 5000}})
```

###  Cookie-Based API Keys

```python
# API key in cookie
app.openapi_config.add_security_scheme(
    "SessionAuth",
    APIKey(
        type="apiKey",
        name="session_token",
        in_="cookie",
        description="Session token stored in HTTP cookie"
    )
)

@app.get(
    "/dashboard",
    security=[{"SessionAuth": []}],
    summary="Get user dashboard"
)
async def get_dashboard(request, response):
    session_token = request.cookies.get('session_token')
    # Validate session
    return response.json({"dashboard": "data"})
```

##  OAuth2 Authentication

OAuth2 provides secure, delegated access and is ideal for third-party integrations. sillo supports all OAuth2 flows:

###  Authorization Code Flow

```python
from sillo.openapi.models import OAuth2

# Register OAuth2 authorization code flow
app.openapi_config.add_security_scheme(
    "OAuth2AuthCode",
    OAuth2(
        type="oauth2",
        flows={
            "authorizationCode": {
                "authorizationUrl": "https://auth.example.com/oauth/authorize",
                "tokenUrl": "https://auth.example.com/oauth/token",
                "refreshUrl": "https://auth.example.com/oauth/refresh",
                "scopes": {
                    "read": "Read access to user data",
                    "write": "Write access to user data",
                    "admin": "Administrative access",
                    "profile": "Access to user profile information"
                }
            }
        },
        description="OAuth2 authorization code flow for secure third-party access"
    )
)

@app.get(
    "/oauth/profile",
    security=[{"OAuth2AuthCode": ["read", "profile"]}],
    summary="Get user profile via OAuth2",
    description="Requires OAuth2 token with 'read' and 'profile' scopes"
)
async def oauth_get_profile(request, response):
    # OAuth2 token validation handled by middleware
    return response.json({"profile": "data"})

@app.post(
    "/oauth/posts",
    security=[{"OAuth2AuthCode": ["write"]}],
    summary="Create post via OAuth2"
)
async def oauth_create_post(request, response):
    return response.json({"created": True}, status=201)

@app.delete(
    "/oauth/admin/users/{user_id}",
    security=[{"OAuth2AuthCode": ["admin"]}],
    summary="Delete user (OAuth2 admin)"
)
async def oauth_delete_user(request, response, user_id: int):
    return response.json({"deleted": True})
```

###  Client Credentials Flow

```python
# OAuth2 client credentials for machine-to-machine
app.openapi_config.add_security_scheme(
    "OAuth2ClientCreds",
    OAuth2(
        type="oauth2",
        flows={
            "clientCredentials": {
                "tokenUrl": "https://auth.example.com/oauth/token",
                "scopes": {
                    "api:read": "Read API access",
                    "api:write": "Write API access",
                    "api:admin": "Admin API access"
                }
            }
        },
        description="OAuth2 client credentials flow for service-to-service authentication"
    )
)

@app.get(
    "/api/v1/data",
    security=[{"OAuth2ClientCreds": ["api:read"]}],
    summary="Get data (service-to-service)"
)
async def get_service_data(request, response):
    return response.json({"data": "service data"})
```

###  Password Flow (Resource Owner)

```python
# OAuth2 password flow (use with caution)
app.openapi_config.add_security_scheme(
    "OAuth2Password",
    OAuth2(
        type="oauth2",
        flows={
            "password": {
                "tokenUrl": "https://auth.example.com/oauth/token",
                "scopes": {
                    "user": "User access",
                    "admin": "Admin access"
                }
            }
        },
        description="OAuth2 password flow (for trusted first-party applications only)"
    )
)

@app.get(
    "/internal/data",
    security=[{"OAuth2Password": ["user"]}],
    summary="Get internal data"
)
async def get_internal_data(request, response):
    return response.json({"internal": "data"})
```

##  Multiple Authentication Methods

Support multiple authentication methods to provide flexibility:

###  Alternative Authentication

```python
# Either Bearer token OR API key
@app.get(
    "/flexible-auth",
    security=[
        {"BearerAuth": []},
        {"ApiKeyAuth": []}
    ],
    summary="Endpoint supporting multiple auth methods",
    description="Accepts either Bearer token or API key authentication"
)
async def flexible_auth_endpoint(request, response):
    # Check which auth method was used
    if request.headers.get('Authorization'):
        auth_type = "bearer"
    elif request.headers.get('X-API-Key'):
        auth_type = "api_key"
    else:
        return response.json({"error": "Authentication required"}, status=401)
    
    return response.json({"auth_type": auth_type, "data": "protected data"})
```

###  Combined Authentication Requirements

```python
# Require BOTH Bearer token AND API key
@app.get(
    "/high-security",
    security=[
        {
            "BearerAuth": [],
            "ApiKeyAuth": []
        }
    ],
    summary="High security endpoint",
    description="Requires both Bearer token and API key for access"
)
async def high_security_endpoint(request, response):
    # Both auth methods must be present
    return response.json({"data": "highly sensitive data"})
```

##  Advanced Authentication Patterns

###  Role-Based Access Control

```python
# Custom security scheme with roles
app.openapi_config.add_security_scheme(
    "RoleBasedAuth",
    HTTPBearer(
        type="http",
        scheme="bearer",
        bearerFormat="JWT",
        description="JWT token with role-based access control"
    )
)

@app.get(
    "/admin/reports",
    security=[{"RoleBasedAuth": []}],
    summary="Admin reports (requires admin role)",
    description="Requires JWT token with 'admin' role claim"
)
async def admin_reports(request, response):
    # Role validation handled in middleware
    return response.json({"reports": []})

@app.get(
    "/moderator/content",
    security=[{"RoleBasedAuth": []}],
    summary="Moderator content (requires moderator role)"
)
async def moderator_content(request, response):
    return response.json({"content": []})
```

###  Conditional Authentication

```python
@app.get(
    "/content/{content_id}",
    summary="Get content (auth optional)",
    description="""
    Get content by ID. Authentication is optional but affects response:
    - Without auth: Returns public content only
    - With auth: Returns full content including private fields
    """
)
async def get_content(request, response, content_id: int):
    # Check if authenticated
    auth_header = request.headers.get('Authorization')
    is_authenticated = bool(auth_header and auth_header.startswith('Bearer '))
    
    if is_authenticated:
        # Return full content
        return response.json({
            "id": content_id,
            "title": "Content Title",
            "body": "Full content body",
            "private_notes": "Internal notes"
        })
    else:
        # Return public content only
        return response.json({
            "id": content_id,
            "title": "Content Title",
            "body": "Full content body"
        })
```

##  Security Best Practices

###  Comprehensive Error Responses

```python
from pydantic import BaseModel

class AuthErrorResponse(BaseModel):
    error: str
    code: int
    message: str
    details: dict = {}

@app.get(
    "/secure-data",
    security=[{"BearerAuth": []}],
    responses={
        200: {"description": "Success"},
        401: AuthErrorResponse,
        403: AuthErrorResponse,
        429: {"description": "Rate limit exceeded"}
    }
)
async def get_secure_data(request, response):
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        error = AuthErrorResponse(
            error="MISSING_AUTH",
            code=401,
            message="Authorization header is required",
            details={"header": "Authorization", "format": "Bearer <token>"}
        )
        return response.json(error.dict(), status=401)
    
    if not auth_header.startswith('Bearer '):
        error = AuthErrorResponse(
            error="INVALID_AUTH_FORMAT",
            code=401,
            message="Invalid authorization format",
            details={"expected": "Bearer <token>", "received": auth_header[:20]}
        )
        return response.json(error.dict(), status=401)
    
    # Token validation logic here
    return response.json({"data": "secure information"})
```

###  Authentication Middleware Integration

```python
# Example authentication middleware
async def auth_middleware(request, response, next_call):
    """Authentication middleware for protected endpoints"""
    
    # Skip auth for public endpoints
    if request.url.path in ['/health', '/docs', '/openapi.json']:
        return await next_call()
    
    # Check for authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return response.json({
            "error": "Authentication required",
            "code": 401
        }, status=401)
    
    # Validate token (implement your logic)
    token = auth_header[7:]  # Remove 'Bearer ' prefix
    user = await validate_jwt_token(token)
    
    if not user:
        return response.json({
            "error": "Invalid or expired token",
            "code": 401
        }, status=401)
    
    # Add user to request context
    request.user = user
    return await next_call()

# Apply middleware
app.use(auth_middleware)
```

##  Documentation Best Practices

###  Clear Security Descriptions

```python
@app.get(
    "/api/users",
    security=[{"BearerAuth": []}],
    summary="List users",
    description="""
    Retrieve a list of users with pagination support.
    
    **Authentication Required:**
    - Valid JWT token in Authorization header
    - Token must not be expired
    - User must have 'read:users' permission
    
    **Rate Limits:**
    - 100 requests per minute per user
    - 1000 requests per hour per API key

    **Example Request:**
        GET /api/users?limit=20
        Authorization: Bearer <token>
    """,
)
async def list_users(request, response): ...
```
    GET /api/users?limit=20&offset=0
    Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    ```
    """
)
```

###  Security Scheme Documentation

```python
# Well-documented security schemes
app.openapi_config.add_security_scheme(
    "ComprehensiveAuth",
    HTTPBearer(
        type="http",
        scheme="bearer",
        bearerFormat="JWT",
        description="""
        JWT Bearer token authentication.
        
        **How to obtain a token:**
        1. POST to /auth/login with credentials
        2. Extract 'access_token' from response
        3. Include in Authorization header: 'Bearer <token>'
        
        **Token format:**
        - Standard JWT with HS256 signature
        - Expires after 1 hour
        - Contains user ID and permissions in claims
        
        **Example:**
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        """
    )
)
```

Authentication documentation is crucial for API adoption and security. Clear, comprehensive documentation helps developers integrate quickly while maintaining security best practices.


##  What the schema can and cannot enforce

A security scheme in the OpenAPI document is a **description**, not a
control. Declaring `bearerAuth` on a route does not make sillo check for
a token — that is what dependencies and middleware are for. The schema
tells clients what to send; your code decides what to accept.

The gap matters in both directions. A route documented as requiring auth
but not actually protected is a vulnerability that reads as secure. A
route protected but not documented is an integration failure that reads
as a bug in the client.

Keep them together structurally. If authentication is applied by a
dependency, attach the security requirement in the same place the
dependency is declared, so adding one without the other is visibly
incomplete.

##  Documenting the token lifecycle

The scheme declaration says "send a bearer token". It does not say where
one comes from, and that is the first thing an integrator needs.

Put the full lifecycle in the scheme description: which endpoint issues a
token, what credentials it takes, how long the token lasts, how to
refresh it, and what a client should do when it expires. A client that
does not know a token expires in fifteen minutes will write code that
breaks fifteen minutes into every session.

Document the failure responses too. A 401 with `WWW-Authenticate` means
"authenticate and retry"; a 403 means "you are authenticated and still
not allowed" and retrying is pointless. Clients that conflate them
produce infinite refresh loops against endpoints they will never be
permitted to call.

##  Scopes, and why they belong per endpoint

If your tokens carry scopes, the schema is where a client learns which
ones a given call needs. Declaring the scheme globally without per-route
scopes tells integrators nothing, and the rational response is to request
every scope available — which is precisely the outcome scopes exist to
prevent.

Attach the minimum scope per route. It costs one line and it means a
generated client, a security review, and an integrator all see the same
answer to "what does this endpoint need".

##  Security hygiene in the document itself

Three things that leak through documentation rather than through code.

**Do not put real credentials in examples.** An example API key in a
published schema is a published API key. Use obviously fake values with a
recognisable prefix.

**Do not document internal endpoints publicly.** Admin routes, debug
handlers, and internal health checks in a public schema are a map for
someone enumerating your surface. Exclude them from the document.

**Do not describe your rate limits so precisely that they become a
targeting guide** — but do describe them well enough that a legitimate
client can respect them. The shape that works: state the limit and the
window, document the `429` response and `Retry-After`, and leave the
enforcement details out.


##  Testing that documented auth matches enforced auth

The drift between "documented as protected" and "actually protected" is
invisible until someone exploits it. One test closes the gap for the
whole API:

```python title="every documented-secure route must reject anonymous calls"
def test_secured_routes_reject_anonymous():
    schema = app.openapi()
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if not operation.get("security"):
                continue
            response = client.request(method.upper(), path.replace("{id}", "1"))
            assert response.status_code in (401, 403), f"{method} {path} is not protected"
```

The inverse test is worth having too: routes that enforce authentication
but declare no `security` in the schema are undocumented, and integrators
will hit a 401 they had no way to anticipate.
