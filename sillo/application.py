from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    AsyncContextManager,
    ContextManager,
    Literal,
    cast,
)

from typing_extensions import Doc

from sillo._internals._middleware import (
    ASGIRequestResponseBridge,
    MiddlewareFactory,
)
from sillo._internals._middleware import DefineMiddleware as Middleware
from sillo.core.dependencies import Depend
from sillo.core.encoding import CUSTOM_ENCODERS, register_encoder
from sillo.core.error import (
    ServerErrHandlerType,
    ServerErrorMiddleware,
)
from sillo.core.helpers.async_helpers import is_async_callable
from sillo.core.routing import Route, Router, WebsocketRoute
from sillo.core.routing.base import BaseRoute
from sillo.env import autoload as _autoload_env
from sillo.events import EventEmitter
from sillo.exception_handler import ExceptionMiddleware
from sillo.logging import create_logger
from sillo.objects import URLPath
from sillo.openapi import Contact, License
from sillo.openapi._builder import APIDocumentation
from sillo.openapi.config import OpenAPIConfig
from sillo.openapi.models import HTTPBearer, Parameter, Server
from sillo.openapi.ui import DocsContext, DocsUI, default_docs

from .types import (
    ArgsType,
    ASGIApp,
    ExceptionHandlerFor,
    ExcT,
    HandlerType,
    Message,
    MiddlewareType,
    Receive,
    Scope,
    Send,
    WsHandlerType,
)

if TYPE_CHECKING:
    from sillo.auth.backend import AuthenticationBackend
    from sillo.console import Command
    from sillo.core.http import Request, Response
    from sillo.users import BaseUser

import json
import warnings

try:
    import uvicorn  # type: ignore[import-untyped]
except ImportError:
    uvicorn = None  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

allowed_methods_default = ["get", "post", "delete", "put", "patch", "options"]

logger = create_logger("sillo")
lifespan_manager = Callable[
    ["SilloApp"], AsyncContextManager[Any] | ContextManager[Any]
]


