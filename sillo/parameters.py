from __future__ import annotations
from inspect import signature, Parameter

import typing
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar, List, Optional

if typing.TYPE_CHECKING:
    from sillo.http import Request


T = TypeVar("T")


class ParameterLocation(Enum):
    """Enumeration of locations from which request parameters can be extracted.

    Defines the source of a parameter value within an HTTP request. Each
    member corresponds to a distinct part of the request that can carry
    client-supplied data, and is used by ``ParameterExtractor`` subclasses
    to indicate where they should look for their values.

    Attributes:
        QUERY: Parameters extracted from the URL query string
            (e.g. ``?key=value``).
        HEADER: Parameters extracted from HTTP request headers
            (e.g. ``X-Custom-Header``).
        COOKIE: Parameters extracted from HTTP cookies sent by the client
            (e.g. ``Cookie: session=abc123``).
    """

    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"


class ParameterExtractor:
    """Base class for extracting parameters from request context.

    Provides the common infrastructure for all parameter extraction strategies
    including default value handling, alias resolution, type conversion, and
    required-field validation. Subclasses implement the ``extract`` method
    to pull values from specific parts of the HTTP request (query string,
    headers, cookies).

    Instances of this class (or its subclasses) are used as default values
    in handler function signatures, where the framework's dependency injection
    system detects them and wires up automatic parameter resolution.

    Attributes:
        default: The default value returned when the parameter is missing.
            Uses the sentinel ``...`` (Ellipsis) to indicate no default.
        alias: An alternative name for the parameter, used when the lookup
            key differs from the Python parameter name.
        required: If ``True``, raises ``ValueError`` when the parameter is
            missing from the request instead of returning the default.
        param_name: The resolved parameter name, set by the dependency
            injection system during handler introspection.

    Args:
        default: Default value if parameter is missing. Use ``...``
            (Ellipsis) to indicate no default is provided.
        alias: Alternative name for the parameter in the request. If not
            set, the Python parameter name is used.
        required: If ``True``, raise an error when the parameter is
            missing from the request. Defaults to ``False``.
    """

    def __init__(
        self,
        default: Any = ...,
        *,
        alias: str | None = None,
        required: bool = False,
    ):
        """Initialize the parameter extractor.

        Sets up the extractor with the provided default value, optional alias,
        and required flag. The ``param_name`` attribute is initialized to
        ``None`` and is populated later by the dependency injection system
        during handler signature introspection.

        Args:
            default: Default value if parameter is missing. Use ``...``
                (Ellipsis) to indicate no default is provided.
            alias: Alternative name for the parameter in the request. If
                not set, the Python parameter name is used during extraction.
            required: If ``True``, raise an error when the parameter is
                missing from the request. Defaults to ``False``.
        """
        self.default = default
        self.alias = alias
        self.required = required
        self.param_name: str | None = None

    def extract(self, request: Request | None) -> Any:
        """Extract the parameter value from the request context.

        Subclasses must override this method to implement the actual
        extraction logic for their specific parameter location (query string,
        headers, cookies). The base implementation raises
        ``NotImplementedError`` to enforce this contract.

        Args:
            request: The incoming HTTP request object, or ``None`` if no
                request context is available (e.g. during testing or
                background tasks).

        Returns:
            The extracted and type-converted parameter value.

        Raises:
            NotImplementedError: Always raised by the base class. Subclasses
                must provide a concrete implementation.
        """
        raise NotImplementedError

    def _get_param_name(self) -> str | None:
        """Get the effective parameter name for request lookups.

        Returns the alias if one was explicitly configured, otherwise falls
        back to the ``param_name`` attribute that was set by the dependency
        injection system. If neither is available, returns ``None``.

        Returns:
            The resolved parameter name string to use for looking up the
            value in the request, or ``None`` if no name is available.
        """
        if self.alias:
            return self.alias
        return self.param_name

    def _convert_param_to_header_name(self, param_name: str) -> str:
        """Convert a snake_case parameter name to an HTTP header name format.

        Splits the parameter name on underscores, capitalizes each segment,
        and joins them with hyphens to produce the standard HTTP header
        naming convention. For example, ``x_custom_header`` becomes
        ``X-Custom-Header``.

        Args:
            param_name: The snake_case parameter name to convert. Should
                be a valid Python identifier using underscores as separators.

        Returns:
            The converted header name string with each segment title-cased
            and segments joined by hyphens.
        """
        parts = param_name.split("_")
        return "-".join(part.title() for part in parts)

    def _convert(self, value: str, default: Any) -> Any:
        """Convert a string value to the expected type based on the default.

        Uses the type of the ``default`` value to determine the target type
        for conversion. Supports ``bool``, ``int``, ``float``, ``list``
        (with comma-separated items), ``Enum`` subclasses, and any type
        with a callable constructor. If the default is ``...`` (Ellipsis)
        or ``None``, the raw string value is returned unchanged.

        Args:
            value: The raw string value extracted from the request. This
                is typically a query parameter value, header value, or
                cookie value.
            default: The default value whose type determines the target
                conversion type. Special values ``...`` and ``None``
                cause the raw string to be returned as-is.

        Returns:
            The value converted to the type indicated by ``default``. For
            list defaults, returns a list of converted items split by
            commas. For enum defaults, attempts member lookup by name.
        """
        if default is ...:
            return value
        if default is None:
            return value

        type_default = type(default)

        if type_default is bool:
            return value.lower() in ("true", "1", "yes")
        elif type_default is int:
            return int(value)
        elif type_default is float:
            return float(value)
        elif isinstance(default, list):
            if hasattr(default, "__iter__") and not isinstance(default, str):
                item_type = type(default[0]) if default else str
                if item_type in (int, float):
                    return [item_type(v) for v in value.split(",")]
                return value.split(",")
            return [value]
        elif isinstance(default, Enum):
            try:
                return type(default)[value]
            except KeyError:
                return value

        return type_default(value)


