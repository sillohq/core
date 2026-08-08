"""Session-based authentication module for the sillo framework.

This package provides server-side session authentication, including the
session auth backend, login/logout helpers, the session guard, and the
session user mixin. It exports all public classes and functions needed
to integrate session-based authentication into a sillo application.

The session authentication flow works by storing user identity information
in a server-managed session after successful login. Subsequent requests
are authenticated by looking up the session data associated with the
request. This module requires the session middleware to be installed in
the application middleware stack.
"""

from sillo.auth.session_auth.backend import SessionAuthBackend, login, logout
from sillo.auth.session_auth.guard import SessionGuard
from sillo.auth.session_auth.mixins import SessionUserMixin
from sillo.auth.session_auth.models import Session

__all__ = [
    "Session",
    "SessionAuthBackend",
    "SessionGuard",
    "SessionUserMixin",
    "login",
    "logout",
]
