"""
sillo.security — Security utilities for sillo applications.

Provides CSRF protection, CORS middleware, and security header management.
All security-related features are consolidated here for a cohesive security API.

Usage::

    from sillo.security import CSRFConfig, CSRFMiddleware
    from sillo.security import CorsConfig, CORSMiddleware
    from sillo.security import Shield

    app = silloApp()
    app.use(CSRFMiddleware(config=CSRFConfig(enabled=True, secret_key="...")))
    app.use(CORSMiddleware(config=CorsConfig(allow_origins=["*"])))
    app.use(Shield())
"""

from .cors import CORSMiddleware, CorsConfig
from .csrf import CSRFConfig, CSRFMiddleware
from .shield import Shield

__all__ = [
    "CSRFConfig",
    "CSRFMiddleware",
    "CorsConfig",
    "CORSMiddleware",
    "Shield",
]
