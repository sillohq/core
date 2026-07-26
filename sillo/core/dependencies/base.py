from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from inspect import signature
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from sillo.validation import (
    CompiledValidator,
    ParameterExtractor,
    SolvedParamDependency,
    compile_validator,
    raise_if_errors,
)

if TYPE_CHECKING:
    from sillo.core.http import Request

# =============================================================================
# User-facing API
# =============================================================================


class Depend:
    """
    Declares a dependency injection marker for route handler parameters.

    Used as a default value in handler function signatures to signal that
    the parameter should be resolved through the dependency injection system
    rather than extracted directly from the request. Wraps a callable that
    produces the injected value and supports optional raw request injection.

    This is the primary user-facing API for declaring dependencies in sillo's
    DI system. Dependencies can be nested — a ``Depend``-wrapped callable may
    itself declare further ``Depend`` parameters, forming a dependency graph
    that is resolved at request time.

    Attributes:
        dependency: The callable whose return value will be injected. If
            ``None`` and ``get_request`` is ``True``, the raw ``Request``
            object is injected instead.
        get_request: When ``True`` and ``dependency`` is ``None``, the
            framework injects the current ``Request`` object directly
            into the parameter.
    """

    def __init__(
        self, dependency: Callable[..., Any] = None, *, get_request: bool = False
    ) -> None:
        """
        Initialize a Depend instance with a dependency callable and request flag.

        Args:
            dependency: An optional callable that produces the value to be
                injected into the handler parameter. Can be a regular function,
                an async function, a generator, or an async generator. When
                ``None``, the ``get_request`` flag must be ``True`` to inject
                the raw request object.
            get_request: A keyword-only boolean flag indicating whether the
                raw ``Request`` object should be injected directly. Defaults
                to ``False``. Only effective when ``dependency`` is ``None``.

        Returns:
            None. This constructor initializes the ``Depend`` marker instance.

        Example::

            async def get_db():
                return await Database.connect()

            @app.get("/items")
            async def list_items(request, response, db=Depend(get_db)):
                return response.json(await db.query("SELECT * FROM items"))

            @app.get("/me")
            async def get_me(request, response, req=Depend(get_request=True)):
                return response.json({"user": req.user})
        """
        self.dependency = dependency
        self.get_request = get_request

    def __class_getitem__(cls, item: Any):
        """
        Support generic subscript syntax for type-checker compatibility.

        Allows ``Depend`` to be used with subscript notation (e.g.,
        ``Depend[SomeType]``) without raising a ``TypeError``. This is
        primarily for static type-checker support and does not alter
        runtime behavior.

        Args:
            item: The type or types used in the subscript expression.
                This value is ignored at runtime.

        Returns:
            The ``Depend`` class itself, unchanged, regardless of the
            subscript argument provided.
        """
        return cls


@dataclass(slots=True)
class ExecutionStep:
    """
    Represents a single step in the flattened dependency execution plan.

    Each execution step wraps a ``Dependant`` node and marks whether it is
    the root (final) dependency whose kwargs should be returned to the
    caller. The execution plan is a pre-computed, depth-first ordered list
    of these steps, enabling iterative (non-recursive) resolution of the
    entire dependency graph at request time.

    Attributes:
        dependant: The ``Dependant`` node to execute at this step, containing
            the callable, its sub-dependencies, and parameter extractors.
        is_root: A boolean flag indicating whether this step represents the
            root dependency. When ``True``, the solver returns the collected
            kwargs instead of executing the callable. Defaults to ``False``.
    """

    dependant: Dependant
    is_root: bool = False


