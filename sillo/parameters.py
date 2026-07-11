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
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"


class ParameterExtractor:
    """Base class for extracting parameters from request context."""

    def __init__(
        self,
        default: Any = ...,
        *,
        alias: str | None = None,
        required: bool = False,
    ):
        """Initialize the parameter extractor.

        Args:
            default: Default value if parameter is missing.
            alias: Alternative name for the parameter.
            required: Raise error if parameter is missing.
        """
        self.default = default
        self.alias = alias
        self.required = required
        self.param_name: str | None = None

    def extract(self, request: Request | None) -> Any:
        """Extract the parameter value from context.

        Args:
            ctx: The dependency injection context.

        Returns:
            The extracted parameter value.
        """
        raise NotImplementedError

    def _get_param_name(self) -> str | None:
        """Get the parameter name, preferring alias."""
        if self.alias:
            return self.alias
        return self.param_name

    def _convert_param_to_header_name(self, param_name: str) -> str:
        """Convert snake_case param name to HTTP header name (X-Custom-Header)."""
        parts = param_name.split("_")
        return "-".join(part.title() for part in parts)

    def _convert(self, value: str, default: Any) -> Any:
        """Convert a string value to the expected type based on default.

        Args:
            value: The string value from request.
            default: Default value defining expected type.

        Returns:
            The value converted to the expected type.
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
    """Extractor for query string parameters."""

    location = ParameterLocation.QUERY

    def extract(self, request: Request | None) -> Any:
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
    """Extractor for HTTP header parameters."""

    location = ParameterLocation.HEADER

    def extract(self, request: Request | None) -> Any:
        """Extract header parameter from request.

        Args:
            request: The incoming HTTP request.

        Returns:
            The header parameter value.
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
    """Extractor for cookie parameters."""

    location = ParameterLocation.COOKIE

    def extract(self, request: Request | None) -> Any:
        """Extract cookie parameter from request.

        Args:
            request: The incoming HTTP request.

        Returns:
            The cookie parameter value.
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
    """A solved parameter dependency with extractor and name."""

    extractor: ParameterExtractor
    param_name: str


def solve_params(handler: Any) -> List["SolvedParamDependency"]:
    """Solve all parameter extractors for a handler.

    Args:
        handler: The handler function to analyze.

    Returns:
        List of SolvedParamDependency objects.
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
