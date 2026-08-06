from __future__ import annotations

import typing
from dataclasses import dataclass
from enum import Enum
from inspect import Parameter, signature
from typing import Any, List, Optional

from pydantic import Field
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

if typing.TYPE_CHECKING:
    from sillo.core.http import Request

__all__ = [
    "ParameterLocation",
    "ParameterExtractor",
    "Query",
    "Header",
    "Cookie",
    "Path",
    "Form",
    "File",
    "UploadFile",
    "SolvedParamDependency",
    "solve_params",
    "resolve_param",
]


class ParameterLocation(Enum):
    """Enumeration of locations from which request data can be extracted.

    Identifies which part of an HTTP request a declared parameter is sourced
    from. ``QUERY``, ``HEADER``, and ``COOKIE`` are the original three sillo
    locations; ``PATH``, ``BODY``, and ``FORM`` were added when validation
    moved onto Pydantic so that every input a handler can declare has a
    location, and so validation errors can report which one failed.

    Attributes:
        QUERY: Parameters from the URL query string (e.g. ``?key=value``).
        HEADER: Parameters from HTTP request headers (e.g. ``X-Custom``).
        COOKIE: Parameters from HTTP cookies sent by the client.
        PATH: Parameters captured from the URL path (e.g. ``/users/{id}``).
        BODY: The JSON request body, declared with the ``request_model=``
            route argument rather than a parameter marker.
        FORM: Fields from a urlencoded or multipart form body, including
            uploaded files.
    """

    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    PATH = "path"
    BODY = "body"
    FORM = "form"


#: Keyword arguments that carry Pydantic validation constraints. Supplying any
#: of these opts a marker into the validated code path — see
#: ``ParameterExtractor.is_legacy``.
_CONSTRAINT_KEYS = (
    "gt",
    "ge",
    "lt",
    "le",
    "multiple_of",
    "min_length",
    "max_length",
    "pattern",
    "strict",
)

#: Keyword arguments that only enrich generated documentation. These are
#: deliberately excluded from the legacy/validated decision so that adding a
#: description to an existing parameter cannot change its runtime behavior.
_METADATA_KEYS = ("title", "description", "example", "deprecated")


