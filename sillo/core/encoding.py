"""JSON encoding utilities for serializing Python objects to JSON-compatible types.

This module provides a comprehensive JSON encoding system that converts arbitrary
Python objects into JSON-serializable representations. It handles Pydantic models,
dataclasses, enums, dates, UUIDs, IP addresses, secrets, and many other common
types. A global custom encoder registry allows applications to extend the encoding
system with support for application-specific types.
"""

from __future__ import annotations

import dataclasses
import datetime
import typing
from collections import defaultdict, deque
from decimal import Decimal
from enum import Enum
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from pathlib import Path, PurePath
from re import Pattern
from types import GeneratorType
from uuid import UUID

from pydantic import BaseModel
from pydantic.networks import AnyUrl, NameEmail
from pydantic.types import SecretBytes, SecretStr
from pydantic_core import PydanticUndefinedType


def isoformat(o: datetime.date | datetime.time) -> str:
    """Convert a date or time object to its ISO 8601 string representation.

    This is a thin wrapper around the ``isoformat()`` method of Python's
    ``datetime.date`` and ``datetime.time`` objects. It is used as the default
    encoder for date and time types in the JSON encoding system.

    Args:
        o: A ``datetime.date`` or ``datetime.time`` instance to serialize.
            Both types implement the ``isoformat()`` method.

    Returns:
        An ISO 8601 formatted string. For dates: ``"YYYY-MM-DD"``. For times:
        ``"HH:MM:SS"`` with optional microseconds and timezone info.

    Note:
        This function also works with ``datetime.datetime`` objects since
        ``datetime`` is a subclass of ``date``. The output format depends on
        whether the input is a date-only or time-aware object.
    """
    return o.isoformat()


def decimal_encoder(dec_value: Decimal) -> int | float:
    """Encode a Decimal value as either an int or float for JSON serialization.

    Examines the exponent of the Decimal to determine whether it represents an
    integer value (non-negative exponent) or a fractional value (negative
    exponent). Integer-valued Decimals are converted to ``int``, while
    fractional Decimals are converted to ``float``.

    Args:
        dec_value: A ``decimal.Decimal`` instance to encode. Can represent
            either an integer value like ``Decimal("42")`` or a fractional
            value like ``Decimal("3.14")``.

    Returns:
        An ``int`` if the Decimal has a non-negative exponent (e.g.,
        ``Decimal("100")`` returns ``100``), or a ``float`` if it has a
        negative exponent (e.g., ``Decimal("1.5")`` returns ``1.5``).

    Note:
        This heuristic preserves precision for integer-valued Decimals by
        avoiding the float conversion, which could lose precision for very
        large integers. For fractional values, the standard float precision
        limitations apply.
    """
    exponent = dec_value.as_tuple().exponent
    if isinstance(exponent, int) and exponent >= 0:
        return int(dec_value)
    else:
        return float(dec_value)


#: Global registry of user-defined encoders. Populated via
#: :func:`register_encoder` or ``SilloApp.add_encoder`` and automatically
#: consulted by :func:`jsonable_encoder`.
CUSTOM_ENCODERS: dict[type[typing.Any], typing.Callable[[typing.Any], typing.Any]] = {}

#: Types that :func:`jsonable_encoder` returns untouched. Matched by exact type
#: rather than ``isinstance``, so subclasses (a ``str``-valued ``Enum``, say)
#: still take the full dispatch path.
_PASSTHROUGH_TYPES = frozenset({str, int, float, bool, type(None)})


def register_encoder(
    type_: type[typing.Any],
    encoder: typing.Callable[[typing.Any], typing.Any],
) -> None:
    """Register a global custom encoder for a specific Python type.

    Adds an encoder function to the global ``CUSTOM_ENCODERS`` registry, which
    is automatically consulted by ``jsonable_encoder`` whenever an object of the
    specified type (or a subclass) is encountered during JSON serialization.
    This allows applications to extend the JSON encoding system without modifying
    the core encoding logic.

    Args:
        type_: The Python type (class, ABC, or abstract base) to register the
            encoder for. When an object is an instance of this type, the
            encoder will be invoked. Subclass relationships are checked using
            ``isinstance``, so registering a base class encoder will also
            cover subclasses unless a more specific encoder exists.
        encoder: A callable that receives an instance of ``type_`` and returns
            a JSON-serializable value (e.g., dict, list, str, int, float, bool,
            or None). The callable should handle all valid instances of the type.

    Returns:
        None. This function modifies the global ``CUSTOM_ENCODERS`` dictionary
        in place as a side effect.

    Note:
        Custom encoders registered via this function take priority over the
        built-in ``ENCODERS_BY_TYPE`` mappings. If multiple custom encoders
        match an object (via inheritance), the exact type match is tried first,
        followed by ``isinstance`` checks in registration order. Encoders
        registered later for the same type will overwrite earlier ones.
    """
    CUSTOM_ENCODERS[type_] = encoder


