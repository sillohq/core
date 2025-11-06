from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Type, Union
from uuid import uuid4

from pydantic import BaseModel

from nexios.http import Request, Response

from .config import OpenAPIConfig
from .models import (
    Components,
    ExternalDocumentation,
    MediaType,
    Operation,
    Parameter,
    PathItem,
    RequestBody,
)
from .models import Response as OpenAPIResponse
from .models import (
    Schema,
)

if TYPE_CHECKING:
    from nexios import NexiosApp


class APIDocumentation:
  

    def __init__(  # type: ignore
        self,
        app: Optional["NexiosApp"] = None,
        config: Optional[OpenAPIConfig] = None,
        swagger_url: str = "/docs",
        redoc_url: str = "/redoc",
        openapi_url: str = "/openapi.json",
    ):
        self.app = app
        self.config = config or OpenAPIConfig()
        self.swagger_url = swagger_url
        self.redoc_url = redoc_url
        self.openapi_url = openapi_url
        if app:
            self._setup_doc_routes()

    def _setup_doc_routes(self):
        """Set up routes for serving OpenAPI specification"""

        @self.app.get(self.openapi_url, exclude_from_schema=True)  # type:ignore
        async def serve_openapi(request: Request, response: Response):
            openapi_json = self.config.openapi_spec.model_dump(
                by_alias=True, exclude_none=True
            )
            return response.json(openapi_json)

        @self.app.get(self.swagger_url, exclude_from_schema=True)  # type:ignore
        async def swagger_ui(request: Request, response: Response):
            return response.html(self._generate_swagger_ui())

        @self.app.get(self.redoc_url, exclude_from_schema=True)  # type:ignore
        async def redoc_ui(request: Request, response: Response):
            return response.html(self._generate_redoc_ui())

    @classmethod
    def get_instance(cls):
        return cls._instance

    def _generate_redoc_ui(self) -> str:
        """Generate ReDoc UI HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{self.config.openapi_spec.info.title} - API Documentation</title>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                }}
            </style>
        </head>
        <body>
            <div id="redoc"></div>
            <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
            <script>
                Redoc.init('{self.openapi_url}', {{
                    scrollYOffset: 50
                }}, document.getElementById('redoc'))
            </script>
        </body>
        </html>
        """

    def _generate_swagger_ui(self) -> str:
        """Generate Swagger UI HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{self.config.openapi_spec.info.title} - Docs</title>
            <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@4.18.3/swagger-ui.css">
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@4/swagger-ui-bundle.js"></script>
            <script>
                window.onload = function() {{
                    SwaggerUIBundle({{
                        url: '{self.openapi_url}',
                        dom_id: '#swagger-ui',
                        presets: [
                            SwaggerUIBundle.presets.apis,
                            SwaggerUIBundle.SwaggerUIStandalonePreset
                        ],
                        layout: "BaseLayout"
                    }});
                }}
            </script>
        </body>
        </html>
        """

    def document_endpoint(
        self,
        path: str,
        method: str,
        summary: str = "",
        description: Optional[str] = None,
        parameters: Optional[List[Parameter]] = None,
        request_body: Optional[Type[BaseModel]] = None,
        request_content_type: str = "application/json",
        responses: Optional[Union[BaseModel, Dict[int, BaseModel]]] = None,
        tags: Optional[List[str]] = None,
        security: Optional[List[Dict[str, List[str]]]] = None,
        operation_id: Optional[str] = None,
        deprecated: bool = False,
        external_docs: Optional[ExternalDocumentation] = None,
    ):
        """
        Decorator to document API endpoints with OpenAPI specification

        :param path: URL path of the endpoint
        :param method: HTTP method (get, post, put, delete, etc.)
        :param summary: Short summary of the endpoint
        :param description: Detailed description of the endpoint
        :param parameters: List of parameters
        :param request_body: Pydantic model for request body
        :param responses: Response model(s)
        :param tags: Categorization tags for the endpoint
        :param security: Security requirements
        :param operation_id: Unique identifier for the operation
        :param deprecated: Whether the endpoint is deprecated
        :param external_docs: External documentation reference
        """

        def decorator(func: Callable[..., Any]):
            # Prepare request body specification
            request_body_spec = None

            if request_body:
                self.add_schema(request_body)
            if request_body:
                request_body_spec = RequestBody(
                    content={
                        request_content_type: MediaType(  # type:ignore
                            schema=Schema(  # type:ignore
                                **request_body.model_json_schema()
                            )
                        )
                    }
                )
            else:
                if method.upper() not in ["GET", "DELETE"]:
                    request_body_spec = RequestBody(
                        content={
                            request_content_type: MediaType(  # type:ignore
                                schema=Schema(
                                    example={
                                        "example": "This is an example request body"
                                    }
                                )  # type:ignore
                            )
                        }
                    )

            responses_spec = {}
            if responses:
                if isinstance(responses, type) and issubclass(responses, BaseModel):
                    responses_spec["200"] = OpenAPIResponse(
                        description="Successful Response",
                        content={
                            "application/json": MediaType(  # type:ignore
                                schema=Schema(  # type:ignore
                                    **responses.model_json_schema(),
                                )
                            )
                        },
                    )
                # Handle List[Model] case
                elif hasattr(responses, "__origin__") and responses.__origin__ is list:
                    item_model = responses.__args__[0]
                    if issubclass(item_model, BaseModel):
                        responses_spec["200"] = OpenAPIResponse(
                            description="Successful Response",
                            content={
                                "application/json": MediaType(  # type:ignore
                                    schema=Schema(  # type:ignore
                                        type="array",
                                        items=Schema(**item_model.model_json_schema()),
                                    )
                                )
                            },
                        )
                # Multiple responses case
                elif isinstance(responses, dict):
                    for status_code, model in responses.items():
                        # Handle direct model
                        if isinstance(model, type) and issubclass(model, BaseModel):
                            responses_spec[str(status_code)] = OpenAPIResponse(
                                description=f"Response for status code {status_code}",
                                content={
                                    "application/json": MediaType(  # type:ignore
                                        schema=Schema(  # type:ignore
                                            **model.model_json_schema()
                                        )
                                    )
                                },
                            )
                        # Handle List[Model]
                        elif hasattr(model, "__origin__") and model.__origin__ is list:
                            item_model = model.__args__[0]
                            if issubclass(item_model, BaseModel):
                                responses_spec[str(status_code)] = OpenAPIResponse(
                                    description=f"Response for status code {status_code}",
                                    content={
                                        "application/json": MediaType(  # type:ignore
                                            schema=Schema(  # type:ignore
                                                type="array",
                                                items=Schema(
                                                    **item_model.model_json_schema()
                                                ),
                                            )
                                        )
                                    },
                                )
            else:
                # Default response if no responses specified
                responses_spec["200"] = OpenAPIResponse(
                    description="Successful Response",
                    content={
                        "application/json": MediaType(  # type:ignore
                            schema=Schema(
                                example={"example": "This is an example response"},
                                type="object",
                            )  # type:ignore
                        )
                    },
                )

            if not responses_spec:
                responses_spec["200"] = OpenAPIResponse(
                    description="Successful Response",
                    content={
                        "application/json": MediaType(
                            schema=Schema(  # type:ignore
                                example={"example": "This is an example response"},
                                type="object",
                            )  # type:ignore
                        )
                    },
                )

            if responses:
                if isinstance(responses, type) and issubclass(responses, BaseModel):
                    self.add_schema(responses)
                elif hasattr(responses, "__origin__") and responses.__origin__ is list:
                    item_model = responses.__args__[0]
                    if issubclass(item_model, BaseModel):
                        self.add_schema(item_model)
                elif isinstance(responses, dict):
                    for model in responses.values():
                        if isinstance(model, type) and issubclass(model, BaseModel):
                            self.add_schema(model)
                        elif hasattr(model, "__origin__") and model.__origin__ is list:
                            item_model = model.__args__[0]
                            if issubclass(item_model, BaseModel):
                                self.add_schema(item_model)

            operation = Operation(
                summary=summary,
                description=description,
                responses=responses_spec,
                tags=tags,
                parameters=parameters or [],  # type:ignore
                requestBody=request_body_spec,
                security=security,
                operationId=operation_id or str(uuid4()),
                deprecated=deprecated,
                externalDocs=external_docs,
            )

            # Add operation to the OpenAPI specification
            if path not in self.config.openapi_spec.paths:
                self.config.openapi_spec.paths[path] = PathItem()

            setattr(self.config.openapi_spec.paths[path], method.lower(), operation)

            @wraps(func)
            async def wrapper(*args: list[Any], **kwargs: dict[str, Any]) -> Any:
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def add_schema(self, schema: Type[BaseModel]) -> None:
        """Add a schema to the OpenAPI components section

        Args:
            schema: A Pydantic model to be added to the components/schemas section
        """
        if not self.config.openapi_spec.components:
            self.config.openapi_spec.components = Components()

        if not self.config.openapi_spec.components.schemas:
            self.config.openapi_spec.components.schemas = {}

        self.config.openapi_spec.components.schemas[schema.__name__] = Schema(
            **schema.model_json_schema()
        )