class SilloApp:
    """
    Core application class for the sillo ASGI web framework.

    This class serves as the central entry point for building asynchronous
    web applications and APIs. It integrates routing, middleware, dependency
    injection, OpenAPI documentation generation, lifespan management, and
    WebSocket support into a single cohesive interface.

    The application follows the ASGI specification and can be served by any
    compliant ASGI server such as uvicorn, granian, or daphne. It provides
    both decorator-based and programmatic route registration patterns.

    Attributes:
        debug: Whether debug mode is enabled for detailed error output.
        dependencies: Global dependency injection definitions.
        custom_encoders: Mapping of types to custom JSON encoder callables.
        http_middleware: Ordered list of HTTP middleware instances.
        startup_handlers: List of async callables executed on application startup.
        shutdown_handlers: List of async callables executed on application shutdown.
        server_error_handler: Optional handler for unhandled server exceptions.
        route_class: The route class used for constructing route instances.
        app: The root router instance managing all registered routes.
        exceptions_handler: The middleware handling registered exception mappings.
        router: Reference to the root router for convenience access.
        state: A shared dictionary for storing application-level state.
        openapi_config: Configuration object for OpenAPI schema generation.
        openapi: The API documentation builder instance.
        events: The event emitter for application-level event broadcasting.
        title: The display title of the application.
    """

    def __init__(
        self,
        debug: Annotated[
            bool,
            Doc("""
                    Whether to enable debug mode.
                    """),
        ] = True,
        title: Annotated[
            str | None,
            Doc("""
                    The title of the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        version: Annotated[
            str | None,
            Doc("""
                    The version of the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        description: Annotated[
            str | None,
            Doc("""
                    A brief description of the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        contact: Annotated[
            Contact | None,
            Doc("""
                    Contact information for the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        license: Annotated[
            License | None,
            Doc("""
                    License information for the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        servers: Annotated[
            list[Server] | None,
            Doc("""
                    A list of servers for the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        terms_of_service: Annotated[
            str | None,
            Doc("""
                    A URL to the terms of service for the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        swagger_docs: Annotated[
            str,
            Doc("""
                    A URL to the Swagger UI documentation for the API, used in the OpenAPI documentation.
                    """),
        ] = "/docs",
        redoc_docs: Annotated[
            str,
            Doc("""
                    A URL to the Redoc documentation for the API, used in the OpenAPI documentation.
                    """),
        ] = "/redoc",
        openapi_url: Annotated[
            str,
            Doc(
                "A  URL to the OpenAPI Specification for the API, used in the OpenAPI documentation."
            ),
        ] = "/openapi.json",
        docs: Annotated[
            Sequence[DocsUI] | None,
            Doc("""
                    The documentation viewers to mount, each serving the generated
                    OpenAPI document at its own path.

                        docs=[Swagger(path="/docs"), Scalar(path="/reference")]

                    Pass ``[]`` to serve no documentation UI; the raw document is
                    still available at ``openapi_url``. Leave it unset for the
                    default pair, Swagger UI and ReDoc.

                    Anything with a ``path`` and a ``render(ctx)`` method works
                    here, so a viewer sillo does not ship needs no changes to
                    sillo. See :class:`sillo.openapi.ui.DocsUI`.
                """),
        ] = None,
        server_error_handler: Annotated[
            ServerErrHandlerType | None,
            Doc(
                """
                        A function in sillo responsible for handling server-side exceptions by logging errors, reporting issues, or initiating recovery mechanisms. It prevents crashes by intercepting unexpected failures, ensuring the application remains stable and operational. This function provides a structured approach to error management, allowing developers to define custom handling strategies such as retrying failed requests, sending alerts, or gracefully degrading functionality. By centralizing error processing, it improves maintainability and observability, making debugging and monitoring more efficient. Additionally, it ensures that critical failures do not disrupt the entire system, allowing services to continue running while appropriately managing faults and failures."""
            ),
        ] = None,
        lifespan: Annotated[
            lifespan_manager | None,
            Doc("""
                    A function in sillo responsible for handling ASGI lifespan protocol events. It handles the startup and shutdown events emitted by the ASGI server. It allows you to perform actions such as initializing resources, opening connections, and tearing down resources during application startup and shutdown.

                    This function is called when the application starts and when it shuts down. It receives a `Receive` function to receive lifespan events and a `Send` function to send lifespan events.

                    The `lifespan_manager` function takes two arguments: `self` and `receive` and `send`. It returns an `AsyncContextManager` that can be used to manage the lifespan of the application.

                    You can use this function to perform actions such as connecting to a database, initializing a cache, or registering a signal handler.
                """),
        ] = None,
        routes: Annotated[
            Sequence[BaseRoute],
            Doc("""
                    A list of routes for the application. These routes define the URLs that the application will handle and the handlers that will be called when those URLs are accessed.

                    Each route is an instance of the `Route` class and defines the URL path, the handler function, and any additional middleware or dependencies that should be applied to that route.

                    You can add routes to the application using the `add_route` method of the `Router` class.
                """),
        ] = [],
        dependencies: Annotated[
            list[Depend] | None,
            Doc("""
                    A list of dependencies for the application. These dependencies are used to resolve dependencies within the application.

                    A dependency is a function that takes a `Request` object and returns the value that should be injected into the dependency.

                    You can add dependencies to the application using the `add_dependency` method of the `Router` class.
                """),
        ] = None,
        route_class: Annotated[
            type[Route],
            Doc("""
                    The class used to create routes. This can be a custom route class that inherits from `Route`.
                """),
        ] = Route,
        strict_validation: Annotated[
            bool,
            Doc("""
                    Validate every declared parameter with Pydantic, including those
                    written in the pre-Pydantic style that only supply a default.
                    Missing or malformed values then return 422 instead of the
                    historical 500. Off by default so existing applications keep
                    their current behavior; recommended for new applications.
                """),
        ] = False,
        auth: Annotated[
            Sequence[AuthenticationBackend] | None,
            Doc("""
                    The authentication backends this application accepts.

                        auth=[JWTAuthBackend(secret_key=...), SessionAuthBackend()]

                    One declaration does two jobs: it mounts
                    ``AuthenticationMiddleware`` with these backends, and it
                    publishes each backend's ``describe()`` under
                    ``components.securitySchemes``. A route then names a
                    scheme once, on its gate, and its documented ``security``
                    follows from that — so the document cannot claim auth the
                    application does not enforce.

                    Backends whose ``describe()`` returns ``None`` still
                    authenticate; they are simply left out of the document.

                    Leaving this unset keeps the previous behaviour, including
                    the legacy ``bearerAuth`` scheme registered by default.
                """),
        ] = None,
        auth_user_model: Annotated[
            type[BaseUser] | None,
            Doc("""
                    User model the mounted authentication middleware loads
                    identities into. Only read when ``auth`` is given.
                """),
        ] = None,
        strict_security: Annotated[
            bool,
            Doc("""
                    Refuse to build a document whose security requirements do
                    not resolve. A route naming a scheme that no backend
                    registered is a silent lie today — the viewer shows an
                    authorize box wired to nothing. Off by default so existing
                    applications keep building; recommended for new ones.
                """),
        ] = False,
    ) -> None:
        """
        Initialize the sillo application with all core subsystems.

        Constructs the root router, configures OpenAPI documentation settings,
        registers default security schemes, sets up the event emitter, and
        wires internal bookkeeping structures such as middleware lists and
        lifecycle handler queues. The ``setup`` method is called at the end
        of initialization to mount built-in documentation routes.

        Args:
            debug: Whether to enable debug mode. When ``True``, detailed
                error traces are included in responses. Defaults to ``True``.
            title: The display title used in generated OpenAPI documentation.
                Falls back to ``"sillo API"`` when not provided.
            version: The semantic version string shown in OpenAPI output.
                Defaults to ``"1.0.0"`` when not provided.
            description: A human-readable description of the API surfaced in
                OpenAPI documentation. Defaults to ``"sillo Asgi framework"``.
            contact: Optional contact information embedded in the OpenAPI schema.
            license: Optional license metadata embedded in the OpenAPI schema.
            servers: An optional list of server entries for the OpenAPI schema.
            terms_of_service: Optional URL pointing to the API terms of service.
            swagger_docs: The URL path at which the Swagger UI is served.
                Defaults to ``"/docs"``. Deprecated in favour of ``docs``;
                passing both raises ``TypeError``.
            redoc_docs: The URL path at which the Redoc UI is served.
                Defaults to ``"/redoc"``. Deprecated in favour of ``docs``;
                passing both raises ``TypeError``.
            openapi_url: The URL path serving the raw OpenAPI JSON schema.
                Defaults to ``"/openapi.json"``.
            docs: The documentation viewers to mount. ``None`` mounts the
                default pair (Swagger UI and ReDoc); ``[]`` mounts none.
            server_error_handler: An optional callable invoked when an
                unhandled exception occurs during request processing.
            lifespan: An optional async context manager factory for managing
                application startup and shutdown lifecycle events.
            routes: An initial sequence of route objects to register with the
                root router. Defaults to an empty list.
            dependencies: An optional list of global dependency injection
                definitions applied across all routes.
            route_class: The class used to instantiate new routes. Allows
                substitution of a custom ``Route`` subclass. Defaults to
                :class:`Route`.
            strict_validation: When ``True``, parameters declared in the
                pre-Pydantic style are validated too, so a missing or malformed
                value produces a 422 rather than a 500. Defaults to ``False``
                to preserve the behavior of existing applications.

        Returns:
            None

        Raises:
            TypeError: If ``docs`` is passed alongside a non-default
                ``swagger_docs`` or ``redoc_docs``, which specify the same
                thing two ways.
            ValueError: If two documentation viewers claim the same path.
        """
        # The project's .env, read once per process. An application that
        # reads os.environ at import time has it already, and no project
        # needs python-dotenv to make that true. SILLO_ENV_FILE="" opts out.
        _autoload_env()

        # Assigned directly: the property setter rebuilds the chain, which
        # cannot happen before the rest of __init__ has run. The chain is
        # built once at the end, when everything it needs exists.
        self._debug = debug
        self.dependencies = dependencies or []
        self.custom_encoders: dict[type, Callable[[Any], Any]] = {}

        self.http_middleware: list[Middleware] = []
        self.startup_handlers: list[Callable[[], Awaitable[None]]] = []
        self.shutdown_handlers: list[Callable[[], Awaitable[None]]] = []
        self.server_error_handler = server_error_handler

        self.route_class = route_class
        self.strict_validation = strict_validation
        # Serialized OpenAPI document per mount prefix, built once.
        self._openapi_documents: dict[str, str] = {}
        self.app = Router(
            routes=routes,
            dependencies=self.dependencies,
            route_class=self.route_class,
            strict_validation=strict_validation,
        )
        self.exceptions_handler = ExceptionMiddleware()
        self.router = self.app
        self.route = self.router.route
        # Ready before the application can receive anything.
        self._build_request_chain()
        self.lifespan_context: lifespan_manager | None = lifespan
        self.state: dict[str, Any] = {}

        #: Console commands this application registers. The ``sillo`` command
        #: reads them after importing the app, which is how a project's own
        #: commands reach the command line without a file of its own.
        self.commands: list[type[Command]] = []

        #: The user model authentication loads identities into, kept so that
        #: tooling can find it. The middleware receives it separately.
        self.auth_user_model = auth_user_model

        self.openapi_config = OpenAPIConfig(
            title=title or "sillo API",
            version=version or "1.0.0",
            description=description or "sillo Asgi framework",
            license=license,
            contact=contact,
            servers=servers,
            termsOfService=terms_of_service,
        )

        self.strict_security = strict_security
        self.auth_backends: list[AuthenticationBackend] = list(auth or [])

        if self.auth_backends:
            self._register_auth(auth_user_model)
        else:
            # Legacy default. An application that declares no backends still
            # advertises JWT bearer auth, which is a claim the document has no
            # basis for — but removing it would dangle every existing
            # `security=[{"bearerAuth": []}]`, so it stands until `auth=` is
            # used. Declaring backends is the opt-out.
            self.openapi_config.add_security_scheme(
                "bearerAuth",
                HTTPBearer(type="http", scheme="bearer", bearerFormat="JWT"),
            )

        self.openapi = APIDocumentation(
            config=self.openapi_config,
            openapi_url=openapi_url,
        )

        self.docs: list[DocsUI] = self._resolve_docs(docs)

        self.events = EventEmitter()
        self.title = title or "sillo API"
        self.setup()

    def _register_auth(self, user_model: type[BaseUser] | None) -> None:
        """Mount the authentication middleware and publish its schemes.

        Args:
            user_model: User model the middleware loads identities into, or
                ``None`` for the middleware's own default.

        Raises:
            ValueError: If two backends claim the same scheme name with
                different definitions. Silently overwriting one with the
                other would document a credential the loser never reads.
        """
        from sillo.auth.middleware import AuthenticationMiddleware

        for backend in self.auth_backends:
            scheme = backend.describe()
            if scheme is None:
                continue

            existing = self.openapi_config.security_schemes.get(backend.name)
            if existing is not None and existing != scheme:
                raise ValueError(
                    f"Two auth backends both claim the scheme {backend.name!r} "
                    f"but describe it differently. Give one of them a distinct "
                    f"name, e.g. {type(backend).__name__}(name='...')."
                )
            self.openapi_config.add_security_scheme(backend.name, scheme)

        middleware = (
            AuthenticationMiddleware(user_model=user_model, backend=self.auth_backends)
            if user_model is not None
            else AuthenticationMiddleware(backend=self.auth_backends)
        )
        self.use(middleware)

    def _check_security(self) -> None:
        """Verify every route's security resolves to a registered scheme.

        The whole point of deriving ``security`` from the gate is that the two
        can be checked against each other. Without this they can disagree
        forever in silence: the viewer renders an authorize box wired to a
        scheme nothing enforces, and the first sign of trouble is a 401 the
        document says is impossible.

        Raises:
            ValueError: If a route requires a scheme that is not registered.
        """
        known = set(self.openapi_config.security_schemes)
        problems: list[str] = []

        for route in self.get_all_routes():
            if getattr(route, "exclude_from_schema", False):
                continue
            for requirement in getattr(route, "security", None) or []:
                for name in requirement:
                    if name not in known:
                        problems.append(f"  {route.raw_path} requires {name!r}")

        if problems:
            listed = ", ".join(sorted(known)) or "none"
            raise ValueError(
                "These routes require security schemes that are not "
                "registered:\n"
                + "\n".join(sorted(set(problems)))
                + f"\nRegistered schemes: {listed}."
            )

    @staticmethod
    def _resolve_docs(
        docs: Sequence[DocsUI] | None,
    ) -> list[DocsUI]:
        """Decide which documentation viewers to mount.

        If ``docs`` is ``None``, mount the default pair (Atlas and ReDoc).
        Otherwise validate and return the provided list.

        Args:
            docs: The presenters given by the caller, or ``None``.

        Returns:
            The presenters to mount, as a new list.

        Raises:
            TypeError: If ``docs`` contains entries that are not documentation
                presenters.
            ValueError: If two presenters claim the same path.
        """
        if docs is None:
            return default_docs()

        resolved = list(docs)
        for entry in resolved:
            if not hasattr(entry, "path") or not callable(
                getattr(entry, "render", None)
            ):
                raise TypeError(
                    f"docs entries need a 'path' and a render(ctx) method; "
                    f"got {entry!r}. Subclass sillo.openapi.ui.DocsUI."
                )

        seen: dict[str, DocsUI] = {}
        for entry in resolved:
            clash = seen.get(entry.path)
            if clash is not None:
                raise ValueError(
                    f"two documentation viewers claim {entry.path!r}: "
                    f"{clash!r} and {entry!r}"
                )
            seen[entry.path] = entry
        return resolved

    def _docs_context(self, root_path: str) -> DocsContext:
        """Build the render context for a request under ``root_path``."""
        info = self.openapi_config.openapi_spec.info
        return DocsContext(
            openapi_url=root_path + self.openapi.openapi_url,
            title=info.title,
            version=info.version,
            description=info.description or "",
            config=self.openapi_config,
        )

    def get_docs_ui(self, name: str) -> DocsUI | None:
        """Return a mounted presenter by its ``name``, or ``None``.

        Args:
            name: The presenter's ``name`` attribute, e.g. ``"swagger"``.

        Returns:
            The first presenter with that name, or ``None`` if none matches.
        """
        return next((ui for ui in self.docs if getattr(ui, "name", None) == name), None)

    def _mount_docs_ui(self, ui: DocsUI) -> None:
        """Mount one documentation presenter at its own path.

        Args:
            ui: The presenter to serve.

        Returns:
            None
        """

        # Bound as a default argument rather than captured: a closure over the
        # loop variable would give every route the last presenter in the list,
        # which shows up as the wrong viewer rendering at the right path.
        @self.get(ui.path, exclude_from_schema=True)
        async def docs_ui(request: Request, response: Response, _ui: DocsUI = ui):
            root_path = request.scope.get("root_path", "")
            return response.html(_ui.render(self._docs_context(root_path)))

    def setup(self) -> None:
        """
        Register the OpenAPI document route and every documentation viewer.

        Invoked automatically during initialization. Mounts one GET endpoint
        serving the raw OpenAPI JSON, then one per entry in ``docs``. All are
        excluded from the generated schema so the documentation does not
        document itself, and all read ``root_path`` from the ASGI scope so
        they work when the application is mounted under a prefix.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        from sillo.core.http.response import BaseResponse

        @self.get(self.openapi.openapi_url, exclude_from_schema=True)
        async def serve_openapi(request: Request, response: Response):
            root_path = request.scope.get("root_path", "")
            return BaseResponse(
                body=self.build_openapi(root_path),
                content_type="application/json",
            )

        for ui in self.docs:
            self._mount_docs_ui(ui)

    def build_openapi(self, root_path: str = "") -> str:
        """Build the OpenAPI document and return it as a JSON string.

        Generating the document walks every route and produces JSON Schema for
        every model, so it is built once — during startup, or on first access
        for a mount prefix not seen at startup — and the serialized result is
        kept. Serving it afterwards writes a stored string, doing no
        generation and no encoding per request.

        Routes are registered before the application starts serving, so there
        is nothing to invalidate; a prefix is built at most once.

        Args:
            root_path: The ASGI mount prefix the document should describe.
                Documents are stored per prefix, since the same application can
                be mounted at more than one path.

        Returns:
            The serialized OpenAPI document.
        """
        cached = self._openapi_documents.get(root_path)
        if cached is None:
            if self.strict_security:
                self._check_security()
            cached = json.dumps(
                self.openapi.get_openapi(self.router, current_prefix=root_path)
            )
            self._openapi_documents[root_path] = cached
        return cached

    def on_startup(
        self, handler: Callable[[], Awaitable[None]]
    ) -> Callable[[], Awaitable[None]]:
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
        return handler

    def on_shutdown(
        self, handler: Callable[[], Awaitable[None]]
    ) -> Callable[[], Awaitable[None]]:
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
        return handler

    async def _startup(self) -> None:
        """
        Execute all registered startup handlers sequentially.

        Iterates through the ``startup_handlers`` list and invokes each
        handler in registration order. Both async and sync callables are
        supported; async handlers are awaited while sync handlers are
        called directly. This method is invoked by the ASGI lifespan
        protocol when no custom lifespan context manager is configured.

        Args:
            None

        Returns:
            None

        Raises:
            Exception: Propagates any exception raised by a startup handler
                to the caller, which typically results in a
                ``lifespan.startup.failed`` ASGI message.
        """
        # All routes are registered by the time the application starts, so the
        # OpenAPI document is built here, once, rather than on a request.
        self.build_openapi()

        for handler in self.startup_handlers:
            if is_async_callable(handler):
                await handler()
            else:
                handler()

    async def _shutdown(self) -> None:
        """
        Execute all registered shutdown handlers sequentially.

        Iterates through the ``shutdown_handlers`` list and invokes each
        handler in registration order. Both async and sync callables are
        supported; async handlers are awaited while sync handlers are
        called directly. This method is invoked by the ASGI lifespan
        protocol when no custom lifespan context manager is configured.

        Args:
            None

        Returns:
            None

        Raises:
            Exception: Propagates any exception raised by a shutdown handler
                to the caller, which typically results in a
                ``lifespan.shutdown.failed`` ASGI message.
        """
        for handler in self.shutdown_handlers:
            if is_async_callable(handler):
                await handler()
            else:
                handler()

    @staticmethod
    def _is_async_context_manager(obj: Any) -> bool:
        """
        Determine whether an object implements the async context manager protocol.

        Checks for the presence of both ``__aenter__`` and ``__aexit__``
        dunder methods on the provided object. This is used internally by
        the lifespan handler to decide whether to await or synchronously
        invoke the context manager entry and exit methods.

        Args:
            obj: Any Python object to inspect for async context manager
                protocol compliance.

        Returns:
            bool: ``True`` if the object implements both ``__aenter__``
                and ``__aexit__``, ``False`` otherwise.

        Raises:
            None
        """
        return hasattr(obj, "__aenter__") and hasattr(obj, "__aexit__")

    async def handle_lifespan(self, receive: Receive, send: Send) -> None:
        """
        Handle the ASGI lifespan protocol for application startup and shutdown.

        Listens for ``lifespan.startup`` and ``lifespan.shutdown`` messages
        from the ASGI server. On startup, either the custom lifespan context
        manager is entered or the registered startup handlers are executed.
        On shutdown, the corresponding cleanup is performed. State returned
        from the lifespan context manager is merged into ``self.state``.

        Args:
            receive: An async callable that yields ASGI scope messages from
                the server. Used to receive lifespan event notifications.
            send: An async callable that sends ASGI messages back to the
                server, such as startup complete or shutdown failed signals.

        Returns:
            None

        Raises:
            None: Exceptions during startup or shutdown are caught internally
                and communicated via ``lifespan.startup.failed`` or
                ``lifespan.shutdown.failed`` messages.
        """

        while True:
            message: Message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    if self.lifespan_context:
                        # If a lifespan context manager is provided, use it
                        self.lifespan_manager: Any = self.lifespan_context(self)
                        if self._is_async_context_manager(self.lifespan_manager):
                            returned_state = await self.lifespan_manager.__aenter__()  # ty: ignore[unresolved-attribute]
                        else:
                            returned_state = self.lifespan_manager.__enter__()  # ty: ignore[unresolved-attribute]
                        if returned_state:
                            self.state.update(returned_state)
                    else:
                        # Otherwise, fall back to the default startup handlers
                        await self._startup()
                    await send({"type": "lifespan.startup.complete"})
                except Exception as e:
                    await send({"type": "lifespan.startup.failed", "message": str(e)})
                    return

            elif message["type"] == "lifespan.shutdown":
                try:
                    if self.lifespan_context:
                        # If a lifespan context manager is provided, use it
                        if self._is_async_context_manager(self.lifespan_manager):
                            await self.lifespan_manager.__aexit__(None, None, None)  # ty: ignore[unresolved-attribute]
                        else:
                            self.lifespan_manager.__exit__(None, None, None)  # ty: ignore[unresolved-attribute]
                    else:
                        # Otherwise, fall back to the default shutdown handlers
                        await self._shutdown()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
                except Exception as e:
                    await send({"type": "lifespan.shutdown.failed", "message": str(e)})
                    return

    def use(
        self,
        middleware: Annotated[
            MiddlewareType | MiddlewareFactory,
            Doc(
                "A callable middleware function that processes requests and responses."
            ),
        ],
        *args: Annotated[
            Any,
            Doc("Positional arguments forwarded to a `raw=True` middleware factory."),
        ],
        raw: Annotated[
            bool,
            Doc(
                "Treat `middleware` as a raw ASGI middleware factory, called as "
                "`middleware(next_app, *args, **kwargs)`, instead of a dispatch "
                "function."
            ),
        ] = False,
        **kwargs: Annotated[
            Any,
            Doc("Keyword arguments forwarded to a `raw=True` middleware factory."),
        ],
    ) -> None:
        """
        Adds middleware to the application.

        Middleware functions are executed in the request-response lifecycle, allowing
        modifications to requests before they reach the route handler and responses
        before they are sent back to the client.

        Two forms are accepted.

        The default is sillo's dispatch form: an instance, or a plain function,
        taking `(request, response, call_next)`. sillo builds the `Request` and
        the `Response` for it and turns the rest of the chain into something
        awaitable. That is convenient, and it costs a request object, a
        response object and a background task per layer per request.

        Passing `raw=True` registers a raw ASGI middleware instead. The
        argument is then a *factory* — usually a class — invoked as
        `middleware(next_app, *args, **kwargs)`, and whatever it returns is
        called with `(scope, receive, send)`. Nothing is built on its behalf,
        so it is the cheaper form and the one to reach for when the middleware
        does not need a parsed request; it is also how sillo's own
        `ServerErrorMiddleware` and `ExceptionMiddleware` are written. ASGI
        middleware from other frameworks generally drops straight in.

        Args:
            middleware: With `raw=False`, a callable taking a `Request`, a
                `Response` and a `call_next` callable, returning a `Response`.
                With `raw=True`, a factory taking the next ASGI application as
                its first argument and returning an ASGI application.
            *args: Positional arguments for the factory. `raw=True` only.
            raw: Whether `middleware` is a raw ASGI middleware factory.
            **kwargs: Keyword arguments for the factory. `raw=True` only.

        Returns:
            None

        Raises:
            TypeError: If extra arguments are passed without `raw=True`. The
                dispatch form takes a middleware that is already configured, so
                there is nowhere for them to go and silently dropping them
                would leave the middleware running on its defaults.

        Example:
            ```python
            # dispatch form
            async def logging_middleware(request: Request, response: Response, call_next):
                print(f"Request received: {request.method} {request.url}")
                return await call_next()

            app.use(logging_middleware)


            # raw ASGI form
            class RequestId:
                def __init__(self, app, header: str = "x-request-id"):
                    self.app = app
                    self.header = header.encode()

                async def __call__(self, scope, receive, send):
                    if scope["type"] != "http":
                        return await self.app(scope, receive, send)

                    async def send_with_id(message):
                        if message["type"] == "http.response.start":
                            message["headers"].append((self.header, uuid4().hex.encode()))
                        await send(message)

                    await self.app(scope, receive, send_with_id)

            app.use(RequestId, raw=True, header="x-trace-id")
            ```
        """
        if not raw and (args or kwargs):
            raise TypeError(
                "use() forwards extra arguments only to raw ASGI middleware. "
                "Pass raw=True to have them handed to the factory, or "
                "configure the middleware before registering it."
            )

        # Authentication can be configured two ways: SilloApp(auth_user_model=…)
        # or AuthenticationMiddleware(user_model=…) passed to use(). Both name
        # the same thing, and tooling that wants to know which model this
        # application authenticates against should not have to care which was
        # used, so the middleware's answer is adopted when nothing else set one.
        if self.auth_user_model is None:
            self.auth_user_model = getattr(middleware, "user_model", None)

        self.http_middleware.insert(
            0,
            # Raw middleware is the factory itself: the chain builder calls
            # `cls(next_app, *args, **kwargs)`, which is exactly the ASGI
            # convention, so no wrapper is involved at all. `raw=True` is the
            # caller stating which half of the union they passed, and nothing
            # in the type system carries that from the flag to the value, so
            # the cast is where that claim is recorded.
            Middleware(cast(MiddlewareFactory, middleware), *args, **kwargs)
            if raw
            else Middleware(ASGIRequestResponseBridge, dispatch=middleware),
        )
        self._build_request_chain()

    def add_encoder(
        self,
        type_: type,
        encoder: Callable[[Any], Any],
    ) -> None:
        """Register a custom JSON encoder for a type across the application.

        Registered encoders are applied automatically whenever sillo serializes
        a response to JSON — including values returned directly from handlers.
        They are merged on top of the built-in type encoders and also feed the
        global :func:`sillo.encoding.register_encoder` registry.

        Args:
            type_: The Python type (or abstract base) to encode.
            encoder: Callable receiving an instance of ``type_`` and returning a
                JSON-serializable value.

        Example:
            ```python
            from decimal import Decimal

            app.add_encoder(Decimal, lambda d: float(d))

            @app.get("/price")
            async def price(request, response):
                return {"total": Decimal("19.99")}
            ```
        """

        self.custom_encoders[type_] = encoder
        CUSTOM_ENCODERS[type_] = encoder
        register_encoder(type_, encoder)

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

        if (
            route
            and (not path or path == route.raw_path)
            and (not handler or handler == route.handler)
        ):
            self.router.add_ws_route(route)
            return

        if path is None or handler is None:
            raise ValueError(
                "path and handler are required when 'route' is not provided."
            )

        self.router.add_ws_route(WebsocketRoute(path, handler))

    def add_command(self, command: type[Command]) -> type[Command]:
        """Register a console command on this application.

        The ``sillo`` command imports the application and runs whatever is
        registered here, so a project's own commands reach the command line
        without a file of its own::

            from sillo.console import Argument, Command


            class Backfill(Command):
                name = "posts:backfill"
                help = "Fill in slugs for older posts"

                arguments = [Argument("since", default=None)]

                async def handle(self):
                    ...


            app.add_command(Backfill)

        Args:
            command: The command class.

        Returns:
            The class, so this can be used as a decorator.

        Raises:
            ValueError: If the command has no name, or that name is already
                registered on this application.
        """
        if not getattr(command, "name", ""):
            raise ValueError(f"{command.__name__} needs a name")

        for existing in self.commands:
            if existing.name == command.name:
                raise ValueError(
                    f"{command.name!r} is already registered to {existing.__name__}"
                )

        self.commands.append(command)
        return command

    def command(
        self,
        name: str,
        help: str = "",
        arguments: Sequence[Any] | None = None,
        aliases: Sequence[str] = (),
        hidden: bool = False,
    ) -> Callable[[Callable], type[Command]]:
        """Register a plain function as a console command.

        The shorthand for a command whose body does not warrant a class::

            @app.command("cache:clear", help="Drop every cached entry")
            async def clear(command):
                await cache.flush()
                command.success("Cache cleared.")

        Args:
            name: How the command is invoked.
            help: One line for the listing.
            arguments: The parameters it accepts.
            aliases: Other names that dispatch here.
            hidden: Keep it out of the listing.

        Returns:
            A decorator returning the generated command class.
        """
        from sillo.console import Console

        # Console.command builds the class; borrowing it here keeps one
        # implementation of the function-to-command wrapping.
        registry = Console()
        decorate = registry.command(
            name, help=help, arguments=arguments, aliases=aliases, hidden=hidden
        )

        def wrapper(function: Callable) -> type[Command]:
            return self.add_command(decorate(function))

        return wrapper

    def mount_router(self, router: Router, name: str | None = None) -> None:
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

    def handle_request(self, scope: Scope, receive: Receive, send: Send):
        """
        Build the middleware chain and dispatch an incoming ASGI request.

        Constructs a layered middleware stack consisting of the server error
        middleware, all registered HTTP middleware, and the exception handler
        middleware. The chain is assembled in reverse order so that the
        outermost layer processes the request first. The root router is used
        as the innermost application in the chain.

        Args:
            scope: The ASGI connection scope dictionary containing metadata
                about the incoming request such as type, path, and headers.
            receive: An async callable that yields ASGI messages from the
                client, such as request body chunks.
            send: An async callable that sends ASGI messages back to the
                client, such as response headers and body chunks.

        Returns:
            An awaitable coroutine representing the fully wrapped ASGI
            application invocation that processes the request through
            all middleware layers and returns a response.

        Raises:
            None: Exceptions are handled by the middleware layers in the
                chain, specifically the server error and exception middleware.
        """
        return self._request_chain(scope, receive, send)

    @property
    def debug(self) -> bool:
        """Whether detailed error output is enabled."""
        return self._debug

    @debug.setter
    def debug(self, value: bool) -> None:
        """Set debug mode, rebuilding the chain that carries the flag.

        ``ServerErrorMiddleware`` is constructed with this value, and the
        chain holding it is assembled once rather than per request — so
        without rebuilding here, toggling ``app.debug`` after construction
        would change the attribute and nothing else.
        """
        self._debug = value
        self._build_request_chain()

    def _build_request_chain(self) -> None:
        """Assemble the middleware chain and keep it on the application.

        Called from ``__init__`` and again from everything that changes what
        the chain is made of, so a built chain is always sitting ready before
        any request arrives. Requests only read it.

        Rebuilding eagerly rather than marking the chain stale and rebuilding
        on next use is what keeps that promise: a lazy rebuild still lands in
        whichever request happens to arrive first, and gives one unlucky
        caller the cost plus whatever a half-built chain would do to a
        second request arriving concurrently.

        Routes are not part of this. They live on the router, which the chain
        holds by reference, so registering one — which the admin panel does
        from a startup hook, long after the chain exists — needs no rebuild.
        """
        app = self.app

        # Innermost first. Both built-in layers are raw ASGI middleware: they
        # take the next app and are called with ``(scope, receive, send)``,
        # with no ``Request``, ``Response`` or background task constructed on
        # their behalf. Neither reads the body or rewrites the response on the
        # way out — they only care about a request that raised — so paying for
        # a dispatch bridge per layer per request bought nothing, and was the
        # largest fixed cost in the request path.
        #
        # The exception middleware is rebound rather than rebuilt because it
        # owns the handler registries, which outlive any single chain:
        # `add_exception_handler` is called after the chain already exists.
        self.exceptions_handler.app = app
        app = self.exceptions_handler

        for cls, args, kwargs in reversed(self.http_middleware):
            app = cls(app, *args, **kwargs)

        app = ServerErrorMiddleware(
            app, handler=self.server_error_handler, debug=self.debug
        )

        self._request_chain = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        ASGI application entry point invoked by the server for every connection.

        Injects the application instance, base application reference, and
        global state dictionary into the ASGI scope for downstream access.
        Dispatches the connection to the appropriate handler based on the
        scope type: lifespan connections are routed to ``handle_lifespan``,
        while HTTP and WebSocket connections are routed to ``handle_request``.

        Args:
            scope: The ASGI connection scope dictionary containing metadata
                such as the connection type, path, headers, and query string.
            receive: An async callable that yields ASGI messages from the
                client throughout the connection lifecycle.
            send: An async callable that sends ASGI messages back to the
                client, such as response start, body, and disconnect signals.

        Returns:
            None

        Raises:
            None: Exceptions are caught and handled by the middleware layers
                within ``handle_request`` or by the lifespan error handling
                within ``handle_lifespan``.
        """
        scope["app"] = self
        scope["base_app"] = self
        scope["global_state"] = self.state

        if scope["type"] == "lifespan":
            await self.handle_lifespan(receive, send)
        elif scope["type"] in ["http", "websocket"]:
            await self.handle_request(scope, receive, send)

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
                async def get_user(request, response):
                    user = await get_user_from_db(request.path_params['user_id'])
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
                Pydantic model for request validation (query params).
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
            auth=auth,
            **kwargs,
        )

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
                Example: True
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
            auth=auth,
            **kwargs,
        )

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
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ],
            Doc("""
                Request content type.
                Example: 'application/json'
            """),
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
        exc_class_or_status_code: type[ExcT] | int,
        handler: ExceptionHandlerFor[ExcT] | None = None,
    ) -> Any:
        """
        Register a custom exception handler for specific exception types or status codes.

        Maps an exception class or HTTP status code to a handler function that
        produces a response when the specified error occurs during request
        processing. Can be used as a direct method call or as a decorator
        when the handler argument is omitted.

        Args:
            exc_class_or_status_code: Either an exception class (subclass of
                ``Exception``) or an integer HTTP status code to handle.
                For example, ``ValueError`` or ``404``.
            handler: An optional callable that accepts ``(request, response,
                exception)`` and returns a ``Response``. When ``None``, a
                decorator is returned instead for deferred registration.

        Returns:
            Any: When ``handler`` is ``None``, returns a decorator that
                accepts the handler function. When ``handler`` is provided,
                returns ``None`` after registering the handler directly.

        Raises:
            None
        """
        if handler is None:
            # If handler is not given yet, return a decorator
            def decorator(func: ExceptionHandlerFor[ExcT]) -> Any:
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
        """
        Generate a URL path for a named route with the given path parameters.

        Looks up a route by its registered name and interpolates the
        provided path parameters into the route's URL pattern to produce
        a concrete ``URLPath`` instance. This is useful for reverse URL
        generation in redirects, hypermedia responses, and templates.

        Args:
            _name: The unique name assigned to the route during registration.
                This corresponds to the ``name`` argument passed to route
                decorators or the ``add_route`` method.
            **path_params: Keyword arguments representing the path parameters
                to substitute into the route's URL pattern. For example,
                ``user_id=42`` for a route pattern ``/users/{user_id}``.

        Returns:
            URLPath: A URL path object containing the fully resolved URL
                string with all path parameters interpolated.

        Raises:
            KeyError: If the named route is not found in the router or if
                required path parameters are missing from the arguments.
        """
        return self.router.url_for(_name, **path_params)

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
        """
        Wraps the entire application with an ASGI middleware.

        This method allows adding middleware at the ASGI level, which intercepts all requests
        (HTTP, WebSocket, and Lifespan) before they reach the application.

        Args:
            middleware_cls: An ASGI middleware class or callable that follows the ASGI interface
            *args: Additional positional arguments to pass to the middleware
            **kwargs: Additional keyword arguments to pass to the middleware

        Returns:
            SilloApp: The application instance for method chaining


        """
        self.app = middleware_cls(self.app, **kwargs)
        self._build_request_chain()

    def get_all_routes(self) -> list[Route]:
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
            Doc("""
                URL path pattern for the WebSocket route.
                Example: '/ws/chat/{room_id}'
            """),
        ],
        handler: Annotated[
            WsHandlerType | None,
            Doc("""
                Async handler function for WebSocket connections.
                Example:
                async def chat_handler(websocket, path):
                    await websocket.send("Welcome to the chat!")
            """),
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

    def __str__(self) -> str:
        """
        Return a human-readable string representation of the application.

        Produces a descriptive string containing the application's title,
        useful for logging, debugging, and development server output.

        Args:
            None

        Returns:
            str: A string in the format ``<SilloApp: {title}>`` where
                ``{title}`` is the application's configured title.

        Raises:
            None
        """
        return f"<SilloApp: {self.title}>"

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
    ):
        """
        Run the application using uvicorn.

        Note: For production, consider using an ASGI server directly:
        - uvicorn app:app --host 0.0.0.0 --port 8000
        - granian app:app --host 0.0.0.0 --port 8000

        Args:
            host (str): Host address to bind.
            port (int): Port number to bind.
            reload (bool): Enable auto-reload.
            **kwargs: Additional keyword arguments for uvicorn.
        """
        warnings.warn(
            "app.run() is inefficient and only for testing. For development and production, use:\n"
            "- uvicorn app:app --host 0.0.0.0 --port 8000\n"
            "- granian app:app --host 0.0.0.0 --port 8000",
            UserWarning,
            stacklevel=2,
        )

        if uvicorn is None:
            raise RuntimeError(
                "uvicorn not found. Install it with: pip install uvicorn\n"
                "Or use uvicorn directly: uvicorn app:app --host 0.0.0.0 --port 8000"
            )
        logger.info(f"Starting server with uvicorn: {host}:{port}")
        uvicorn.run(self, host=host, port=port, reload=reload)
