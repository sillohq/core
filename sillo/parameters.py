"""Request parameter markers.

This module is the long-standing public import path for sillo's parameter
markers. The implementation now lives in :mod:`sillo.validation.fields`, where
the markers are backed by Pydantic, and is re-exported here unchanged so that
``from sillo.parameters import Query, Header, Cookie`` keeps working exactly as
before.

``Query``, ``Header``, and ``Cookie`` retain their original constructor
signatures and their original behavior when constructed the original way. They
additionally accept a ``type`` argument and Pydantic constraints, which opt the
parameter into validation — see :mod:`sillo.validation` for the full picture,
including the ``Path``, ``Body``, ``Form``, and ``File`` markers added
alongside them.
"""

from sillo.validation.fields import (
    Cookie,
    Header,
    ParameterExtractor,
    ParameterLocation,
    Query,
    SolvedParamDependency,
    bind_marker,
    resolve_param,
    solve_params,
)

__all__ = [
    "Query",
    "Header",
    "Cookie",
    "ParameterLocation",
    "ParameterExtractor",
    "SolvedParamDependency",
    "solve_params",
    "resolve_param",
    "bind_marker",
]
