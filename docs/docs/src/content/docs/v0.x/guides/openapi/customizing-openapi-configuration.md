---
title: Customizing OpenAPI Configuration in sillo
description: >
    sillo provides extensive customization options for your OpenAPI documentation, allowing you to create professional, branded, and comprehensive API documentation that meets enterprise requirements and enhances developer experience.
---

#  Customizing OpenAPI Configuration in sillo

sillo provides extensive customization options for your OpenAPI documentation, allowing you to create professional, branded, and comprehensive API documentation that meets enterprise requirements and enhances developer experience.

##  Why Customize OpenAPI Configuration?

Customizing your OpenAPI configuration provides several benefits:

- **Professional Branding**: Match your company's branding and style guidelines
- **Legal Compliance**: Include terms of service, licenses, and contact information
- **Developer Experience**: Provide clear, comprehensive information for API consumers
- **Enterprise Requirements**: Meet corporate documentation standards
- **Support Efficiency**: Reduce support requests with better documentation

##  Basic Configuration

Set fundamental API information directly in the `SilloApp` constructor:

```python
from sillo import SilloApp

app = SilloApp(
    title="E-Commerce API",
    version="2.1.0",
    description="""
    A comprehensive e-commerce API providing:
    - Product catalog management
    - Order processing and fulfillment
    - User authentication and profiles
    - Payment processing integration
    - Inventory management
    - Analytics and reporting
    
    This API follows REST principles and provides consistent, 
    predictable interfaces for all operations.
    """
)

@app.get("/health")
async def health_check(request, response):
    """API health check endpoint."""
    return response.json({
        "status": "healthy",
        "version": "2.1.0",
        "timestamp": "2024-01-01T12:00:00Z"
    })
```

##  Advanced Configuration

For complete control over your OpenAPI specification, use the configuration system:

```python
from sillo.openapi.models import Contact, License, Server, Tag, ExternalDocumentation
from sillo import SilloApp

app = SilloApp(
    title="Enterprise E-Commerce API",
    version="2.1.0",
    description="""
    Enterprise-grade e-commerce API with comprehensive business logic,
    security features, and integration capabilities.
    
    **Features:**
    - Multi-tenant architecture
    - Advanced security with OAuth2 and API keys
    - Real-time inventory management
    - Comprehensive audit logging
    - High availability and scalability
    """
)

# Add server information
app.openapi_config.openapi_spec.servers = [
    Server(
        url="https://api.example.com/v2",
        description="Production server"
    ),
    Server(
        url="https://staging-api.example.com/v2",
        description="Staging server for testing"
    ),
    Server(
        url="https://dev-api.example.com/v2",
        description="Development server"
    ),
    Server(
        url="http://localhost:8000",
        description="Local development server"
    )
]

# Add contact information
app.openapi_config.openapi_spec.info.contact = Contact(
    name="API Support Team",
    url="https://example.com/support",
    email="api-support@example.com"
)

# Add license information
app.openapi_config.openapi_spec.info.license = License(
    name="MIT License",
    url="https://opensource.org/licenses/MIT"
)

# Add terms of service
app.openapi_config.openapi_spec.info.termsOfService = "https://example.com/terms"

# Add external documentation
app.openapi_config.openapi_spec.externalDocs = ExternalDocumentation(
    description="Complete API Documentation",
    url="https://docs.example.com/api"
)
```

##  Tags and Organization

Organize your API endpoints with comprehensive tagging:

```python
# Define comprehensive tags for API organization
api_tags = [
    Tag(
        name="Authentication",
        description="User authentication and authorization endpoints",
        externalDocs=ExternalDocumentation(
            description="Authentication Guide",
            url="https://docs.example.com/auth"
        )
    ),
    Tag(
        name="Users",
        description="User management and profile operations"
    ),
    Tag(
        name="Products",
        description="Product catalog management including search and filtering"
    ),
    Tag(
        name="Orders",
        description="Order processing, tracking, and fulfillment"
    ),
    Tag(
        name="Payments",
        description="Payment processing and transaction management"
    ),
    Tag(
        name="Admin",
        description="Administrative operations requiring elevated privileges"
    ),
    Tag(
        name="Analytics",
        description="Business intelligence and reporting endpoints"
    ),
    Tag(
        name="Webhooks",
        description="Webhook management for real-time notifications"
    )
]

# Add tags to OpenAPI spec
app.openapi_config.openapi_spec.tags = api_tags

# Use tags in endpoints
@app.post(
    "/auth/login",
    tags=["Authentication"],
    summary="User login",
    description="Authenticate user and return access token"
)
async def login(request, response):
    return response.json({"access_token": "jwt_token_here"})

@app.get(
    "/products",
    tags=["Products"],
    summary="List products",
    description="Retrieve paginated list of products with filtering options"
)
async def list_products(request, response):
    return response.json({"products": [], "total": 0})
```

##  Security Schemes Configuration

Configure comprehensive security schemes for different authentication methods:

```python
from sillo.openapi.models import HTTPBearer, APIKey, OAuth2

# JWT Bearer authentication
app.openapi_config.add_security_scheme(
    "BearerAuth",
    HTTPBearer(
        type="http",
        scheme="bearer",
        bearerFormat="JWT",
        description="""
        JWT Bearer token authentication.
        
        **How to obtain:**
        1. POST to /auth/login with credentials
        2. Use the returned access_token
        3. Include in Authorization header: 'Bearer <token>'
        
        **Token lifetime:** 1 hour (3600 seconds)
        **Refresh:** Use /auth/refresh endpoint
        """
    )
)

# API Key authentication
app.openapi_config.add_security_scheme(
    "ApiKeyAuth",
    APIKey(
        type="apiKey",
        name="X-API-Key",
        in_="header",
        description="""
        API Key authentication for programmatic access.
        
        **How to obtain:**
        1. Log into the developer portal
        2. Generate an API key for your application
        3. Include in X-API-Key header
        
        **Rate limits:** 1000 requests/hour per key
        """
    )
)

# OAuth2 with multiple flows
app.openapi_config.add_security_scheme(
    "OAuth2",
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
                    "orders:read": "Read access to orders",
                    "orders:write": "Create and modify orders",
                    "products:read": "Read access to products",
                    "products:write": "Create and modify products"
                }
            },
            "clientCredentials": {
                "tokenUrl": "https://auth.example.com/oauth/token",
                "scopes": {
                    "api:read": "Read API access",
                    "api:write": "Write API access"
                }
            }
        },
        description="OAuth2 authentication with authorization code and client credentials flows"
    )
)

# Admin-only API key
app.openapi_config.add_security_scheme(
    "AdminKey",
    APIKey(
        type="apiKey",
        name="X-Admin-Key",
        in_="header",
        description="Administrative API key for elevated operations"
    )
)
```

##  Multiple Environments Configuration

Configure different environments with appropriate settings:

```python
import os
from sillo import SilloApp

# Environment-based configuration
environment = os.getenv('ENVIRONMENT', 'development')

if environment == 'production':
    app = SilloApp(
        title="E-Commerce API",
        version="2.1.0",
        description="Production e-commerce API"
    )
    
    app.openapi_config.openapi_spec.servers = [
        Server(
            url="https://api.example.com/v2",
            description="Production server"
        )
    ]
    
elif environment == 'staging':
    app = SilloApp(
        title="E-Commerce API (Staging)",
        version="2.1.0-staging",
        description="Staging environment for testing"
    )
    
    app.openapi_config.openapi_spec.servers = [
        Server(
            url="https://staging-api.example.com/v2",
            description="Staging server"
        )
    ]
    
else:  # development
    app = SilloApp(
        title="E-Commerce API (Development)",
        version="2.1.0-dev",
        description="Development environment"
    )
    
    app.openapi_config.openapi_spec.servers = [
        Server(
            url="http://localhost:8000",
            description="Local development server"
        )
    ]

# Environment-specific contact info
if environment == 'production':
    app.openapi_config.openapi_spec.info.contact = Contact(
        name="Production Support",
        email="support@example.com",
        url="https://example.com/support"
    )
else:
    app.openapi_config.openapi_spec.info.contact = Contact(
        name="Development Team",
        email="dev-team@example.com",
        url="https://dev.example.com/support"
    )
```

