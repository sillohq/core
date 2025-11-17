from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Type,
    Union,
)

from pydantic import BaseModel
from typing_extensions import Annotated, Doc

from nexios._internals._middleware import (
    ASGIRequestResponseBridge,
)
from nexios._internals._middleware import DefineMiddleware as Middleware
from nexios.config import DEFAULT_CONFIG, MakeConfig
from nexios.dependencies import Depend
from nexios.events import AsyncEventEmitter
from nexios.exception_handler import ExceptionHandlerType, ExceptionMiddleware
from nexios.logging import create_logger
from nexios.middleware.errors.server_error_handler import (
    ServerErrHandlerType,
    ServerErrorMiddleware,
)
from nexios.openapi._builder import APIDocumentation
from nexios.openapi.config import OpenAPIConfig
from nexios.openapi.models import HTTPBearer, Parameter,Server
from nexios.routing.base import BaseRoute
from nexios.structs import URLPath

from .routing import Route, Router, WebsocketRoute
from .types import (
    ASGIApp,
    HandlerType,
    Message,
    MiddlewareType,
    Receive,
    Scope,
    Send,
    WsHandlerType,
    WsMiddlewareType,
)

if TYPE_CHECKING:
    from nexios.http import Request, Response
allowed_methods_default = ["get", "post", "delete", "put", "patch", "options"]

logger = create_logger("nexios")
lifespan_manager = Callable[["NexiosApp"], AsyncContextManager[bool]]