def get_custom_encoders() -> dict[
    type[typing.Any], typing.Callable[[typing.Any], typing.Any]
]:
    """Return a shallow copy of the currently registered global custom encoders.

    Provides read-only access to the global ``CUSTOM_ENCODERS`` registry by
    returning a copy. Modifications to the returned dictionary do not affect
    the actual registry; use ``register_encoder`` to add new encoders.

    Returns:
        A new dictionary mapping types to their encoder callables. The returned
        dictionary is a snapshot and will not reflect subsequent registrations.

    Note:
        This function is useful for debugging, introspection, and testing. It
        allows callers to inspect which custom encoders are currently active
        without risking accidental modification of the global registry.
    """
    return dict(CUSTOM_ENCODERS)


ENCODERS_BY_TYPE: dict[type[typing.Any], typing.Callable[[typing.Any], typing.Any]] = {
    bytes: lambda o: o.decode(),
    datetime.date: isoformat,
    datetime.datetime: isoformat,
    datetime.time: isoformat,
    datetime.timedelta: lambda td: td.total_seconds(),
    Decimal: decimal_encoder,
    Enum: lambda o: o.value,
    frozenset: list,
    deque: list,
    GeneratorType: list,
    IPv4Address: str,
    IPv4Interface: str,
    IPv4Network: str,
    IPv6Address: str,
    IPv6Interface: str,
    IPv6Network: str,
    NameEmail: str,
    Path: str,
    Pattern: lambda o: o.pattern,
    SecretBytes: str,
    SecretStr: str,
    set: list,
    UUID: str,
    AnyUrl: str,
}


def generate_encoders_by_class_tuples(
    type_encoder_map: dict[typing.Any, typing.Callable[[typing.Any], typing.Any]],
) -> dict[typing.Callable[[typing.Any], typing.Any], tuple[typing.Any, ...]]:
    """Invert a type-to-encoder mapping into an encoder-to-types-tuple mapping.

    Takes a dictionary that maps individual types to their encoder functions
    and produces the inverse mapping: each encoder function maps to a tuple of
    all types it handles. This inverted structure enables efficient ``isinstance``
    checks during encoding, where a single encoder call can handle multiple
    related types (e.g., one ``str`` encoder handles ``IPv4Address``,
    ``IPv6Address``, ``Path``, etc.).

    Args:
        type_encoder_map: A dictionary mapping Python types to their encoder
            callables. Multiple types may map to the same encoder function
            (e.g., both ``set`` and ``frozenset`` map to ``list``).

    Returns:
        A dictionary mapping each unique encoder callable to a tuple of all
        types that it handles. The tuple preserves the order in which types
        were encountered during iteration of the input map.

    Note:
        This function is called once at module load time to pre-compute the
        inverted mapping for ``ENCODERS_BY_TYPE``. The result is cached in
        the module-level ``encoders_by_class_tuples`` variable for performance.
    """
    encoders_by_class_tuples: dict[
        typing.Callable[[typing.Any], typing.Any], tuple[typing.Any, ...]
    ] = defaultdict(tuple)
    for type_, encoder in type_encoder_map.items():
        encoders_by_class_tuples[encoder] += (type_,)
    return encoders_by_class_tuples


encoders_by_class_tuples = generate_encoders_by_class_tuples(ENCODERS_BY_TYPE)


