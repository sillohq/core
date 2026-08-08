from __future__ import annotations

import typing
from collections.abc import Callable
from copy import copy
from dataclasses import dataclass, field
from operator import attrgetter
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from .errors import RequestValidationError, ResponseValidationError, prefix_errors
from .fields import (
    File,
    ParameterExtractor,
    ParameterLocation,
    SolvedParamDependency,
    bind_marker,
)

if typing.TYPE_CHECKING:
    from sillo.core.http import Request

__all__ = [
    "CompiledValidator",
    "LocationSpec",
    "ResponseModelValidator",
    "compile_validator",
]


_MODEL_CONFIG = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

#: Locations whose values are available on the request object without awaiting
#: the body. These are resolved together in a single synchronous pass.
_SYNC_LOCATIONS = (
    ParameterLocation.PATH,
    ParameterLocation.QUERY,
    ParameterLocation.HEADER,
    ParameterLocation.COOKIE,
)


#: Maps each synchronously-readable location to a C-level attribute getter for
#: the request attribute holding its values. Resolved once at registration so
#: the request path never branches to find its source.
_SOURCE_GETTERS = {
    ParameterLocation.QUERY: attrgetter("query_params"),
    ParameterLocation.HEADER: attrgetter("headers"),
    ParameterLocation.COOKIE: attrgetter("cookies"),
    ParameterLocation.PATH: attrgetter("path_params"),
}


def _is_sequence_type(tp: Any) -> bool:
    """Report whether a resolved type should read repeated request values.

    A parameter declared as a list or tuple maps to repeated occurrences of the
    same key (``?tag=a&tag=b``), which must be gathered with ``getlist`` rather
    than a plain ``get`` that would silently keep only the first.

    Args:
        tp: The resolved field type to inspect. May be a bare ``list``, a
            parameterized generic such as ``List[str]``, or any other type.

    Returns:
        ``True`` when values for this field should be collected as a list.
    """
    origin = typing.get_origin(tp) or tp
    return origin in (list, tuple, set, frozenset)


