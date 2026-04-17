import contextvars
import inspect
from dataclasses import dataclass, field
from inspect import Parameter, signature
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from typing_extensions import Annotated, Doc
from nexios.parameters import resolve_param

if TYPE_CHECKING:
    from nexios import NexiosApp, Router
    from nexios.auth.users.base import BaseUser
    from nexios.http import Request
    from nexios.parameters import SolvedParamDependency


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
            Doc("""
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
                """),
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


@dataclass(frozen=True, slots=True)
class SolvedDependency:
    dependency: Callable[..., Any]
    parameter_name: Optional[str] = None
    nested_dependencies: Tuple["SolvedDependency", ...] = field(default_factory=tuple)
    context_parameter_names: Tuple[str, ...] = field(default_factory=tuple)
    param_dependencies: Tuple["SolvedParamDependency", ...] = field(
        default_factory=tuple
    )
    is_async_generator: bool = False
    is_generator: bool = False
    is_coroutine: bool = False


def _solve_depend(
    depend: Depend,
    parameter_name: Optional[str] = None,
) -> SolvedDependency:
    from nexios.parameters import ParameterExtractor

    dependency_func = depend.dependency
    if dependency_func is None:
        if parameter_name is None:
            raise ValueError("Dependency has no provider")
        raise ValueError(f"Dependency for parameter '{parameter_name}' has no provider")

    dependency_signature = signature(dependency_func)
    nested_dependencies: List[SolvedDependency] = []
    context_parameter_names: List[str] = []
    param_dependencies: List["SolvedParamDependency"] = []

    for param in dependency_signature.parameters.values():
        if param.default != Parameter.empty and isinstance(param.default, Depend):
            nested_dependencies.append(_solve_depend(param.default, param.name))
        elif param.default != Parameter.empty and isinstance(param.default, Context):
            context_parameter_names.append(param.name)
        elif param.default != Parameter.empty and isinstance(
            param.default, ParameterExtractor
        ):
            from nexios.parameters import Header, SolvedParamDependency

            extractor = param.default
            extractor.param_name = param.name
            if not extractor.alias:
                if isinstance(extractor, Header):
                    extractor.alias = extractor._convert_param_to_header_name(
                        param.name
                    )
                else:
                    extractor.alias = param.name

            param_dependencies.append(SolvedParamDependency(extractor, param.name))

    return SolvedDependency(
        dependency=dependency_func,
        parameter_name=parameter_name,
        nested_dependencies=tuple(nested_dependencies),
        context_parameter_names=tuple(context_parameter_names),
        param_dependencies=tuple(param_dependencies),
        is_async_generator=inspect.isasyncgenfunction(dependency_func),
        is_generator=inspect.isgeneratorfunction(dependency_func),
        is_coroutine=inspect.iscoroutinefunction(dependency_func),
    )


def solve_dependencies(dependencies: Sequence[Depend]) -> List[SolvedDependency]:
    return [_solve_depend(depend) for depend in dependencies]


def solve_handler_dependencies(handler: Callable[..., Any]) -> List[SolvedDependency]:
    handler_signature = signature(handler)
    solved_dependencies: List[SolvedDependency] = []

    for param in handler_signature.parameters.values():
        if param.default != Parameter.empty and isinstance(param.default, Depend):
            solved_dependencies.append(_solve_depend(param.default, param.name))

    return solved_dependencies


async def resolve_dependency(
    dependency: SolvedDependency,
    ctx: Optional[Context] = None,
    cleanup_callbacks: Optional[List[Callable[[], Any]]] = None,
) -> Any:
    if cleanup_callbacks is None:
        cleanup_callbacks = []

    dep_kwargs = {}

    for nested_dependency in dependency.nested_dependencies:
        if nested_dependency.parameter_name is None:
            raise ValueError("Nested dependency is missing a parameter name")
        dep_kwargs[nested_dependency.parameter_name] = await resolve_dependency(
            nested_dependency, ctx, cleanup_callbacks
        )

    for context_parameter_name in dependency.context_parameter_names:
        dep_kwargs[context_parameter_name] = ctx

    for param_dep in dependency.param_dependencies:
        dep_kwargs[param_dep.param_name] = await resolve_param(param_dep, ctx)

    func = dependency.dependency

    if dependency.is_async_generator:
        agen = func(**dep_kwargs)
        value = await agen.__anext__()
        cleanup_callbacks.append(lambda agen=agen: agen.aclose())
        return value
    elif dependency.is_generator:
        gen = func(**dep_kwargs)
        value = next(gen)
        cleanup_callbacks.append(lambda gen=gen: gen.close())
        return value
    elif dependency.is_coroutine:
        return await func(**dep_kwargs)
    else:
        return func(**dep_kwargs)