##  Custom Documentation URLs

Customize the documentation endpoint URLs to match your preferences:

Paths are set at construction, because the routes are registered there:

```python
from sillo.openapi.ui import Atlas, ReDoc

app = SilloApp(
    title="Custom API",
    version="1.0.0",
    openapi_url="/api-spec.json",
    docs=[
        Atlas(path="/api-docs"),
        ReDoc(path="/api-reference"),
    ],
)

# Documentation is now available at:
# - /api-docs      (Atlas)
# - /api-reference (ReDoc)
# - /api-spec.json (OpenAPI JSON)
```

To drop a viewer, leave it out of the list:

```python
app = SilloApp(docs=[Atlas()])     # Atlas only
app = SilloApp(docs=[])            # no documentation UI at all
```

<aside type="caution">

**Assigning to `app.openapi.swagger_url` after construction does nothing.** The
routes are registered during `__init__`, so a later assignment changes an
attribute nobody reads again. `/docs` keeps serving and the new path 404s.
Setting `app.openapi.redoc_url = None` likewise does not disable ReDoc. Pass
`docs=` instead.

</aside>

See [Documentation UI](/v0.x/guides/openapi/documentation-ui/) for configuring
the viewers themselves.

##  Custom Response Examples

Add comprehensive examples to your OpenAPI specification:

```python
from sillo.openapi.models import Example

# Add reusable examples
app.openapi_config.add_example(
    "UserExample",
    Example(
        summary="Example user",
        description="A typical user object with all fields populated",
        value={
            "id": 123,
            "username": "johndoe",
            "email": "john@example.com",
            "full_name": "John Doe",
            "is_active": True,
            "created_at": "2024-01-01T12:00:00Z",
            "profile": {
                "bio": "Software developer",
                "avatar_url": "https://example.com/avatar.jpg"
            }
        }
    )
)

app.openapi_config.add_example(
    "ErrorExample",
    Example(
        summary="Error response",
        description="Standard error response format",
        value={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "code": 400,
            "details": {
                "field_errors": [
                    {
                        "field": "email",
                        "message": "Invalid email format"
                    }
                ]
            },
            "timestamp": "2024-01-01T12:00:00Z"
        }
    )
)
```

##  Advanced Customization

###  Custom OpenAPI Extensions

Add custom extensions for specific tooling or documentation needs:

```python
# Add custom extensions to the OpenAPI spec
app.openapi_config.openapi_spec.info.extensions = {
    "x-api-id": "ecommerce-api-v2",
    "x-audience": "external",
    "x-maturity": "stable",
    "x-category": "business"
}

# Add custom extensions to specific endpoints
@app.get(
    "/products/{product_id}",
    summary="Get product details",
    **{
        "x-code-samples": [
            {
                "lang": "curl",
                "source": "curl -X GET https://api.example.com/products/123"
            },
            {
                "lang": "python",
                "source": "import requests\nresponse = requests.get('https://api.example.com/products/123')"
            }
        ],
        "x-rate-limit": {
            "limit": 100,
            "window": "1h"
        }
    }
)
async def get_product(request, response, product_id: int):
    return response.json({"id": product_id, "name": "Product Name"})
```

###  Conditional Documentation

Show different documentation based on user roles or API versions:

```python
def create_api_for_role(role: str):
    """Create API instance with role-specific documentation"""
    
    if role == "admin":
        app = SilloApp(
            title="Admin API",
            version="2.1.0",
            description="Administrative interface with full access"
        )
        
        @app.get("/admin/users", tags=["Admin"])
        async def admin_list_users(request, response):
            return response.json({"users": []})
            
    elif role == "partner":
        app = SilloApp(
            title="Partner API",
            version="2.1.0",
            description="Partner integration API with limited access"
        )
        
        @app.get("/partner/orders", tags=["Orders"])
        async def partner_orders(request, response):
            return response.json({"orders": []})
            
    else:  # public
        app = SilloApp(
            title="Public API",
            version="2.1.0",
            description="Public API with read-only access"
        )
        
        @app.get("/products", tags=["Products"])
        async def public_products(request, response):
            return response.json({"products": []})
    
    return app

# Usage
admin_app = create_api_for_role("admin")
partner_app = create_api_for_role("partner")
public_app = create_api_for_role("public")
```

##  Documentation Analytics

Track documentation usage and effectiveness:

```python
# Add analytics tracking to documentation
@app.get("/docs-analytics")
async def docs_analytics(request, response):
    """Track documentation page views"""
    # Log documentation access
    user_agent = request.headers.get('User-Agent', '')
    referrer = request.headers.get('Referer', '')
    
    # Track metrics (implement your analytics logic)
    await track_docs_access(user_agent, referrer)
    
    return response.json({"tracked": True})

# Custom documentation with analytics
custom_docs_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>API Documentation</title>
    <!-- Analytics tracking -->
    <script>
        // Your analytics code here
        gtag('event', 'page_view', {{
            'page_title': 'API Documentation',
            'page_location': window.location.href
        }});
    </script>
</head>
<body>
    <!-- Your custom documentation UI -->
</body>
</html>
"""

@app.get("/custom-docs")
async def custom_docs(request, response):
    return response.html(custom_docs_html)
```

##  Best Practices

###  Configuration Management

```python
# Use environment variables for configuration
import os

class APIConfig:
    TITLE = os.getenv('API_TITLE', 'Default API')
    VERSION = os.getenv('API_VERSION', '1.0.0')
    DESCRIPTION = os.getenv('API_DESCRIPTION', 'API Description')
    CONTACT_EMAIL = os.getenv('API_CONTACT_EMAIL', 'support@example.com')
    CONTACT_URL = os.getenv('API_CONTACT_URL', 'https://example.com/support')
    LICENSE_NAME = os.getenv('API_LICENSE_NAME', 'MIT')
    LICENSE_URL = os.getenv('API_LICENSE_URL', 'https://opensource.org/licenses/MIT')
    TERMS_URL = os.getenv('API_TERMS_URL', 'https://example.com/terms')

app = SilloApp(
    title=APIConfig.TITLE,
    version=APIConfig.VERSION,
    description=APIConfig.DESCRIPTION
)

app.openapi_config.openapi_spec.info.contact = Contact(
    email=APIConfig.CONTACT_EMAIL,
    url=APIConfig.CONTACT_URL
)

app.openapi_config.openapi_spec.info.license = License(
    name=APIConfig.LICENSE_NAME,
    url=APIConfig.LICENSE_URL
)

app.openapi_config.openapi_spec.info.termsOfService = APIConfig.TERMS_URL
```

###  Version Management

```python
# Semantic versioning with detailed information
VERSION_INFO = {
    "version": "2.1.0",
    "build": "20240101.1200",
    "commit": "abc123def456",
    "release_date": "2024-01-01",
    "changelog_url": "https://example.com/changelog/v2.1.0"
}

app = SilloApp(
    title="Versioned API",
    version=VERSION_INFO["version"],
    description=f"""
    API Version: {VERSION_INFO['version']}
    Build: {VERSION_INFO['build']}
    Release Date: {VERSION_INFO['release_date']}
    
    [View Changelog]({VERSION_INFO['changelog_url']})
    """
)
```

