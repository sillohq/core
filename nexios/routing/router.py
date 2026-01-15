from __future__ import annotations

import copy
import inspect
import re
import typing
import warnings
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Pattern,
    Sequence,
    Type,
    Union,
)

from pydantic import BaseModel
from typing_extensions import Doc

from nexios._internals._middleware import (
    ASGIRequestResponseBridge,
)
from nexios._internals._middleware import DefineMiddleware as Middleware
from nexios._internals._middleware import (
    wrap_middleware,
)
from nexios._internals._response_transformer import request_response
from nexios._internals._route_builder import RouteBuilder
from nexios.dependencies import Depend, inject_dependencies
from nexios.events import EventEmitter
from nexios.exceptions import NotFoundException
from nexios.http import Request, Response
from nexios.http.response import JSONResponse
from nexios.objects import RouteParam, URLPath
from nexios.openapi.models import Parameter
from nexios.types import ASGIApp, HandlerType, MiddlewareType, Receive, Scope, Send

from ._utils import MatchStatus, get_route_path
from .base import BaseRoute, BaseRouter
from .grouping import Group
from .websocket import WebsocketRoute

allowed_methods_default = ["get", "post", "delete", "put", "patch", "options"]


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
            Doc(
                """
            URL path pattern for the endpoint. Supports dynamic parameters using curly brace syntax.
            Examples:
            - '/users' (static path)
            - '/posts/{id}' (path parameter)
            - '/files/{filepath:.*}' (regex-matched path parameter)
            """
            ),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc(
                """
            Callable responsible for processing requests to this endpoint. Can be:
            - A regular function
            - An async function
            - A class method
            - Any object implementing __call__

            The handler should accept a request object and return a response object.
            Example: def user_handler(request: Request) -> Response: ...
            """
            ),
        ],
        methods: Annotated[
            Optional[List[str]],
            Doc(
                """
            HTTP methods allowed for this endpoint. Common methods include:
            - GET: Retrieve resources
            - POST: Create resources
            - PUT: Update resources
            - DELETE: Remove resources
            - PATCH: Partial updatess

            Defaults to ['GET'] if not specified. Use uppercase method names.
            """
            ),
        ] = allowed_methods_default,
        name: Annotated[
            Optional[str],
            Doc(
                """The unique identifier for the route. This name is used to generate 
            URLs dynamically with `url_for`. It should be a valid, unique string 
            that represents the route within the application."""
            ),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc(
                "A brief summary of the API endpoint. This should be a short, one-line description providing a high-level overview of its purpose."
            ),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc(
                "A detailed explanation of the API endpoint, including functionality, expected behavior, and additional context."
            ),
        ] = None,
        responses: Annotated[
            Optional[Dict[int, Any]],
            Doc(
                "A dictionary mapping HTTP status codes to response schemas or descriptions. Keys are HTTP status codes (e.g., 200, 400), and values define the response format."
            ),
        ] = None,
        request_model: Annotated[
            Optional[Type[BaseModel]],
            Doc(
                "A Pydantic model representing the expected request payload. Defines the structure and validation rules for incoming request data."
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
        tags: Optional[Sequence[str]] = None,
        security: Optional[List[Dict[str, List[str]]]] = None,
        operation_id: Optional[str] = None,
        deprecated: bool = False,
        parameters: Optional[List[Parameter]] = None,
        middleware: Optional[List[Any]] = None,
        exclude_from_schema: bool = False,
        **kwargs: Dict[str, Any],
    ):
        """
        Initialize a route configuration with endpoint details.

        Args:
            path: URL path pattern with optional parameters.
            handler: Request processing function/method.
            methods: Allowed HTTP methods (default: ['GET']).
            validator: Multi-layer request validation rules.
            request_schema: Request body structure definition.
            response_schema: Success response structure definition.
            deprecated: Deprecation marker.
            tags: Documentation categories.
            description: Comprehensive endpoint documentation.
            summary: Brief endpoint description.

        Raises:
            AssertionError: If handler is not callable.
        """
        assert callable(handler), "Route handler must be callable"

        self.prefix: Optional[str] = None
        if path == "":
            path = "/"
        self.raw_path = path
        self.handler = inject_dependencies(handler)
        self.name = name

        self.route_info = RouteBuilder.create_pattern(path)
        self.pattern: Pattern[str] = self.route_info.pattern
        self.param_names = self.route_info.param_names
        self.route_type = self.route_info.route_type
        self.middleware: typing.List[MiddlewareType] = (
            list(middleware) if middleware else []
        )
        self.summary = summary
        self.description = description
        self.responses = responses
        self.request_model = request_model
        self.request_content_type = request_content_type
        self.kwargs = kwargs
        self.tags = tags
        self.security = security
        self.operation_id = operation_id
        self.deprecated = deprecated
        self.parameters = parameters or []
        self.exclude_from_schema = exclude_from_schema
        self.methods = {method.upper() for method in methods}
        if "GET" in self.methods:
            self.methods.add("HEAD")

    def match(self, scope: Scope) -> typing.Tuple[MatchStatus, Any]:
        """
        Match a path against this route's pattern and return captured parameters.

        Args:
            path: The URL path to match.

        Returns:
            Optional[Dict[str, Any]]: A dictionary of captured parameters if the path matches,
            otherwise None.
        """
        if scope.get("type") != "http":
            return MatchStatus.NONE, {}
        path = get_route_path(scope)
        method = scope["method"]
        match = self.pattern.match(path)
        if match:
            matched_params = match.groupdict()
            for key, value in matched_params.items():
                matched_params[key] = self.route_info.convertor[  # type: ignore
                    key
                ].convert(value)
            is_method_allowed = method.lower() in (m.lower() for m in self.methods)
            if not is_method_allowed:
                return MatchStatus.PARTIAL, matched_params

            return MatchStatus.FULL, matched_params
        return MatchStatus.NONE, {}

    def url_path_for(self, _name: str, **path_params: Dict[str, Any]) -> URLPath:
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
        if _name != self.name:
            raise ValueError(
                f"Route name '{_name}' does not match the current route name '{self.name}'."
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

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Process an incoming request using the route's handler.

        Args:
            request: The incoming HTTP request object.
            response: The outgoing HTTP response object.

        Returns:
            Response: The processed HTTP response object.
        """

        async def apply_middleware(app: ASGIApp) -> ASGIApp:
            middleware: typing.List[Middleware] = []
            for mdw in self.middleware:
                middleware.append(wrap_middleware(mdw))  # type: ignore
            for cls, args, kwargs in reversed(middleware):
                app = cls(app, *args, **kwargs)
            return app

        if self.methods and scope["method"] not in self.methods:
            app = JSONResponse(
                {"Method Not Allowed"},
                status_code=405,
                headers={"Allow": ", ".join(self.methods)},
            )
        else:
            app = await apply_middleware(await request_response(self.handler))

        await app(scope, receive, send)

    def __repr__(self) -> str:
        """
        Return a string representation of the route.

        Returns:
            str: A string describing the route.
        """
        return f"<Route {self.raw_path} methods={self.methods}>"


class Router(BaseRouter):
    def __init__(
        self,
        prefix: Optional[str] = None,
        routes: Optional[Sequence[Union[Route, type[BaseRoute]]]] = None,
        tags: Optional[Sequence[str]] = None,
        exclude_from_schema: bool = False,
        name: Optional[str] = None,
        dependencies: Optional[list[Depend]] = None,
    ):
        self.prefix = prefix or ""
        self.prefix.rstrip("/")
        self.routes = list(routes or [])
        self.middleware: typing.List[Middleware] = []
        self.sub_routers: Dict[str, Union[Router, ASGIApp]] = {}
        self.route_class = Route
        self.tags = tags or []
        self.exclude_from_schema = exclude_from_schema
        self.name = name
        self.event = EventEmitter()
        self.dependencies = dependencies or []
        self.root_path = ""

        if self.prefix and not self.prefix.startswith("/"):
            warnings.warn("Router prefix should start with '/'")
            self.prefix = f"/{self.prefix}"

        if routes:
            for route in routes:
                self.add_route(route)

    def build_middleware_stack(self, app: ASGIApp) -> ASGIApp:
        """
        Builds the middleware stack by applying all registered middleware to the app.

        Args:
            app: The base ASGI application.

        Returns:
            ASGIApp: The application wrapped with all middleware.
        """

        for cls, args, kwargs in reversed(self.middleware):
            app = cls(app, *args, **kwargs)
        return app

    def add_route(
        self,
        route: Annotated[
            Optional[Union[Route, type[BaseRoute]]],
            Doc("An instance of the Route class representing an HTTP route."),
        ] = None,
        path: Annotated[
            Optional[str],
            Doc(
                """
                URL path pattern for the HEAD endpoint.
                Example: '/api/v1/resources/{id}'
            """
            ),
        ] = None,
        methods: Annotated[
            List[str],
            Doc(
                """
                List of HTTP methods this route should handle.
                Common methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']
                Defaults to all standard methods if not specified.
            """
            ),
        ] = allowed_methods_default,
        handler: Annotated[
            Optional[HandlerType],
            Doc(
                """
                Async handler function for HEAD requests.
                Example:
                async def check_resource(request, response):
                    exists = await Resource.exists(request.path_params['id'])
                    return response.status(200 if exists else 404)
            """
            ),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc(
                """
                Unique route name for URL generation.
                Example: 'api-v1-check-resource'
            """
            ),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc(
                """
                Brief endpoint summary.
                Example: 'Check resource existence'
            """
            ),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc(
                """
                Detailed endpoint description.
                Example: 'Returns headers only to check if resource exists'
            """
            ),
        ] = None,
        responses: Annotated[
            Optional[Dict[int, Any]],
            Doc(
                """
                Response schemas by status code.
                Example: {
                    200: None,
                    404: None
                }
            """
            ),
        ] = None,
        request_model: Annotated[
            Optional[Type[BaseModel]],
            Doc(
                """
                Model for request validation.
                Example:
                class ResourceCheck(BaseModel):
                    check_children: bool = False
            """
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
        middleware: Annotated[
            List[Any],
            Doc(
                """
                Route-specific middleware.
                Example: [cache_control('public')]
            """
            ),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc(
                """
                OpenAPI tags for grouping.
                Example: ["Resource Management"]
            """
            ),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc(
                """
                Security requirements.
                Example: [{"ApiKeyAuth": []}]
            """
            ),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc(
                """
                Unique operation ID.
                Example: 'checkResource'
            """
            ),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc(
                """
                Mark as deprecated.
                Example: False
            """
            ),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc(
                """
                Additional parameters.
                Example: [Parameter(name="X-Check-Type", in_="header")]
            """
            ),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc(
                """
                Hide from OpenAPI docs.
                Example: False
            """
            ),
        ] = False,
        **kwargs: Annotated[
            Dict[str, Any],
            Doc(
                """
                Additional metadata.
                Example: {"x-head-only": True}
            """
            ),
        ],
    ) -> None:
        """
        Adds an HTTP route to the application.

        This method registers an HTTP route, allowing the application to handle requests for a specific URL path.

        Args:
            route (Route): The HTTP route configuration.

        Returns:
            None

        Example:
            ```python
            route = Route("/home", home_handler, methods=["GET", "POST"])
            app.add_route(route)
            ```
        """
        if not route:
            if (not path) or (not handler):
                raise ValueError(
                    "path and handler are required if route is not provided"
                )
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

        route.tags = list(self.tags).extend(route.tags) if route.tags else self.tags
        if self.exclude_from_schema:
            route.exclude_from_schema = True
        original_handler = route.handler

        async def wrapped_handler(
            request: Request, response: Response, **kwargs: Dict[str, Any]
        ):
            sig = inspect.signature(original_handler)
            params = list(sig.parameters.keys())
            handler_args = [request, response]
            handler_kwargs = {}
            if len(params) > 2:
                # Get path parameters from request
                path_params = request.path_params

                # For parameters after the first two (request/response)
                for param in params[2:]:
                    if param in path_params:
                        handler_kwargs[param] = path_params[param]

            return await original_handler(*handler_args, **handler_kwargs)

        route.handler = wrapped_handler
        self.routes.append(route)
        if getattr(route, "exclude_from_schema", False):
            return

    def add_middleware(self, middleware: MiddlewareType) -> None:
        """Add middleware to the router"""
        if callable(middleware):
            mdw = Middleware(ASGIRequestResponseBridge, dispatch=middleware)  # type: ignore
            self.middleware.insert(0, mdw)

    def get(
        self,
        path: Annotated[
            str,
            Doc(
                """
                URL path pattern for the GET endpoint.
                Supports path parameters using {param} syntax.
                Example: '/users/{user_id}'
            """
            ),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc(
                """
                Async handler function for GET requests.
                Receives (request, response) and returns response or raw data.
                
                Example:
                async def get_user(request, response):
                    user = await get_user_from_db(request.path_params['user_id'])
                    return response.json(user)
            """
            ),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc(
                """
                Unique route identifier for URL generation.
                Example: 'get-user-by-id'
            """
            ),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc(
                """
                Brief summary for OpenAPI documentation.
                Example: 'Retrieves a user by ID'
            """
            ),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc(
                """
                Detailed description for OpenAPI documentation.
                Example: 'Returns full user details including profile information'
            """
            ),
        ] = None,
        responses: Annotated[
            Optional[Dict[int, Any]],
            Doc(
                """
                Response models by status code.
                Example: 
                {
                    200: UserSchema,
                    404: {"description": "User not found"},
                    500: {"description": "Server error"}
                }
            """
            ),
        ] = None,
        request_model: Annotated[
            Optional[Type[BaseModel]],
            Doc(
                """
                Pydantic model for request validation (query params).
                Example:
                class UserQuery(BaseModel):
                    active_only: bool = True
                    limit: int = 100
            """
            ),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc(
                """
                List of route-specific middleware functions.
                Example: [auth_required, rate_limit]
            """
            ),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc(
                """
                OpenAPI tags for grouping related endpoints.
                Example: ["Users", "Public"]
            """
            ),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc(
                """
                Security requirements for OpenAPI docs.
                Example: [{"BearerAuth": []}]
            """
            ),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc(
                """
                Unique operation identifier for OpenAPI.
                Example: 'users.get_by_id'
            """
            ),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc(
                """
                Mark endpoint as deprecated in docs.
                Example: True
            """
            ),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc(
                """
                Additional OpenAPI parameter definitions.
                Example: [Parameter(name="fields", in_="query", description="Fields to include")]
            """
            ),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc(
                """
                Exclude this route from OpenAPI docs.
                Example: True for internal endpoints
            """
            ),
        ] = False,
        **kwargs: Annotated[
            Dict[str, Any],
            Doc(
                """
                Additional route metadata.
                Example: {"x-internal": True}
            """
            ),
        ],
    ) -> Callable[..., Any]:
        """
        Register a GET endpoint with comprehensive OpenAPI support.

        Examples:
            1. Basic GET endpoint:
            @router.get("/users")
            async def get_users(request: Request, response: Response):
                users = await get_all_users()
                return response.json(users)

            2. GET with path parameter and response model:
            @router.get(
                "/users/{user_id}",
                responses={
                    200: UserResponse,
                    404: {"description": "User not found"}
                }
            )
            async def get_user(request: Request, response: Response):
                user_id = request.path_params['user_id']
                user = await get_user_by_id(user_id)
                if not user:
                    return response.status(404).json({"error": "User not found"})
                return response.json(user)

            3. GET with query parameters:
            class UserQuery(BaseModel):
                active: bool = True
                limit: int = 100

            @router.get("/users/search", request_model=UserQuery)
            async def search_users(request: Request, response: Response):
                query = request.query_params
                users = await search_users(
                    active=query['active'],
                    limit=query['limit']
                )
                return response.json(users)
        """

        def decorator(handler: HandlerType) -> HandlerType:
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
            Doc(
                """
                URL path pattern for the POST endpoint.
                Example: '/api/v1/users'
            """
            ),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc(
                """
                Async handler function for POST requests.
                Example:
                async def create_user(request, response):
                    user_data = request.json
                    return response.json(user_data, status=201)
            """
            ),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc(
                """
                Unique route name for URL generation.
                Example: 'api-v1-create-user'
            """
            ),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc(
                """
                Brief endpoint summary.
                Example: 'Create new user'
            """
            ),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc(
                """
                Detailed endpoint description.
                Example: 'Creates new user with provided data'
            """
            ),
        ] = None,
        responses: Annotated[
            Optional[Dict[int, Any]],
            Doc(
                """
                Response schemas by status code.
                Example: {
                    201: UserSchema,
                    400: {"description": "Invalid input"},
                    409: {"description": "User already exists"}
                }
            """
            ),
        ] = None,
        request_model: Annotated[
            Optional[Type[BaseModel]],
            Doc(
                """
                Model for request body validation.
                Example:
                class UserCreate(BaseModel):
                    username: str
                    email: EmailStr
                    password: str
            """
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
        middleware: Annotated[
            List[Any],
            Doc(
                """
                Route-specific middleware.
                Example: [rate_limit(10), validate_content_type('json')]
            """
            ),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc(
                """
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """
            ),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc(
                """
                Security requirements.
                Example: [{"BearerAuth": []}]
            """
            ),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc(
                """
                Unique operation ID.
                Example: 'createUser'
            """
            ),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc(
                """
                Mark as deprecated.
                Example: False
            """
            ),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc(
                """
                Additional parameters.
                Example: [Parameter(name="X-Request-ID", in_="header")]
            """
            ),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc(
                """
                Hide from OpenAPI docs.
                Example: False
            """
            ),
        ] = False,
        **kwargs: Annotated[
            Dict[str, Any],
            Doc(
                """
                Additional metadata.
                Example: {"x-audit-log": True}
            """
            ),
        ],
    ) -> Callable[..., Any]:
        """
        Register a POST endpoint with the application.

        Examples:
            1. Simple POST endpoint:
            @router.post("/messages")
            async def create_message(request, response):
                message = await Message.create(**request.json)
                return response.json(message, status=201)

            2. POST with request validation:
            class ProductCreate(BaseModel):
                name: str
                price: float
                category: str

            @router.post(
                "/products",
                request_model=ProductCreate,
                responses={201: ProductSchema}
            )
            async def create_product(request, response):
                product = await Product.create(**request.validated_data)
                return response.json(product, status=201)

            3. POST with file upload:
            @router.post("/upload")
            async def upload_file(request, response):
                file = request.files.get('file')
                # Process file upload
                return response.json({"filename": file.filename})
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
            **kwargs,
        )

    def delete(
        self,
        path: Annotated[
            str,
            Doc(
                """
                URL path pattern for the DELETE endpoint.
                Example: '/api/v1/users/{id}'
            """
            ),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc(
                """
                Async handler function for DELETE requests.
                Example:
                async def delete_user(request, response):
                    user_id = request.path_params['id']
                    return response.json({"deleted": user_id})
            """
            ),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc(
                """
                Unique route name for URL generation.
                Example: 'api-v1-delete-user'
            """
            ),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc(
                """
                Brief endpoint summary.
                Example: 'Delete user account'
            """
            ),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc(
                """
                Detailed endpoint description.
                Example: 'Permanently deletes user account and all associated data'
            """
            ),
        ] = None,
        responses: Annotated[
            Optional[Dict[int, Any]],
            Doc(
                """
                Response schemas by status code.
                Example: {
                    204: None,
                    404: {"description": "User not found"},
                    403: {"description": "Forbidden"}
                }
            """
            ),
        ] = None,
        request_model: Annotated[
            Optional[Type[BaseModel]],
            Doc(
                """
                Model for request validation.
                Example:
                class DeleteConfirmation(BaseModel):
                    confirm: bool
            """
            ),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc(
                """
                Route-specific middleware.
                Example: [admin_required, confirm_action]
            """
            ),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc(
                """
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """
            ),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc(
                """
                Security requirements.
                Example: [{"BearerAuth": []}]
            """
            ),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc(
                """
                Unique operation ID.
                Example: 'deleteUser'
            """
            ),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc(
                """
                Mark as deprecated.
                Example: False
            """
            ),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc(
                """
                Additional parameters.
                Example: [Parameter(name="confirm", in_="query")]
            """
            ),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc(
                """
                Hide from OpenAPI docs.
                Example: False
            """
            ),
        ] = False,
        **kwargs: Annotated[
            Dict[str, Any],
            Doc(
                """
                Additional metadata.
                Example: {"x-destructive": True}
            """
            ),
        ],
    ) -> Callable[..., Any]:
        """
        Register a DELETE endpoint with the application.

        Examples:
            1. Simple DELETE endpoint:
            @router.delete("/users/{id}")
            async def delete_user(request, response):
                await User.delete(request.path_params['id'])
                return response.status(204)

            2. DELETE with confirmation:
            @router.delete(
                "/account",
                responses={
                    204: None,
                    400: {"description": "Confirmation required"}
                }
            )
            async def delete_account(request, response):
                if not request.query_params.get('confirm'):
                    return response.status(400)
                await request.user.delete()
                return response.status(204)

            3. Soft DELETE:
            @router.delete("/posts/{id}")
            async def soft_delete_post(request, response):
                await Post.soft_delete(request.path_params['id'])
                return response.json({"status": "archived"})
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
            **kwargs,
        )

    def put(
        self,
        path: Annotated[
            str,
            Doc(
                """
                URL path pattern for the PUT endpoint.
                Example: '/api/v1/users/{id}'
            """
            ),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc(
                """
                Async handler function for PUT requests.
                Example:
                async def update_user(request, response):
                    user_id = request.path_params['id']
                    return response.json({"updated": user_id})
            """
            ),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc(
                """
                Unique route name for URL generation.
                Example: 'api-v1-update-user'
            """
            ),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc(
                """
                Brief endpoint summary.
                Example: 'Update user details'
            """
            ),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc(
                """
                Detailed endpoint description.
                Example: 'Full update of user resource'
            """
            ),
        ] = None,
        responses: Annotated[
            Optional[Dict[int, Any]],
            Doc(
                """
                Response schemas by status code.
                Example: {
                    200: UserSchema,
                    400: {"description": "Invalid input"},
                    404: {"description": "User not found"}
                }
            """
            ),
        ] = None,
        request_model: Annotated[
            Optional[Type[BaseModel]],
            Doc(
                """
                Model for request body validation.
                Example:
                class UserUpdate(BaseModel):
                    email: Optional[EmailStr]
                    password: Optional[str]
            """
            ),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc(
                """
                Route-specific middleware.
                Example: [owner_required, validate_etag]
            """
            ),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc(
                """
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """
            ),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc(
                """
                Security requirements.
                Example: [{"BearerAuth": []}]
            """
            ),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc(
                """
                Unique operation ID.
                Example: 'updateUser'
            """
            ),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc(
                """
                Mark as deprecated.
                Example: False
            """
            ),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc(
                """
                Additional parameters.
                Example: [Parameter(name="If-Match", in_="header")]
            """
            ),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc(
                """
                Hide from OpenAPI docs.
                Example: False
            """
            ),
        ] = False,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ],
            Doc(
                """
                Request content type.
                Example: 'application/json'
            """
            ),
        ] = "application/json",
        **kwargs: Annotated[
            Dict[str, Any],
            Doc(
                """
                Additional metadata.
                Example: {"x-idempotent": True}
            """
            ),
        ],
    ) -> Callable[..., Any]:
        """
        Register a PUT endpoint with the application.

        Examples:
            1. Simple PUT endpoint:
            @router.put("/users/{id}")
            async def update_user(request, response):
                user_id = request.path_params['id']
                await User.update(user_id, **request.json)
                return response.json({"status": "updated"})

            2. PUT with full resource replacement:
            @router.put(
                "/articles/{slug}",
                request_model=ArticleUpdate,
                responses={
                    200: ArticleSchema,
                    404: {"description": "Article not found"}
                }
            )
            async def replace_article(request, response):
                article = await Article.replace(
                    request.path_params['slug'],
                    request.validated_data
                )
                return response.json(article)

            3. PUT with conditional update:
            @router.put("/resources/{id}")
            async def update_resource(request, response):
                if request.headers.get('If-Match') != expected_etag:
                    return response.status(412)
                # Process update
                return response.json({"status": "success"})
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
            **kwargs,
        )

    def patch(
        self,
        path: Annotated[
            str,
            Doc(
                """
                URL path pattern for the PATCH endpoint.
                Example: '/api/v1/users/{id}'
            """
            ),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc(
                """
                Async handler function for PATCH requests.
                Example:
                async def partial_update_user(request, response):
                    user_id = request.path_params['id']
                    return response.json({"updated": user_id})
            """
            ),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc(
                """
                Unique route name for URL generation.
                Example: 'api-v1-partial-update-user'
            """
            ),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc(
                """
                Brief endpoint summary.
                Example: 'Partially update user details'
            """
            ),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc(
                """
                Detailed endpoint description.
                Example: 'Partial update of user resource'
            """
            ),
        ] = None,
        responses: Annotated[
            Optional[Dict[int, Any]],
            Doc(
                """
                Response schemas by status code.
                Example: {
                    200: UserSchema,
                    400: {"description": "Invalid input"},
                    404: {"description": "User not found"}
                }
            """
            ),
        ] = None,
        request_model: Annotated[
            Optional[Type[BaseModel]],
            Doc(
                """
                Model for request body validation.
                Example:
                class UserPatch(BaseModel):
                    email: Optional[EmailStr] = None
                    password: Optional[str] = None
            """
            ),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc(
                """
                Route-specific middleware.
                Example: [owner_required, validate_patch]
            """
            ),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc(
                """
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """
            ),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc(
                """
                Security requirements.
                Example: [{"BearerAuth": []}]
            """
            ),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc(
                """
                Unique operation ID.
                Example: 'partialUpdateUser'
            """
            ),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc(
                """
                Mark as deprecated.
                Example: False
            """
            ),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc(
                """
                Additional parameters.
                Example: [Parameter(name="fields", in_="query")]
            """
            ),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc(
                """
                Hide from OpenAPI docs.
                Example: False
            """
            ),
        ] = False,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ],
            Doc(
                """
                Request content type.
                Example: 'application/json'
            """
            ),
        ] = "application/json",
        **kwargs: Annotated[
            Dict[str, Any],
            Doc(
                """
                Additional metadata.
                Example: {"x-partial-update": True}
            """
            ),
        ],
    ) -> Callable[..., Any]:
        """
        Register a PATCH endpoint with the application.

        Examples:
            1. Simple PATCH endpoint:
            @router.patch("/users/{id}")
            async def update_user(request, response):
                user_id = request.path_params['id']
                await User.partial_update(user_id, **request.json)
                return response.json({"status": "updated"})

            2. PATCH with JSON Merge Patch:
            @router.patch(
                "/articles/{id}",
                request_model=ArticlePatch,
                responses={200: ArticleSchema}
            )
            async def patch_article(request, response):
                article = await Article.patch(
                    request.path_params['id'],
                    request.validated_data
                )
                return response.json(article)

            3. PATCH with selective fields:
            @router.patch("/profile")
            async def update_profile(request, response):
                allowed_fields = {'bio', 'avatar_url'}
                updates = {k: v for k, v in request.json.items()
                        if k in allowed_fields}
                await Profile.update(request.user.id, **updates)
                return response.json(updates)
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
            **kwargs,
        )

    def options(
        self,
        path: Annotated[
            str,
            Doc(
                """
                URL path pattern for the OPTIONS endpoint.
                Example: '/api/v1/users'
            """
            ),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc(
                """
                Async handler function for OPTIONS requests.
                Example:
                async def user_options(request, response):
                    response.headers['Allow'] = 'GET, POST, OPTIONS'
                    return response
            """
            ),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc(
                """
                Unique route name for URL generation.
                Example: 'api-v1-user-options'
            """
            ),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc(
                """
                Brief endpoint summary.
                Example: 'Get supported operations'
            """
            ),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc(
                """
                Detailed endpoint description.
                Example: 'Returns supported HTTP methods and CORS headers'
            """
            ),
        ] = None,
        responses: Annotated[
            Optional[Dict[int, Any]],
            Doc(
                """
                Response schemas by status code.
                Example: {
                    200: None,
                    204: None
                }
            """
            ),
        ] = None,
        request_model: Annotated[
            Optional[Type[BaseModel]],
            Doc(
                """
                Model for request validation.
                Example:
                class OptionsQuery(BaseModel):
                    detailed: bool = False
            """
            ),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc(
                """
                Route-specific middleware.
                Example: [cors_middleware]
            """
            ),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc(
                """
                OpenAPI tags for grouping.
                Example: ["CORS"]
            """
            ),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc(
                """
                Security requirements.
                Example: []
            """
            ),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc(
                """
                Unique operation ID.
                Example: 'userOptions'
            """
            ),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc(
                """
                Mark as deprecated.
                Example: False
            """
            ),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc(
                """
                Additional parameters.
                Example: [Parameter(name="Origin", in_="header")]
            """
            ),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc(
                """
                Hide from OpenAPI docs.
                Example: True
            """
            ),
        ] = False,
        **kwargs: Annotated[
            Dict[str, Any],
            Doc(
                """
                Additional metadata.
                Example: {"x-cors": True}
            """
            ),
        ],
    ) -> Callable[..., Any]:
        """
        Register an OPTIONS endpoint with the application.

        Examples:
            1. Simple OPTIONS endpoint:
            @router.options("/users")
            async def user_options(request, response):
                response.headers['Allow'] = 'GET, POST, OPTIONS'
                return response

            2. CORS OPTIONS handler:
            @router.options("/{path:path}")
            async def cors_options(request, response):
                response.headers.update({
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Max-Age': '86400'
                })
                return response.status(204)

            3. Detailed OPTIONS response:
            @router.options("/resources")
            async def resource_options(request, response):
                return response.json({
                    "methods": ["GET", "POST"],
                    "formats": ["application/json"],
                    "limits": {"max_size": "10MB"}
                })
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
            **kwargs,
        )

    def head(
        self,
        path: Annotated[
            str,
            Doc(
                """
                URL path pattern for the HEAD endpoint.
                Example: '/api/v1/resources/{id}'
            """
            ),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc(
                """
                Async handler function for HEAD requests.
                Example:
                async def check_resource(request, response):
                    exists = await Resource.exists(request.path_params['id'])
                    return response.status(200 if exists else 404)
            """
            ),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc(
                """
                Unique route name for URL generation.
                Example: 'api-v1-check-resource'
            """
            ),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc(
                """
                Brief endpoint summary.
                Example: 'Check resource existence'
            """
            ),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc(
                """
                Detailed endpoint description.
                Example: 'Returns headers only to check if resource exists'
            """
            ),
        ] = None,
        responses: Annotated[
            Optional[Dict[int, Any]],
            Doc(
                """
                Response schemas by status code.
                Example: {
                    200: None,
                    404: None
                }
            """
            ),
        ] = None,
        request_model: Annotated[
            Optional[Type[BaseModel]],
            Doc(
                """
                Model for request validation.
                Example:
                class ResourceCheck(BaseModel):
                    check_children: bool = False
            """
            ),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc(
                """
                Route-specific middleware.
                Example: [cache_control('public')]
            """
            ),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc(
                """
                OpenAPI tags for grouping.
                Example: ["Resource Management"]
            """
            ),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc(
                """
                Security requirements.
                Example: [{"ApiKeyAuth": []}]
            """
            ),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc(
                """
                Unique operation ID.
                Example: 'checkResource'
            """
            ),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc(
                """
                Mark as deprecated.
                Example: False
            """
            ),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc(
                """
                Additional parameters.
                Example: [Parameter(name="X-Check-Type", in_="header")]
            """
            ),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc(
                """
                Hide from OpenAPI docs.
                Example: False
            """
            ),
        ] = False,
        **kwargs: Annotated[
            Dict[str, Any],
            Doc(
                """
                Additional metadata.
                Example: {"x-head-only": True}
            """
            ),
        ],
    ) -> Callable[..., Any]:
        """
        Register a HEAD endpoint with the application.

        Examples:
            1. Simple HEAD endpoint:
            @router.head("/resources/{id}")
            async def check_resource(request, response):
                exists = await Resource.exists(request.path_params['id'])
                return response.status(200 if exists else 404)

            2. HEAD with cache headers:
            @router.head("/static/{path:path}")
            async def check_static(request, response):
                path = request.path_params['path']
                if not static_file_exists(path):
                    return response.status(404)
                response.headers['Last-Modified'] = get_last_modified(path)
                return response.status(200)

            3. HEAD with metadata:
            @router.head("/documents/{id}")
            async def document_metadata(request, response):
                doc = await Document.metadata(request.path_params['id'])
                if not doc:
                    return response.status(404)
                response.headers['X-Document-Size'] = str(doc.size)
                return response.status(200)
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
            **kwargs,
        )

    def route(
        self,
        path: Annotated[
            str,
            Doc(
                """
                The URL path pattern for the route. Supports path parameters using curly braces:
                - '/users/{user_id}' - Simple path parameter
                - '/files/{filepath:path}' - Matches any path (including slashes)
                - '/items/{id:int}' - Type-constrained parameter
            """
            ),
        ],
        methods: Annotated[
            List[str],
            Doc(
                """
                List of HTTP methods this route should handle.
                Common methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']
                Defaults to all standard methods if not specified.
            """
            ),
        ] = allowed_methods_default,
        handler: Annotated[
            Optional[HandlerType],
            Doc(
                """
                The async handler function for this route. Must accept:
                - request: Request object
                - response: Response object
                And return either a Response object or raw data (dict, list, str)
            """
            ),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc(
                """
                Unique name for this route, used for URL generation with url_for().
                If not provided, will be generated from the path and methods.
            """
            ),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc("Brief one-line description of the route for OpenAPI docs"),
        ] = None,
        description: Annotated[
            Optional[str], Doc("Detailed description of the route for OpenAPI docs")
        ] = None,
        responses: Annotated[
            Optional[Dict[int, Union[Type[BaseModel], Dict[str, Any]]]],
            Doc(
                """
                Response models by status code for OpenAPI docs.
                Example: {200: UserModel, 404: ErrorModel}
            """
            ),
        ] = None,
        request_model: Annotated[
            Optional[Type[BaseModel]],
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
            List[MiddlewareType],
            Doc(
                """
                List of middleware specific to this route.
                These will be executed in order before the route handler.
            """
            ),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc(
                """
                OpenAPI tags for grouping related routes in documentation.
                Inherits parent router tags if not specified.
            """
            ),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc(
                """
                Security requirements for this route.
                Example: [{"bearerAuth": []}] for JWT auth.
            """
            ),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc(
                """
                Unique identifier for this operation in OpenAPI docs.
                Auto-generated if not provided.
            """
            ),
        ] = None,
        deprecated: Annotated[
            bool, Doc("Mark route as deprecated in OpenAPI docs")
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc(
                """
                Additional OpenAPI parameter definitions.
                Path parameters are automatically included from the path pattern.
            """
            ),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc(
                """
                If True, excludes this route from OpenAPI documentation.
                Useful for internal or admin routes.
            """
            ),
        ] = False,
        **kwargs: Annotated[
            Dict[str, Any],
            Doc(
                """
                Additional route metadata that will be available in the request scope.
                Useful for custom extensions or plugin-specific data.
            """
            ),
        ],
    ) -> Union[HandlerType, Callable[..., HandlerType]]:
        """
        Register a route with configurable HTTP methods and OpenAPI documentation.

        This is the most flexible way to register routes, allowing full control over
        HTTP methods, request/response validation, and OpenAPI documentation.

        Can be used as a decorator:
            @router.route("/users", methods=["GET", "POST"])
            async def user_handler(request, response):
                ...

        Or directly:
            router.route("/users", methods=["GET", "POST"], handler=user_handler)

        Args:
            path: URL path pattern with optional parameters
            methods: HTTP methods this route accepts
            handler: Async function to handle requests
            name: Unique route identifier
            summary: Brief route description
            description: Detailed route description
            responses: Response models by status code
            request_model: Request body validation model
            middleware: Route-specific middleware
            tags: OpenAPI tags for grouping
            security: Security requirements
            operation_id: OpenAPI operation ID
            deprecated: Mark as deprecated
            parameters: Additional OpenAPI parameters
            exclude_from_schema: Hide from docs
            **kwargs: Additional route metadata

        Returns:
            The route handler function (when used as decorator)
        """

        def decorator(handler: HandlerType) -> HandlerType:
            route = self.route_class(
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
            self.add_route(route)
            return handler

        if handler is None:
            return decorator
        return decorator(handler)

    def add_ws_route(
        self,
        route: Optional[
            Annotated[
                WebsocketRoute,
                Doc("An instance of the Route class representing a WebSocket route."),
            ]
        ] = None,
        path: Optional[str] = None,
        handler: Optional[WsHandlerType] = None,
        middleware: List[WsMiddlewareType] = [],
    ) -> None:
        """
        Adds a WebSocket route to the application.

        This method registers a WebSocket route, allowing the application to handle WebSocket connections.

        Args:
            route: Either a pre-constructed WebsocketRoute instance or None
            path: The URL path for the WebSocket route (required if route is None)
            handler: The WebSocket handler function (required if route is None)
            middleware: List of middleware for this route

        Returns:
            None

        Example:
            ```python
            # Using with a pre-constructed route
            route = WebsocketRoute("/ws/chat", chat_handler)
            app.add_ws_route(route)

            # Or directly with path and handler
            app.add_ws_route(path="/ws/chat", handler=chat_handler)
            ```
        """
        if route is not None:
            self.routes.append(route)
        elif path is not None and handler is not None:
            self.routes.append(WebsocketRoute(path, handler, middleware=middleware))
        else:
            raise ValueError("Either route or both path and handler must be provided")

    def ws_route(
        self,
        path: Annotated[
            str, Doc("The WebSocket route path. Must be a valid URL pattern.")
        ],
        handler: Annotated[
            Optional[WsHandlerType],
            Doc("The WebSocket handler function. Must be an async function."),
        ] = None,
        middleware: Annotated[
            List[WsMiddlewareType],
            Doc("List of middleware to be executes before the router handler"),
        ] = [],
    ) -> Any:
        """
        Registers a WebSocket route.

        This decorator is used to define WebSocket routes in the application, allowing handlers
        to manage WebSocket connections. When a WebSocket client connects to the given path,
        the specified handler function will be executed.

        Returns:
            Callable: The original WebSocket handler function.

        Example:
            ```python

            @app.ws_route("/ws/chat")
            async def chat_handler(websocket):
                await websocket.accept()
                while True:
                    message = await websocket.receive_text()
                    await websocket.send_text(f"Echo: {message}")
            ```
        """
        if handler:
            return self.add_ws_route(
                WebsocketRoute(path, handler, middleware=middleware)
            )

        def decorator(handler: WsHandlerType) -> WsHandlerType:
            self.add_ws_route(WebsocketRoute(path, handler, middleware=middleware))
            return handler

        return decorator

    def url_for(self, _name: str, **path_params: Any) -> URLPath:
        """
        Generate a URL path including all router prefixes for nested routes.

        Args:
            _name: Route name in format 'router1.router2.route_name'
            **path_params: Path parameters to substitute

        Returns:
            URLPath: Complete path including all router prefixes
        """
        name_parts = _name.split(".")

        # If it's a simple route name (no dots), search directly in current routes
        if len(name_parts) == 1:
            route_name = name_parts[0]
            for route in self.routes:
                if getattr(route, "name", None) == route_name:
                    route_path = route.url_path_for(_name=route_name, **path_params)
                    return URLPath(path=str(route_path), protocol="http")
            raise ValueError(f"Route '{route_name}' not found in router")

        # For nested routes, recursively search through Group objects
        return self._search_nested_route(_name, name_parts, [], **path_params)

    def _search_nested_route(
        self,
        full_name: str,
        name_parts: List[str],
        path_segments: List[str],
        **path_params: Any,
    ) -> URLPath:
        """
        Recursively search for a route in nested Group objects.

        Args:
            full_name: The original full route name for error messages
            name_parts: Remaining parts of the route name to resolve
            path_segments: Accumulated path segments from parent routers
            **path_params: Path parameters to substitute

        Returns:
            URLPath: Complete path including all router prefixes
        """
        if not name_parts:
            raise ValueError(f"Invalid route name format: '{full_name}'")

        current_part = name_parts[0]
        remaining_parts = name_parts[1:]

        # If this is the last part, it's the route name
        if len(remaining_parts) == 0:
            for route in self.routes:
                if getattr(route, "name", None) == current_part:
                    route_path = route.url_path_for(_name=current_part, **path_params)
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

    def __repr__(self) -> str:
        return f"<Router prefix='{self.prefix}' routes={len(self.routes)}>"

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> Any:
        app = self.build_middleware_stack(self.app)
        await app(scope, receive, send)

    async def app(self, scope: Scope, receive: Receive, send: Send):
        scope["app"] = self

        path_match = None

        for route in self.routes:
            match, matched_params = route.match(scope)  # type:ignore
            if match == MatchStatus.FULL:
                scope["route_params"] = RouteParam(matched_params)
                await route.handle(scope, receive, send)  # type:ignore
                return
            elif match == MatchStatus.PARTIAL and path_match is None:
                path_match = route

        if path_match is not None:
            scope["route_params"] = RouteParam(matched_params)
            await path_match.handle(scope, receive, send)
            return
        if scope.get("type") == "http":
            raise NotFoundException
        else:
            await send({"type": "websocket.close", "code": 4404})

    def mount_router(self, app: "Router", name: Optional[str] = None):
        """
        Mount an ASGI application (e.g., another Router) using its prefix.

        Args:
            app: The ASGI application (e.g., another Router) to mount.
        """
        path = app.prefix
        self.routes.append(Group(app=app, path=path, name=name))

    def get_all_routes(self) -> List[Route]:
        """Returns a flat list of all HTTP routes in this router and all nested sub-routers"""
        all_routes: List[Route] = []
        routers_to_process: List[Any] = [(self, "")]  # (router, current_prefix)

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
        """
        Register an ASGI application (e.g., another Router) under a specdefific path prefix.

        Args:
            app: The ASGI application (e.g., another Router) to register.
            prefix: The path prefix under which the app will be registered.
        """

        self.add_route(Group(app=app, path=prefix))


Routes = Route  # for backward compatibilty
