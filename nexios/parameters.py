from __future__ import annotations
from inspect import signature, Parameter

import typing
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar, List, Optional

if typing.TYPE_CHECKING:
    from nexios.dependencies import Context


T = TypeVar("T")


class ParameterLocation(Enum):
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"


class ParameterExtractor:
    def __init__(
        self,
        default: Any = ...,
        *,
        alias: str | None = None,
        required: bool = False,
    ):
        self.default = default
        self.alias = alias
        self.required = required
        self.param_name: str | None = None

    def extract(self, ctx: Context | None) -> Any:
        raise NotImplementedError

    def _get_param_name(self) -> str | None:
        if self.alias:
            return self.alias
        return self.param_name

    def _convert_param_to_header_name(self, param_name: str) -> str:
        parts = param_name.split("_")
        return "-".join(part.title() for part in parts)

    def _convert(self, value: str, default: Any) -> Any:
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
    location = ParameterLocation.QUERY

    def extract(self, ctx: Context | None) -> Any:
        if ctx is None or ctx.request is None:
            return self.default

        param_name = self._get_param_name()
        if not param_name:
            return self.default

        value = ctx.request.query_params.get(param_name)

        if value is None:
            if self.required:
                raise ValueError(f"Query parameter '{param_name}' is required")
            if self.default is ...:
                return None
            return self.default

        return self._convert(value, self.default)


class Header(ParameterExtractor):
    location = ParameterLocation.HEADER

    def extract(self, ctx: Context | None) -> Any:
        if ctx is None or ctx.request is None:
            return self.default

        param_name = self._get_param_name()
        if not param_name:
            return self.default

        value = ctx.request.headers.get(param_name)

        if value is None:
            if self.required:
                raise ValueError(f"Header '{param_name}' is required")
            if self.default is ...:
                return None
            return self.default

        return self._convert(value, self.default)


class Cookie(ParameterExtractor):
    location = ParameterLocation.COOKIE

    def extract(self, ctx: Context | None) -> Any:
        if ctx is None or ctx.request is None:
            return self.default

        param_name = self._get_param_name()
        if not param_name:
            return self.default

        value = ctx.request.cookies.get(param_name)

        if value is None:
            if self.required:
                raise ValueError(f"Cookie '{param_name}' is required")
            if self.default is ...:
                return None
            return self.default

        return self._convert(value, self.default)


@dataclass(frozen=True, slots=True)
class SolvedParamDependency:
    extractor: ParameterExtractor
    param_name: str


def solve_params(handler: Any) -> List["SolvedParamDependency"]:

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
    ctx: Optional["Context"] = None,
) -> Any:
    return param_dep.extractor.extract(ctx)


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