class Query(ParameterExtractor):
    """Extractor for query string parameters from the URL.

    Retrieves parameter values from the URL query string (the portion after
    ``?`` in the URL). Supports type conversion, default values, aliases,
    and required-field validation through the base ``ParameterExtractor``
    infrastructure.

    Use this as a default value in handler signatures to automatically
    extract query parameters::

        async def handler(page: int = Query(1)):
            ...

    Attributes:
        location: The parameter location enum value, always ``QUERY``.
    """

    location = ParameterLocation.QUERY

    def extract(self, request: Request | None) -> Any:
        """Extract a query string parameter value from the request URL.

        Looks up the parameter name in the request's query parameters
        dictionary. If the parameter is not found, applies the configured
        default value or raises an error if the parameter is marked as
        required. Found values are type-converted based on the default.

        Args:
            request: The incoming HTTP request object containing the
                query parameters, or ``None`` if no request context
                is available.

        Returns:
            The extracted and type-converted query parameter value, or
            the default value if the parameter is missing and not required.

        Raises:
            ValueError: If the parameter is marked as required and is
                not present in the request query string.
        """
        if request is None:
            return self.default

        param_name = self._get_param_name()
        if not param_name:
            return self.default

        value = request.query_params.get(param_name)

        if value is None:
            if self.required:
                raise ValueError(f"Query parameter '{param_name}' is required")
            if self.default is ...:
                return None
            return self.default

        return self._convert(value, self.default)


class Header(ParameterExtractor):
    """Extractor for HTTP header parameters from the request.

    Retrieves parameter values from the HTTP request headers. Supports
    automatic snake_case to Header-Case conversion for parameter names
    (e.g. ``x_custom_header`` becomes ``X-Custom-Header``), type conversion,
    default values, aliases, and required-field validation through the
    base ``ParameterExtractor`` infrastructure.

    Use this as a default value in handler signatures to automatically
    extract header values::

        async def handler(auth: str = Header(...)):
            ...

    Attributes:
        location: The parameter location enum value, always ``HEADER``.
    """

    location = ParameterLocation.HEADER

    def extract(self, request: Request | None) -> Any:
        """Extract an HTTP header parameter value from the request.

        Looks up the parameter name in the request's headers dictionary.
        If the parameter is not found, applies the configured default value
        or raises an error if the parameter is marked as required. Found
        values are type-converted based on the default.

        Args:
            request: The incoming HTTP request object containing the
                headers, or ``None`` if no request context is available.

        Returns:
            The extracted and type-converted header value, or the default
            value if the header is missing and not required.

        Raises:
            ValueError: If the parameter is marked as required and is
                not present in the request headers.
        """
        if request is None:
            return self.default

        param_name = self._get_param_name()
        if not param_name:
            return self.default

        value = request.headers.get(param_name)

        if value is None:
            if self.required:
                raise ValueError(f"Header '{param_name}' is required")
            if self.default is ...:
                return None
            return self.default

        return self._convert(value, self.default)


