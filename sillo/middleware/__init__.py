"""Middleware base class and the security middleware re-exported beside it.

The security imports below reach back into this package's own ``base`` module.
Everything under ``sillo.security`` now imports ``BaseMiddleware`` from
``sillo.middleware.base`` directly rather than from this package, which is what
keeps that from being a cycle — importing it from here worked only while this
file happened to bind ``BaseMiddleware`` before triggering the security import,
so sorting these two lines was enough to raise ImportError on ``import sillo``.
"""

from sillo.security.cors import CORSMiddleware
from sillo.security.csrf import CSRFMiddleware

from .base import BaseMiddleware

__all__ = ["BaseMiddleware", "CORSMiddleware", "CSRFMiddleware"]