@dataclass(slots=True)
class LocationSpec:
    """A compiled Pydantic model covering every parameter from one location.

    Rather than validating each parameter individually, all parameters sharing
    a request location are folded into a single synthetic Pydantic model built
    once at route registration. Validating a location is then one
    ``model_validate`` call, and Pydantic reports every failure in that
    location at once instead of stopping at the first.

    Attributes:
        location: The request location this spec reads from.
        model: The synthetic Pydantic model whose fields are the parameters.
        markers: Mapping of handler parameter name to its declared marker.
        list_aliases: Wire names that must be gathered with ``getlist``.
        passthrough: Handler parameter names, mapped to their wire names, that
            bypass Pydantic entirely — uploaded files, whose spooled handles
            are not meaningfully validatable.
    """

    location: ParameterLocation
    model: type[BaseModel]
    markers: dict[str, ParameterExtractor] = field(default_factory=dict)
    list_aliases: frozenset = frozenset()
    passthrough: dict[str, str] = field(default_factory=dict)

    # --- Precomputed at registration; read-only at request time. -------------
    #: ``request`` attribute holding this location's values, as a C-level
    #: attrgetter so the hot path does no branching to find its source.
    source_getter: Callable[[Any], Any] | None = None
    #: Wire names read with a plain ``get``.
    scalar_aliases: tuple[str, ...] = ()
    #: Wire names read with ``getlist`` because the field is a sequence. Almost
    #: always empty, which lets the hot path skip that branch entirely.
    list_plan: tuple[str, ...] = ()
    #: ``(param_name, alias, default, is_required)`` for markers that bypass
    #: Pydantic — currently uploaded files.
    passthrough_plan: tuple[tuple[str, str, Any, bool], ...] = ()
    #: ``self.location.value``, resolved once to keep enum lookups off the
    #: error path.
    location_value: str = ""

    def gather(self, source: Any) -> dict[str, Any]:
        """Pull this location's raw values out of a request mapping.

        Walks precomputed alias tuples rather than re-deriving names, list-ness,
        and passthrough membership from the markers on every request.

        Absent keys are deliberately omitted from the result rather than set to
        ``None``, so Pydantic can distinguish "not supplied" (apply the default,
        or report the field as missing) from "explicitly null".

        Args:
            source: The request mapping to read, such as ``request.query_params``
                or ``request.headers``. May be ``None``.

        Returns:
            A dictionary keyed by wire name containing only the keys present in
            ``source``.
        """
        data: dict[str, Any] = {}
        if source is None:
            return data

        get = source.get
        for alias in self.scalar_aliases:
            value = get(alias)
            if value is not None:
                data[alias] = value

        if self.list_plan:
            getlist = getattr(source, "getlist", None)
            for alias in self.list_plan:
                if getlist is None:
                    value = get(alias)
                    if value is not None:
                        data[alias] = value
                    continue
                values = getlist(alias)
                if values:
                    data[alias] = values

        return data

    def validate(self, source: Any) -> tuple[dict[str, Any], Any]:
        """Validate this location and produce handler keyword arguments.

        Args:
            source: The request mapping to read this location's values from.

        Returns:
            A two-tuple of the validated values keyed by *handler parameter
            name*, and location-prefixed error dictionaries. On success the
            error sequence is empty; on failure the value dictionary is empty
            and every failure in this location is reported.
        """
        try:
            validated = self.model.model_validate(self.gather(source))
        except ValidationError as exc:
            return {}, prefix_errors(exc, self.location_value)

        # Field names are the handler parameter names by construction, so the
        # model's instance dict is already the kwargs mapping. Copying it beats
        # a getattr per field.
        values = dict(validated.__dict__)

        if not self.passthrough_plan:
            return values, ()

        missing = None
        for param_name, alias, default, required in self.passthrough_plan:
            found = source.get(alias) if source is not None else None
            if found is not None:
                values[param_name] = found
            elif required:
                if missing is None:
                    missing = []
                missing.append((alias,))
            else:
                values[param_name] = default

        if missing:
            return {}, [
                {
                    "loc": [self.location_value, alias],
                    "msg": "Field required",
                    "type": "missing",
                }
                for (alias,) in missing
            ]

        return values, ()


