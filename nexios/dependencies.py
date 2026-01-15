import contextvars
import inspect
from functools import wraps
from inspect import Parameter, signature
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from typing_extensions import Annotated, Doc

from nexios.utils.async_helpers import is_async_callable
from nexios.utils.concurrency import run_in_threadpool

if TYPE_CHECKING:
    from nexios import NexiosApp, Router
    from nexios.auth.users.base import BaseUser
    from nexios.http import Request


class Depend:
    """
    Dependency injection marker for Nexios framework.

    This class is used to mark function parameters as dependencies that should be
    automatically resolved and injected by the framework's dependency injection system.

    The dependency injection system supports:
    - Async and sync functions
    - Generator functions (for cleanup)
    - Async generator functions (for async cleanup)
    - Nested dependencies (dependencies can have their own dependencies)
    - Context-aware dependencies (access to request, user, app instances)

    Examples:
        1. Basic dependency:
        ```python
        def get_database():
            return Database()

        @app.get("/users")
        async def get_users(request, response, db=Depend(get_database)):
            users = await db.query("SELECT * FROM users")
            return response.json(users)
        ```

        2. Async dependency:
        ```python
        async def get_async_database():
            db = await AsyncDatabase.connect()
            return db

        @app.get("/users")
        async def get_users(request, response, db=Depend(get_async_database)):
            users = await db.query("SELECT * FROM users")
            return response.json(users)
        ```

        3. Dependency with cleanup (generator):
        ```python
        def get_database_with_cleanup():
            db = Database()
            try:
                yield db
            finally:
                db.close()

        @app.get("/users")
        async def get_users(request, response, db=Depend(get_database_with_cleanup)):
            users = await db.query("SELECT * FROM users")
            return response.json(users)
        ```

        4. Nested dependencies:
        ```python
        def get_config():
            return Config()

        def get_database(config=Depend(get_config)):
            return Database(config.db_url)

        @app.get("/users")
        async def get_users(request, response, db=Depend(get_database)):
            users = await db.query("SELECT * FROM users")
            return response.json(users)
        ```

        5. Context-aware dependency:
        ```python
        def get_current_user(ctx=Depend(Context)):
            if not ctx.request.user:
                raise HTTPException(401, "Not authenticated")
            return ctx.request.user

        @app.get("/profile")
        async def get_profile(request, response, user=Depend(get_current_user)):
            return response.json({"user_id": user.id})
        ```
    """

    def __init__(
        self,
        dependency: Annotated[
            Optional[Callable[..., Any]],
            Doc(
                """
                The dependency provider function that will be called to resolve this dependency.
                
                This can be:
                - A regular function that returns a value
                - An async function that returns a value
                - A generator function that yields a value (supports cleanup)
                - An async generator function that yields a value (supports async cleanup)
                
                The function can have its own dependencies by using Depend() in its parameters.
                
                Example:
                ```python
                def database_dependency():
                    return Database()
                
                # Usage
                db_dep = Depend(database_dependency)
                ```
                """
            ),
        ] = None,
    ):
        self.dependency = dependency

    def __class_getitem__(cls, item: Any):
        return cls


class Context:
    """
    Dependency injection context that provides access to request-scoped objects.

    The Context class is used as a dependency to access framework objects like
    the current request, authenticated user, and application instances within
    dependency provider functions.

    This is particularly useful for creating context-aware dependencies that
    need access to request-specific information.

    Attributes:
        request: The current HTTP request object
        user: The authenticated user (if authentication middleware is used)
        base_app: The main NexiosApp instance
        app: The current router instance

    Examples:
        1. Access current request in dependency:
        ```python
        def get_user_from_token(ctx=Depend(Context)):
            token = ctx.request.headers.get("Authorization")
            if not token:
                raise HTTPException(401, "Missing token")
            return decode_token(token)

        @app.get("/profile")
        async def profile(request, response, user=Depend(get_user_from_token)):
            return response.json({"user": user})
        ```

        2. Access app configuration:
        ```python
        def get_database_url(ctx=Depend(Context)):
            return ctx.base_app.config.database_url

        def get_database(db_url=Depend(get_database_url)):
            return Database(db_url)
        ```

        3. User-specific dependencies:
        ```python
        def get_user_preferences(ctx=Depend(Context)):
            if not ctx.user:
                return default_preferences()
            return UserPreferences.get(ctx.user.id)

        @app.get("/dashboard")
        async def dashboard(request, response, prefs=Depend(get_user_preferences)):
            return response.json({"preferences": prefs})
        ```
    """

    def __init__(
        self,
        request: Annotated[
            Optional["Request"],
            Doc(
                "The current HTTP request object containing headers, body, and metadata"
            ),
        ] = None,
        user: Annotated[
            Optional["BaseUser"],
            Doc(
                "The authenticated user object (available when authentication middleware is used)"
            ),
        ] = None,
        base_app: Annotated[
            Optional["NexiosApp"],
            Doc(
                "The main NexiosApp instance providing access to global configuration and state"
            ),
        ] = None,
        app: Annotated[
            Optional["Router"], Doc("The current router instance handling the request")
        ] = None,
        **kwargs: Annotated[
            Dict[str, Any],
            Doc(
                "Additional context data that can be set by middleware or other components"
            ),
        ],
    ):
        self.request = request
        self.user = user
        self.base_app = base_app
        self.app = app
        for k, v in kwargs.items():
            setattr(self, k, v)


