"""Pydantic-backed validation engine for sillo.

This package is the single source of truth for how sillo parses, coerces,
validates, and documents everything a route consumes and produces. Declaring a
parameter with a marker gives you validation, type coercion, and an OpenAPI
entry from one declaration, so the published schema and the runtime behavior
cannot drift apart.

Parameters are declared as handler defaults, sillo-style, with the type on the
marker — type annotations are never required and are never read::

    from sillo import Query, Path

    @app.post("/teams/{team_id}/users",
              request_model=UserCreate,
              response_model=UserOut)
    async def create_user(request, response, user,
                          team_id=Path(type=int),
                          notify=Query(False, type=bool)):
        ...

The JSON body is the one input declared on the decorator rather than with a
marker, via ``request_model=``, so there is exactly one way to declare it. It
is injected into the handler's first plain parameter and composes freely with
dependencies, markers, and path parameters.

Every other location has a marker: ``Query``, ``Header``, ``Cookie``, ``Path``,
``Form``, and ``File``. Each route compiles one Pydantic model per location at
registration time, so a request costs a fixed number of validation calls with
no signature introspection on the hot path.

Markers constructed the pre-Pydantic way — with only a default, ``alias``, or
``required`` — keep their original behavior exactly, so existing applications
are unaffected. Supplying a ``type`` or any constraint opts a parameter into
validation. To opt an entire application in at once, including markers written
the old way, construct it with ``silloApp(strict_validation=True)``.
"""

from .compiler import (
    CompiledValidator,
    LocationSpec,
    ResponseModelValidator,
    compile_validator,
    raise_if_errors,
)
from .errors import (
    RequestValidationError,
    ResponseValidationError,
    prefix_errors,
)
from .fields import (
    Cookie,
    File,
    Form,
    Header,
    ParameterExtractor,
    ParameterLocation,
    Path,
    Query,
    SolvedParamDependency,
    UploadFile,
    bind_marker,
    resolve_param,
    solve_params,
)

__all__ = [
    "Query",
    "Header",
    "Cookie",
    "Path",
    "Form",
    "File",
    "UploadFile",
    "ParameterLocation",
    "ParameterExtractor",
    "SolvedParamDependency",
    "solve_params",
    "resolve_param",
    "bind_marker",
    "CompiledValidator",
    "LocationSpec",
    "ResponseModelValidator",
    "compile_validator",
    "raise_if_errors",
    "RequestValidationError",
    "ResponseValidationError",
    "prefix_errors",
]
