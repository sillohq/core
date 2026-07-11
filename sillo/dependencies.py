from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from inspect import signature
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from sillo.parameters import (
    Header,
    ParameterExtractor,
    SolvedParamDependency,
    resolve_param,
)

if TYPE_CHECKING:
    from sillo.http import Request

# =============================================================================
# User-facing API
# =============================================================================


class Depend:
    def __init__(self, dependency: Callable[..., Any] = None, *, get_request: bool = False) -> None:
        self.dependency = dependency
        self.get_request = get_request

    def __class_getitem__(cls, item: Any):
        return cls


@dataclass
class Dependant:
    """A node in the dependency resolution tree.

    Built at registration time (analysis phase) and walked at request time
    (resolution phase).

    Attributes:
        call: The dependency callable to invoke (``None`` for the root/handler).
        name: Parameter name this node fills in its parent.
        dependencies: Sub-dependencies (child ``Dependant`` nodes).
        param_extractors: Query/Header/Cookie extractors.
        is_coroutine: ``True`` if ``call`` is an ``async def``.
        is_generator: ``True`` if ``call`` is a sync generator.
        is_async_generator: ``True`` if ``call`` is an async generator.
        cache_key: Opaque key for result caching ``(callable, *param_names)``.
        use_cache: Whether the result should be cached for the request.
    """

    call: Optional[Callable[..., Any]] = None
    name: Optional[str] = None
    dependencies: List["Dependant"] = field(default_factory=list)
    request_param_names: List[str] = field(default_factory=list)
    param_extractors: List[SolvedParamDependency] = field(default_factory=list)
    is_coroutine: bool = False
    is_generator: bool = False
    is_async_generator: bool = False
    cache_key: Optional[Tuple[Callable[..., Any], Tuple[str, ...]]] = None
    use_cache: bool = True


# =============================================================================
# Analysis phase — build the Dependant tree from a callable's signature
# =============================================================================


def get_dependant(
    call: Callable[..., Any],
    name: Optional[str] = None,
) -> Dependant:
    sig = signature(call)
    deps: List[Dependant] = []
    request_params: List[str] = []
    extractors: List[SolvedParamDependency] = []
    cache_key_parts: List[str] = []

    for param_name, param in sig.parameters.items():
        default = param.default

        if isinstance(default, Depend):
            if default.get_request and default.dependency is None:
                request_params.append(param_name)
            else:
                sub = get_dependant(default.dependency, param_name)
                deps.append(sub)
                cache_key_parts.append(param_name)

        elif isinstance(default, ParameterExtractor):
            extractor = default
            extractor.param_name = param_name
            if not extractor.alias:
                if isinstance(extractor, Header):
                    extractor.alias = extractor._convert_param_to_header_name(
                        param_name
                    )
                else:
                    extractor.alias = param_name
            extractors.append(SolvedParamDependency(extractor, param_name))

    cache_key: Any = None
    if cache_key_parts:
        cache_key = (call, tuple(cache_key_parts))

    return Dependant(
        call=call,
        name=name,
        dependencies=deps,
        request_param_names=request_params,
        param_extractors=extractors,
        is_coroutine=inspect.iscoroutinefunction(call),
        is_generator=inspect.isgeneratorfunction(call),
        is_async_generator=inspect.isasyncgenfunction(call),
        cache_key=cache_key,
        use_cache=True,
    )


# ==========================================================================
# Resolution — recursively walk the Dependant tree
# ==========================================================================

DependencyCache = Dict[Tuple[Callable[..., Any], Tuple[str, ...]], Any]


async def solve_dependencies(
    dependant: Dependant,
    request: Optional["Request"] = None,
    dependency_cache: Optional[DependencyCache] = None,
    cleanup_callbacks: Optional[List[Callable[[], Any]]] = None,
) -> Dict[str, Any]:
    cache: DependencyCache = dependency_cache if dependency_cache is not None else {}
    cleanups: List[Callable[[], Any]] = (
        cleanup_callbacks if cleanup_callbacks is not None else []
    )
    values: Dict[str, Any] = {}

    for sub in dependant.dependencies:
        if sub.use_cache and sub.cache_key and sub.cache_key in cache:
            values[sub.name] = cache[sub.cache_key]
            continue

        sub_kwargs = await solve_dependencies(sub, request, cache, cleanups)

        for ext in sub.param_extractors:
            sub_kwargs[ext.param_name] = await resolve_param(ext, request)

        result = await _execute_dependency(sub, sub_kwargs, cleanups)

        if sub.use_cache and sub.cache_key:
            cache[sub.cache_key] = result

        if sub.name:
            values[sub.name] = result

    for ext in dependant.param_extractors:
        values[ext.param_name] = await resolve_param(ext, request)

    for rparam in dependant.request_param_names:
        values[rparam] = request

    return values


# =============================================================================
# Internal helpers
# =============================================================================


async def _execute_dependency(
    dependant: Dependant,
    kwargs: Dict[str, Any],
    cleanup_callbacks: List[Callable[[], Any]],
) -> Any:
    """Invoke *dependant*  .call with *kwargs*, handling generators."""
    func = dependant.call
    if func is None:
        raise RuntimeError("Dependant node has no callable to execute")

    if dependant.is_async_generator:
        agen = func(**kwargs)
        value = await agen.__anext__()
        cleanup_callbacks.append(lambda agen=agen: agen.aclose())
        return value

    if dependant.is_generator:
        gen = func(**kwargs)
        value = next(gen)
        cleanup_callbacks.append(lambda gen=gen: gen.close())
        return value

    if dependant.is_coroutine:
        return await func(**kwargs)

    return func(**kwargs)