###  Documentation Testing

```python
def test_openapi_spec():
    """Test OpenAPI specification validity"""
    spec = app.openapi.get_openapi(app.router)
    
    # Validate required fields
    assert spec['openapi'] == '3.0.0'
    assert spec['info']['title']
    assert spec['info']['version']
    
    # Validate paths exist
    assert 'paths' in spec
    assert len(spec['paths']) > 0
    
    # Validate security schemes
    if 'components' in spec and 'securitySchemes' in spec['components']:
        for scheme_name, scheme in spec['components']['securitySchemes'].items():
            assert 'type' in scheme
            assert scheme['type'] in ['http', 'apiKey', 'oauth2', 'openIdConnect']
```

Customizing your OpenAPI configuration is essential for creating professional, comprehensive API documentation that serves both your development team and API consumers effectively. Proper configuration enhances developer experience, reduces support overhead, and ensures compliance with enterprise standards.


##  Servers, environments, and the URL problem

The `servers` list tells clients where to send requests, and it is the
field most often wrong. A schema generated in CI and served from staging
that lists `https://api.example.com` will send every integrator
experimenting in your staging docs to production.

Derive it from configuration rather than hard-coding:

```python title="servers per environment"
import os

SERVERS = {
    "production": [{"url": "https://api.example.com", "description": "Production"}],
    "staging": [{"url": "https://staging-api.example.com", "description": "Staging"}],
    "development": [{"url": "http://localhost:8000", "description": "Local"}],
}[os.getenv("ENV", "development")]
```

List production first when you list several. Interactive UIs default to
the first entry, and the default is what most people will use without
noticing there was a choice.

##  Versioning the document

The `version` field is the version of your **API**, not of your
application. Bumping it because you deployed is noise; bumping it because
the contract changed is signal.

Two workable conventions. Semantic versioning of the contract, where the major
version increments only on a breaking change, gives clients a single number
that answers "will my code still work". Date-based versioning (`2026-03-01`)
suits APIs that ship changes continuously and lets clients pin to a date they
tested against.

Whichever you choose, the important part is that it changes when the
contract changes and not otherwise. A version that increments on every
deploy carries no information, and clients learn to ignore it.

##  Tags are the navigation

Beyond about twenty endpoints, the tag list is how anyone finds anything.
Two rules make it work.

**Tag by resource, not by layer.** `Orders`, `Customers`, `Invoices`: not `GET
endpoints`, `Admin`, `V2`. A reader arrives looking for a noun.

**Order tags deliberately.** Declaring tag metadata at the application
level fixes the order in the UI and lets each tag carry a description.
Without it, tags appear in whatever order routes were registered, which
is an implementation detail leaking into your documentation's navigation.

A tag description is a good place for the prose the schema cannot carry:
the lifecycle of the resource, the states it moves through, and the
endpoints that must be called in order.

##  Deciding what not to publish

Not every route belongs in the document. Exclude health checks, metrics
endpoints, internal callbacks, and anything mounted for operational
tooling. They add noise for integrators and surface for attackers, and
nobody generates a client for `/healthz`.

The same applies to fields. A response model that includes an internal
correlation id documents an implementation detail clients will start
depending on. Publishing a field is a commitment to keep sending it.


##  Contact, licence, and terms

Three fields nobody fills in and every integrator eventually needs.

`contact` is where someone goes when the documentation does not answer
their question. An address that reaches a human beats a perfect schema
with no escape hatch.

`license` matters for public APIs, because it tells consumers what they may do
with responses, an API returning data under an open licence and one returning
proprietary data look identical without it.

`termsOfService` is a link, and having one saves the conversation about
rate limits, acceptable use, and what happens when you deprecate
something.

None of these change behaviour. All of them appear at the top of the
rendered documentation, which is exactly where someone deciding whether
to integrate is looking.