@dataclass(slots=True)
class Dependant:
    """
    Represents a single node in the dependency injection resolution graph.

    A ``Dependant`` wraps a callable and holds all the metadata needed to
    execute it during dependency resolution: its sub-dependencies, parameter
    extractors, introspection flags (coroutine, generator, async generator),
    and a pre-computed flat execution plan for iterative solving.

    The dependency tree is built statically by ``get_dependant`` during route
    registration, and the execution plan is flattened via depth-first traversal
    so that runtime resolution is a simple iterative loop with zero recursion.

    Attributes:
        call: The wrapped callable that produces the dependency value. May be
            a regular function, async function, generator, or async generator.
            Can be ``None`` for the root dependant that represents the handler
            itself.
        name: The parameter name under which this dependency's result is stored
            in the resolved values dictionary. ``None`` for the root node.
        dependencies: A list of child ``Dependant`` nodes representing direct
            sub-dependencies declared via ``Depend()`` defaults.
        request_param_names: Parameter names that should receive the raw
            ``Request`` object directly (declared via ``Depend(get_request=True)``).
        param_extractors: A list of solved parameter extractor dependencies
            (e.g., ``Query``, ``Header``, ``Cookie``) that pull values from
            specific parts of the incoming request.
        is_coroutine: ``True`` if ``call`` is an ``async def`` function.
        is_generator: ``True`` if ``call`` is a synchronous generator function.
        is_async_generator: ``True`` if ``call`` is an async generator function.
        cache_key: An optional tuple used as a cache key for deduplication.
            When set, repeated resolutions of the same dependency within a
            single request return the cached value. ``None`` disables caching.
        use_cache: Whether to use caching for this dependency. Defaults to
            ``True``.
        validator: The ``CompiledValidator`` holding the Pydantic models built
            for this callable's validated parameters, or ``None`` when it
            declares none. Compiled once here at registration so request-time
            validation performs no signature introspection.
        _execution_plan: A pre-computed flat list of ``ExecutionStep`` objects
            representing the depth-first traversal order for iterative solving.
        _validator_plan: A pre-computed tuple of ``(node id, validator)`` pairs
            for every node in the execution plan that declares validated
            parameters. Empty for the common case, which lets request handling
            skip validation with a single truth test instead of walking the
            tree. Built once, at registration.
        _needs_form: Whether any node in the tree declares form or file
            parameters, so the form body is parsed once per request rather than
            being checked for per node.
    """

    call: Optional[Callable[..., Any]] = None
    name: Optional[str] = None
    dependencies: List["Dependant"] = field(default_factory=list)
    request_param_names: List[str] = field(default_factory=list)
    param_extractors: List[SolvedParamDependency] = field(default_factory=list)
    validator: Optional[CompiledValidator] = None
    is_coroutine: bool = False
    is_generator: bool = False
    is_async_generator: bool = False
    cache_key: Optional[Tuple[Callable[..., Any], Tuple[str, ...]]] = None
    use_cache: bool = True
    _execution_plan: List[ExecutionStep] = field(default_factory=list)
    _validator_plan: Tuple[Tuple[int, CompiledValidator], ...] = ()
    _needs_form: bool = False


# =============================================================================
# Analysis phase — build the Dependant tree from a callable's signature
# =============================================================================


def get_dependant(
    call: Callable[..., Any],
    name: Optional[str] = None,
    *,
    strict_validation: bool = False,
) -> Dependant:
    """
    Analyze a callable's signature and build a Dependant dependency tree.

    Inspects the parameters of the given callable to discover dependency
    injection markers (``Depend`` instances) and parameter extractors
    (``ParameterExtractor`` instances such as ``Query``, ``Header``,
    ``Cookie``). Recursively builds a tree of ``Dependant`` nodes for
    nested dependencies, then flattens the tree into an execution plan
    for efficient iterative resolution at request time.

    Args:
        call: The callable to analyze. Can be a regular function, async
            function, generator, or async generator. Its signature is
            inspected to discover ``Depend`` and ``ParameterExtractor``
            default values on each parameter.
        name: An optional name to assign to this dependant node. Typically
            corresponds to the parameter name in the parent callable's
            signature. Used as the key when storing resolved values.
        strict_validation: When ``True``, markers written in the pre-Pydantic
            style are compiled onto the validated path as well, so missing or
            malformed values produce a 422 instead of the historical 500.
            Propagates to nested dependencies so a whole application validates
            consistently.

    Returns:
        A fully constructed ``Dependant`` instance with its dependency tree,
        parameter extractors, introspection flags, cache key, and pre-computed
        execution plan populated and ready for resolution.

    Example::

        async def get_db():
            return await Database.connect()

        dependant = get_dependant(get_db, name="db")
        # dependant.call == get_db
        # dependant.is_coroutine == True
    """
    sig = signature(call)
    deps: List[Dependant] = []
    request_params: List[str] = []
    markers: List[Tuple[str, ParameterExtractor]] = []
    cache_key_parts: List[str] = []

    for param_name, param in sig.parameters.items():
        default = param.default

        if isinstance(default, Depend):
            if default.get_request and default.dependency is None:
                request_params.append(param_name)
            else:
                sub = get_dependant(
                    default.dependency,
                    param_name,
                    strict_validation=strict_validation,
                )
                deps.append(sub)
                cache_key_parts.append(param_name)

        elif isinstance(default, ParameterExtractor):
            markers.append((param_name, default))

    # Compiling here partitions the markers: those written in the pre-Pydantic
    # style stay on the synchronous extractor path they have always used, while
    # the rest are folded into per-location Pydantic models. Both halves are
    # produced by a single pass so the two paths cannot disagree about aliases.
    validator = compile_validator(
        markers,
        name=getattr(call, "__name__", "handler"),
        strict=strict_validation,
    )
    extractors = list(validator.legacy)

    cache_key: Any = None
    if cache_key_parts:
        cache_key = (call, tuple(cache_key_parts))

    dependant = Dependant(
        call=call,
        name=name,
        dependencies=deps,
        request_param_names=request_params,
        param_extractors=extractors,
        validator=validator if validator.is_active else None,
        is_coroutine=inspect.iscoroutinefunction(call),
        is_generator=inspect.isgeneratorfunction(call),
        is_async_generator=inspect.isasyncgenfunction(call),
        cache_key=cache_key,
        use_cache=True,
    )
    dependant._execution_plan = _build_execution_plan(dependant)

    # Flatten the validators out of the execution plan once, so a request only
    # has to test a tuple for emptiness rather than walk the tree looking for
    # work that usually is not there.
    validator_plan = tuple(
        (id(step.dependant), step.dependant.validator)
        for step in dependant._execution_plan
        if step.dependant.validator is not None
    )
    dependant._validator_plan = validator_plan
    dependant._needs_form = any(v.needs_form for _, v in validator_plan)

    return dependant


