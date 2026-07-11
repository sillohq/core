from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from inspect import signature
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from sillo.parameters import (
    Header,
    ParameterExtractor,
    SolvedParamDependency,
)

if TYPE_CHECKING:
    from sillo.http import Request

# =============================================================================
# User-facing API
# =============================================================================


class Depend:
    def __init__(
        self, dependency: Callable[..., Any] = None, *, get_request: bool = False
    ) -> None:
        self.dependency = dependency
        self.get_request = get_request

    def __class_getitem__(cls, item: Any):
        return cls


@dataclass(slots=True)
class ExecutionStep:
    dependant: Dependant
    is_root: bool = False


@dataclass(slots=True)
class Dependant:
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
    _execution_plan: List[ExecutionStep] = field(default_factory=list)


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

    dependant = Dependant(
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
    dependant._execution_plan = _build_execution_plan(dependant)
    return dependant


def _build_execution_plan(root: Dependant) -> List[ExecutionStep]:
    steps: List[ExecutionStep] = []

    def _collect(node: Dependant) -> None:
        for sub in node.dependencies:
            _collect(sub)
            steps.append(ExecutionStep(dependant=sub))

    _collect(root)
    steps.append(ExecutionStep(dependant=root, is_root=True))
    return steps


def _collect_kwargs(
    node: Dependant,
    values: Dict[str, Any],
    request: Optional["Request"],
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        dep.name: values[dep.name]
        for dep in node.dependencies
        if dep.name
    }
    for ext in node.param_extractors:
        kwargs[ext.param_name] = ext.extractor.extract(request)
    for rp in node.request_param_names:
        kwargs[rp] = request
    return kwargs


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

    for step in dependant._execution_plan:
        sub = step.dependant

        if sub.use_cache and sub.cache_key and sub.cache_key in cache:
            if sub.name:
                values[sub.name] = cache[sub.cache_key]
            continue

        kwargs = _collect_kwargs(sub, values, request)

        if step.is_root:
            return kwargs

        result = await _execute_dependency(sub, kwargs, cleanups)

        if sub.use_cache and sub.cache_key:
            cache[sub.cache_key] = result

        if sub.name:
            values[sub.name] = result

    return {}


async def _execute_dependency(
    dependant: Dependant,
    kwargs: Dict[str, Any],
    cleanup_callbacks: List[Callable[[], Any]],
) -> Any:
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