class ParameterExtractor:
    """Base class for every declared request parameter in sillo.

    A ``ParameterExtractor`` is placed as the default value of a handler
    parameter, where the framework detects it during signature analysis and
    wires up automatic extraction and validation. It is the single marker type
    the rest of the framework tests against, so ``isinstance`` checks that
    predate the Pydantic engine continue to recognize the newer markers.

    Each marker runs in one of two modes:

    **Legacy mode** — constructed with only ``default``, ``alias``, and
    ``required``. Behavior is byte-for-byte what sillo has always done:
    coercion is inferred from the runtime type of ``default`` (see
    ``_convert``), a missing required parameter raises ``ValueError``, and a
    parameter with no default yields the raw string. Existing applications keep
    working unchanged.

    **Validated mode** — constructed with an explicit ``type`` or any Pydantic
    constraint. The parameter is compiled into a Pydantic model field at route
    registration and validated per request, producing a proper 422 on bad or
    missing input instead of a 500.

    The mode is chosen by what the marker was constructed with, never by type
    annotations — sillo handlers are not required to annotate anything.

    Attributes:
        location: The ``ParameterLocation`` this marker reads from. Set by
            each subclass.
        default: Value used when the parameter is absent. ``...`` means no
            default was supplied.
        type: The declared type, or ``None`` to infer one from ``default``.
        alias: The wire name, when it differs from the Python parameter name.
        required: Legacy flag forcing an error when the value is absent.
        param_name: The Python parameter name, populated during signature
            analysis.
        constraints: Pydantic constraint keyword arguments that were supplied.
        metadata: Documentation-only keyword arguments that were supplied.
    """

    location: ParameterLocation = ParameterLocation.QUERY

    def __init__(
        self,
        default: Any = ...,
        *,
        type: Any = None,
        alias: Optional[str] = None,
        required: bool = False,
        title: Optional[str] = None,
        description: Optional[str] = None,
        example: Any = None,
        deprecated: Optional[bool] = None,
        gt: Any = None,
        ge: Any = None,
        lt: Any = None,
        le: Any = None,
        multiple_of: Any = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        pattern: Optional[str] = None,
        strict: Optional[bool] = None,
    ):
        """Initialize a parameter marker.

        Args:
            default: Value used when the parameter is missing from the request.
                Leave as ``...`` to indicate no default. In validated mode a
                marker with no default is a required field.
            type: The declared type used for validation and schema generation.
                Supplying this opts the marker into validated mode. When
                omitted, the type is inferred from ``default``.
            alias: The name to look for on the wire. Defaults to the Python
                parameter name, except for ``Header`` which converts to
                ``Header-Case``.
            required: Legacy flag. When ``True`` in legacy mode, a missing
                value raises ``ValueError``. In validated mode, omitting a
                default already makes the field required.
            title: Human-readable title for generated documentation.
            description: Description for generated documentation.
            example: Example value for generated documentation.
            deprecated: Marks the parameter deprecated in generated docs.
            gt: Value must be greater than this.
            ge: Value must be greater than or equal to this.
            lt: Value must be less than this.
            le: Value must be less than or equal to this.
            multiple_of: Value must be a multiple of this.
            min_length: Minimum length for strings and collections.
            max_length: Maximum length for strings and collections.
            pattern: Regular expression a string value must match.
            strict: Disables Pydantic's lax coercion for this field.
        """
        self.default = default
        self.type = type
        self.alias = alias
        self.required = required
        self.param_name: Optional[str] = None

        local = locals()
        self.constraints = {
            key: local[key] for key in _CONSTRAINT_KEYS if local[key] is not None
        }
        self.metadata = {
            key: local[key] for key in _METADATA_KEYS if local[key] is not None
        }

    @property
    def is_legacy(self) -> bool:
        """Whether this marker uses the pre-Pydantic extraction path.

        A marker stays legacy until it is given information that only the
        Pydantic engine can act on: an explicit ``type`` or a validation
        constraint. Documentation-only keywords such as ``description`` are
        deliberately not considered, so enriching a parameter's OpenAPI entry
        can never silently change how it validates at runtime.

        Returns:
            ``True`` when the marker should use the legacy ``extract`` path,
            ``False`` when it should be compiled into a Pydantic field.
        """
        return self.type is None and not self.constraints

    def resolve_type(self) -> Any:
        """Determine the type to validate this parameter against.

        Resolution never consults type annotations. It uses, in order: the
        explicit ``type`` argument; the runtime type of ``default`` (which
        reproduces sillo's historical inference so that ``Query(1)`` remains an
        integer and ``Query([])`` remains a list of strings); and finally
        ``str``, matching the legacy behavior of returning raw strings when
        there is nothing to infer from.

        Returns:
            The resolved type, suitable for use as a Pydantic field
            annotation.
        """
        if self.type is not None:
            return self.type
        if self.default is ... or self.default is None:
            return str
        if isinstance(self.default, list):
            item_type = builtin_type(self.default[0]) if self.default else str
            # The element type is computed from a runtime value.
            return List[item_type]  # ty: ignore[invalid-type-form]
        return builtin_type(self.default)

    def to_field_info(self) -> FieldInfo:
        """Build the Pydantic ``FieldInfo`` describing this parameter.

        Combines the default, wire alias, validation constraints, and
        documentation metadata into the single object the compiler hands to
        ``pydantic.create_model``. Using one ``FieldInfo`` for both validation
        and schema generation is what keeps the OpenAPI document and runtime
        behavior from drifting apart.

        Returns:
            A ``FieldInfo`` whose default is ``...`` when the parameter is
            required, and whose alias matches the name expected on the wire.
        """
        kwargs: dict = dict(self.constraints)
        if "example" in self.metadata:
            kwargs["examples"] = [self.metadata["example"]]
        for key in ("title", "description", "deprecated"):
            if key in self.metadata:
                kwargs[key] = self.metadata[key]

        alias = self._get_param_name()
        if alias:
            kwargs["alias"] = alias

        default = ... if (self.default is ... or self.required) else self.default
        return Field(default, **kwargs)

    def extract(self, request: "Request | None") -> Any:
        """Extract this parameter's value from the request (legacy path).

        Subclasses that read from a synchronously-available part of the request
        override this. Markers whose source requires awaiting the request body
        (``Body``, ``Form``, ``File``) never take this path — they are always
        compiled and resolved asynchronously.

        Args:
            request: The incoming request, or ``None`` when no request context
                is available.

        Returns:
            The extracted, coerced parameter value.

        Raises:
            NotImplementedError: Always, in the base class.
        """
        raise NotImplementedError

    def _extract_from(self, source: Any, request: "Request | None") -> Any:
        """Look a value up in a mapping and apply legacy coercion.

        Shared implementation behind ``Query.extract``, ``Header.extract``, and
        ``Cookie.extract``, which previously each carried an identical copy of
        this logic.

        Args:
            source: The request mapping to read from, such as
                ``request.query_params`` or ``request.headers``.
            request: The incoming request, or ``None``. When ``None``, the
                default is returned without any lookup.

        Returns:
            The coerced value, or the configured default when the parameter is
            absent, or ``None`` when it is absent and no default was given.

        Raises:
            ValueError: If ``required`` is set and the value is absent.
        """
        if request is None:
            return self.default

        param_name = self._get_param_name()
        if not param_name:
            return self.default

        value = source.get(param_name)

        if value is None:
            if self.required:
                raise ValueError(
                    f"{self.location.value.capitalize()} parameter "
                    f"'{param_name}' is required"
                )
            if self.default is ...:
                return None
            return self.default

        return self._convert(value, self.default)

    def _get_param_name(self) -> Optional[str]:
        """Get the effective name used to look this parameter up on the wire.

        Returns:
            The alias if one was configured, otherwise the Python parameter
            name recorded during signature analysis, or ``None`` if neither is
            available.
        """
        if self.alias:
            return self.alias
        return self.param_name

    def _convert_param_to_header_name(self, param_name: str) -> str:
        """Convert a snake_case parameter name into HTTP header casing.

        Splits on underscores, title-cases each segment, and rejoins with
        hyphens, so ``x_custom_header`` becomes ``X-Custom-Header``.

        Args:
            param_name: The snake_case parameter name to convert.

        Returns:
            The header-cased name.
        """
        parts = param_name.split("_")
        return "-".join(part.title() for part in parts)

    def _convert(self, value: str, default: Any) -> Any:
        """Coerce a raw string using the runtime type of the default (legacy).

        This is sillo's original coercion strategy, preserved exactly. It keys
        off the *default value's* type rather than any declared type, which is
        why a marker with no default returns the raw string unchanged. Markers
        in validated mode never reach this method; they are coerced by Pydantic
        against their resolved type instead.

        Args:
            value: The raw string pulled from the request.
            default: The default value whose runtime type selects the target
                type. ``...`` and ``None`` both mean "leave the string alone".

        Returns:
            The converted value. Lists are produced by splitting on commas;
            enums are looked up by member name, falling back to the raw string.
        """
        if default is ...:
            return value
        if default is None:
            return value

        type_default = builtin_type(default)

        if type_default is bool:
            return value.lower() in ("true", "1", "yes")
        elif type_default is int:
            return int(value)
        elif type_default is float:
            return float(value)
        elif isinstance(default, list):
            if hasattr(default, "__iter__") and not isinstance(default, str):
                item_type = builtin_type(default[0]) if default else str
                if item_type in (int, float):
                    return [item_type(v) for v in value.split(",")]
                return value.split(",")
            return [value]
        elif isinstance(default, Enum):
            try:
                return type_default[value]
            except KeyError:
                return value

        return type_default(value)


