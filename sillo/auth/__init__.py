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