def _build_execution_plan(root: Dependant) -> List[ExecutionStep]:
    """
    Build a flattened execution plan from a dependency tree via DFS traversal.

    Performs a recursive depth-first traversal of the ``Dependant`` tree rooted
    at ``root``, emitting an ``ExecutionStep`` for each non-root node in
    post-order (children before parents). A final step wrapping the root node
    with ``is_root=True`` is appended at the end. This produces a flat list
    that the solver can iterate through without recursion.

    Args:
        root: The root ``Dependant`` node of the dependency tree. Its
            sub-dependencies are traversed recursively to build the
            complete execution plan.

    Returns:
        A list of ``ExecutionStep`` instances in depth-first post-order,
        with the root step marked as ``is_root=True`` at the end of the
        list. All child steps appear before the root step.
    """
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
    validated: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Collect keyword arguments for executing a dependency node.

    Gathers all the arguments needed to call a ``Dependant`` node's callable
    by combining resolved sub-dependency values, parameter extractor results,
    and raw request references from the already-computed values dictionary.

    Args:
        node: The ``Dependant`` node whose arguments are being collected.
            Its ``dependencies``, ``param_extractors``, and
            ``request_param_names`` fields determine which values are gathered.
        values: A dictionary of already-resolved dependency results, keyed
            by dependency name. Sub-dependency values are looked up here.
        request: The current ``Request`` object, or ``None`` if not available.
            Used to satisfy parameter extractors and raw request parameters.
        validated: Values produced by the Pydantic validators, keyed by the
            id of the ``Dependant`` they belong to. Resolved ahead of this
            call because body and form parsing are asynchronous, whereas this
            function is deliberately synchronous.

    Returns:
        A dictionary of keyword arguments ready to be unpacked into the
        node's callable. Keys are parameter names and values are the
        resolved dependency results, extracted parameters, or request
        references as appropriate.
    """
    kwargs: Dict[str, Any] = {
        dep.name: values[dep.name] for dep in node.dependencies if dep.name
    }
    for ext in node.param_extractors:
        kwargs[ext.param_name] = ext.extractor.extract(request)
    if validated:
        node_values = validated.get(id(node))
        if node_values:
            kwargs.update(node_values)
    for rp in node.request_param_names:
        kwargs[rp] = request
    return kwargs


async def resolve_validated_params(
    dependant: Dependant,
    request: Optional["Request"],
) -> Dict[int, Dict[str, Any]]:
    """
    Run every Pydantic validator in a dependency tree against the request.

    Walks the pre-computed execution plan and validates each node that
    declared validated parameters. Failures from every node and every request
    location are accumulated and reported together, so a client with a bad
    query parameter *and* a malformed body learns about both in one response
    rather than one per round trip.

    Form payloads are read through the request's own caching accessor, so
    declaring form fields across several dependencies parses the payload only
    once. JSON bodies are not handled here — they are declared with the
    ``request_model=`` route argument and validated by the route.

    Args:
        dependant: The root ``Dependant`` whose execution plan should be
            walked. Nodes without a validator are skipped.
        request: The current ``Request``. When ``None`` there is nothing to
            validate against and an empty mapping is returned.

    Returns:
        A mapping from ``id(dependant_node)`` to the validated keyword
        arguments for that node. Empty when no node declares validated
        parameters.

    Raises:
        RequestValidationError: If any declared parameter failed validation.
    """
    resolved: Dict[int, Dict[str, Any]] = {}
    errors: List[Dict[str, Any]] = []

    # Parsed once for the whole tree rather than per node; the request caches
    # the result anyway, but this also keeps the await off the per-node path.
    form = await request.form if dependant._needs_form else None

    for node_id, validator in dependant._validator_plan:
        node_values, node_errors = validator.validate_sync(request)
        if node_errors:
            errors.extend(node_errors)

        if validator.form_spec is not None:
            form_values, form_errors = validator.validate_form(form)
            node_values.update(form_values)
            if form_errors:
                errors.extend(form_errors)

        resolved[node_id] = node_values

    if errors:
        raise_if_errors(errors)
    return resolved


DependencyCache = Dict[Tuple[Callable[..., Any], Tuple[str, ...]], Any]

#: Shared empty mapping returned when a tree declares no validated parameters.
#: Only ever read, never mutated, so one instance is safe to share.
_NO_VALIDATED: Dict[int, Dict[str, Any]] = {}


async def solve_dependencies(
    dependant: Dependant,
    request: Optional["Request"] = None,
    dependency_cache: Optional[DependencyCache] = None,
    cleanup_callbacks: Optional[List[Callable[[], Any]]] = None,
) -> Dict[str, Any]:
    """
    Resolve all dependencies in a Dependant tree iteratively using the execution plan.

    Walks through the pre-computed execution plan of the given ``Dependant``,
    executing each dependency node in order and collecting results. Supports
    caching to avoid redundant executions and handles async generators and
    sync generators by registering cleanup callbacks for teardown.

    Args:
        dependant: The root ``Dependant`` node whose execution plan should
            be resolved. The plan was built during route registration by
            ``get_dependant``.
        request: The current ``Request`` object to pass to parameter
            extractors and ``Depend(get_request=True)`` dependencies.
            May be ``None`` for non-request contexts.
        dependency_cache: An optional dictionary for caching resolved
            dependency values across the resolution. If ``None``, a fresh
            empty cache is created. Keys are ``(callable, param_names)``
            tuples; values are the resolved results.
        cleanup_callbacks: An optional list to which generator teardown
            callbacks are appended. After the request is handled, the
            framework calls each callback to close generators properly.

    Returns:
        A dictionary mapping parameter names to their resolved values for
        the root dependant. These are the keyword arguments that should be
        passed to the route handler.

    Raises:
        RuntimeError: If a dependant node has no callable to execute
            (propagated from ``_execute_dependency``).
    """
    cache: DependencyCache = dependency_cache if dependency_cache is not None else {}
    cleanups: List[Callable[[], Any]] = (
        cleanup_callbacks if cleanup_callbacks is not None else []
    )
    values: Dict[str, Any] = {}
    # The overwhelmingly common case is a route with nothing to validate. Test
    # the precomputed plan first so those requests never allocate a coroutine.
    validated = (
        await resolve_validated_params(dependant, request)
        if dependant._validator_plan and request is not None
        else _NO_VALIDATED
    )

    for step in dependant._execution_plan:
        sub = step.dependant

        if sub.use_cache and sub.cache_key and sub.cache_key in cache:
            if sub.name:
                values[sub.name] = cache[sub.cache_key]
            continue

        kwargs = _collect_kwargs(sub, values, request, validated)

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
    """
    Execute a single dependency node and return its produced value.

    Dispatches the execution based on the dependant's introspection flags,
    handling four callable types: async generators (yields one value then
    registers an ``aclose`` cleanup), sync generators (yields one value
    then registers a ``close`` cleanup), async functions (awaited), and
    regular functions (called directly).

    Args:
        dependant: The ``Dependant`` node to execute. Must have a non-``None``
            ``call`` attribute. The execution strategy is determined by the
            ``is_async_generator``, ``is_generator``, and ``is_coroutine``
            flags on this node.
        kwargs: The keyword arguments dictionary to pass to the callable.
            These are collected by ``_collect_kwargs`` from resolved
            sub-dependencies and parameter extractors.
        cleanup_callbacks: A mutable list to which generator teardown
            callbacks are appended. For generator-based dependencies, a
            lambda capturing the generator object is added so that the
            framework can properly close it after the request completes.

    Returns:
        The value produced by the dependency callable. For generators, this
        is the first yielded value. For async generators, this is the first
        value from ``__anext__``. For coroutines, the awaited result. For
        regular functions, the direct return value.

    Raises:
        RuntimeError: If the dependant node has no callable assigned
            (``dependant.call`` is ``None``).
    """
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