class NexiosApp(object):
    def __init__(
        self,
        config: Annotated[
            Optional[MakeConfig],
            Doc(
                """
                    This subclass is derived from the MakeConfig class and is responsible for managing configurations within the Nexios framework. It takes arguments in the form of dictionaries, allowing for structured and flexible configuration handling. By using dictionaries, this subclass makes it easy to pass multiple configuration values at once, reducing complexity and improving maintainability.

                    One of the key advantages of this approach is its ability to dynamically update and modify settings without requiring changes to the core codebase. This is particularly useful in environments where configurations need to be frequently adjusted, such as database settings, API credentials, or feature flags. The subclass can also validate the provided configuration data, ensuring that incorrect or missing values are handled properly.

                    Additionally, this design allows for merging and overriding configurations, making it adaptable for various use cases. Whether used for small projects or large-scale applications, this subclass ensures that configuration management remains efficient and scalable. By extending MakeConfig, it leverages existing functionality while adding new capabilities tailored to Nexios. This makes it an essential component for maintaining structured and well-organized application settings.
                    """
            ),
        ] = DEFAULT_CONFIG,
        title: Annotated[
            Optional[str],
            Doc(
                """
                    The title of the API, used in the OpenAPI documentation.
                    """
            ),
        ] = None,
        version: Annotated[
            Optional[str],
            Doc(
                """
                    The version of the API, used in the OpenAPI documentation.
                    """
            ),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc(
                """
                    A brief description of the API, used in the OpenAPI documentation.
                    """
            ),
        ] = None,
        server_error_handler: Annotated[
            Optional[ServerErrHandlerType],
            Doc(
                """
                        A function in Nexios responsible for handling server-side exceptions by logging errors, reporting issues, or initiating recovery mechanisms. It prevents crashes by intercepting unexpected failures, ensuring the application remains stable and operational. This function provides a structured approach to error management, allowing developers to define custom handling strategies such as retrying failed requests, sending alerts, or gracefully degrading functionality. By centralizing error processing, it improves maintainability and observability, making debugging and monitoring more efficient. Additionally, it ensures that critical failures do not disrupt the entire system, allowing services to continue running while appropriately managing faults and failures."""
            ),
        ] = None,
        lifespan: Optional[lifespan_manager] = None,
        routes: Optional[List[Route]] = None,
        dependencies: Optional[list[Depend]] = None,
    ):
        self.config = config or DEFAULT_CONFIG
        self.dependencies = dependencies or []
        try:
            from nexios.cli.utils import get_config as get_nexios_config
        except ImportError:

            def get_nexios_config() -> Dict[str, Any]:
                return {}

        from nexios.config import get_config, set_config

        try:
            get_config()
        except RuntimeError:
            set_config(self.config)
        self.config.update(
            get_nexios_config(),
        )
        self.http_middleware: List[Middleware] = []
        self.startup_handlers: List[Callable[[], Awaitable[None]]] = []
        self.shutdown_handlers: List[Callable[[], Awaitable[None]]] = []
        self.server_error_handler = server_error_handler
        self._background_tasks = set()  # type:ignore

        self.app = Router(routes=routes, dependencies=self.dependencies)  # type:ignore
        self.exceptions_handler = ExceptionMiddleware()
        self.router = self.app
        self.route = self.router.route
        self.lifespan_context: Optional[lifespan_manager] = lifespan
        self.state: Dict[str, Any] = {}

        openapi_config: Dict[str, Any] = self.config.to_dict().get("openapi", {})  # type:ignore
        
        # Handle license - ensure it's a License model instance
        license_data = openapi_config.get("license")
        license_instance = None
        if license_data:
            if isinstance(license_data, dict):
                from nexios.openapi.models import License
                license_instance = License(**license_data)
            else:
                license_instance = license_data
        
        # Handle contact - ensure it's a Contact model instance  
        contact_data = openapi_config.get("contact")
        contact_instance = None
        if contact_data:
            if isinstance(contact_data, dict):
                from nexios.openapi.models import Contact
                contact_instance = Contact(**contact_data)
            else:
                contact_instance = contact_data
        
        # Handle servers - ensure they are Server model instances
        servers_data = openapi_config.get("servers")
        servers_instances = None
        if servers_data:
            if isinstance(servers_data, list):
                servers_instances = []
                for server in servers_data:
                    if isinstance(server, dict):
                        servers_instances.append(Server(**server))
                    else:
                        servers_instances.append(server)
            else:
                servers_instances = servers_data
        
        self.openapi_config = OpenAPIConfig(
            title=openapi_config.get("title", title or "Nexios API"),
            version=openapi_config.get("version", version or "1.0.0"),
            description=openapi_config.get(
                "description", description or "Nexios API Documentation"
            ),
            license=license_instance,
            contact=contact_instance,
            servers=servers_instances,
        )

        self.openapi_config.add_security_scheme(
            "bearerAuth", HTTPBearer(type="http", scheme="bearer", bearerFormat="JWT")
        )

        self.openapi = APIDocumentation(
            config=self.openapi_config,
            swagger_url=openapi_config.get("swagger_url", "/docs"),
            redoc_url=openapi_config.get("redoc_url", "/redoc"),
            openapi_url=openapi_config.get("openapi_url", "/openapi.json"),
        )

        self.events = AsyncEventEmitter()
        self.title = title or "Nexios API"
        self.setup()

    def setup(self):
        @self.get(self.openapi.openapi_url, exclude_from_schema=True)  # type:ignore
        async def serve_openapi(request: "Request", response: "Response"):
            root_path = request.scope.get("root_path", "")
            
            return response.json(
                self.openapi.get_openapi(self.router, current_prefix=root_path)
            )

        @self.get(self.openapi.swagger_url, exclude_from_schema=True)  # type:ignore
        async def swagger_ui(request: "Request", response: "Response"):
            # Get the current mount path from the request scope
            root_path = request.scope.get("root_path", "")
            openapi_url = root_path + self.openapi.openapi_url
            return response.html(self.openapi._generate_swagger_ui(openapi_url))

        @self.get(self.openapi.redoc_url, exclude_from_schema=True)  # type:ignore
        async def redoc_ui(request: "Request", response: "Response"):
            # Get the current mount path from the request scope
            root_path = request.scope.get("root_path", "")
            openapi_url = root_path + self.openapi.openapi_url
            return response.html(self.openapi._generate_redoc_ui(openapi_url))

    def on_startup(self, handler: Callable[[], Awaitable[None]]) -> None:
        """
        Registers a startup handler that executes when the application starts.

        This method allows you to define functions that will be executed before
        the application begins handling requests. It is useful for initializing
        resources such as database connections, loading configuration settings,
        or preparing caches.

        The provided function must be asynchronous (`async def`) since it
        will be awaited during the startup phase.

        Args:
            handler (Callable): An asynchronous function to be executed at startup.

        Returns:
            Callable: The same handler function, allowing it to be used as a decorator.

        Example:
            ```python

            @app.on_startup
            async def connect_to_db():
                global db
                db = await Database.connect("postgres://user:password@localhost:5432/mydb")
                print("Database connection established.")

            @app.on_startup
            async def cache_warmup():
                global cache
                cache = await load_initial_cache()
                print("Cache warmed up and ready.")
            ```

        In this example:
        - `connect_to_db` establishes a database connection before the app starts.
        - `cache_warmup` preloads data into a cache for faster access.

        These functions will be executed in the order they are registered when the
        application starts.
        """
        self.startup_handlers.append(handler)

    def on_shutdown(self, handler: Callable[[], Awaitable[None]]) -> None:
        """
        Registers a shutdown handler that executes when the application is shutting down.

        This method allows you to define functions that will be executed when the
        application is stopping. It is useful for cleaning up resources such as
        closing database connections, saving application state, or gracefully
        terminating background tasks.

        The provided function must be asynchronous (`async def`) since it will be
        awaited during the shutdown phase.

        Args:
            handler (Callable): An asynchronous function to be executed during shutdown.

        Returns:
            Callable: The same handler function, allowing it to be used as a decorator.

        Example:
            ```python
            app = NexioApp()

            @app.on_shutdown
            async def disconnect_db():
                global db
                await db.disconnect()
                print("Database connection closed.")

            @app.on_shutdown
            async def clear_cache():
                global cache
                await cache.clear()
                print("Cache cleared before shutdown.")
            ```

        In this example:
        - `disconnect_db` ensures that the database connection is properly closed.
        - `clear_cache` removes cached data to free up memory before the app stops.

        These functions will be executed in the order they are registered when the
        application is shutting down.
        """
        self.shutdown_handlers.append(handler)

    async def _startup(self) -> None:
        """Execute all startup handlers sequentially"""
        for handler in self.startup_handlers:
            try:
                await handler()
            except Exception as e:
                raise e

    async def _shutdown(self) -> None:
        """Execute all shutdown handlers sequentially with error handling"""
        for handler in self.shutdown_handlers:
            try:
                await handler()
            except Exception as e:
                raise e

    async def handle_lifespan(self, receive: Receive, send: Send) -> None:
        """Handle ASGI lifespan protocol events."""
        # self._setup_openapi()
        try:
            while True:
                message: Message = await receive()
                if message["type"] == "lifespan.startup":
                    try:
                        if self.lifespan_context:
                            # If a lifespan context manager is provided, use it
                            self.lifespan_manager: Any = self.lifespan_context(self)
                            returned_state = await self.lifespan_manager.__aenter__()
                            if returned_state:
                                self.state.update(returned_state)
                        else:
                            # Otherwise, fall back to the default startup handlers
                            await self._startup()
                        await send({"type": "lifespan.startup.complete"})
                    except Exception as e:
                        await send(
                            {"type": "lifespan.startup.failed", "message": str(e)}
                        )
                        return

                elif message["type"] == "lifespan.shutdown":
                    try:
                        if self.lifespan_context:
                            # If a lifespan context manager is provided, use it
                            await self.lifespan_manager.__aexit__(None, None, None)
                        else:
                            # Otherwise, fall back to the default shutdown handlers
                            await self._shutdown()
                        await send({"type": "lifespan.shutdown.complete"})
                        return
                    except Exception as e:
                        await send(
                            {"type": "lifespan.shutdown.failed", "message": str(e)}
                        )
                        return

        except Exception as e:
            logger.debug(f"Error handling lifespan event: {e}")
            if message["type"].startswith("lifespan.startup"):  # type: ignore
                await send({"type": "lifespan.startup.failed", "message": str(e)})
            else:
                await send({"type": "lifespan.shutdown.failed", "message": str(e)})

    def add_middleware(
        self,
        middleware: Annotated[
            MiddlewareType,
            Doc(
                "A callable middleware function that processes requests and responses."
            ),
        ],
    ) -> None:
        """
        Adds middleware to the application.

        Middleware functions are executed in the request-response lifecycle, allowing
        modifications to requests before they reach the route handler and responses
        before they are sent back to the client.

        Args:
            middleware (MiddlewareType): A callable that takes a `Request`, `Response`,
            and a `Callable` (next middleware or handler) and returns a `Response`.

        Returns:
            None

        Example:
            ```python
            def logging_middleware(request: Request, response: Response, next_call: Callable) -> Response:
                print(f"Request received: {request.method} {request.url}")
                return next_call()

            app.add_middleware(logging_middleware)
            ```
        """

        self.http_middleware.insert(
            0,
            Middleware(ASGIRequestResponseBridge, dispatch=middleware),  # type:ignore
        )

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
            route (Route): The WebSocket route configuration.

        Returns:
            None

        Example:
            ```python
            route = Route("/ws/chat", chat_handler)
            app.add_ws_route(route)
            ```
        """

        if route:
            if (not path or path == route.raw_path) and (
                not handler or handler == route.handler
            ):
                self.router.add_ws_route(route)
                return

        if path is None or handler is None:
            raise ValueError(
                "path and handler are required when 'route' is not provided."
            )

        self.ws_router.add_ws_route(
            WebsocketRoute(path, handler, middleware=middleware)
        )

    def mount_router(self, router: Router, name: Optional[str] = None) -> None:
        """
        Mounts a router and all its routes to the application using the router's prefix.

        This method allows integrating another `Router` instance, registering all its
        defined routes into the current application. It is useful for modularizing routes
        and organizing large applications.

        Args:
            router (Router): The `Router` instance whose routes will be added.

        Returns:
            None

        Example:
            ```python
            user_router = Router(prefix="/users")

            @user_router.route("/list", methods=["GET"])
            def get_users(request, response):
                 response.json({"users": ["Alice", "Bob"]})

            app.mount_router(user_router)  # Mounts the user routes into the main app
            ```
        """
        self.router.mount_router(router, name=name)

  

    def add_asgi_middleware(
        self,
        middleware: Annotated[
            ASGIApp,
            Doc(
                "A callable function that intercepts and processes WebSocket connections."
            ),
        ],
    ) -> None:
        """
        Adds a WebSocket middleware to the application.

        WebSocket middleware functions allow pre-processing of WebSocket requests before they
        reach their final handler. Middleware can be used for authentication, logging, or
        modifying the WebSocket request/response.

        Args:
            middleware (Callable): A callable function that handles WebSocket connections.

        Returns:
            None

        Example:
            ```python
            def ws_auth_middleware(ws, next_handler):
                if not ws.headers.get("Authorization"):
                    ...
                return next_handler(ws)

            app.add_asgi_middleware(ws_auth_middleware)
            ```
        """
        self.ws_middleware.append(middleware)

    def handle_request(self, scope: Scope, receive: Receive, send: Send):
        app = self.app
        middleware = (
            [
                Middleware(
                    ASGIRequestResponseBridge,
                    dispatch=ServerErrorMiddleware(handler=self.server_error_handler),
                )
            ]
            + self.http_middleware
            + [
                Middleware(ASGIRequestResponseBridge, dispatch=self.exceptions_handler)  # type:ignore
            ]
        )
        for cls, args, kwargs in reversed(middleware):
            app = cls(app, *args, **kwargs)
        return app(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI application callable"""
        scope["app"] = self
        scope["base_app"] = self
        scope["global_state"] = self.state

        if scope["type"] == "lifespan":
            await self.handle_lifespan(receive, send)
        elif scope["type"] in ["http","websocket"]:
            await self.handle_request(scope, receive, send)



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

        return self.route(
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
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            request_content_type="application/json",
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
                data = await request.json
                updates = {k: v for k, v in data.items()
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
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            request_content_type="application/json",
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
        self.router.add_route(route)

    def add_exception_handler(
        self,
        exc_class_or_status_code: Union[Type[Exception], int],
        handler: Optional[ExceptionHandlerType] = None,
    ) -> Any:
        if handler is None:
            # If handler is not given yet, return a decorator
            def decorator(func: ExceptionHandlerType) -> Any:
                self.exceptions_handler.add_exception_handler(
                    exc_class_or_status_code, func
                )
                return func

            return decorator
        else:
            # Normal direct handler registration
            self.exceptions_handler.add_exception_handler(
                exc_class_or_status_code, handler
            )

    def url_for(self, _name: str, **path_params: Any) -> URLPath:
        return self.router.url_for(_name, **path_params)

    def wrap_asgi(
        self,
        middleware_cls: Annotated[
            Callable[[ASGIApp], Any],
            Doc(
                "An ASGI middleware class or callable that takes an app as its first argument and returns an ASGI app"
            ),
        ],
        **kwargs: Dict[str, Any],
    ) -> None:
        """
        Wraps the entire application with an ASGI middleware.

        This method allows adding middleware at the ASGI level, which intercepts all requests
        (HTTP, WebSocket, and Lifespan) before they reach the application.

        Args:
            middleware_cls: An ASGI middleware class or callable that follows the ASGI interface
            *args: Additional positional arguments to pass to the middleware
            **kwargs: Additional keyword arguments to pass to the middleware

        Returns:
            NexiosApp: The application instance for method chaining


        """
        self.app = middleware_cls(self.app, **kwargs)
        return None

    def get_all_routes(self) -> List[Route]:
        """
        Returns all routes registered in the application.

        This method retrieves a list of all HTTP and WebSocket routes defined in the application.

        Returns:
            List[Route]: A list of all registered routes.

        Example:
            ```python
            routes = app.get_all_routes()
            for route in routes:
                print(route.path, route.methods)
            ```
        """
        return self.router.get_all_routes()

    def ws_route(
        self,
        path: Annotated[
            str,
            Doc(
                """
                URL path pattern for the WebSocket route.
                Example: '/ws/chat/{room_id}'
            """
            ),
        ],
        handler: Annotated[
            Optional[WsHandlerType],
            Doc(
                """
                Async handler function for WebSocket connections.
                Example:
                async def chat_handler(websocket, path):
                    await websocket.send("Welcome to the chat!")
            """
            ),
        ] = None,
    ):
        """
        Register a WebSocket route with the application.

        Args:
            path (str): URL path pattern for the WebSocket route.
            handler (Callable): Async handler function for WebSocket connections.
                Example: async def chat_handler(websocket, path): pass

        Returns:
            Callable: A decorator to register the WebSocket route.
        """
        return self.router.ws_route(
            path=path,
            handler=handler,
        )

    def register(
        self,
        app: ASGIApp,
        prefix: str = "",
    ) -> None:
        self.router.register(app, prefix)

    def __str__(self) -> str:
        return f"<NexiosApp: {self.title}>"

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
    ):
        """
        Run the application using uvicorn.

        Note: For production, consider using the Nexios CLI or ASGI servers directly:
        - nexios run --host 0.0.0.0 --port 8000
        - uvicorn app:app --host 0.0.0.0 --port 8000
        - granian app:app --host 0.0.0.0 --port 8000

        Args:
            host (str): Host address to bind.
            port (int): Port number to bind.
            reload (bool): Enable auto-reload.
            **kwargs: Additional keyword arguments for uvicorn.
        """
        import warnings

        warnings.warn(
            "app.run() is inefficient and only for testing. For development and production, use:\n"
            "- nexios run --host 0.0.0.0 --port 8000\n"
            "- uvicorn app:app --host 0.0.0.0 --port 8000\n"
            "- granian app:app --host 0.0.0.0 --port 8000",
            UserWarning,
            stacklevel=2,
        )

        try:
            import uvicorn

            print(f"Starting server with uvicorn: {host}:{port}")
            uvicorn.run(self, host=host, port=port, reload=reload)
        except ImportError:
            raise RuntimeError(
                "uvicorn not found. Install it with: pip install uvicorn\n"
                "Or use the Nexios CLI: nexios run"
            )