# ``type`` is shadowed by the ``type`` keyword argument inside the marker
# classes, so keep a module-level handle on the builtin.
builtin_type = type


class Query(ParameterExtractor):
    """Extractor for a URL query string parameter.

    Reads from the portion of the URL after ``?``. Used as a handler parameter
    default::

        async def handler(request, response, page=Query(1, type=int, ge=1)):
            ...

    Attributes:
        location: Always ``ParameterLocation.QUERY``.
    """

    location = ParameterLocation.QUERY

    def extract(self, request: "Request | None") -> Any:
        """Read this parameter from the request's query string.

        Args:
            request: The incoming request, or ``None`` when unavailable.

        Returns:
            The coerced query parameter value, or the configured default.

        Raises:
            ValueError: If the parameter is required and absent.
        """
        return self._extract_from(
            request.query_params if request is not None else None, request
        )


class Header(ParameterExtractor):
    """Extractor for an HTTP request header.

    Parameter names are converted to header casing automatically, so a
    parameter called ``x_api_key`` reads the ``X-Api-Key`` header unless an
    explicit ``alias`` is given.

    Attributes:
        location: Always ``ParameterLocation.HEADER``.
    """

    location = ParameterLocation.HEADER

    def extract(self, request: "Request | None") -> Any:
        """Read this parameter from the request's headers.

        Args:
            request: The incoming request, or ``None`` when unavailable.

        Returns:
            The coerced header value, or the configured default.

        Raises:
            ValueError: If the header is required and absent.
        """
        return self._extract_from(
            request.headers if request is not None else None, request
        )


