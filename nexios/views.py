import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Type

from typing_extensions import Annotated, Doc

from nexios.http import Request, Response
from nexios.routing import Route as Route
from nexios.types import MiddlewareType

logger = logging.getLogger(__name__)


class APIView:
    """
    Class-based view for organizing related HTTP endpoints in a single class.
    
    APIView provides a clean, object-oriented way to group related HTTP methods
    and share common functionality like middleware, error handling, and validation.
    Each HTTP method (GET, POST, PUT, DELETE, PATCH) can be implemented as a
    method on the class.
    
    Features:
    - Automatic HTTP method routing based on method names
    - Class-level middleware that applies to all methods
    - Custom error handlers for specific exceptions
    - Easy conversion to Route objects for registration
    - Method-level customization and validation
    
    Examples:
        1. Basic APIView:
        ```python
        class UserView(APIView):
            async def get(self, request: Request, response: Response):
                users = await get_all_users()
                return response.json(users)
            
            async def post(self, request: Request, response: Response):
                data = await request.json
                user = await create_user(data)
                return response.json(user, status=201)
        
        # Register with app
        app.add_route(UserView.as_route("/users"))
        ```
        
        2. APIView with middleware:
        ```python
        class ProtectedView(APIView):
            middleware = [auth_required, rate_limit(100)]
            
            async def get(self, request: Request, response: Response):
                return response.json({"message": "Protected resource"})
        
        app.add_route(ProtectedView.as_route("/protected"))
        ```
        
        3. APIView with error handling:
        ```python
        class UserView(APIView):
            error_handlers = {
                ValidationError: handle_validation_error,
                NotFoundError: handle_not_found,
            }
            
            async def get(self, request: Request, response: Response):
                user_id = request.path_params['id']
                user = await get_user(user_id)  # May raise NotFoundError
                return response.json(user)
        
        app.add_route(UserView.as_route("/users/{id}"))
        ```
        
        4. APIView with path parameters:
        ```python
        class UserDetailView(APIView):
            async def get(self, request: Request, response: Response):
                user_id = request.path_params['id']
                user = await User.get(user_id)
                return response.json(user.dict())
            
            async def put(self, request: Request, response: Response):
                user_id = request.path_params['id']
                data = await request.json
                user = await User.update(user_id, **data)
                return response.json(user.dict())
            
            async def delete(self, request: Request, response: Response):
                user_id = request.path_params['id']
                await User.delete(user_id)
                return response.status(204)
        
        app.add_route(UserDetailView.as_route("/users/{id}"))
        ```
    """

    middleware: Annotated[
        List[MiddlewareType], 
        Doc(
            """
            List of middleware functions to apply to all methods in this view.
            
            Middleware will be executed in the order specified for each request
            to any method in this view class.
            
            Example:
            ```python
            class ProtectedView(APIView):
                middleware = [
                    auth_required,
                    rate_limit(requests=100, window=3600),
                    log_requests
                ]
            ```
            """
        )
    ] = []

    error_handlers: Annotated[
        Dict[
            Type[Exception],
            Callable[[Request, Response, Exception], Coroutine[Any, Any, Response]],
        ],
        Doc(
            """
            Dictionary mapping exception types to handler functions.
            
            When an exception occurs during request processing, the framework
            will check if there's a registered handler for that exception type
            and call it instead of letting the exception propagate.
            
            Handler functions should accept (request, response, exception) and
            return a Response object.
            
            Example:
            ```python
            async def handle_validation_error(request, response, exc):
                return response.json(
                    {"error": "Validation failed", "details": str(exc)},
                    status=400
                )
            
            class UserView(APIView):
                error_handlers = {
                    ValidationError: handle_validation_error,
                    PermissionError: handle_permission_error,
                }
            ```
            """
        )
    ] = {}

    @classmethod
    def as_route(
        cls, 
        path: Annotated[
            str, 
            Doc(
                """
                URL path pattern for this view's endpoints.
                
                Supports path parameters using {param} syntax.
                All HTTP methods implemented in the view will be available at this path.
                
                Examples:
                - "/users" - static path
                - "/users/{id}" - path with parameter
                - "/files/{path:.*}" - path with regex parameter
                """
            )
        ], 
        methods: Annotated[
            Optional[List[str]], 
            Doc(
                """
                List of HTTP methods to enable for this view.
                
                If not specified, automatically detects methods based on
                implemented methods in the view class (get, post, put, delete, patch).
                
                Example: ["GET", "POST"] to only allow GET and POST requests
                """
            )
        ] = None, 
        **kwargs: Annotated[
            Dict[str, Any], 
            Doc(
                """
                Additional route configuration options.
                
                These are passed directly to the Route constructor and can include:
                - name: Route name for URL generation
                - summary: OpenAPI summary
                - description: OpenAPI description
                - tags: OpenAPI tags
                - responses: Response schemas
                - etc.
                """
            )
        ]
    ) -> Route:
        """
        Convert the APIView class into a Route object for registration.
        
        This class method creates a Route instance that can be registered with
        a Nexios app or router. It automatically sets up method dispatch and
        applies the view's middleware and error handlers.
        
        Returns:
            Route: A configured Route object ready for registration
            
        Examples:
            1. Basic registration:
            ```python
            class UserView(APIView):
                async def get(self, request, response):
                    return response.json({"users": []})
            
            app.add_route(UserView.as_route("/users"))
            ```
            
            2. With custom configuration:
            ```python
            route = UserView.as_route(
                "/users",
                name="user-list",
                tags=["Users"],
                summary="User management endpoints"
            )
            app.add_route(route)
            ```
            
            3. Limiting methods:
            ```python
            # Only allow GET and POST, even if PUT/DELETE are implemented
            route = UserView.as_route("/users", methods=["GET", "POST"])
            app.add_route(route)
            ```
        """
        if methods is None:
            methods = [
                name.lower()
                for name in {"get", "post", "put", "delete", "patch"}
                if name in cls.__dict__
            ]

        async def handler(
            req: Request, res: Response, **kwargs: Dict[str, Any]
        ) -> Response:
            instance = cls()
            return await instance.dispatch(req, res, **kwargs)

        return Route(
            path,
            handler,
            methods=methods,
            middleware=cls.middleware,
            **kwargs,  #  type: ignore
        )

    async def dispatch(
        self, req: Request, res: Response, **kwargs: Dict[str, Any]
    ) -> Response:
        """
        Dispatch the request to the appropriate handler method.
        """

        self.request = req
        self.res = res
        try:
            method = req.method.lower()
            handler = getattr(self, method, self.method_not_allowed)
            return await handler(req, res, **kwargs)
        except Exception as e:
            for exc_type, handler in self.error_handlers.items():
                if isinstance(e, exc_type):
                    return await handler(req, res, e)
            raise e

    async def method_not_allowed(self, req: Request, res: Response) -> Response:
        """
        Handle requests with unsupported HTTP methods.
        """
        return res.status(405).json({"error": "Method Not Allowed"})

    async def get(self, req: Request, res: Response) -> Response:
        """
        Handle GET requests.
        """
        return res.status(404).json({"error": "Not Found"})

    async def post(self, req: Request, res: Response) -> Response:
        """
        Handle POST requests.
        """
        return res.status(404).json({"error": "Not Found"})

    async def put(self, req: Request, res: Response) -> Response:
        """
        Handle PUT requests.
        """
        return res.status(404).json({"error": "Not Found"})

    async def delete(self, req: Request, res: Response) -> Response:
        """
        Handle DELETE requests.
        """
        return res.status(404).json({"error": "Not Found"})

    async def patch(self, req: Request, res: Response) -> Response:
        """
        Handle PATCH requests.
        """
        return res.status(404).json({"error": "Not Found"})