class Cookie(ParameterExtractor):
    """Extractor for cookie parameters from the request.

    Retrieves parameter values from the HTTP cookies sent by the client.
    Supports type conversion, default values, aliases, and required-field
    validation through the base ``ParameterExtractor`` infrastructure.

    Use this as a default value in handler signatures to automatically
    extract cookie values::

        async def handler(session: str = Cookie(None)):
            ...

    Attributes:
        location: The parameter location enum value, always ``COOKIE``.
    """

    location = ParameterLocation.COOKIE

    def extract(self, request: Request | None) -> Any:
        """Extract a cookie parameter value from the request.

        Looks up the parameter name in the request's cookies dictionary.
        If the parameter is not found, applies the configured default value
        or raises an error if the parameter is marked as required. Found
        values are type-converted based on the default.

        Args:
            request: The incoming HTTP request object containing the
                cookies, or ``None`` if no request context is available.

        Returns:
            The extracted and type-converted cookie value, or the default
            value if the cookie is missing and not required.

        Raises:
            ValueError: If the parameter is marked as required and is
                not present in the request cookies.
        """
        if request is None:
            return self.default

        param_name = self._get_param_name()
        if not param_name:
            return self.default

        value = request.cookies.get(param_name)

        if value is None:
            if self.required:
                raise ValueError(f"Cookie '{param_name}' is required")
            if self.default is ...:
                return None
            return self.default

        return self._convert(value, self.default)


@dataclass(frozen=True, slots=True)
class SolvedParamDependency:
    """A resolved parameter dependency pairing an extractor with its name.

    Represents a single parameter that has been introspected from a handler
    function signature and bound to its corresponding ``ParameterExtractor``
    instance. Created by the ``solve_params`` function during handler
    registration and consumed by the dependency injection system at
    request time.

    This dataclass is immutable (frozen) and uses ``__slots__`` for
    memory efficiency, since many instances may exist in applications
    with numerous handler parameters.

    Attributes:
        extractor: The ``ParameterExtractor`` instance responsible for
            extracting the parameter value from the request at runtime.
        param_name: The Python parameter name from the handler function
            signature that this dependency is bound to.
    """

    extractor: ParameterExtractor
    param_name: str


def solve_params(handler: Any) -> List["SolvedParamDependency"]:
    """Introspect a handler function and resolve all parameter extractors.

    Examines the function signature of the given handler to find parameters
    whose default values are ``ParameterExtractor`` instances. For each such
    parameter, the extractor's ``param_name`` is set to the Python parameter
    name, and if no alias is configured, one is derived automatically.
    ``Header`` extractors receive a Header-Case alias (e.g. ``X-Custom``),
    while other extractors use the parameter name as-is.

    Args:
        handler: The handler function to introspect. Can be a regular
            function, async function, or any callable with a valid
            Python signature.

    Returns:
        A list of ``SolvedParamDependency`` objects, one for each
        parameter that has a ``ParameterExtractor`` as its default
        value. The list preserves the order of parameters in the
        function signature.
    """
    sig = signature(handler)
    solved = []

    for param_name, param in sig.parameters.items():
        if param.default is not Parameter.empty:
            if isinstance(param.default, ParameterExtractor):
                extractor = param.default
                extractor.param_name = param_name
                if not extractor.alias:
                    if isinstance(extractor, Header):
                        extractor.alias = extractor._convert_param_to_header_name(
                            param_name
                        )
                    else:
                        extractor.alias = param_name
                solved.append(SolvedParamDependency(extractor, param_name))

    return solved


async def resolve_param(
    param_dep: SolvedParamDependency,
    request: Optional["Request"] = None,
) -> Any:
    """Resolve a single parameter dependency by extracting its value.

    Delegates to the parameter dependency's extractor to pull the
    appropriate value from the incoming HTTP request. This is an async
    function to maintain a uniform interface with other dependency
    resolution mechanisms in the framework, even though the extraction
    itself is synchronous.

    Args:
        param_dep: The solved parameter dependency containing the
            extractor and resolved parameter name to use for extraction.
        request: The incoming HTTP request object from which to extract
            the parameter value. May be ``None`` if no request context
            is available.

    Returns:
        The extracted and type-converted parameter value as determined
        by the dependency's extractor. Returns the extractor's default
        value if the parameter is not present in the request.
    """
    return param_dep.extractor.extract(request)


__all__ = [
    "Query",
    "Header",
    "Cookie",
    "ParameterLocation",
    "ParameterExtractor",
    "SolvedParamDependency",
    "solve_params",
    "resolve_param",
]
