from __future__ import annotations

import copy
import difflib
import inspect
import re
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from re import Pattern
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    cast,
)

from pydantic import BaseModel, ValidationError
from typing_extensions import Doc

from sillo._internals._middleware import (
    ASGIRequestResponseBridge,
    wrap_middleware,
)
from sillo._internals._middleware import DefineMiddleware as Middleware
from sillo.core.dependencies import (
    Depend,
    Dependant,
    _execute_dependency,
    get_dependant,
    solve_dependencies,
)
from sillo.core.encoding import jsonable_encoder
from sillo.core.helpers.async_helpers import is_async_callable
from sillo.core.http import Request, Response
from sillo.core.http.response import BaseResponse, JSONResponse, Responder
from sillo.events import EventEmitter
from sillo.exceptions import HTTPException, NotFoundException
from sillo.frontend import FrontendApp
from sillo.objects import RouteParam, URLPath
from sillo.openapi.models import Parameter
from sillo.parameters import ParameterExtractor, SolvedParamDependency
from sillo.route_builder import RouteBuilder
from sillo.types import (
    ArgsType,
    ASGIApp,
    HandlerType,
    MiddlewareType,
    Receive,
    Scope,
    Send,
)
from sillo.utils.concurrency import run_in_threadpool
from sillo.validation import (
    RequestValidationError,
    ResponseModelValidator,
    prefix_errors,
)

from ._utils import MatchStatus, get_route_path
from .base import BaseRoute, BaseRouter
from .grouping import Group
from .websocket import WebsocketRoute

if TYPE_CHECKING:
    from sillo.types import WsHandlerType

allowed_methods_default = ["get", "post", "delete", "put", "patch", "options"]


def _known_route_kwargs() -> frozenset:
    """Return the keyword arguments ``Route.__init__`` accepts by name.

    Computed on first use and cached, because the verb decorators forward
    ``**kwargs`` and we want to check them without paying for signature
    introspection on every route registration.
    """
    global _ROUTE_KWARGS
    if _ROUTE_KWARGS is None:
        params = inspect.signature(Route.__init__).parameters
        _ROUTE_KWARGS = frozenset(
            name
            for name, p in params.items()
            if name not in ("self", "kwargs")
            and p.kind is not inspect.Parameter.VAR_KEYWORD
        )
    return _ROUTE_KWARGS


_ROUTE_KWARGS: frozenset | None = None


def _reject_unknown_route_kwargs(kwargs: dict[str, Any]) -> None:
    """Fail on keyword arguments that no route option matches.

    The verb decorators accept ``**kwargs`` so that route metadata can be
    forwarded, which means a misspelled option would otherwise be accepted and
    silently ignored. That is dangerous for options whose whole purpose is to
    constrain output — ``response_modle=UserOut`` would leave the endpoint
    returning every field of every object it is given.

    Args:
        kwargs: The leftover keyword arguments handed to ``Route.__init__``.

    Raises:
        TypeError: If any key is not a known route option, naming the closest
            match when there is one.
    """
    unknown = sorted(set(kwargs) - _known_route_kwargs())
    if not unknown:
        return

    details = []
    for name in unknown:
        close = difflib.get_close_matches(name, _known_route_kwargs(), n=1, cutoff=0.7)
        details.append(
            f"{name!r}" + (f" (did you mean {close[0]!r}?)" if close else "")
        )
    raise TypeError("Route() got unexpected keyword argument(s): " + ", ".join(details))


