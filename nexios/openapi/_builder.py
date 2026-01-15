from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel

from nexios.routing import Route, Router
from nexios.routing.grouping import Group

from .config import OpenAPIConfig
from .models import (
    MediaType,
    Operation,
    Parameter,
    Path,
    PathItem,
    RequestBody,
)
from .models import Response as OpenAPIResponse
from .models import (
    Schema,
)


class APIDocumentation:
    def __init__(  # type: ignore
        self,
        config: Optional[OpenAPIConfig] = None,
        swagger_url: str = "/docs",
        redoc_url: str = "/redoc",
        openapi_url: str = "/openapi.json",
    ):
        self.config = config or OpenAPIConfig()
        self.swagger_url = swagger_url
        self.redoc_url = redoc_url
        self.openapi_url = openapi_url

    def _generate_redoc_ui(self, openapi_url: str = None) -> str:
        """Generate ReDoc UI HTML"""
        url = openapi_url or self.openapi_url
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{self.config.openapi_spec.info.title} - API Documentation</title>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
            <link rel="icon" href="https://nexioslabs.com/logo.png" type="image/png">

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
                Redoc.init('{url}', {{
                    scrollYOffset: 50
                }}, document.getElementById('redoc'))
            </script>
        </body>
        </html>
        """

    def _generate_swagger_ui(self, openapi_url: str = None) -> str:
        """Generate Swagger UI HTML"""
        url = openapi_url or self.openapi_url
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{self.config.openapi_spec.info.title} - Docs</title>
            <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@4.18.3/swagger-ui.css">
            <link rel="icon" href="https://nexioslabs.com/logo.png" type="image/png">

        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@4/swagger-ui-bundle.js"></script>
            <script>
                window.onload = function() {{
                    SwaggerUIBundle({{
                        url: '{url}',
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

    def get_openapi(
        self, route: Union[Route, Router, Group, Any], current_prefix: str = ""
    ) -> Dict[str, Any]:
        """
        Recursively extract all Route with their full paths, automatically add them to OpenAPI spec,
        and return the complete OpenAPI specification as a dictionary.
        """
        # First, collect all routes with their full paths
        routes_with_paths = self._collect_routes_with_paths(route, current_prefix)

        # Process each route and add to OpenAPI spec
        for full_path, route_obj in routes_with_paths:
            if isinstance(route_obj, Route) and not getattr(
                route_obj, "exclude_from_schema", False
            ):
                self._add_route_to_openapi_spec(full_path, route_obj)

        # Return the complete OpenAPI spec as dictionary
        return self.config.openapi_spec.model_dump(by_alias=True, exclude_none=True)

    def _collect_routes_with_paths(
        self, route: Union[Route, Router, Group, Any], current_prefix: str = ""
    ) -> List[Tuple[str, Route]]:
        """
        Recursively collect all Route with their full paths, tracking prefixes through nested structures.
        """
        routes_with_paths: List[Tuple[str, Route]] = []

        if isinstance(route, Route):
            # Combine current prefix with route's raw_path
            full_path = self._normalize_path(current_prefix + route.raw_path)
            return [(full_path, route)]

        if isinstance(route, Router):
            # For routers, only add prefix if it's not already included in current_prefix
            # This handles the case where router is mounted via mount_router (which creates a Group)
            router_prefix = route.prefix or ""

            # Check if the router's prefix is already in the current prefix
            if router_prefix and current_prefix.endswith(router_prefix):
                new_prefix = current_prefix  # Don't add prefix again
            else:
                new_prefix = self._normalize_path(current_prefix + router_prefix)

            for sub_route in route.routes:
                routes_with_paths.extend(
                    self._collect_routes_with_paths(sub_route, new_prefix)
                )
            return routes_with_paths

        if isinstance(route, Group):
            # Build new prefix by adding group's path
            group_path = route.path or ""
            new_prefix = self._normalize_path(current_prefix + group_path)

            if hasattr(route, "_base_app") and isinstance(route._base_app, Router):
                # Don't add the router's prefix since it's already in the group path
                for sub_route in route._base_app.routes:
                    routes_with_paths.extend(
                        self._collect_routes_with_paths(sub_route, new_prefix)
                    )

            elif hasattr(route, "routes"):
                for sub_route in route.routes:
                    routes_with_paths.extend(
                        self._collect_routes_with_paths(sub_route, new_prefix)
                    )
            return routes_with_paths

        # Handle other route containers
        if hasattr(route, "routes"):
            for sub_route in route.routes:
                routes_with_paths.extend(
                    self._collect_routes_with_paths(sub_route, current_prefix)
                )

        return routes_with_paths

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path by ensuring it starts with / and removing duplicate slashes.
        """
        if not path:
            return "/"

        if not path.startswith("/"):
            path = "/" + path

        # Remove duplicate slashes but preserve parameter patterns like {id}
        import re

        path = re.sub(r"/+", "/", path)

        # Ensure we don't end with / unless it's the root
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        return path

    def _add_route_to_openapi_spec(self, full_path: str, route: Route) -> None:
        """
        Add a route to the OpenAPI specification without using the decorator pattern.
        """
        # Convert path parameters to OpenAPI format
        openapi_path = self._convert_path_to_openapi_format(full_path)

        # Process each HTTP method for this route
        for method in route.methods:
            # Prepare request body specification
            request_body_spec = self._build_request_body_spec(route, method)

            # Prepare response specifications
            responses_spec = self._build_responses_spec(route)

            # Prepare parameters (path, query, header)
            parameters = self._build_parameters_spec(route)

            # Create the operation object
            operation = Operation(
                summary=route.summary or f"{method.upper()} {openapi_path}",
                description=route.description,
                responses=responses_spec,
                tags=route.tags or [],
                parameters=parameters,
                requestBody=request_body_spec,
                security=route.security,
                operationId=route.operation_id
                or f"{method.lower()}_{openapi_path.replace('/', '_').replace('{', '').replace('}', '')}",
                deprecated=route.deprecated,
                externalDocs=getattr(route, "external_docs", None),
            )

            # Add operation to the OpenAPI specification
            if openapi_path not in self.config.openapi_spec.paths:
                self.config.openapi_spec.paths[openapi_path] = PathItem()

            setattr(
                self.config.openapi_spec.paths[openapi_path], method.lower(), operation
            )

    def _convert_path_to_openapi_format(self, path: str) -> str:
        """
        Convert Nexios path format to OpenAPI format.
        Example: /users/{id:int} -> /users/{id}
        """
        import re

        return re.sub(r"\{(\w+):[^}]+\}", r"{\1}", path)

    def _build_request_body_spec(
        self, route: Route, method: str
    ) -> Optional[RequestBody]:
        """
        Build request body specification for the route.
        """
        if route.request_model:
            schema_dict = route.request_model.model_json_schema()
            processed_schema = self._extract_and_add_nested_schemas(schema_dict)
            return RequestBody(
                content={
                    getattr(
                        route, "request_content_type", "application/json"
                    ): MediaType(schema=Schema(**processed_schema))
                }
            )
        elif method.upper() not in ["GET", "DELETE", "HEAD", "OPTIONS"]:
            # Default request body for methods that typically have bodies
            return RequestBody(
                content={
                    "application/json": MediaType(
                        schema=Schema(
                            example={"example": "This is an example request body"},
                            type="object",
                        )
                    )
                }
            )
        return None

    def _build_responses_spec(self, route: Route) -> Dict[str, OpenAPIResponse]:
        """
        Build response specifications for the route.
        """
        responses_spec = {}

        if route.responses:
            if isinstance(route.responses, dict):
                for status_code, model in route.responses.items():
                    responses_spec[str(status_code)] = self._create_response_spec(
                        model, status_code
                    )
            else:
                # Single response model
                responses_spec["200"] = self._create_response_spec(route.responses, 200)
        else:
            # Default response
            responses_spec["200"] = OpenAPIResponse(
                description="Successful Response",
                content={
                    "application/json": MediaType(
                        schema=Schema(
                            example={"example": "This is an example response"},
                            type="object",
                        )
                    )
                },
            )

        return responses_spec

    def _extract_and_add_nested_schemas(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract nested schemas from Pydantic's $defs and add them to components.schemas.
        Returns the cleaned schema with updated references.
        """
        if "$defs" not in schema:
            return schema

        # Extract all nested schemas and add them to components
        for def_name, def_schema in schema["$defs"].items():
            # Recursively process nested schemas
            processed_schema = self._extract_and_add_nested_schemas(def_schema)
            self.config.add_schema(def_name, Schema(**processed_schema))

        # Remove $defs from the schema
        cleaned_schema = schema.copy()
        del cleaned_schema["$defs"]

        # Update all references to use OpenAPI format
        self._update_schema_references(cleaned_schema)

        return cleaned_schema

    def _update_schema_references(self, schema: Any) -> None:
        """
        Recursively update #/$defs/ references to #/components/schemas/ format.
        """
        if isinstance(schema, dict):
            for key, value in schema.items():
                if (
                    key == "$ref"
                    and isinstance(value, str)
                    and value.startswith("#/$defs/")
                ):
                    schema[key] = value.replace("#/$defs/", "#/components/schemas/")
                else:
                    self._update_schema_references(value)
        elif isinstance(schema, list):
            for item in schema:
                self._update_schema_references(item)

    def _create_response_spec(self, model: Any, status_code: int) -> OpenAPIResponse:
        """
        Create a response specification from a model.
        """

        if isinstance(model, type) and issubclass(model, BaseModel):
            schema_dict = model.model_json_schema()
            processed_schema = self._extract_and_add_nested_schemas(schema_dict)
            return OpenAPIResponse(
                description=f"Response for status code {status_code}",
                content={
                    "application/json": MediaType(schema=Schema(**processed_schema))
                },
            )
        elif hasattr(model, "__origin__") and model.__origin__ is list:
            # Handle List[Model]
            item_model = model.__args__[0]
            if issubclass(item_model, BaseModel):
                schema_dict = item_model.model_json_schema()
                processed_schema = self._extract_and_add_nested_schemas(schema_dict)
                return OpenAPIResponse(
                    description=f"Response for status code {status_code}",
                    content={
                        "application/json": MediaType(
                            schema=Schema(
                                type="array",
                                items=Schema(**processed_schema),
                            )
                        )
                    },
                )
        elif isinstance(model, dict):
            # Handle dict response (like {"description": "Error message"})
            return OpenAPIResponse(
                description=model.get(
                    "description", f"Response for status code {status_code}"
                ),
                content={
                    "application/json": MediaType(
                        schema=Schema(type="object", example=model)
                    )
                },
            )

        # Fallback
        return OpenAPIResponse(
            description=f"Response for status code {status_code}",
            content={"application/json": MediaType(schema=Schema(type="object"))},
        )

    def _build_parameters_spec(self, route: Route) -> List[Parameter]:
        """
        Build parameter specifications for the route.
        """
        parameters = []

        # Add path parameters using the specific Path type
        for param_name in route.param_names:
            parameters.append(
                Path(name=param_name, required=True, schema=Schema(type="string"))
            )

        # Add any additional parameters defined on the route
        if hasattr(route, "parameters") and route.parameters:
            parameters.extend(route.parameters)

        return parameters

    def _add_response_schemas(self, responses: Any) -> None:
        """
        Add response model schemas to components.
        """
        if isinstance(responses, dict):
            for model in responses.values():
                if isinstance(model, type) and issubclass(model, BaseModel):
                    self.add_schema(model)
                elif hasattr(model, "__origin__") and model.__origin__ is list:
                    item_model = model.__args__[0]
                    if issubclass(item_model, BaseModel):
                        self.add_schema(item_model)
        elif isinstance(responses, type) and issubclass(responses, BaseModel):
            self.add_schema(responses)