class Cookie(ParameterExtractor):
    """Extractor for a cookie sent by the client.

    Attributes:
        location: Always ``ParameterLocation.COOKIE``.
    """

    location = ParameterLocation.COOKIE

    def extract(self, request: "Request | None") -> Any:
        """Read this parameter from the request's cookies.

        Args:
            request: The incoming request, or ``None`` when unavailable.

        Returns:
            The coerced cookie value, or the configured default.

        Raises:
            ValueError: If the cookie is required and absent.
        """
        return self._extract_from(
            request.cookies if request is not None else None, request
        )


class Path(ParameterExtractor):
    """Extractor for a URL path parameter.

    Path values have already been through the route's regex convertors by the
    time this marker sees them (``/users/{id:int}`` yields an ``int``), so this
    marker layers declared-type validation and constraints on top rather than
    replacing that step. Declaring ``Path`` lets a plain ``/users/{id}`` route
    validate ``id`` without embedding the type in the URL pattern.

    A path parameter is always required — a request that lacked it could not
    have matched the route — so ``default`` is ignored for requiredness.

    Attributes:
        location: Always ``ParameterLocation.PATH``.
    """

    location = ParameterLocation.PATH

    def extract(self, request: "Request | None") -> Any:
        """Read this parameter from the request's matched path parameters.

        Args:
            request: The incoming request, or ``None`` when unavailable.

        Returns:
            The path parameter value, or the configured default.
        """
        return self._extract_from(
            request.path_params if request is not None else None, request
        )

    def to_field_info(self) -> FieldInfo:
        """Build a Pydantic field that is always required.

        Overrides the base implementation because a path parameter cannot be
        absent from a request that matched the route, so a default would be
        unreachable and would wrongly render the parameter optional in the
        OpenAPI document.

        Returns:
            A required ``FieldInfo`` carrying this parameter's constraints.
        """
        info = super().to_field_info()
        # Assigning ``...`` here would not work: Ellipsis is only meaningful to
        # ``Field()``, which translates it. Assigned directly it becomes a
        # literal default value, leaving the field optional and able to inject
        # Ellipsis into a handler. PydanticUndefined is what marks it required.
        info.default = PydanticUndefined
        return info