class Route(BaseRoute):
    """
    Encapsulates all routing information for an API endpoint, including path handling,
    validation, OpenAPI documentation, and request processing.

    Attributes:
        raw_path: The original URL path string provided during initialization.
        pattern: Compiled regex pattern for path matching.
        handler: Callable that processes incoming requests.
        methods: List of allowed HTTP methods for this endpoint.
        validator: Request parameter validation rules.
        request_schema: Schema for request body documentation.
        response_schema: Schema for response documentation.
        deprecated: Deprecation status indicator.
        tags: OpenAPI documentation tags.
        description: Endpoint functionality details.
        summary: Concise endpoint purpose.
    """

    def __init__(
        self,
        path: Annotated[
            str,
            Doc("""
            URL path pattern for the endpoint. Supports dynamic parameters using curly brace syntax.
            Examples:
            - '/users' (static path)
            - '/posts/{id}' (path parameter)
            - '/files/{filepath:.*}' (regex-matched path parameter)
            """),
        ],
        handler: Annotated[
            HandlerType | None,
            Doc("""
            Callable responsible for processing requests to this endpoint. Can be:
            - A regular function
            - An async function
            - A class method
            - Any object implementing __call__

            The handler should accept a request object and return a response object.
            Example: def user_handler(request: Request) -> Response: ...
            """),
        ],
        methods: Annotated[
            list[str],
            Doc("""
            HTTP methods allowed for this endpoint. Common methods include:
            - GET: Retrieve resources
            - POST: Create resources
            - PUT: Update resources
            - DELETE: Remove resources
            - PATCH: Partial updatess

            Defaults to ['GET'] if not specified. Use uppercase method names.
            """),
        ] = allowed_methods_default,
        name: Annotated[
            str | None,
            Doc("""The unique identifier for the route. This name is used to generate 
            URLs dynamically with `url_for`. It should be a valid, unique string 
            that represents the route within the application."""),
        ] = None,
        summary: Annotated[
            str | None,
            Doc(
                "A brief summary of the API endpoint. This should be a short, one-line description providing a high-level overview of its purpose."
            ),
        ] = None,
        description: Annotated[
            str | None,
            Doc(
                "A detailed explanation of the API endpoint, including functionality, expected behavior, and additional context."
            ),
        ] = None,
        responses: Annotated[
            ArgsType | None,
            Doc(
                "A dictionary mapping HTTP status codes to response schemas or descriptions. Keys are HTTP status codes (e.g., 200, 400), and values define the response format."
            ),
        ] = None,
        request_model: Annotated[
            ArgsType | None,
            Doc(
                "A Pydantic model representing the expected request payload, a dict of status codes to models, or a nested dict. Defines the structure and validation rules for incoming request data."
            ),
        ] = None,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "multipart/form-data",
                "application/x-www-form-urlencoded",
            ],
            Doc(
                "Content type for the request body in OpenAPI docs. Defaults to 'application/json'."
            ),
        ] = "application/json",
        response_model: Annotated[
            ArgsType | None,
            Doc(
                "A Pydantic model describing this endpoint's successful response. When set, the handler's return value is validated against it, undeclared fields are dropped, and the OpenAPI response schema is generated from it — so the published contract is enforced rather than merely documented."
            ),
        ] = None,
        response_model_many: bool = False,
        response_model_exclude_none: bool = False,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_by_alias: bool = True,
        strict_validation: bool = False,
        tags: Sequence[str] | None = None,
        security: list[dict[str, list[str]]] | None = None,
        operation_id: str | None = None,
        deprecated: bool = False,
        parameters: list[Parameter] | None = None,
        middleware: list[Any] | None = None,
        exclude_from_schema: bool = False,
        auth: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a Route instance with full endpoint configuration.

        Constructs a new Route that encapsulates all information needed to
        match incoming HTTP requests, validate parameters, apply middleware,
        and dispatch to the appropriate handler function. The path pattern
        is compiled into a regex for efficient matching, and the handler
        is introspected to extract dependency injection metadata.

        An internal ASGI application is built by composing the handler with
        all route-specific middleware layers, enabling per-route middleware
        chains that execute before the handler is invoked.

        Args:
            path: URL path pattern for the endpoint, supporting dynamic
                parameters via curly brace syntax such as ``/users/{id}``.
            handler: Callable responsible for processing requests. Must
                accept at least a request and response argument.
            methods: HTTP methods allowed for this endpoint. Defaults to
                all standard methods. ``HEAD`` is added automatically when
                ``GET`` is present.
            name: Unique identifier for the route, used with ``url_for``
                to generate URLs dynamically.
            summary: Brief one-line description for OpenAPI documentation.
            description: Detailed explanation of the endpoint purpose,
                behavior, and any relevant context for API consumers.
            responses: Mapping of HTTP status codes to response schemas
                or descriptions for OpenAPI documentation.
            request_model: Pydantic model or dict of status codes to models
                defining the expected request payload structure.
            request_content_type: Content type for the request body in
                OpenAPI docs. Defaults to ``"application/json"``.
            response_model: Pydantic model describing the successful response.
                When provided the handler's return value is validated and
                shaped against it before encoding, so fields the model does
                not declare never reach the client.
            response_model_many: Set when the handler returns a list of
                ``response_model`` rather than a single instance.
            response_model_exclude_none: Omit response fields whose value
                is ``None``.
            response_model_exclude_unset: Omit response fields that were
                never explicitly set.
            response_model_exclude_defaults: Omit response fields still equal
                to their declared default.
            response_model_by_alias: Serialize the response using field
                aliases. Defaults to ``True``.
            strict_validation: Compile parameters written in the pre-Pydantic
                style onto the validated path as well, so missing or malformed
                values produce a 422 rather than the historical 500.
            tags: Sequence of OpenAPI tags for grouping this endpoint in
                generated documentation.
            security: List of security requirement dicts for OpenAPI docs.
            operation_id: Unique operation identifier for OpenAPI docs.
            deprecated: Whether to mark this endpoint as deprecated in
                the generated OpenAPI documentation.
            parameters: Additional OpenAPI parameter definitions beyond
                those extracted from the path pattern.
            middleware: List of route-specific middleware callables or
                middleware tuples to apply before the handler.
            exclude_from_schema: When True, this route is omitted from
                OpenAPI documentation generation entirely.
            auth: Optional authentication gate instance for route-level
                authentication and authorization checks.
            **kwargs: Additional metadata stored on the route instance
                for use by plugins or custom extensions.

        Raises:
            AssertionError: If the provided handler is not callable.
        """
        assert callable(handler), "Route handler must be callable"

        self.prefix: str | None = None
        if path == "":
            path = "/"
        self.raw_path = path
        self.handler = handler
        self.auth = auth
        self.handler_signature = inspect.signature(handler)
        self.name = name
        self.dependant = get_dependant(handler, strict_validation=strict_validation)
        self._router_dependants: list[Dependant] = []

        self.route_info = RouteBuilder.create_pattern(path)
        self.pattern: Pattern[str] = self.route_info.pattern
        self.param_names = self.route_info.param_names
        self.route_type = self.route_info.route_type
        self.middleware: list[MiddlewareType] = list(middleware) if middleware else []
        self.summary = summary
        self.description = description
        self.responses = responses
        self.request_model = request_model
        self.request_content_type = request_content_type
        self.strict_validation = strict_validation
        self.response_model = response_model
        self.response_model_many = response_model_many
        self.response_validator = (
            ResponseModelValidator(
                response_model,
                many=response_model_many,
                exclude_none=response_model_exclude_none,
                exclude_unset=response_model_exclude_unset,
                exclude_defaults=response_model_exclude_defaults,
                by_alias=response_model_by_alias,
            )
            if response_model is not None
            else None
        )
        _reject_unknown_route_kwargs(kwargs)
        self.kwargs = kwargs
        self.tags = tags
        # A gate that names schemes already says what the document should
        # say, so `security` is derived rather than written a second time.
        # An explicit `security=` still wins: a gateway may terminate auth
        # ahead of the application, and then the document has to describe
        # something this process does not enforce.
        if security is None and auth is not None:
            derive = getattr(auth, "security_requirements", None)
            if callable(derive):
                security = derive()
        self.security = security
        self.operation_id = operation_id
        self.deprecated = deprecated
        self.parameters = parameters or []
        self.exclude_from_schema = exclude_from_schema
        self.methods = {method.upper() for method in methods}
        if "GET" in self.methods:
            self.methods.add("HEAD")

        self._validated_param_name: str | None = self._find_body_param()

        async def _route_asgi_app(scope: Scope, receive: Receive, send: Send) -> None:
            """Serve as the base ASGI application for this route.

            Creates a Request and Response pair from the raw ASGI connection
            triple, invokes the route handler through the full dependency
            injection pipeline, serializes the handler's return value into
            an HTTP response, and sends it back to the client.

            This function is wrapped by route-level middleware before being
            assigned as the route's ``app`` attribute.

            Args:
                scope: ASGI scope dictionary containing request metadata.
                receive: ASGI receive callable for reading the request body.
                send: ASGI send callable for transmitting the response.

            Returns:
                None. The response is sent directly through ``send``.
            """
            request = Request(scope, receive, send)
            response_manager = Response(request)
            func_result = await self.get_route_handler(
                request, response_manager, **request.path_params
            )
            if isinstance(func_result, (BaseResponse, Responder)):
                # The handler built its own response — status, headers, and
                # body are its business, so the response model is not applied.
                response = func_result
            elif self.response_validator is not None:
                # Pydantic already serialized to JSON-safe primitives, so the
                # encoder is skipped: running it here would walk the entire
                # payload a second time, at a cost that grows with response
                # size rather than staying constant.
                response = JSONResponse(
                    content=self.response_validator.validate(func_result),
                    use_encoder=False,
                )
            else:
                encoded = jsonable_encoder(func_result)
                if isinstance(encoded, str):
                    response = BaseResponse(body=encoded, content_type="text/plain")
                else:
                    # Already encoded a line above. Letting JSONResponse encode
                    # again walks the whole payload a second time for a result
                    # it already has.
                    response = JSONResponse(content=encoded, use_encoder=False)
            return await response(scope, receive, send)

        route_handler_as_asgi_app = _route_asgi_app

        def apply_middleware(app: ASGIApp) -> ASGIApp:
            """Build the middleware chain around a base ASGI application.

            Wraps the provided ASGI application with all route-specific
            middleware registered on this route. Each middleware is first
            normalized through ``wrap_middleware`` to ensure a consistent
            interface, then applied in reverse order so that the first
            middleware in the list becomes the outermost layer.

            Args:
                app: The base ASGI application to wrap with the route's
                    middleware stack.

            Returns:
                The ASGI application wrapped with all registered route-level
                middleware, forming a complete middleware chain ready to
                process incoming requests.
            """
            middleware: list[Middleware] = []
            for mdw in self.middleware:
                middleware.append(wrap_middleware(mdw))
            for cls, args, kwargs in reversed(middleware):
                app = cls(app, *args, **kwargs)
            return app

        self.app = apply_middleware(route_handler_as_asgi_app)

    def _find_body_param(self) -> str | None:
        """Find the handler parameter that should receive the validated body.

        ``request_model`` declares a body on the decorator, so something has to
        decide which parameter receives it. The rule is name-agnostic and
        composes with everything else a handler can declare:

        A candidate is any parameter after ``request`` and ``response`` that is
        not filled by some other mechanism — so ``Depend`` and parameter
        markers are skipped because dependency injection fills them, and path
        parameter names are skipped because the router already passes those in
        as keyword arguments. Of the remaining candidates the **first parameter
        with no default** wins: Python requires such parameters to come first,
        and nothing else in the framework would ever fill one, so binding it is
        unambiguous.

        Failing that, a parameter sitting immediately after ``response`` and
        carrying a plain default is accepted, which preserves the behavior of
        handlers written against the original positional rule.

        Returns:
            The parameter name to inject the validated body into, or ``None``
            when the handler takes the body off ``request.validated_data``
            instead.
        """
        if self.request_model is None:
            return None

        candidates = [
            param
            for param in list(self.handler_signature.parameters.values())[2:]
            if param.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            and param.name not in self.param_names
            and not isinstance(param.default, (Depend, ParameterExtractor))
        ]

        for param in candidates:
            if param.default is inspect.Parameter.empty:
                return param.name

        if candidates and candidates[0].name == self._third_param_name():
            return candidates[0].name
        return None

    def _third_param_name(self) -> str | None:
        """Return the name of the handler's third parameter, if it has one.

        Used only to preserve the original positional binding rule for
        handlers that declare the body parameter with a default.

        Returns:
            The third parameter's name, or ``None`` for shorter signatures.
        """
        names = list(self.handler_signature.parameters.keys())
        return names[2] if len(names) >= 3 else None

    @property
    def resolved_params(self) -> list[SolvedParamDependency]:
        """Expose parameter extractors for backward-compatible OpenAPI generation.

        Provides access to the resolved parameter dependencies from the
        route's dependant object. This property exists primarily for
        backward compatibility with the OpenAPI documentation generation
        system that needs to inspect route parameters.

        Returns:
            A list of SolvedParamDependency instances representing the
            extracted and resolved parameters for this route's handler.
        """
        return list(self.dependant.param_extractors)

    @property
    def _own_resolved_dependencies(self) -> list[Dependant]:
        """Expose the handler's own dependency sub-tree for backward compatibility.

        Provides access to the list of dependant objects that represent
        the direct dependencies of this route's handler function. This
        property exists primarily for backward compatibility with systems
        that need to introspect the dependency graph.

        Returns:
            A list of Dependant instances representing the handler's
            direct dependency sub-tree, excluding transitive dependencies.
        """
        return list(self.dependant.dependencies)

    def match(self, scope: Scope) -> tuple[MatchStatus, Any]:
        """Match an HTTP request path against this route's URL pattern.

        Extracts the path from the ASGI scope and attempts to match it
        against the compiled regex pattern. When a match is found, path
        parameters are extracted and converted to their appropriate types.
        The method also checks whether the HTTP method is allowed, returning
        a partial match if the path matches but the method is not permitted.

        This distinction between full and partial matches allows the router
        to return proper 405 Method Not Allowed responses when a path exists
        but the requested method is not supported.

        Args:
            scope: ASGI scope containing the request path, HTTP method,
                and connection metadata used for route matching.

        Returns:
            A tuple of (MatchStatus, dict) containing the match status
            and any captured path parameters. Returns MatchStatus.FULL
            when both path and method match, MatchStatus.PARTIAL when
            only the path matches, or MatchStatus.NONE on failure.
        """
        if scope.get("type") != "http":
            return MatchStatus.NONE, {}
        path = get_route_path(scope)
        method = scope["method"]
        match = self.pattern.match(path)
        if match:
            matched_params = match.groupdict()
            for key, value in matched_params.items():
                matched_params[key] = self.route_info.convertor[key].convert(value)
            is_method_allowed = method.upper() in self.methods
            if not is_method_allowed:
                return MatchStatus.PARTIAL, matched_params

            return MatchStatus.FULL, matched_params
        return MatchStatus.NONE, {}

    def url_path_for(self, name: str, **path_params: dict[str, Any]) -> URLPath:
        """
        Generate a URL path for the route with the given name and parameters.

        Args:
            name: The name of the route.
            path_params: A dictionary of path parameters to substitute into the route's path.

        Returns:
            str: The generated URL path.

        Raises:
            ValueError: If the route name does not match or if required parameters are missing.
        """
        if name != self.name:
            raise ValueError(
                f"Route name '{name}' does not match the current route name '{self.name}'."
            )

        required_params = set(self.param_names)
        provided_params = set(path_params.keys())
        if required_params != provided_params:
            missing_params = required_params - provided_params
            extra_params = provided_params - required_params
            raise ValueError(
                f"Missing parameters: {missing_params}. Extra parameters: {extra_params}."
            )

        path = self.raw_path
        for param_name, param_value in path_params.items():
            param_value = str(param_value)

            path = re.sub(rf"\{{{param_name}(:[^}}]+)?}}", param_value, path)

        return URLPath(path=path, protocol="http")

    async def get_route_handler(
        self, request: Request, response: Response, **kwargs: Any
    ) -> Any:
        """
        The main hook for handling the request. This can be overridden in subclasses
        to modify how the handler is invoked.

        Args:
            request: The incoming HTTP request.
            response: The outgoing HTTP response.
            **kwargs: Captured path parameters.

        Returns:
            Any: The response from the handler.
        """
        cleanup_callbacks: list[Callable[[], Any]] = []
        injected: dict[str, Any] = {}
        dependency_cache: dict[Any, Any] = {}

        for rd in self._router_dependants:
            sub_values = await solve_dependencies(
                rd, request, dependency_cache, cleanup_callbacks
            )
            if rd.call is not None:
                result = await _execute_dependency(rd, sub_values, cleanup_callbacks)
                if rd.use_cache and rd.cache_key:
                    dependency_cache[rd.cache_key] = result

        handler_values = await solve_dependencies(
            self.dependant, request, dependency_cache, cleanup_callbacks
        )
        injected.update(handler_values)

        if self.request_model is not None:
            validated = await self._validate_body(request)
            request._validated_data = validated
            if self._validated_param_name:
                injected[self._validated_param_name] = validated

        if self.auth is not None:
            await self.auth.authenticate(request)

        # Path parameters reach the handler as **kwargs. When one is also
        # declared with a validation marker, the validated value supersedes the
        # raw captured one — without this the handler would receive the same
        # keyword twice.
        if injected:
            kwargs = {k: v for k, v in kwargs.items() if k not in injected}

        try:
            if is_async_callable(self.handler):
                return await self.handler(request, response, **kwargs, **injected)
            return await run_in_threadpool(
                self.handler, request, response, **kwargs, **injected
            )
        finally:
            for cleanup in reversed(cleanup_callbacks):
                result = cleanup()
                if inspect.isawaitable(result):
                    await result

    async def _validate_body(self, request: Request) -> Any:
        """Read and validate the JSON request body against ``request_model``.

        Args:
            request: The incoming request whose body should be validated.

        Returns:
            The validated model instance, or the raw decoded payload when
            ``request_model`` is not a Pydantic model class (it may be a
            documentation-only mapping of status codes to models).

        Raises:
            RequestValidationError: When ``strict_validation`` is enabled and
                the body is malformed or fails validation. Reports errors in
                the unified shape, prefixed with the ``body`` location.
            HTTPException: Otherwise, a 422 whose detail is the bare list of
                Pydantic errors — the shape sillo has always returned for
                ``request_model``, preserved for existing clients.
        """
        try:
            payload = await request.json
        except Exception:
            errors = [
                {
                    "loc": ["body"],
                    "msg": "Request body is not valid JSON",
                    "type": "json_invalid",
                }
            ]
            # Malformed JSON used to escape as an unhandled decode error and
            # surface as a 500. It is a client mistake, so it is a 422 in both
            # modes; only the payload shape differs.
            if self.strict_validation:
                raise RequestValidationError(errors)
            raise HTTPException(status_code=422, detail=errors)

        if not (
            isinstance(self.request_model, type)
            and issubclass(self.request_model, BaseModel)
        ):
            return payload

        try:
            # model_validate rather than the historical ``Model(**payload)``
            # splat: a JSON array or scalar body now reports as a validation
            # error instead of raising TypeError and becoming a 500.
            return self.request_model.model_validate(payload)
        except ValidationError as exc:
            if self.strict_validation:
                raise RequestValidationError(
                    prefix_errors(exc, "body"), body=payload
                ) from exc
            raise HTTPException(status_code=422, detail=exc.errors()) from exc

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process an incoming HTTP request using the route's middleware stack.

        Dispatches the request through the route's ASGI application chain
        which includes all route-specific middleware and the request handler.
        If the HTTP method is not in the allowed methods list, a 405 Method
        Not Allowed JSON response is returned instead of invoking the handler.

        This method is called by the router after a successful path match
        has been confirmed via the ``match`` method.

        Args:
            scope: ASGI scope containing request information including
                path, method, headers, and captured path parameters.
            receive: ASGI receive callable for reading the request body
                and other incoming messages from the client.
            send: ASGI send callable for transmitting the response data
                back to the client.
        """

        if self.methods and scope["method"] not in self.methods:
            response = JSONResponse(
                {"detail": "Method Not Allowed"},
                status_code=405,
                headers={"Allow": ", ".join(sorted(self.methods))},
            )
            return await response(scope, receive, send)

        await self.app(scope, receive, send)

    def __repr__(self) -> str:
        """Return a detailed string representation of this route.

        Produces a human-readable string that includes the raw path pattern
        and the set of allowed HTTP methods. This is useful for debugging
        and logging purposes, providing a quick overview of the route's
        configuration at a glance.

        Returns:
            A formatted string in the form
            ``<Route /path methods={'GET', 'POST'}>`` showing the
            key attributes of this HTTP route.
        """
        return f"<Route {self.raw_path} methods={self.methods}>"