current_context: contextvars.ContextVar[Context] = contextvars.ContextVar(
    "current_context"
)


async def resolve_dependency(
    func: Callable[..., Any],
    ctx: Optional[Context] = None,
    cleanup_callbacks: Optional[List[Callable[[], Any]]] = None,
) -> Any:
    if cleanup_callbacks is None:
        cleanup_callbacks = []

    dep_sig = signature(func)
    dep_kwargs = {}

    for param in dep_sig.parameters.values():
        if param.default != Parameter.empty and isinstance(param.default, Depend):
            nested_func = param.default.dependency
            if nested_func is None:
                raise ValueError(
                    f"Dependency for parameter '{param.name}' has no provider"
                )
            dep_kwargs[param.name] = await resolve_dependency(
                nested_func, ctx, cleanup_callbacks
            )
        elif param.default != Parameter.empty and isinstance(param.default, Context):
            dep_kwargs[param.name] = ctx

    if inspect.isasyncgenfunction(func):
        agen = func(**dep_kwargs)
        value = await agen.__anext__()
        cleanup_callbacks.append(lambda agen=agen: agen.aclose())
        return value
    elif inspect.isgeneratorfunction(func):
        gen = func(**dep_kwargs)
        value = next(gen)
        cleanup_callbacks.append(lambda gen=gen: gen.close())
        return value
    elif inspect.iscoroutinefunction(func):
        return await func(**dep_kwargs)
    else:
        return func(**dep_kwargs)


def inject_dependencies(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to inject dependencies into a route handler while supporting deep DI."""

    @wraps(handler)
    async def wrapped(*args: List[Any], **kwargs: Dict[str, Any]) -> Any:
        sig = signature(handler)
        bound_args = sig.bind_partial(*args, **kwargs)
        params = list(sig.parameters.values())

        try:
            ctx = current_context.get()
        except LookupError:
            ctx = None

        cleanup_callbacks: List[Callable[[], Any]] = []
        if ctx is not None and not hasattr(ctx, "_dependency_cleanup"):
            setattr(ctx, "_dependency_cleanup", [])
        if ctx is not None:
            cleanup_callbacks = getattr(ctx, "_dependency_cleanup")

        if ctx is not None and ctx.base_app:
            app_dependencies = get_app_dependencies(ctx.base_app.router)
            for dep in app_dependencies:
                dependency_func = dep.dependency
                if dependency_func is None:
                    raise ValueError("Dependency has no provider")
                await resolve_dependency(dependency_func, ctx, cleanup_callbacks)

        for param in params:
            if (
                param.default != Parameter.empty
                and isinstance(param.default, Depend)
                and param.name not in bound_args.arguments
            ):
                depend = param.default
                dependency_func = depend.dependency
                if dependency_func is None:
                    raise ValueError(
                        f"Dependency for parameter '{param.name}' has no provider"
                    )

                bound_args.arguments[param.name] = await resolve_dependency(
                    dependency_func, ctx, cleanup_callbacks
                )

        try:
            if is_async_callable(handler):
                return await handler(**bound_args.arguments)
            else:
                return await run_in_threadpool(handler, **bound_args.arguments)
        finally:
            for cleanup in reversed(cleanup_callbacks):
                result = cleanup()
                if inspect.isawaitable(result):
                    await result

    return wrapped


def get_app_dependencies(router: "Router") -> List[Depend]:
    dependencies: List[Depend] = []
    if hasattr(router, "sub_routers"):
        for child_router in router.sub_routers.values():
            dependencies.extend(get_app_dependencies(child_router))  # type: ignore[arg-type]
    if hasattr(router, "dependencies"):
        dependencies.extend(router.dependencies)
    return dependencies