class Form(ParameterExtractor):
    """Marker for a field in a urlencoded or multipart form body.

    Declaring any ``Form`` or ``File`` parameter switches the route to parsing
    the body as a form rather than as JSON.

    Attributes:
        location: Always ``ParameterLocation.FORM``.
    """

    location = ParameterLocation.FORM

    @property
    def is_legacy(self) -> bool:
        """Whether this marker uses the legacy path.

        Returns:
            Always ``False``. Form field binding did not exist before the
            Pydantic engine.
        """
        return False


class File(Form):
    """Marker for an uploaded file in a multipart form body.

    The value is delivered as the framework's ``UploadedFile`` and is passed
    through without Pydantic coercion, since the object wraps a spooled file
    handle rather than data Pydantic can meaningfully validate. Constraints
    such as ``min_length`` therefore do not apply to file parameters.

    Attributes:
        location: Always ``ParameterLocation.FORM``.
    """

    def resolve_type(self) -> Any:
        """Determine the type for this file parameter.

        Returns:
            The explicitly declared ``type`` if one was given, otherwise
            ``UploadedFile``.
        """
        if self.type is not None:
            return self.type
        return UploadFile


@dataclass(frozen=True, slots=True)
class SolvedParamDependency:
    """A parameter marker bound to the handler parameter name it fills.

    Produced during signature analysis and consumed at request time by the
    legacy extraction path. Frozen and slotted because an application may hold
    a great many of these across its routes.

    Attributes:
        extractor: The marker responsible for producing the value.
        param_name: The Python parameter name it is bound to.
    """

    extractor: ParameterExtractor
    param_name: str


def bind_marker(extractor: ParameterExtractor, param_name: str) -> None:
    """Bind a marker to a handler parameter name and derive its wire alias.

    Records the Python parameter name on the marker and, when no explicit alias
    was configured, derives one: ``Header`` markers get header casing, every
    other location uses the parameter name verbatim.

    This is the single implementation of a step that was previously duplicated
    between ``solve_params`` and the dependency analyzer, which risked the two
    drifting apart.

    Args:
        extractor: The marker to bind. Mutated in place.
        param_name: The Python parameter name the marker was found on.
    """
    extractor.param_name = param_name
    if not extractor.alias:
        if isinstance(extractor, Header):
            extractor.alias = extractor._convert_param_to_header_name(param_name)
        else:
            extractor.alias = param_name


def solve_params(handler: Any) -> List[SolvedParamDependency]:
    """Introspect a callable and collect its parameter markers.

    Scans the signature for parameters whose default is a
    ``ParameterExtractor``, binds each one to its parameter name, and returns
    them in signature order.

    Args:
        handler: Any callable with an inspectable signature.

    Returns:
        A list of ``SolvedParamDependency`` objects, one per marker found.
    """
    sig = signature(handler)
    solved = []

    for param_name, param in sig.parameters.items():
        if param.default is not Parameter.empty:
            if isinstance(param.default, ParameterExtractor):
                bind_marker(param.default, param_name)
                solved.append(SolvedParamDependency(param.default, param_name))

    return solved


async def resolve_param(
    param_dep: SolvedParamDependency,
    request: "Optional[Request]" = None,
) -> Any:
    """Resolve a single parameter dependency by extracting its value.

    Async purely to present a uniform interface alongside the other dependency
    resolution paths; the extraction itself is synchronous.

    Args:
        param_dep: The bound marker to resolve.
        request: The incoming request, or ``None`` when unavailable.

    Returns:
        The extracted parameter value.
    """
    return param_dep.extractor.extract(request)


# Imported last: sillo.objects.http pulls in the datastructures module, and
# importing it at the top would create a cycle for modules that import fields
# during their own initialization.
from sillo.objects.http import UploadedFile as UploadFile  # noqa: E402