class Router(BaseRouter):
    """Main router implementation for the sillo ASGI framework.

    The Router is the central component for organizing and dispatching HTTP
    and WebSocket requests. It maintains a collection of routes, manages
    middleware stacks, supports nested sub-routers, and provides decorator
    methods for convenient route registration.

    Key features include prefix-based route grouping, dependency injection
    propagation, tag inheritance for OpenAPI documentation, and flexible
    middleware application at both router and route levels.

    The router implements the ASGI callable interface, allowing it to be
    used directly as an ASGI application or mounted within other ASGI
    applications.
    """

    def __init__(
        self,
        prefix: str | None = None,
        routes: Sequence[BaseRoute] = [],
        tags: Sequence[str] | None = None,
        exclude_from_schema: bool = False,
        name: str | None = None,
        dependencies: list[Depend] | None = None,
        route_class: type[Route] = Route,
        strict_validation: bool = False,
    ):
        """Initialize the router with configuration options.

        Creates a new Router instance with the specified prefix, initial
        routes, tags, and dependency injection configuration. The router
        validates the prefix format and establishes the dependency graph
        for all registered routes.

        An EventEmitter is created for lifecycle event handling, and the
        route dependency tree is refreshed to ensure all routes have the
        correct inherited dependencies.

        Args:
            prefix: URL path prefix for all routes in this router. Should
                start with a forward slash. A warning is issued if it does
                not, and the prefix is corrected automatically.
            routes: Initial sequence of route instances to register with
                this router upon creation.
            tags: Default OpenAPI tags applied to all routes in this router.
                Individual routes can add additional tags.
            exclude_from_schema: When True, all routes in this router are
                excluded from OpenAPI documentation generation.
            name: Optional name for this router, used in nested URL
                generation with dot-separated notation.
            dependencies: List of dependency injection definitions that
                apply to all routes in this router.
            strict_validation: Propagated to every route created by this
                router, opting parameters declared in the pre-Pydantic style
                into full validation so bad input returns 422 rather than 500.
            route_class: The Route class to use when creating new routes
                via decorator methods. Defaults to the standard Route class.
        """
        self.prefix = prefix or ""
        self.routes = list(routes)
        self.middleware: list[Middleware] = []
        self.sub_routers: dict[str, Router | ASGIApp] = {}
        self.route_class = route_class
        self.strict_validation = strict_validation
        self.tags = tags or []
        self.exclude_from_schema = exclude_from_schema
        self.name = name
        self.event = EventEmitter()
        # `Depend()` is allowed to carry no callable, so a router-level
        # dependency can be a marker with nothing to solve. Those are skipped:
        # get_dependant() would be inspecting None. This was hidden by an
        # implicit-Optional annotation that claimed dependency was never None.
        self.dependencies: list[Dependant] = [
            get_dependant(d.dependency)
            for d in (dependencies or [])
            if d.dependency is not None
        ]
        self._inherited_dependencies: list[Dependant] = []
        self.root_path = ""

        if self.prefix and not self.prefix.startswith("/"):
            warnings.warn("Router prefix should start with '/'")
            self.prefix = f"/{self.prefix}"

        self._refresh_route_dependencies()

    def _get_combined_dependencies(self) -> list[Dependant]:
        """Combine inherited and local dependencies into a single list.

        Merges the dependencies inherited from parent routers with the
        dependencies defined locally on this router. Inherited dependencies
        appear first to ensure proper resolution order in the dependency
        injection pipeline.

        Returns:
            A list of Dependant instances representing all dependencies
            that should be applied to routes in this router, combining
            both inherited and locally defined entries.
        """
        return [*self._inherited_dependencies, *self.dependencies]

    def _refresh_route_dependencies(self) -> None:
        """Propagate combined dependencies to all registered routes.

        Iterates through all routes and updates their router-level
        dependant lists with the current combined dependencies. For
        Route instances, the dependants are set directly. For Group
        instances containing a Router, the inherited dependencies are
        propagated recursively through the sub-router hierarchy.

        This method is called whenever dependencies change to ensure
        all routes have up-to-date dependency information.
        """
        combined_dependencies = self._get_combined_dependencies()
        for route in self.routes:
            if isinstance(route, Route):
                route._router_dependants = list(combined_dependencies)
            elif isinstance(route, Group):
                mounted_router = getattr(route, "_base_app", None)
                if isinstance(mounted_router, Router):
                    mounted_router._set_inherited_dependencies(combined_dependencies)

    def _set_inherited_dependencies(
        self, inherited_dependencies: Sequence[Dependant]
    ) -> None:
        """Set dependencies inherited from a parent router and refresh routes.

        Updates the inherited dependencies list and triggers a refresh of
        all route dependencies to incorporate the new inherited values.
        This method is called by parent routers when mounting sub-routers
        to propagate the dependency chain downward.

        Args:
            inherited_dependencies: Sequence of Dependant instances from
                the parent router that should be applied to all routes
                in this router.
        """
        self._inherited_dependencies = list(inherited_dependencies)
        self._refresh_route_dependencies()

    def build_middleware_stack(self, app: ASGIApp) -> ASGIApp:
        """Build the middleware stack by applying all registered middleware.

        Constructs the full middleware chain by wrapping the provided ASGI
        application with all middleware components registered on this router.
        Middleware is applied in reverse order so that the first middleware
        added via ``use`` is the outermost wrapper in the call chain.

        This method is called during request dispatch to ensure that all
        router-level middleware is properly applied before the request
        reaches the matched route handler.

        Args:
            app: The base ASGI application to wrap with middleware. This
                is typically the internal request dispatching application.

        Returns:
            The ASGI application wrapped with all registered middleware,
            forming a complete middleware stack ready to process requests.
        """

        for cls, args, kwargs in reversed(self.middleware):
            app = cls(app, *args, **kwargs)
        return app

    def add_route(
        self,
        route: Annotated[
            BaseRoute | None,
            Doc("An instance of the Route class representing an HTTP route."),
        ] = None,
        path: Annotated[
            str | None,
            Doc("""
                URL path pattern for the HEAD endpoint.
                Example: '/api/v1/resources/{id}'
            """),
        ] = None,
        methods: Annotated[
            list[str],
            Doc("""
                List of HTTP methods this route should handle.
                Common methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']
                Defaults to all standard methods if not specified.
            """),
        ] = allowed_methods_default,
        handler: Annotated[
            HandlerType | None,
            Doc("""
                Async handler function for HEAD requests.
                Example:
                async def check_resource(request, response):
                    exists = await Resource.exists(request.path_params['id'])
                    return response.status(200 if exists else 404)
            """),
        ] = None,
        name: Annotated[
            str | None,
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-check-resource'
            """),
        ] = None,
        summary: Annotated[
            str | None,
            Doc("""
                Brief endpoint summary.
                Example: 'Check resource existence'
            """),
        ] = None,
        description: Annotated[
            str | None,
            Doc("""
                Detailed endpoint description.
                Example: 'Returns headers only to check if resource exists'
            """),
        ] = None,
        responses: Annotated[
            ArgsType | None,
            Doc("""
                Response schemas by status code.
                Example: {
                    200: None,
                    404: None
                }
            """),
        ] = None,
        request_model: Annotated[
            ArgsType | None,
            Doc("""
                Model for request validation.
                Example:
                class ResourceCheck(BaseModel):
                    check_children: bool = False
            """),
        ] = None,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "multipart/form-data",
                "application/x-www-form-urlencoded",
            ],
            Doc(
                "Content type for the request body in OpenAPI docs. Defaults to 'application/json'."
            ),
        ] = "application/json",
        middleware: Annotated[
            list[Any],
            Doc("""
                Route-specific middleware.
                Example: [cache_control('public')]
            """),
        ] = [],
        tags: Annotated[
            list[str] | None,
            Doc("""
                OpenAPI tags for grouping.
                Example: ["Resource Management"]
            """),
        ] = None,
        security: Annotated[
            list[dict[str, list[str]]] | None,
            Doc("""
                Security requirements.
                Example: [{"ApiKeyAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            str | None,
            Doc("""
                Unique operation ID.
                Example: 'checkResource'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            list[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="X-Check-Type", in_="header")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-head-only": True}
            """),
        ],
    ) -> None:
        """Add an HTTP route to the router's route collection.

        Registers a route on this router either from a pre-constructed
        ``Route`` instance or by constructing one from the provided keyword
        arguments. When a ``Route`` instance is provided, the router's tags
        are prepended to the route's existing tags, schema exclusion is
        propagated from the router level, and combined dependencies are
        attached to the route for dependency injection.

        Non-``Route`` base routes (such as ``Group`` or ``WebsocketRoute``)
        are appended directly without tag or dependency processing, as they
        manage their own configuration independently.

        Args:
            route: A pre-constructed ``Route`` instance to register. When
                provided, all other parameters are ignored.
            path: URL path pattern for the route. Required when ``route``
                is not provided.
            methods: List of HTTP methods this route should handle.
                Defaults to all standard methods if not specified.
            handler: Async handler function for processing requests.
                Required when ``route`` is not provided.
            name: Unique route name for URL generation with ``url_for``.
            summary: Brief endpoint summary for OpenAPI documentation.
            description: Detailed endpoint description for OpenAPI docs.
            responses: Response schemas by HTTP status code for OpenAPI.
            request_model: Pydantic model for request body validation.
            request_content_type: Content type for the request body in
                OpenAPI docs. Defaults to ``"application/json"``.
            middleware: List of route-specific middleware to apply.
            tags: OpenAPI tags for grouping related endpoints.
            security: Security requirements for OpenAPI documentation.
            operation_id: Unique operation ID for OpenAPI documentation.
            deprecated: Whether to mark the endpoint as deprecated in
                the generated OpenAPI documentation.
            parameters: Additional OpenAPI parameter definitions.
            exclude_from_schema: When True, hides this route from OpenAPI
                documentation entirely.
            **kwargs: Additional metadata stored on the route instance.

        Returns:
            None. The route is appended to the router's internal route
            list after tag and dependency processing.

        Raises:
            ValueError: If neither ``route`` nor both ``path`` and
                ``handler`` are provided.
        """
        if not route:
            if (not path) or (not handler):
                raise ValueError(
                    "path and handler are required if route is not provided"
                )
            kwargs.setdefault("strict_validation", self.strict_validation)
            route = Route(
                path=path,
                handler=handler,
                methods=methods,
                name=name,
                summary=summary,
                description=description,
                responses=responses,
                request_model=request_model,
                request_content_type=request_content_type,
                middleware=middleware,
                tags=tags,
                security=security,
                operation_id=operation_id,
                deprecated=deprecated,
                parameters=parameters,
                exclude_from_schema=exclude_from_schema,
                **kwargs,
            )

        if not isinstance(route, Route):
            self.routes.append(route)
            return

        if route.tags:
            route.tags = list(self.tags) + list(route.tags)
        else:
            route.tags = self.tags
        if self.exclude_from_schema:
            route.exclude_from_schema = True
        route._router_dependants = list(self._get_combined_dependencies())

        self.routes.append(route)

    def use(self, middleware: MiddlewareType) -> None:
        """Register a middleware component on this router.

        Adds a middleware callable to the router's middleware stack. The
        middleware is wrapped in an ``ASGIRequestResponseBridge`` to ensure
        compatibility with the internal ASGI middleware pipeline, then
        inserted at the beginning of the middleware list so that it
        executes as the outermost layer in the request processing chain.

        Router-level middleware applies to all routes registered on this
        router and its sub-routers, making it suitable for cross-cutting
        concerns such as authentication, logging, or CORS handling.

        Args:
            middleware: A middleware callable or middleware tuple following
                the framework's middleware interface. Can be a simple async
                callable or a tuple of ``(cls, args, kwargs)`` for
                class-based middleware with constructor arguments.

        Returns:
            None. The middleware is inserted at the front of the router's
            internal middleware list.
        """
        if callable(middleware):
            mdw = Middleware(ASGIRequestResponseBridge, dispatch=middleware)
            self.middleware.insert(0, mdw)

    def get(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the GET endpoint.
                Supports path parameters using {param} syntax.
                Example: '/users/{user_id}'
            """),
        ],
        handler: Annotated[
            HandlerType | None,
            Doc("""
                Async handler function for GET requests.
                Receives (request, response) and returns response or raw data.
                
                Example:
                async def get_user(request, response, user_id: str):
                    user = await get_user_from_db(user_id)
                    return response.json(user)
            """),
        ] = None,
        name: Annotated[
            str | None,
            Doc("""
                Unique route identifier for URL generation.
                Example: 'get-user-by-id'
            """),
        ] = None,
        summary: Annotated[
            str | None,
            Doc("""
                Brief summary for OpenAPI documentation.
                Example: 'Retrieves a user by ID'
            """),
        ] = None,
        description: Annotated[
            str | None,
            Doc("""
                Detailed description for OpenAPI documentation.
                Example: 'Returns full user details including profile information'
            """),
        ] = None,
        responses: Annotated[
            ArgsType | None,
            Doc("""
                Response models by status code.
                Example: 
                {
                    200: UserSchema,
                    404: {"description": "User not found"},
                    500: {"description": "Server error"}
                }
            """),
        ] = None,
        request_model: Annotated[
            ArgsType | None,
            Doc("""
                Pydantic model or model mapping for request validation.
                Can be a single model, a dict of status codes to models, or a nested dict.
                Example:
                class UserQuery(BaseModel):
                    active_only: bool = True
                    limit: int = 100
            """),
        ] = None,
        middleware: Annotated[
            list[Any],
            Doc("""
                List of route-specific middleware functions.
                Example: [auth_required, rate_limit]
            """),
        ] = [],
        tags: Annotated[
            list[str] | None,
            Doc("""
                OpenAPI tags for grouping related endpoints.
                Example: ["Users", "Public"]
            """),
        ] = None,
        security: Annotated[
            list[dict[str, list[str]]] | None,
            Doc("""
                Security requirements for OpenAPI docs.
                Example: [{"BearerAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            str | None,
            Doc("""
                Unique operation identifier for OpenAPI.
                Example: 'users.get_by_id'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark endpoint as deprecated in docs.
                Example: True
            """),
        ] = False,
        parameters: Annotated[
            list[Parameter],
            Doc("""
                Additional OpenAPI parameter definitions.
                Example: [Parameter(name="fields", in_="query", description="Fields to include")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Exclude this route from OpenAPI docs.
                Example: True for internal endpoints
            """),
        ] = False,
        auth: Annotated[
            Any | None,
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional route metadata.
                Example: {"x-internal": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """Register a GET endpoint decorator with comprehensive OpenAPI support.

        Creates and registers a Route configured for HTTP GET requests on the
        given path. Can be used as a decorator with or without arguments, or
        called directly by passing the handler function. Supports full OpenAPI
        documentation metadata including response schemas, security requirements,
        and deprecation markers.

        When used as a decorator the original handler function is returned
        unchanged so it can still be referenced directly in application code.

        Args:
            path: URL path pattern for the GET endpoint, supporting dynamic
                parameters using curly brace syntax such as ``/users/{id}``.
            handler: Optional async handler function for GET requests. If
                provided the route is registered immediately; if omitted a
                decorator is returned instead.
            name: Unique route identifier used for URL generation with
                ``url_for``. Should be unique across the entire application.
            summary: Brief one-line summary for OpenAPI documentation.
            description: Detailed description of the endpoint for OpenAPI
                documentation generation.
            responses: Mapping of HTTP status codes to response schemas or
                description dicts for OpenAPI documentation.
            request_model: Pydantic model for request body validation, or a
                dict mapping status codes to models for complex scenarios.
            middleware: List of route-specific middleware functions or
                middleware tuples to apply before the handler.
            tags: OpenAPI tags for grouping related endpoints together in
                the generated API documentation.
            security: List of security requirement dicts for OpenAPI docs,
                such as ``[{"BearerAuth": []}]``.
            operation_id: Unique operation identifier for OpenAPI docs.
                Auto-generated from the path if not provided.
            deprecated: When True, marks the endpoint as deprecated in the
                generated OpenAPI documentation.
            parameters: Additional OpenAPI parameter definitions beyond
                those automatically extracted from the path pattern.
            exclude_from_schema: When True, this route is excluded from
                OpenAPI documentation entirely.
            auth: Optional route-level authentication gate instance.
            **kwargs: Additional route metadata stored on the route instance
                for use by plugins or custom extensions.

        Returns:
            A decorator function that registers the handler as a GET route
            and returns the original handler, or the original handler
            directly if it was provided.

        Raises:
            ValueError: If the path is empty or handler is not callable
                when constructing the underlying Route instance.
        """

        def decorator(handler: HandlerType) -> HandlerType:
            """Create a GET route from the handler and register it.

            Constructs a new Route instance configured for HTTP GET requests
            using the captured closure variables from the enclosing ``get``
            method call, then registers it with this router. The original
            handler is returned unchanged so it remains directly callable.

            Args:
                handler: The async handler function to wrap as a GET route.

            Returns:
                The original handler function, unmodified, allowing it to
                be referenced directly outside of the routing context.
            """
            route = self.route_class(
                path=path,
                handler=handler,
                methods=["GET"],
                name=name,
                summary=summary,
                description=description,
                responses=responses,
                request_model=request_model,
                request_content_type="application/json",
                middleware=middleware,
                tags=tags,
                security=security,
                operation_id=operation_id,
                deprecated=deprecated,
                parameters=parameters,
                exclude_from_schema=exclude_from_schema,
                auth=auth,
                **kwargs,
            )
            self.add_route(route)
            return handler

        if handler is None:
            return decorator
        return decorator(handler)

    def post(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the POST endpoint.
                Example: '/api/v1/users'
            """),
        ],
        handler: Annotated[
            HandlerType | None,
            Doc("""
                Async handler function for POST requests.
                Example:
                async def create_user(request, response):
                    user_data = request.json
                    return response.json(user_data, status=201)
            """),
        ] = None,
        name: Annotated[
            str | None,
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-create-user'
            """),
        ] = None,
        summary: Annotated[
            str | None,
            Doc("""
                Brief endpoint summary.
                Example: 'Create new user'
            """),
        ] = None,
        description: Annotated[
            str | None,
            Doc("""
                Detailed endpoint description.
                Example: 'Creates new user with provided data'
            """),
        ] = None,
        responses: Annotated[
            ArgsType | None,
            Doc("""
                Response schemas by status code.
                Example: {
                    201: UserSchema,
                    400: {"description": "Invalid input"},
                    409: {"description": "User already exists"}
                }
            """),
        ] = None,
        request_model: Annotated[
            ArgsType | None,
            Doc("""
                Model for request body validation.
                Example:
                class UserCreate(BaseModel):
                    username: str
                    email: EmailStr
                    password: str
            """),
        ] = None,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "multipart/form-data",
                "application/x-www-form-urlencoded",
            ],
            Doc(
                "Content type for the request body in OpenAPI docs. Defaults to 'application/json'."
            ),
        ] = "application/json",
        middleware: Annotated[
            list[Any],
            Doc("""
                Route-specific middleware.
                Example: [rate_limit(10), validate_content_type('json')]
            """),
        ] = [],
        tags: Annotated[
            list[str] | None,
            Doc("""
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """),
        ] = None,
        security: Annotated[
            list[dict[str, list[str]]] | None,
            Doc("""
                Security requirements.
                Example: [{"BearerAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            str | None,
            Doc("""
                Unique operation ID.
                Example: 'createUser'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            list[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="X-Request-ID", in_="header")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Any | None,
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-audit-log": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """Register a POST endpoint decorator with request validation support.

        Creates and registers a Route configured for HTTP POST requests on the
        given path. Delegates to the generic ``route`` method with the methods
        list set to ``["POST"]``. Supports the same decorator pattern and full
        OpenAPI documentation metadata as all other HTTP method decorators.

        POST endpoints typically handle resource creation and operations that
        cause side effects on the server. The ``request_model`` parameter enables
        automatic Pydantic validation of the incoming request body.

        Args:
            path: URL path pattern for the POST endpoint, supporting dynamic
                parameters using curly brace syntax.
            handler: Optional async handler function for POST requests. If
                provided the route is registered immediately; if omitted a
                decorator is returned instead.
            name: Unique route identifier used for URL generation with
                ``url_for``. Should be unique across the application.
            summary: Brief one-line summary for OpenAPI documentation.
            description: Detailed description of the endpoint for OpenAPI
                documentation generation.
            responses: Mapping of HTTP status codes to response schemas or
                description dicts for OpenAPI documentation.
            request_model: Pydantic model for request body validation, or a
                dict mapping status codes to models for complex scenarios.
            request_content_type: Content type for the request body in OpenAPI
                docs. Defaults to ``"application/json"``.
            middleware: List of route-specific middleware functions or
                middleware tuples to apply before the handler.
            tags: OpenAPI tags for grouping related endpoints together in
                the generated API documentation.
            security: List of security requirement dicts for OpenAPI docs.
            operation_id: Unique operation identifier for OpenAPI docs.
                Auto-generated from the path if not provided.
            deprecated: When True, marks the endpoint as deprecated in the
                generated OpenAPI documentation.
            parameters: Additional OpenAPI parameter definitions beyond
                those automatically extracted from the path pattern.
            exclude_from_schema: When True, this route is excluded from
                OpenAPI documentation entirely.
            auth: Optional route-level authentication gate instance.
            **kwargs: Additional route metadata stored on the route instance
                for use by plugins or custom extensions.

        Returns:
            A decorator function that registers the handler as a POST route
            and returns the original handler, or the original handler
            directly if it was provided.

        Raises:
            ValueError: If the path is empty or handler is not callable
                when constructing the underlying Route instance.
        """
        return self.route(
            path=path,
            methods=["POST"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type=request_content_type,
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def delete(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the DELETE endpoint.
                Example: '/api/v1/users/{id}'
            """),
        ],
        handler: Annotated[
            HandlerType | None,
            Doc("""
                Async handler function for DELETE requests.
                Example:
                async def delete_user(request, response):
                    user_id = request.path_params['id']
                    return response.json({"deleted": user_id})
            """),
        ] = None,
        name: Annotated[
            str | None,
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-delete-user'
            """),
        ] = None,
        summary: Annotated[
            str | None,
            Doc("""
                Brief endpoint summary.
                Example: 'Delete user account'
            """),
        ] = None,
        description: Annotated[
            str | None,
            Doc("""
                Detailed endpoint description.
                Example: 'Permanently deletes user account and all associated data'
            """),
        ] = None,
        responses: Annotated[
            ArgsType | None,
            Doc("""
                Response schemas by status code.
                Example: {
                    204: None,
                    404: {"description": "User not found"},
                    403: {"description": "Forbidden"}
                }
            """),
        ] = None,
        request_model: Annotated[
            ArgsType | None,
            Doc("""
                Model for request validation.
                Example:
                class DeleteConfirmation(BaseModel):
                    confirm: bool
            """),
        ] = None,
        middleware: Annotated[
            list[Any],
            Doc("""
                Route-specific middleware.
                Example: [admin_required, confirm_action]
            """),
        ] = [],
        tags: Annotated[
            list[str] | None,
            Doc("""
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """),
        ] = None,
        security: Annotated[
            list[dict[str, list[str]]] | None,
            Doc("""
                Security requirements.
                Example: [{"BearerAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            str | None,
            Doc("""
                Unique operation ID.
                Example: 'deleteUser'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            list[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="confirm", in_="query")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Any | None,
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-destructive": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """Register a DELETE endpoint decorator for resource removal operations.

        Creates and registers a Route configured for HTTP DELETE requests on the
        given path. Delegates to the generic ``route`` method with the methods
        list set to ``["DELETE"]``. Supports the same decorator pattern and full
        OpenAPI documentation metadata as all other HTTP method decorators.

        DELETE endpoints typically handle resource removal or soft-deletion.
        The ``responses`` parameter should document 204 No Content for success
        and 404 Not Found for missing resources.

        Args:
            path: URL path pattern for the DELETE endpoint, supporting dynamic
                parameters using curly brace syntax.
            handler: Optional async handler function for DELETE requests. If
                provided the route is registered immediately; if omitted a
                decorator is returned instead.
            name: Unique route identifier used for URL generation with
                ``url_for``. Should be unique across the application.
            summary: Brief one-line summary for OpenAPI documentation.
            description: Detailed description of the endpoint for OpenAPI
                documentation generation.
            responses: Mapping of HTTP status codes to response schemas or
                description dicts for OpenAPI documentation.
            request_model: Pydantic model for request body validation, or a
                dict mapping status codes to models for complex scenarios.
            middleware: List of route-specific middleware functions or
                middleware tuples to apply before the handler.
            tags: OpenAPI tags for grouping related endpoints together in
                the generated API documentation.
            security: List of security requirement dicts for OpenAPI docs.
            operation_id: Unique operation identifier for OpenAPI docs.
                Auto-generated from the path if not provided.
            deprecated: When True, marks the endpoint as deprecated in the
                generated OpenAPI documentation.
            parameters: Additional OpenAPI parameter definitions beyond
                those automatically extracted from the path pattern.
            exclude_from_schema: When True, this route is excluded from
                OpenAPI documentation entirely.
            auth: Optional route-level authentication gate instance.
            **kwargs: Additional route metadata stored on the route instance
                for use by plugins or custom extensions.

        Returns:
            A decorator function that registers the handler as a DELETE route
            and returns the original handler, or the original handler
            directly if it was provided.

        Raises:
            ValueError: If the path is empty or handler is not callable
                when constructing the underlying Route instance.
        """
        return self.route(
            path=path,
            methods=["DELETE"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type="application/json",
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def put(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the PUT endpoint.
                Example: '/api/v1/users/{id}'
            """),
        ],
        handler: Annotated[
            HandlerType | None,
            Doc("""
                Async handler function for PUT requests.
                Example:
                async def update_user(request, response):
                    user_id = request.path_params['id']
                    return response.json({"updated": user_id})
            """),
        ] = None,
        name: Annotated[
            str | None,
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-update-user'
            """),
        ] = None,
        summary: Annotated[
            str | None,
            Doc("""
                Brief endpoint summary.
                Example: 'Update user details'
            """),
        ] = None,
        description: Annotated[
            str | None,
            Doc("""
                Detailed endpoint description.
                Example: 'Full update of user resource'
            """),
        ] = None,
        responses: Annotated[
            ArgsType | None,
            Doc("""
                Response schemas by status code.
                Example: {
                    200: UserSchema,
                    400: {"description": "Invalid input"},
                    404: {"description": "User not found"}
                }
            """),
        ] = None,
        request_model: Annotated[
            ArgsType | None,
            Doc("""
                Model for request body validation.
                Example:
                class UserUpdate(BaseModel):
                    email: Optional[EmailStr]
                    password: Optional[str]
            """),
        ] = None,
        middleware: Annotated[
            list[Any],
            Doc("""
                Route-specific middleware.
                Example: [owner_required, validate_etag]
            """),
        ] = [],
        tags: Annotated[
            list[str] | None,
            Doc("""
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """),
        ] = None,
        security: Annotated[
            list[dict[str, list[str]]] | None,
            Doc("""
                Security requirements.
                Example: [{"BearerAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            str | None,
            Doc("""
                Unique operation ID.
                Example: 'updateUser'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            list[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="If-Match", in_="header")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Any | None,
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ],
            Doc("""
                Request content type.
                Example: 'application/json'
            """),
        ] = "application/json",
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-idempotent": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """Register a PUT endpoint decorator for full resource replacement.

        Creates and registers a Route configured for HTTP PUT requests on the
        given path. Delegates to the generic ``route`` method with the methods
        list set to ``["PUT"]``. Supports the same decorator pattern and full
        OpenAPI documentation metadata as all other HTTP method decorators.

        PUT endpoints typically handle full resource replacement where the
        client sends a complete representation of the resource. The
        ``request_model`` parameter enables automatic Pydantic validation of
        the incoming request body before it reaches the handler.

        Args:
            path: URL path pattern for the PUT endpoint, supporting dynamic
                parameters using curly brace syntax.
            handler: Optional async handler function for PUT requests. If
                provided the route is registered immediately; if omitted a
                decorator is returned instead.
            name: Unique route identifier used for URL generation with
                ``url_for``. Should be unique across the application.
            summary: Brief one-line summary for OpenAPI documentation.
            description: Detailed description of the endpoint for OpenAPI
                documentation generation.
            responses: Mapping of HTTP status codes to response schemas or
                description dicts for OpenAPI documentation.
            request_model: Pydantic model for request body validation, or a
                dict mapping status codes to models for complex scenarios.
            middleware: List of route-specific middleware functions or
                middleware tuples to apply before the handler.
            tags: OpenAPI tags for grouping related endpoints together in
                the generated API documentation.
            security: List of security requirement dicts for OpenAPI docs.
            operation_id: Unique operation identifier for OpenAPI docs.
                Auto-generated from the path if not provided.
            deprecated: When True, marks the endpoint as deprecated in the
                generated OpenAPI documentation.
            parameters: Additional OpenAPI parameter definitions beyond
                those automatically extracted from the path pattern.
            exclude_from_schema: When True, this route is excluded from
                OpenAPI documentation entirely.
            auth: Optional route-level authentication gate instance.
            request_content_type: Content type for the request body in
                OpenAPI docs. Defaults to ``"application/json"``.
            **kwargs: Additional route metadata stored on the route instance
                for use by plugins or custom extensions.

        Returns:
            A decorator function that registers the handler as a PUT route
            and returns the original handler, or the original handler
            directly if it was provided.

        Raises:
            ValueError: If the path is empty or handler is not callable
                when constructing the underlying Route instance.
        """
        return self.route(
            path=path,
            methods=["PUT"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type=request_content_type,
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def patch(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the PATCH endpoint.
                Example: '/api/v1/users/{id}'
            """),
        ],
        handler: Annotated[
            HandlerType | None,
            Doc("""
                Async handler function for PATCH requests.
                Example:
                async def partial_update_user(request, response):
                    user_id = request.path_params['id']
                    return response.json({"updated": user_id})
            """),
        ] = None,
        name: Annotated[
            str | None,
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-partial-update-user'
            """),
        ] = None,
        summary: Annotated[
            str | None,
            Doc("""
                Brief endpoint summary.
                Example: 'Partially update user details'
            """),
        ] = None,
        description: Annotated[
            str | None,
            Doc("""
                Detailed endpoint description.
                Example: 'Partial update of user resource'
            """),
        ] = None,
        responses: Annotated[
            ArgsType | None,
            Doc("""
                Response schemas by status code.
                Example: {
                    200: UserSchema,
                    400: {"description": "Invalid input"},
                    404: {"description": "User not found"}
                }
            """),
        ] = None,
        request_model: Annotated[
            ArgsType | None,
            Doc("""
                Model for request body validation.
                Example:
                class UserPatch(BaseModel):
                    email: Optional[EmailStr] = None
                    password: Optional[str] = None
            """),
        ] = None,
        middleware: Annotated[
            list[Any],
            Doc("""
                Route-specific middleware.
                Example: [owner_required, validate_patch]
            """),
        ] = [],
        tags: Annotated[
            list[str] | None,
            Doc("""
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """),
        ] = None,
        security: Annotated[
            list[dict[str, list[str]]] | None,
            Doc("""
                Security requirements.
                Example: [{"BearerAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            str | None,
            Doc("""
                Unique operation ID.
                Example: 'partialUpdateUser'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            list[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="fields", in_="query")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Any | None,
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ],
            Doc("""
                Request content type.
                Example: 'application/json'
            """),
        ] = "application/json",
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-partial-update": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """Register a PATCH endpoint decorator for partial resource updates.

        Creates and registers a Route configured for HTTP PATCH requests on the
        given path. Delegates to the generic ``route`` method with the methods
        list set to ``["PATCH"]``. Supports the same decorator pattern and full
        OpenAPI documentation metadata as all other HTTP method decorators.

        PATCH endpoints typically handle partial resource modifications where
        the client sends only the fields that need to change, as opposed to
        PUT which expects a complete resource representation.

        Args:
            path: URL path pattern for the PATCH endpoint, supporting dynamic
                parameters using curly brace syntax.
            handler: Optional async handler function for PATCH requests. If
                provided the route is registered immediately; if omitted a
                decorator is returned instead.
            name: Unique route identifier used for URL generation with
                ``url_for``. Should be unique across the application.
            summary: Brief one-line summary for OpenAPI documentation.
            description: Detailed description of the endpoint for OpenAPI
                documentation generation.
            responses: Mapping of HTTP status codes to response schemas or
                description dicts for OpenAPI documentation.
            request_model: Pydantic model for request body validation, or a
                dict mapping status codes to models for complex scenarios.
            middleware: List of route-specific middleware functions or
                middleware tuples to apply before the handler.
            tags: OpenAPI tags for grouping related endpoints together in
                the generated API documentation.
            security: List of security requirement dicts for OpenAPI docs.
            operation_id: Unique operation identifier for OpenAPI docs.
                Auto-generated from the path if not provided.
            deprecated: When True, marks the endpoint as deprecated in the
                generated OpenAPI documentation.
            parameters: Additional OpenAPI parameter definitions beyond
                those automatically extracted from the path pattern.
            exclude_from_schema: When True, this route is excluded from
                OpenAPI documentation entirely.
            auth: Optional route-level authentication gate instance.
            request_content_type: Content type for the request body in
                OpenAPI docs. Defaults to ``"application/json"``.
            **kwargs: Additional route metadata stored on the route instance
                for use by plugins or custom extensions.

        Returns:
            A decorator function that registers the handler as a PATCH route
            and returns the original handler, or the original handler
            directly if it was provided.

        Raises:
            ValueError: If the path is empty or handler is not callable
                when constructing the underlying Route instance.
        """
        return self.route(
            path=path,
            methods=["PATCH"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type=request_content_type,
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def options(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the OPTIONS endpoint.
                Example: '/api/v1/users'
            """),
        ],
        handler: Annotated[
            HandlerType | None,
            Doc("""
                Async handler function for OPTIONS requests.
                Example:
                async def user_options(request, response):
                    response.headers['Allow'] = 'GET, POST, OPTIONS'
                    return response
            """),
        ] = None,
        name: Annotated[
            str | None,
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-user-options'
            """),
        ] = None,
        summary: Annotated[
            str | None,
            Doc("""
                Brief endpoint summary.
                Example: 'Get supported operations'
            """),
        ] = None,
        description: Annotated[
            str | None,
            Doc("""
                Detailed endpoint description.
                Example: 'Returns supported HTTP methods and CORS headers'
            """),
        ] = None,
        responses: Annotated[
            ArgsType | None,
            Doc("""
                Response schemas by status code.
                Example: {
                    200: None,
                    204: None
                }
            """),
        ] = None,
        request_model: Annotated[
            ArgsType | None,
            Doc("""
                Model for request validation.
                Example:
                class OptionsQuery(BaseModel):
                    detailed: bool = False
            """),
        ] = None,
        middleware: Annotated[
            list[Any],
            Doc("""
                Route-specific middleware.
                Example: [cors_middleware]
            """),
        ] = [],
        tags: Annotated[
            list[str] | None,
            Doc("""
                OpenAPI tags for grouping.
                Example: ["CORS"]
            """),
        ] = None,
        security: Annotated[
            list[dict[str, list[str]]] | None,
            Doc("""
                Security requirements.
                Example: []
            """),
        ] = None,
        operation_id: Annotated[
            str | None,
            Doc("""
                Unique operation ID.
                Example: 'userOptions'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            list[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="Origin", in_="header")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Any | None,
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-cors": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """Register an OPTIONS endpoint decorator for CORS and method discovery.

        Creates and registers a Route configured for HTTP OPTIONS requests on
        the given path. Delegates to the generic ``route`` method with the
        methods list set to ``["OPTIONS"]``. Supports the same decorator
        pattern and full OpenAPI documentation metadata as all other HTTP
        method decorators.

        OPTIONS endpoints are commonly used for CORS preflight requests and
        for advertising the set of HTTP methods supported by a resource.
        Browsers send OPTIONS requests automatically before cross-origin
        requests to verify that the server permits the actual request.

        Args:
            path: URL path pattern for the OPTIONS endpoint, supporting
                dynamic parameters using curly brace syntax.
            handler: Optional async handler function for OPTIONS requests.
                If provided the route is registered immediately; if omitted
                a decorator is returned instead.
            name: Unique route identifier used for URL generation with
                ``url_for``. Should be unique across the application.
            summary: Brief one-line summary for OpenAPI documentation.
            description: Detailed description of the endpoint for OpenAPI
                documentation generation.
            responses: Mapping of HTTP status codes to response schemas or
                description dicts for OpenAPI documentation.
            request_model: Pydantic model for request body validation, or a
                dict mapping status codes to models for complex scenarios.
            middleware: List of route-specific middleware functions or
                middleware tuples to apply before the handler.
            tags: OpenAPI tags for grouping related endpoints together in
                the generated API documentation.
            security: List of security requirement dicts for OpenAPI docs.
            operation_id: Unique operation identifier for OpenAPI docs.
                Auto-generated from the path if not provided.
            deprecated: When True, marks the endpoint as deprecated in the
                generated OpenAPI documentation.
            parameters: Additional OpenAPI parameter definitions beyond
                those automatically extracted from the path pattern.
            exclude_from_schema: When True, this route is excluded from
                OpenAPI documentation entirely.
            auth: Optional route-level authentication gate instance.
            **kwargs: Additional route metadata stored on the route instance
                for use by plugins or custom extensions.

        Returns:
            A decorator function that registers the handler as an OPTIONS
            route and returns the original handler, or the original handler
            directly if it was provided.

        Raises:
            ValueError: If the path is empty or handler is not callable
                when constructing the underlying Route instance.
        """
        return self.route(
            path=path,
            methods=["OPTIONS"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type="application/json",
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def head(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the HEAD endpoint.
                Example: '/api/v1/resources/{id}'
            """),
        ],
        handler: Annotated[
            HandlerType | None,
            Doc("""
                Async handler function for HEAD requests.
                Example:
                async def check_resource(request, response):
                    exists = await Resource.exists(request.path_params['id'])
                    return response.status(200 if exists else 404)
            """),
        ] = None,
        name: Annotated[
            str | None,
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-check-resource'
            """),
        ] = None,
        summary: Annotated[
            str | None,
            Doc("""
                Brief endpoint summary.
                Example: 'Check resource existence'
            """),
        ] = None,
        description: Annotated[
            str | None,
            Doc("""
                Detailed endpoint description.
                Example: 'Returns headers only to check if resource exists'
            """),
        ] = None,
        responses: Annotated[
            ArgsType | None,
            Doc("""
                Response schemas by status code.
                Example: {
                    200: None,
                    404: None
                }
            """),
        ] = None,
        request_model: Annotated[
            ArgsType | None,
            Doc("""
                Model for request validation.
                Example:
                class ResourceCheck(BaseModel):
                    check_children: bool = False
            """),
        ] = None,
        middleware: Annotated[
            list[Any],
            Doc("""
                Route-specific middleware.
                Example: [cache_control('public')]
            """),
        ] = [],
        tags: Annotated[
            list[str] | None,
            Doc("""
                OpenAPI tags for grouping.
                Example: ["Resource Management"]
            """),
        ] = None,
        security: Annotated[
            list[dict[str, list[str]]] | None,
            Doc("""
                Security requirements.
                Example: [{"ApiKeyAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            str | None,
            Doc("""
                Unique operation ID.
                Example: 'checkResource'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            list[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="X-Check-Type", in_="header")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Any | None,
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-head-only": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """Register a HEAD endpoint decorator for header-only responses.

        Creates and registers a Route configured for HTTP HEAD requests on the
        given path. Delegates to the generic ``route`` method with the methods
        list set to ``["HEAD"]``. Supports the same decorator pattern and full
        OpenAPI documentation metadata as all other HTTP method decorators.

        HEAD endpoints return only headers without a response body, making them
        useful for checking resource existence, retrieving metadata such as
        content length or last-modified timestamps, and validating cache
        freshness without transferring the full resource.

        Args:
            path: URL path pattern for the HEAD endpoint, supporting dynamic
                parameters using curly brace syntax.
            handler: Optional async handler function for HEAD requests. If
                provided the route is registered immediately; if omitted a
                decorator is returned instead.
            name: Unique route identifier used for URL generation with
                ``url_for``. Should be unique across the application.
            summary: Brief one-line summary for OpenAPI documentation.
            description: Detailed description of the endpoint for OpenAPI
                documentation generation.
            responses: Mapping of HTTP status codes to response schemas or
                description dicts for OpenAPI documentation.
            request_model: Pydantic model for request body validation, or a
                dict mapping status codes to models for complex scenarios.
            middleware: List of route-specific middleware functions or
                middleware tuples to apply before the handler.
            tags: OpenAPI tags for grouping related endpoints together in
                the generated API documentation.
            security: List of security requirement dicts for OpenAPI docs.
            operation_id: Unique operation identifier for OpenAPI docs.
                Auto-generated from the path if not provided.
            deprecated: When True, marks the endpoint as deprecated in the
                generated OpenAPI documentation.
            parameters: Additional OpenAPI parameter definitions beyond
                those automatically extracted from the path pattern.
            exclude_from_schema: When True, this route is excluded from
                OpenAPI documentation entirely.
            auth: Optional route-level authentication gate instance.
            **kwargs: Additional route metadata stored on the route instance
                for use by plugins or custom extensions.

        Returns:
            A decorator function that registers the handler as a HEAD route
            and returns the original handler, or the original handler
            directly if it was provided.

        Raises:
            ValueError: If the path is empty or handler is not callable
                when constructing the underlying Route instance.
        """
        return self.route(
            path=path,
            methods=["HEAD"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type="application/json",
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def route(
        self,
        path: Annotated[
            str,
            Doc("""
                The URL path pattern for the route. Supports path parameters using curly braces:
                - '/users/{user_id}' - Simple path parameter
                - '/files/{filepath:path}' - Matches any path (including slashes)
                - '/items/{id:int}' - Type-constrained parameter
            """),
        ],
        methods: Annotated[
            list[str],
            Doc("""
                List of HTTP methods this route should handle.
                Common methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']
                Defaults to all standard methods if not specified.
            """),
        ] = allowed_methods_default,
        handler: Annotated[
            HandlerType | None,
            Doc("""
                The async handler function for this route. Must accept:
                - request: Request object
                - response: Response object
                And return either a Response object or raw data (dict, list, str)
            """),
        ] = None,
        name: Annotated[
            str | None,
            Doc("""
                Unique name for this route, used for URL generation with url_for().
                If not provided, will be generated from the path and methods.
            """),
        ] = None,
        summary: Annotated[
            str | None,
            Doc("Brief one-line description of the route for OpenAPI docs"),
        ] = None,
        description: Annotated[
            str | None, Doc("Detailed description of the route for OpenAPI docs")
        ] = None,
        responses: Annotated[
            ArgsType | None,
            Doc("""
                Response models by status code for OpenAPI docs.
                Example: {200: UserModel, 404: ErrorModel}
            """),
        ] = None,
        request_model: Annotated[
            ArgsType | None,
            Doc("Pydantic model for request body validation and OpenAPI docs"),
        ] = None,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "multipart/form-data",
                "application/x-www-form-urlencoded",
            ],
            Doc(
                "Content type for the request body in OpenAPI docs. Defaults to 'application/json'."
            ),
        ] = "application/json",
        middleware: Annotated[
            list[MiddlewareType],
            Doc("""
                List of middleware specific to this route.
                These will be executed in order before the route handler.
            """),
        ] = [],
        tags: Annotated[
            list[str] | None,
            Doc("""
                OpenAPI tags for grouping related routes in documentation.
                Inherits parent router tags if not specified.
            """),
        ] = None,
        security: Annotated[
            list[dict[str, list[str]]] | None,
            Doc("""
                Security requirements for this route.
                Example: [{"bearerAuth": []}] for JWT auth.
            """),
        ] = None,
        operation_id: Annotated[
            str | None,
            Doc("""
                Unique identifier for this operation in OpenAPI docs.
                Auto-generated if not provided.
            """),
        ] = None,
        deprecated: Annotated[
            bool, Doc("Mark route as deprecated in OpenAPI docs")
        ] = False,
        parameters: Annotated[
            list[Parameter],
            Doc("""
                Additional OpenAPI parameter definitions.
                Path parameters are automatically included from the path pattern.
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                If True, excludes this route from OpenAPI documentation.
                Useful for internal or admin routes.
            """),
        ] = False,
        auth: Annotated[
            Any | None,
            Doc("""
                Route-level authentication gate.  Pass a
                :class:`sillo.auth.useAuth` instance to require
                authentication and/or check permissions/scopes.
            """),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional route metadata that will be available in the request scope.
                Useful for custom extensions or plugin-specific data.
            """),
        ],
    ) -> HandlerType | Callable[..., HandlerType]:
        """Register a route with configurable HTTP methods and OpenAPI metadata.

        This is the most flexible route registration method, allowing full
        control over HTTP methods, request/response validation, and OpenAPI
        documentation generation. All convenience decorators (``get``, ``post``,
        ``put``, ``delete``, ``patch``, ``options``, ``head``) delegate to this
        method internally with their respective method lists.

        Can be used as a decorator with or without arguments, or called
        directly by passing the handler function. When used as a decorator
        the original handler is returned unchanged for direct reference.

        Args:
            path: URL path pattern with optional parameters using curly brace
                syntax such as ``/users/{user_id}`` or ``/files/{filepath:path}``.
            methods: List of HTTP methods this route accepts. Defaults to all
                standard methods if not specified.
            handler: Optional async function to handle requests. If provided
                the route is registered immediately; if omitted a decorator
                is returned instead.
            name: Unique route identifier used for URL generation with
                ``url_for``. Auto-generated from the path if not provided.
            summary: Brief one-line description of the route for OpenAPI
                documentation generation.
            description: Detailed description of the route for OpenAPI
                documentation generation.
            responses: Mapping of HTTP status codes to response models or
                description dicts for OpenAPI documentation.
            request_model: Pydantic model for request body validation and
                OpenAPI documentation generation.
            request_content_type: Content type for the request body in OpenAPI
                docs. Defaults to ``"application/json"``.
            middleware: List of route-specific middleware callables or tuples
                to execute in order before the route handler.
            tags: OpenAPI tags for grouping related routes together in the
                generated API documentation.
            security: List of security requirement dicts for OpenAPI docs,
                such as ``[{"bearerAuth": []}]`` for JWT authentication.
            operation_id: Unique identifier for this operation in OpenAPI
                docs. Auto-generated if not provided.
            deprecated: When True, marks the route as deprecated in the
                generated OpenAPI documentation.
            parameters: Additional OpenAPI parameter definitions beyond
                those automatically extracted from the path pattern.
            exclude_from_schema: When True, excludes this route from OpenAPI
                documentation entirely. Useful for internal or admin routes.
            auth: Optional route-level authentication gate instance for
                requiring authentication and checking permissions.
            **kwargs: Additional route metadata available in the request
                scope for use by plugins or custom extensions.

        Returns:
            The route handler function when used as a decorator, or a
            decorator function that registers the handler and returns it.

        Raises:
            ValueError: If the path is empty or handler is not callable
                when constructing the underlying Route instance.
        """

        def decorator(handler: HandlerType):
            """Create a route from the handler and register it.

            Constructs a new Route instance using the captured closure
            variables from the enclosing ``route`` method call, then
            registers it with this router via ``add_route``. The original
            handler is not returned; this decorator is used internally
            for side-effect registration only.

            Args:
                handler: The async handler function to wrap as a route
                    with the configured HTTP methods and metadata.

            Returns:
                None. The route is registered as a side effect via
                ``add_route`` on the enclosing router instance.
            """
            route_instance = self.route_class(
                path=path,
                handler=handler,
                methods=methods,
                name=name,
                summary=summary,
                description=description,
                responses=responses,
                request_model=request_model,
                request_content_type=request_content_type,
                middleware=middleware,
                tags=tags,
                security=security,
                operation_id=operation_id,
                deprecated=deprecated,
                parameters=parameters,
                exclude_from_schema=exclude_from_schema,
                auth=auth,
                **{"strict_validation": self.strict_validation, **kwargs},
            )
            self.add_route(route_instance)

        if handler is None:
            return decorator
        return decorator(handler)

    def add_ws_route(
        self,
        route: Annotated[
            WebsocketRoute,
            Doc("An instance of the Route class representing a WebSocket route."),
        ]
        | None = None,
        path: str | None = None,
        handler: WsHandlerType | None = None,
    ) -> None:
        """Add a WebSocket route to the application router.

        Registers a WebSocket route either from a pre-constructed
        ``WebsocketRoute`` instance or by creating one from the provided
        path and handler arguments. This enables the application to handle
        persistent WebSocket connections for real-time bidirectional
        communication between clients and the server.

        Exactly one of ``route`` or both ``path`` and ``handler`` must be
        provided. If ``route`` is given it is appended directly; otherwise
        a new ``WebsocketRoute`` is constructed from the path and handler.

        Args:
            route: A pre-constructed ``WebsocketRoute`` instance to register.
                When provided, ``path`` and ``handler`` are ignored.
            path: The URL path pattern for the WebSocket endpoint. Required
                when ``route`` is not provided. Supports dynamic parameters
                using curly brace syntax.
            handler: The async WebSocket handler function. Required when
                ``route`` is not provided. Must accept a single
                ``WebSocket`` argument.

        Returns:
            None. The route is appended to the router's internal route list.

        Raises:
            ValueError: If neither ``route`` nor both ``path`` and
                ``handler`` are provided.
        """
        if route is not None:
            self.routes.append(route)
        elif path is not None and handler is not None:
            self.routes.append(WebsocketRoute(path, handler))
        else:
            raise ValueError("Either route or both path and handler must be provided")

    def ws_route(
        self,
        path: Annotated[
            str, Doc("The WebSocket route path. Must be a valid URL pattern.")
        ],
        handler: Annotated[
            WsHandlerType | None,
            Doc("The WebSocket handler function. Must be an async function."),
        ] = None,
    ) -> Any:
        """Register a WebSocket route as a decorator or direct call.

        Creates and registers a ``WebsocketRoute`` for handling persistent
        WebSocket connections at the given path. Can be used as a decorator
        with or without the handler argument, enabling flexible registration
        patterns for WebSocket endpoints.

        When a handler is provided directly the route is registered
        immediately and the result of ``add_ws_route`` is returned. When
        handler is omitted a decorator is returned that wraps the handler
        and registers the route upon decoration.

        Args:
            path: The WebSocket route path pattern. Must be a valid URL
                pattern supporting dynamic parameters via curly brace syntax
                such as ``/ws/chat/{room_id}``.
            handler: Optional async WebSocket handler function. Must be a
                coroutine function accepting a single ``WebSocket`` argument.
                If provided the route is registered immediately.

        Returns:
            The original handler function if handler was provided directly,
            or a decorator function that registers the handler as a WebSocket
            route and returns the original handler.

        Raises:
            AssertionError: If the handler is not callable or is not an
                async coroutine function (raised during WebsocketRoute
                construction).
        """
        if handler:
            return self.add_ws_route(WebsocketRoute(path, handler))

        def decorator(handler: WsHandlerType) -> WsHandlerType:
            """Create a WebSocket route from the handler and register it.

            Constructs a new ``WebsocketRoute`` instance from the captured
            path and the provided handler, then registers it with this
            router via ``add_ws_route``. The original handler is returned
            unchanged so it remains directly callable outside the routing
            context.

            Args:
                handler: The async WebSocket handler function to wrap as
                    a WebSocket route at the configured path.

            Returns:
                The original handler function, unmodified, allowing it to
                be referenced directly outside of the routing context.
            """
            self.add_ws_route(WebsocketRoute(path, handler))
            return handler

        return decorator

    def url_for(self, _name: str, **path_params: Any) -> URLPath:
        """Generate a complete URL path including all router prefixes.

        Performs reverse URL resolution by looking up a named route and
        substituting the provided path parameters into its URL pattern.
        Supports both simple route names (searched directly in the current
        router's routes) and dot-separated nested names that traverse
        through ``Group`` objects to find routes in sub-routers.

        The returned ``URLPath`` includes the full path from the root of
        the application, incorporating all intermediate router prefixes
        accumulated during the nested route search.

        Args:
            _name: Route name to resolve. Simple names like ``"get_user"``
                search the current router directly. Dot-separated names
                like ``"api.v1.get_user"`` traverse nested Group objects
                recursively to find the target route.
            **path_params: Path parameters to substitute into the resolved
                route's URL pattern. Keys must match the parameter names
                defined in the route path using curly brace syntax.

        Returns:
            A ``URLPath`` instance containing the complete resolved path
            string including all router prefixes, with the ``"http"``
            protocol set.

        Raises:
            ValueError: If the named route cannot be found in the current
                router or any nested sub-routers, or if the route name
                format is invalid for nested resolution.
        """
        name_parts = _name.split(".")

        # If it's a simple route name (no dots), search directly in current routes
        if len(name_parts) == 1:
            route_name = name_parts[0]
            for route in self.routes:
                if getattr(route, "name", None) == route_name:
                    route_path = route.url_path_for(name=route_name, **path_params)
                    return URLPath(path=str(route_path), protocol="http")
            raise ValueError(f"Route '{route_name}' not found in router")

        # For nested routes, recursively search through Group objects
        return self._search_nested_route(_name, name_parts, [], **path_params)

    def _search_nested_route(
        self,
        full_name: str,
        name_parts: list[str],
        path_segments: list[str],
        **path_params: Any,
    ) -> URLPath:
        """Recursively search for a named route through nested Group objects.

        Traverses the router hierarchy by consuming dot-separated name parts
        one at a time. Each intermediate part is matched against Group objects
        in the current router's route list, and the search descends into the
        Group's underlying sub-router. The final name part is matched against
        actual route instances to produce the resolved URL.

        Path segments from each traversed Group are accumulated and prepended
        to the final route path, producing a complete URL that includes all
        intermediate router prefixes.

        Args:
            full_name: The original full dot-separated route name, used in
                error messages when resolution fails at any level.
            name_parts: Remaining list of name segments to resolve. The first
                element is matched against Groups or routes at the current
                level; remaining elements are passed recursively downward.
            path_segments: Accumulated path segments from parent routers and
                Groups traversed so far. Each segment has leading and trailing
                slashes stripped for clean joining.
            **path_params: Path parameters to substitute into the resolved
                route's URL pattern via ``url_path_for``.

        Returns:
            A ``URLPath`` instance containing the complete resolved path
            including all accumulated router prefixes, with the ``"http"``
            protocol set.

        Raises:
            ValueError: If no name parts remain, if a route with the
                expected name is not found at the current level, or if a
                Group does not contain a Router as its underlying app.
        """
        if not name_parts:
            raise ValueError(f"Invalid route name format: '{full_name}'")

        current_part = name_parts[0]
        remaining_parts = name_parts[1:]

        # If this is the last part, it's the route name
        if len(remaining_parts) == 0:
            for route in self.routes:
                if getattr(route, "name", None) == current_part:
                    route_path = route.url_path_for(name=current_part, **path_params)
                    path_segments.append(str(route_path).strip("/"))
                    full_path = "/" + "/".join(filter(None, path_segments))
                    return URLPath(path=full_path, protocol="http")
            raise ValueError(f"Route '{current_part}' not found in router")

        # Look for a Group with the current part as name
        for route in self.routes:
            if (
                isinstance(route, Group)
                and getattr(route, "name", None) == current_part
            ):
                # Add this Group's path to segments
                group_path = route.path.strip("/")
                if group_path:
                    new_path_segments = path_segments + [group_path]
                else:
                    new_path_segments = path_segments

                # Get the underlying router from the Group
                underlying_router = getattr(route, "_base_app", None)
                if isinstance(underlying_router, Router):
                    return underlying_router._search_nested_route(
                        full_name, remaining_parts, new_path_segments, **path_params
                    )
                else:
                    raise ValueError(
                        f"Group '{current_part}' does not contain a Router"
                    )

        raise ValueError(
            f"Router '{current_part}' not found while building URL for '{full_name}'"
        )

    def frontend(
        self,
        path: str = "/",
        directory: str | Path = "dist",
        fallback: str | bool | None = "auto",
        name: str | None = None,
        cache_control: str | None = None,
    ) -> None:
        """Mount a frontend SPA build directory with fallback routing.

        Registers a :class:`FrontendApp` as a :class:`Group` at the given
        path, so that static files from the build directory are served and
        unknown paths fall back to a fallback HTML file (typically
        ``index.html``). This enables single-page application hosting
        alongside API routes within the same server instance.

        Because this adds a route to the router's route list, any API routes
        registered *before* calling ``frontend()`` are matched first. This
        guarantees that API endpoints take precedence over the frontend
        catch-all, preventing API paths from being shadowed by the SPA.

        Args:
            path: URL path prefix to mount the frontend at. Defaults to
                ``"/"`` which catches all unmatched paths. Should start
                with a forward slash.
            directory: Path to the directory containing the built frontend
                files. Can be an absolute or relative filesystem path.
                Defaults to ``"dist"``.
            fallback: Fallback behaviour for unmatched paths. ``"auto"``
                (default) tries ``404.html`` then ``index.html``. Pass an
                explicit filename string to use a specific fallback file,
                or ``None``/``False`` to disable fallback entirely.
            name: Optional name for the route group, used with ``url_for``
                for reverse URL generation of the frontend mount point.
            cache_control: Optional ``Cache-Control`` header value applied
                to all static file responses served from this mount.

        Returns:
            None. A ``Group`` containing the ``FrontendApp`` is appended
            to the router's internal route list.

        Raises:
            FileNotFoundError: If the specified directory does not exist
                when the FrontendApp attempts to serve files.
        """
        frontend_app = FrontendApp(
            directory=directory,
            fallback=fallback,
            cache_control=cache_control,
        )
        group = Group(path=path, app=frontend_app, name=name)
        self.add_route(group)

    def __repr__(self) -> str:
        """Return a detailed string representation of this router.

        Produces a human-readable string that includes the router's URL
        prefix and the total number of registered routes. This is useful
        for debugging and logging purposes, providing a quick overview
        of the router's configuration at a glance.

        Returns:
            A formatted string in the form
            ``<Router prefix='/api' routes=5>`` showing the key
            attributes of this router instance.
        """
        return f"<Router prefix='{self.prefix}' routes={len(self.routes)}>"

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> Any:
        """Dispatch an incoming ASGI request through the full middleware stack.

        Implements the ASGI callable interface, allowing the Router to be
        used directly as an ASGI application. Builds the complete middleware
        stack by wrapping the internal dispatch application with all
        registered router-level middleware, then invokes the resulting
        application with the provided ASGI connection triple.

        This method is the entry point for all requests handled by this
        router, whether mounted as the top-level application or as a
        sub-router within a larger application hierarchy.

        Args:
            scope: ASGI scope dictionary containing request information
                including type, path, method, headers, and query string.
            receive: ASGI receive callable for reading the request body
                and other incoming messages from the client.
            send: ASGI send callable for transmitting the response data
                back to the client.

        Returns:
            The return value of the inner ASGI application, which is
            typically None for standard ASGI applications.
        """
        app = self.build_middleware_stack(cast(ASGIApp, self.app))
        await app(scope, receive, send)

    async def app(self, scope: Scope, receive: Receive, send: Send):
        """Dispatch a request to the first matching route handler.

        Iterates through all registered routes in order, attempting to match
        the incoming request path against each route's URL pattern. When a
        full match is found (both path and HTTP method match), the request
        is dispatched to that route's handler immediately. If only a partial
        match is found (path matches but method does not), the first partial
        match is stored and used if no full match is found later, enabling
        proper 405 Method Not Allowed responses.

        For HTTP requests that match no route, a ``NotFoundException`` is
        raised which results in a 404 response. For WebSocket connections
        that match no route, a close frame with code 4404 is sent to the
        client instead of raising an exception.

        Args:
            scope: ASGI scope dictionary containing request information
                including type, path, method, headers, and query string.
                The scope is mutated to include ``"app"`` and ``"route_params"``
                keys for downstream use by handlers.
            receive: ASGI receive callable for reading the request body
                and other incoming messages from the client.
            send: ASGI send callable for transmitting the response data
                back to the client.

        Returns:
            None. The response is sent directly through the ``send`` callable.

        Raises:
            NotFoundException: If no route matches the request path for
                HTTP-type connections.
        """
        scope["app"] = self

        path_match = None
        path_match_params: dict[str, Any] = {}

        for route in self.routes:
            match, matched_params = route.match(scope)
            if match == MatchStatus.FULL:
                scope["route_params"] = RouteParam(matched_params)
                await route.handle(scope, receive, send)
                return
            elif match == MatchStatus.PARTIAL and path_match is None:
                path_match = route
                path_match_params = matched_params

        if path_match is not None:
            scope["route_params"] = RouteParam(path_match_params)
            await path_match.handle(scope, receive, send)
            return
        if scope.get("type") == "http":
            raise NotFoundException
        else:
            await send({"type": "websocket.close", "code": 4404})

    def mount_router(self, app: Router, name: str | None = None):
        """Mount a sub-router under this router using its prefix.

        Attaches another Router instance as a sub-application wrapped in a
        ``Group`` object, using the sub-router's prefix as the mount path.
        The sub-router inherits the combined dependencies from this router,
        ensuring that dependency injection propagates correctly through the
        entire router hierarchy.

        This is the primary mechanism for composing large applications from
        smaller, modular router components. Each sub-router maintains its
        own routes, middleware, and dependency configuration while inheriting
        parent-level dependencies.

        Args:
            app: The Router instance to mount as a sub-application. The
                router's ``prefix`` attribute determines the URL path at
                which it will be mounted.
            name: Optional name for the Group wrapping the sub-router.
                Used for reverse URL generation with ``url_for`` using
                dot-separated notation.

        Returns:
            None. A ``Group`` containing the sub-router is appended to
            this router's internal route list.
        """
        app._set_inherited_dependencies(self._get_combined_dependencies())
        path = app.prefix
        self.routes.append(Group(app=app, path=path, name=name))

    def get_all_routes(self) -> list[Route]:
        """Collect all HTTP routes from this router and all nested sub-routers.

        Performs a breadth-first traversal of the router hierarchy, starting
        from this router and descending into all mounted sub-routers. Each
        route is shallow-copied and its ``raw_path`` is updated to include
        the accumulated prefix from all parent routers, producing a flat
        list of routes with fully qualified paths.

        This method is primarily used by the OpenAPI documentation generator
        to collect all routes across the entire application for schema
        generation, and by debugging tools that need a complete route listing.

        Args:
            None. This method takes no arguments beyond the implicit
                ``self`` reference to the current router instance.

        Returns:
            A flat list of ``Route`` instances from this router and all
            nested sub-routers, with each route's ``raw_path`` updated
            to include the full accumulated prefix from parent routers.
        """
        all_routes: list[Route] = []
        routers_to_process: list[Any] = [(self, "")]  # (router, current_prefix)

        while routers_to_process:
            current_router, current_prefix = routers_to_process.pop(0)

            for route in current_router.routes:
                # Create a copy of the route with updated path
                new_route = copy.copy(route)
                new_route.raw_path = current_prefix + route.raw_path
                new_route.prefix = current_prefix
                all_routes.append(new_route)

            for mount_path, sub_router in current_router.sub_routers.items():
                if isinstance(sub_router, Router):
                    new_prefix = current_prefix + mount_path
                    routers_to_process.append((sub_router, new_prefix))

        return all_routes

    def register(
        self,
        app: ASGIApp,
        prefix: str = "",
    ):
        """Register an ASGI application under a specific path prefix.

        Wraps the provided ASGI application in a ``Group`` and adds it to
        this router's route list at the given prefix. This method is
        deprecated in favor of using ``Group`` directly or
        ``mount_router`` for sub-router mounting.

        A ``DeprecationWarning`` is issued when this method is called,
        directing users to the preferred alternatives for sub-application
        mounting.

        Args:
            app: The ASGI application to register. Can be another Router
                instance or any ASGI-compatible callable.
            prefix: The URL path prefix under which the application will
                be registered. Defaults to an empty string for root-level
                mounting.

        Returns:
            None. A ``Group`` containing the application is appended to
            this router's internal route list.
        """

        warnings.warn(
            "Router.register(...) is deprecated and will be removed in Sillo 0.2.0. "
            "Please mount sub-apps using Group directly (Group(path=..., app=...)) or use Router.mount_router(...) for sub-routers.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.add_route(Group(app=app, path=prefix))

    def wrap_asgi(
        self,
        middleware_cls: Annotated[
            Callable[[ASGIApp], Any],
            Doc(
                "An ASGI middleware class or callable that takes an app as its first argument and returns an ASGI app"
            ),
        ],
        **kwargs: Any,
    ) -> None:
        """Wrap the entire router with an ASGI-level middleware.

        Applies an ASGI middleware around the router's internal dispatch
        application, intercepting all requests (both HTTP and WebSocket)
        before they reach the route matching and handling pipeline. This
        operates at a lower level than router-level middleware added via
        ``use``, wrapping the entire dispatch application rather than
        individual route handlers.

        This is useful for cross-cutting concerns that must apply to every
        request regardless of which route is matched, such as request
        logging, tracing, or protocol-level transformations.

        Args:
            middleware_cls: An ASGI middleware class or callable that
                follows the ASGI interface, accepting an app as its first
                argument and returning an ASGI-compatible application.
            **kwargs: Additional keyword arguments passed to the middleware
                constructor alongside the application reference.

        Returns:
            None. The router's internal ``app`` attribute is replaced with
            the middleware-wrapped version.
        """
        self.app = middleware_cls(
            self.app,  # ty:ignore[invalid-argument-type]
            **kwargs,
        )


Routes = Route  # for backward compatibilty
