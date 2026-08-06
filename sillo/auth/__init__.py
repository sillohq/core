"""Authentication package for the Sillo framework.

This package provides a comprehensive authentication system including
JWT-based authentication, session-based authentication, and API key
authentication backends. It exposes decorators, middleware, and utility
functions for securing application endpoints and managing user identity.

Attributes:
    AuthenticationMiddleware: ASGI middleware that performs authentication
        on every incoming request using configured backends.
    APIKeyAuthBackend: Authentication backend that validates API keys
        sent via HTTP headers.
    JWTAuthBackend: Authentication backend that validates JSON Web Tokens.
    create_jwt: Helper function to generate a signed JWT token.
    decode_jwt: Helper function to decode and verify a JWT token.
    useAuth: Dependency-injection helper for accessing the current
        authenticated user inside route handlers.
    BaseUser: Base user model class for authentication identities.
    SimpleUser: Lightweight user representation for common use cases.
"""

from sillo._internals.lazy import deferred
from sillo.users import BaseUser, SimpleUser

from .backend import AuthenticationBackend
from .decorator import auth, has_permission
from .middleware import AuthenticationMiddleware
from .use_auth import useAuth

# The session and API-key backends define Tortoise models, and the JWT one
# needs PyJWT. All three used to be imported here, which meant `import sillo`
# — this package is reached from the exception handler — required the `record`
# and `jwt` extras that are supposed to be optional. They load on first use
# instead; the import paths and __all__ are unchanged.
__getattr__ = deferred(
    __name__,
    {
        "apikey": ".apikey",
        "jwt_auth": ".jwt_auth",
        "session_auth": ".session_auth",
        "APIKeyAuthBackend": ".apikey",
        "JWTAuthBackend": ".jwt_auth",
        "SessionAuthBackend": ".session_auth",
        "create_jwt": ".jwt_auth",
        "decode_jwt": ".jwt_auth",
    },
)

__all__ = [
    "AuthenticationMiddleware",
    "AuthenticationBackend",
    "APIKeyAuthBackend",
    "JWTAuthBackend",
    "SessionAuthBackend",
    "create_jwt",
    "decode_jwt",
    "useAuth",
    "BaseUser",
    "SimpleUser",
    "jwt_auth",
    "session_auth",
    "apikey",
]