@dataclass(slots=True)
class CompiledValidator:
    """Everything needed to validate one route's inputs, compiled up front.

    All model construction happens once, when the route is registered. At
    request time the work is a fixed number of dictionary builds and
    ``model_validate`` calls with no introspection and no recursion, matching
    the pre-flattened execution plan the dependency injector already uses.

    JSON request bodies are not represented here — they are declared with the
    ``request_model=`` route argument and validated by the route itself, so
    there is exactly one way to declare a body.

    Attributes:
        specs: Compiled per-location models for path, query, header, and
            cookie — every location readable without awaiting the body.
        form_spec: A location spec covering ``Form`` and ``File`` parameters.
        legacy: Markers left on the pre-Pydantic extraction path, resolved by
            the existing synchronous extractor machinery.
    """

    specs: tuple[LocationSpec, ...] = ()
    form_spec: LocationSpec | None = None
    legacy: tuple[SolvedParamDependency, ...] = ()

    @property
    def needs_form(self) -> bool:
        """Whether this route must parse a form or multipart request body.

        Returns:
            ``True`` if any ``Form`` or ``File`` marker was declared.
        """
        return self.form_spec is not None

    @property
    def is_active(self) -> bool:
        """Whether this validator has any validated-mode work to do.

        Routes using only legacy markers compile to an inactive validator and
        skip the Pydantic path entirely, which is what keeps existing
        applications running on exactly their previous code path.

        Returns:
            ``True`` if any location was compiled into a model.
        """
        return bool(self.specs) or self.needs_form

    def validate_sync(
        self, request: Request
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Validate every location available without awaiting the body.

        Args:
            request: The incoming request.

        Returns:
            A two-tuple of validated handler keyword arguments and accumulated
            error dictionaries. Errors from all locations are gathered so a
            client sees every problem at once rather than one per round trip.
        """
        values: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []

        for spec in self.specs:
            if spec.source_getter is None:
                continue
            spec_values, spec_errors = spec.validate(spec.source_getter(request))
            values.update(spec_values)
            if spec_errors:
                errors.extend(spec_errors)

        return values, errors

    def validate_form(self, form: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Validate parsed form data against the route's form declarations.

        Args:
            form: The parsed ``FormData`` mapping, containing string fields and
                ``UploadedFile`` objects.

        Returns:
            A two-tuple of validated handler keyword arguments and error
            dictionaries.
        """
        if self.form_spec is None:
            return {}, []
        return self.form_spec.validate(form)


def _build_spec(
    location: ParameterLocation,
    markers: list[tuple[str, ParameterExtractor]],
    model_name: str,
) -> LocationSpec:
    """Compile one location's markers into a synthetic Pydantic model.

    Args:
        location: The request location the markers belong to.
        markers: ``(handler parameter name, marker)`` pairs for this location.
        model_name: Name given to the generated model, used in error messages
            and generated schema component names.

    Returns:
        A ``LocationSpec`` holding the generated model and the metadata needed
        to feed it at request time.
    """
    definitions: dict[str, Any] = {}
    list_aliases = set()
    passthrough: dict[str, str] = {}
    by_name: dict[str, ParameterExtractor] = {}

    for param_name, marker in markers:
        by_name[param_name] = marker
        alias = marker._get_param_name() or param_name

        if isinstance(marker, File):
            passthrough[param_name] = alias
            continue

        resolved = marker.resolve_type()
        if _is_sequence_type(resolved):
            list_aliases.add(alias)
        definitions[param_name] = (resolved, marker.to_field_info())

    model = create_model(  # type: ignore[call-overload]
        model_name, __config__=_MODEL_CONFIG, **definitions
    )

    # Flatten everything the request path would otherwise re-derive: which wire
    # name each field reads, whether it needs getlist, and what a missing
    # passthrough value should fall back to.
    scalar_aliases = []
    list_plan = []
    for param_name in definitions:
        alias = by_name[param_name]._get_param_name() or param_name
        if alias in list_aliases:
            list_plan.append(alias)
        else:
            scalar_aliases.append(alias)

    passthrough_plan = tuple(
        (
            param_name,
            alias,
            by_name[param_name].default,
            by_name[param_name].default is ...,
        )
        for param_name, alias in passthrough.items()
    )

    return LocationSpec(
        location=location,
        model=model,
        markers=by_name,
        list_aliases=frozenset(list_aliases),
        passthrough=passthrough,
        source_getter=_SOURCE_GETTERS.get(location),
        scalar_aliases=tuple(scalar_aliases),
        list_plan=tuple(list_plan),
        passthrough_plan=passthrough_plan,
        location_value=location.value,
    )


def compile_validator(
    markers: list[tuple[str, ParameterExtractor]],
    *,
    name: str = "Route",
    strict: bool = False,
) -> CompiledValidator:
    """Compile a callable's parameter markers into a request validator.

    Markers are partitioned into the legacy extraction path and the Pydantic
    path, then the Pydantic ones are grouped by location and each group
    compiled into a single model. This runs once per route at registration.

    Args:
        markers: ``(handler parameter name, marker)`` pairs discovered on the
            callable's signature, in signature order.
        name: A prefix for generated model names, normally derived from the
            handler's name, to keep generated schema components readable.
        strict: When ``True``, legacy-style markers are compiled onto the
            Pydantic path too. This is the application-level opt-in that turns
            missing or malformed parameters into 422 responses instead of the
            historical 500.

    Returns:
        A ``CompiledValidator`` ready to be stored on the route.
    """
    legacy: list[SolvedParamDependency] = []
    grouped: dict[ParameterLocation, list[tuple[str, ParameterExtractor]]] = {}

    for param_name, marker in markers:
        # Bind a copy rather than the marker itself. A marker held in a module
        # constant and reused across handlers would otherwise keep whichever
        # parameter name bound it first, so a second handler using it under a
        # different name would silently read the wrong key off the wire.
        marker = copy(marker)
        bind_marker(marker, param_name)

        if marker.is_legacy and not strict:
            legacy.append(SolvedParamDependency(marker, param_name))
            continue

        grouped.setdefault(marker.location, []).append((param_name, marker))

    specs = tuple(
        _build_spec(
            location,
            grouped[location],
            f"{name}_{location.value.capitalize()}",
        )
        for location in _SYNC_LOCATIONS
        if location in grouped
    )

    form_spec = (
        _build_spec(
            ParameterLocation.FORM,
            grouped[ParameterLocation.FORM],
            f"{name}_Form",
        )
        if ParameterLocation.FORM in grouped
        else None
    )

    return CompiledValidator(
        specs=specs,
        form_spec=form_spec,
        legacy=tuple(legacy),
    )


class ResponseModelValidator:
    """Validates and shapes a handler's return value against a response model.

    Declaring a response model turns the documented output schema into an
    enforced one: fields the model does not declare are dropped, declared
    fields are coerced, and a handler that returns something incompatible
    fails loudly instead of leaking an unintended shape to clients.

    Attributes:
        model: The Pydantic model the return value is validated against.
        many: Whether the handler returns a collection of ``model``.
        dump_options: Options forwarded to ``model_dump`` when serializing.
    """

    __slots__ = ("_adapter", "dump_options", "many", "model")

    def __init__(
        self,
        model: Any,
        *,
        many: bool = False,
        exclude_none: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        by_alias: bool = True,
    ) -> None:
        """Initialize the response validator.

        Args:
            model: The Pydantic model class describing the response.
            many: Set when the handler returns a list of ``model``.
            exclude_none: Omit fields whose value is ``None``.
            exclude_unset: Omit fields that were never explicitly set.
            exclude_defaults: Omit fields still equal to their default.
            by_alias: Serialize using field aliases. Defaults to ``True`` to
                match the framework's existing encoder behavior.
        """
        from pydantic import TypeAdapter

        self.model = model
        self.many = many
        self.dump_options = {
            "exclude_none": exclude_none,
            "exclude_unset": exclude_unset,
            "exclude_defaults": exclude_defaults,
            "by_alias": by_alias,
        }
        self._adapter = TypeAdapter(list[model] if many else model)  # type: ignore[valid-type]

    def validate(self, value: Any) -> Any:
        """Validate a handler return value and serialize it to plain data.

        Args:
            value: Whatever the handler returned.

        Returns:
            The validated value dumped to JSON-compatible primitives, ready to
            hand to the response encoder.

        Raises:
            ResponseValidationError: If the value does not satisfy the declared
                model. This surfaces as a 500 because the fault is the
                application's, not the caller's.
        """
        try:
            validated = self._adapter.validate_python(value, from_attributes=True)
        except ValidationError as exc:
            raise ResponseValidationError(
                prefix_errors(exc, "response"), body=value
            ) from exc
        # Passed by name rather than spread from `dump_options`: a ** spread
        # is checked against every parameter of `dump_python`, including the
        # include/exclude ones this dict never carries.
        return self._adapter.dump_python(
            validated,
            mode="json",
            exclude_none=self.dump_options["exclude_none"],
            exclude_unset=self.dump_options["exclude_unset"],
            exclude_defaults=self.dump_options["exclude_defaults"],
            by_alias=self.dump_options["by_alias"],
        )


def raise_if_errors(errors: list[dict[str, Any]], *, body: Any = None) -> None:
    """Raise a request validation error when any failures were collected.

    Args:
        errors: Accumulated location-prefixed error dictionaries.
        body: The raw payload that failed, attached for debugging.

    Raises:
        RequestValidationError: If ``errors`` is non-empty.
    """
    if errors:
        raise RequestValidationError(errors, body=body)
