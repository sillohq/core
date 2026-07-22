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

from .decorator import auth, has_permission
from .middleware import AuthenticationMiddleware
from .use_auth import useAuth

from . import jwt_auth, session_auth, apikey

from sillo.users import BaseUser, SimpleUser

APIKeyAuthBackend = apikey.APIKeyAuthBackend
JWTAuthBackend = jwt_auth.JWTAuthBackend
create_jwt = jwt_auth.create_jwt
decode_jwt = jwt_auth.decode_jwt

__all__ = [
    "AuthenticationMiddleware",
    "APIKeyAuthBackend",
    "JWTAuthBackend",
    "create_jwt",
    "decode_jwt",
    "useAuth",
    "BaseUser",
    "SimpleUser",
    "jwt_auth",
    "session_auth",
    "apikey",
]
