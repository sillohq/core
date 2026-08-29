"""Middleware: the contract applications write against, and the plumbing under it.

What is where:

``base``
    :class:`~sillo.middleware.base.BaseMiddleware` — the contract. Subclass it
    and override ``dispatch(ctx, call_next)``.
``define``
    :class:`~sillo.middleware.define.DefineMiddleware`, the deferred
    factory-plus-arguments pair the chain builders iterate, and
    :func:`~sillo.middleware.define.wrap_middleware`, which normalises a
    dispatch function into one.
``bridge``
    :class:`~sillo.middleware.bridge.ASGIRequestResponseBridge` — how a
    dispatch middleware is mounted above an ASGI application, which cannot
    return a response object on its own.
``gzip``, ``security``
    Middleware that ships with the framework.
``utils``
    :func:`~sillo.middleware.utils.use_for_route`, to scope a middleware to a
    path pattern.

Only ``base`` and the shipped middleware are public API. ``define`` and
``bridge`` are how the framework assembles a chain; import them by their module
path rather than from here, which is also what keeps the security re-exports
below from becoming a cycle.

Those re-exports reach back into this package's own ``base`` module. Everything
under ``sillo.security`` imports ``BaseMiddleware`` from ``sillo.middleware.base``
directly rather than from this package, which is what keeps that from being a
cycle — importing it from here worked only while this file happened to bind
``BaseMiddleware`` before triggering the security import, so sorting these two
lines was enough to raise ImportError on ``import sillo``.
"""

from sillo.security.cors import CORSMiddleware
from sillo.security.csrf import CSRFMiddleware

from .base import BaseMiddleware

__all__ = ["BaseMiddleware", "CORSMiddleware", "CSRFMiddleware"]