def jsonable_encoder(
    obj: typing.Any,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    by_alias: bool = True,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    custom_encoder: dict[type, typing.Callable[[typing.Any], typing.Any]] | None = None,
) -> typing.Any:
    """Convert any Python object into a JSON-serializable representation.

    Recursively traverses an arbitrary Python object and converts it into a
    composition of JSON-native types (dict, list, str, int, float, bool, None).
    Handles Pydantic models, dataclasses, enums, dates, UUIDs, IP addresses,
    paths, sets, generators, and any type registered in the built-in or custom
    encoder registries. This is the core serialization function used by all
    sillo JSON responses.

    Args:
        obj: The Python object to encode. Can be any type including nested
            structures of dicts, lists, Pydantic models, dataclasses, etc.
        include: An optional set of field names to include when encoding
            Pydantic models and dataclasses. If provided, only these fields
            will appear in the output. Defaults to None (include all fields).
        exclude: An optional set of field names to exclude when encoding
            Pydantic models and dataclasses. If provided, these fields will
            be omitted from the output. Defaults to None (exclude nothing).
        by_alias: Whether to use field aliases (True) or original field names
            (False) when encoding Pydantic models. Defaults to True.
        exclude_unset: Whether to exclude fields that were not explicitly set
            during Pydantic model construction. Defaults to False.
        exclude_defaults: Whether to exclude fields whose values match their
            declared defaults. Defaults to False.
        exclude_none: Whether to exclude fields whose values are None. When
            True, any key-value pair with a None value is omitted from the
            output. Defaults to False.
        custom_encoder: An optional dictionary mapping types to encoder
            callables for this specific invocation. These are merged with
            the global ``CUSTOM_ENCODERS`` registry, with per-call encoders
            taking precedence. Defaults to None.

    Returns:
        A JSON-serializable value: typically a dict, list, str, int, float,
        bool, or None. The exact structure mirrors the input object with all
        non-JSON-native types converted to their serializable equivalents.

    Raises:
        ValueError: If the object cannot be encoded by any registered encoder
            and cannot be converted to a dict via ``dict()`` or ``vars()``.
            The exception contains a list of all encoding errors encountered.

    Note:
        The encoding priority is: (1) custom encoders (global + per-call),
        (2) Pydantic model_dump, (3) dataclass asdict, (4) Enum value,
        (5) PurePath str, (6) primitive passthrough, (7) dict/list recursion,
        (8) ENCODERS_BY_TYPE lookup, (9) isinstance-based encoder tuples,
        (10) dict()/vars() fallback. This order ensures the most specific
        encoder is always preferred.
    """
    if CUSTOM_ENCODERS or custom_encoder:
        custom_encoder = {**CUSTOM_ENCODERS, **(custom_encoder or {})}
    else:
        custom_encoder = {}
        # Nothing in this call can change how a dict or list is walked, so the
        # JSON-native shapes are returned directly. The checks are on the
        # exact type -- a str-valued Enum, a defaultdict or a tuple all have
        # to keep falling through to the full dispatch below.
        #
        # The dash is load-bearing. Written as "the exact type:" the line wrapped
        # so that "# type:" began a line, and mypy reads a line-initial
        # "# type:" as a PEP 484 type comment: it reported "Invalid syntax"
        # here and then stopped, so nobody importing sillo could type-check
        # their own project at all.
        if (
            not include
            and not exclude
            and not exclude_unset
            and not exclude_defaults
            and not exclude_none
        ):
            obj_type = type(obj)
            if obj_type in _PASSTHROUGH_TYPES:
                return obj
            if obj_type is dict:
                return {
                    jsonable_encoder(k): jsonable_encoder(v) for k, v in obj.items()
                }
            if obj_type is list:
                return [jsonable_encoder(v) for v in obj]
    if custom_encoder:
        if type(obj) in custom_encoder:
            return custom_encoder[type(obj)](obj)
        else:
            for encoder_type, encoder_instance in custom_encoder.items():
                if isinstance(obj, encoder_type):
                    return encoder_instance(obj)
    if include is not None and not isinstance(include, (set, dict)):
        include = set(include)
    if exclude is not None and not isinstance(exclude, (set, dict)):
        exclude = set(exclude)
    if isinstance(obj, BaseModel):
        obj_dict = obj.model_dump(
            mode="json",
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_none=exclude_none,
            exclude_defaults=exclude_defaults,
        )
        return jsonable_encoder(
            obj_dict,
            exclude_none=exclude_none,
            exclude_defaults=exclude_defaults,
        )
    if dataclasses.is_dataclass(obj):
        assert not isinstance(obj, type)
        obj_dict = dataclasses.asdict(obj)
        return jsonable_encoder(
            obj_dict,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            custom_encoder=custom_encoder,
        )
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, PurePath):
        return str(obj)
    if isinstance(obj, (str, int, float, type(None))):
        return obj
    if isinstance(obj, PydanticUndefinedType):
        return None
    if isinstance(obj, dict):
        encoded_dict: dict[str, typing.Any] = {}
        allowed_keys: set[typing.Any] = set(obj.keys())
        if include is not None:
            allowed_keys &= set(include)
        if exclude is not None:
            allowed_keys -= set(exclude)
        for key, value in obj.items():
            if (value is not None or not exclude_none) and key in allowed_keys:
                encoded_key = jsonable_encoder(
                    key,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_none=exclude_none,
                    custom_encoder=custom_encoder,
                )
                encoded_value = jsonable_encoder(
                    value,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_none=exclude_none,
                    custom_encoder=custom_encoder,
                )
                encoded_dict[encoded_key] = encoded_value
        return encoded_dict
    if isinstance(obj, (list, set, frozenset, GeneratorType, tuple, deque)):
        encoded_list: list[typing.Any] = []
        for item in obj:
            encoded_list.append(
                jsonable_encoder(
                    item,
                    include=include,
                    exclude=exclude,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_defaults=exclude_defaults,
                    exclude_none=exclude_none,
                    custom_encoder=custom_encoder,
                )
            )
        return encoded_list

    if type(obj) in ENCODERS_BY_TYPE:
        return ENCODERS_BY_TYPE[type(obj)](obj)
    for encoder, classes_tuple in encoders_by_class_tuples.items():
        if isinstance(obj, classes_tuple):
            return encoder(obj)
    try:
        data = dict(obj)
    except Exception as e:
        errors: list[Exception] = [e]
        try:
            data = vars(obj)
        except Exception as e:
            errors.append(e)
            raise ValueError(errors) from e
    return jsonable_encoder(
        data,
        include=include,
        exclude=exclude,
        by_alias=by_alias,
        exclude_unset=exclude_unset,
        exclude_defaults=exclude_defaults,
        exclude_none=exclude_none,
        custom_encoder=custom_encoder,
    )
