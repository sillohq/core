from __future__ import annotations

import copy
import re
from typing import Any

from pydantic import BaseModel

from sillo.core.routing import Route, Router
from sillo.core.routing.grouping import Group
from sillo.openapi.models import Reference
from sillo.parameters import Cookie, Header, Query, SolvedParamDependency
from sillo.validation import ParameterLocation

from .config import OpenAPIConfig
from .models import (
    Cookie as OpenAPICookie,
)
from .models import (
    Header as OpenAPIHeader,
)
from .models import (
    MediaType,
    Operation,
    Parameter,
    PathItem,
    RequestBody,
    Schema,
)
from .models import (
    Path as OpenAPIPath,
)
from .models import (
    Query as OpenAPIQuery,
)
from .models import Response as OpenAPIResponse


class APIDocumentation:
    """Apidocumentation"""

    def __init__(
        self,
        config: OpenAPIConfig | None = None,
        swagger_url: str = "/docs",
        redoc_url: str = "/redoc",
        openapi_url: str = "/openapi.json",
    ):
        """Init"""
        self.config = config or OpenAPIConfig()
        self.swagger_url = swagger_url
        self.redoc_url = redoc_url
        self.openapi_url = openapi_url
        # Per-build memo of each route's compiled validators, so the parameter,
        # request-body, and response sections do not each re-collect them.
        self._validator_memo: dict[int, list[Any]] = {}

    def _docs_context(self, openapi_url: str | None = None):
        """Build a render context for the standalone HTML generators."""
        from sillo.openapi.ui import DocsContext

        info = self.config.openapi_spec.info
        return DocsContext(
            openapi_url=openapi_url or self.openapi_url,
            title=info.title,
            version=info.version,
            description=info.description or "",
            config=self.config,
        )

    def _generate_redoc_ui(self, openapi_url: str | None = None) -> str:
        """Generate ReDoc UI HTML.

        Retained for callers that render a page outside the application's own
        routes. The application itself mounts presenters from ``docs``, so
        this delegates rather than holding a second copy of the markup.
        """
        from sillo.openapi.ui import ReDoc

        return ReDoc().render(self._docs_context(openapi_url))

    def _generate_swagger_ui(self, openapi_url: str | None = None) -> str:
        """Generate Swagger UI HTML.

        Delegates to :class:`sillo.openapi.ui.Swagger`; see
        :meth:`_generate_redoc_ui`.
        """
        from sillo.openapi.ui import Swagger

        return Swagger().render(self._docs_context(openapi_url))

    def get_openapi(
        self, route: Route | Router | Group | Any, current_prefix: str = ""
    ) -> dict[str, Any]:
        """
        Recursively extract all Route with their full paths, automatically add them to OpenAPI spec,
        and return the complete OpenAPI specification as a dictionary.

        Building the document walks every route and generates JSON Schema for
        every model. It is called once, after routes are registered, and the
        result handed to the serving route — see ``silloApp.build_openapi``.
        """
        # Memo is scoped to a single build.
        self._validator_memo = {}

        # First, collect all routes with their full paths
        routes_with_paths = self._collect_routes_with_paths(route, current_prefix)

        # Process each route and add to OpenAPI spec
        for full_path, route_obj in routes_with_paths:
            if isinstance(route_obj, Route) and not getattr(
                route_obj, "exclude_from_schema", False
            ):
                self._add_route_to_openapi_spec(full_path, route_obj)

        # mode="json" so pydantic's rich types land as JSON-native values.
        # Several spec fields are typed AnyUrl — Contact.url, License.url,
        # ExternalDocumentation.url, OAuth refreshUrl — and the default
        # mode leaves those as AnyUrl objects, which json.dumps refuses.
        # Setting any one of them turned /openapi.json into a 500.
        spec = self.config.openapi_spec.model_dump(
            by_alias=True, exclude_none=True, mode="json"
        )
        self._validator_memo = {}
        return spec

    def _collect_routes_with_paths(
        self, route: Route | Router | Group | Any, current_prefix: str = ""
    ) -> list[tuple[str, Route]]:
        """
        Recursively collect all Route with their full paths, tracking prefixes through nested structures.
        """
        routes_with_paths: list[tuple[str, Route]] = []

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

    def _route_security(self, route: Any) -> Any:
        """The ``security`` to publish for one route.

        A route that declared ``security=`` explicitly, or whose gate named
        schemes, already settled this when it was registered. What is left is
        the bare ``useAuth()`` — a gate that rejects anonymous callers without
        naming a scheme. It has nothing to derive from on its own, but by the
        time the document is built the registered schemes are known, and "any
        of these" is exactly what such a gate enforces.

        Filling it in matters more than the overstated case it complements:
        a route documented as public that answers 401 sends a consumer
        looking for a bug in their client.

        Args:
            route: The route being described.

        Returns:
            The route's security requirements, or ``None`` when it is public
            or nothing is derivable.
        """
        if route.security is not None:
            return route.security

        gate = getattr(route, "auth", None)
        derive = getattr(gate, "security_requirements", None)
        if not callable(derive):
            return None

        return derive(available=list(self.config.security_schemes))

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path by ensuring it starts with / and removing duplicate slashes.
        """
        if not path:
            return "/"

        if not path.startswith("/"):
            path = "/" + path

        # Remove duplicate slashes but preserve parameter patterns like {id}
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
                tags=route.tags or [],  # ty:ignore[invalid-argument-type]
                parameters=parameters,  # ty:ignore[invalid-argument-type]
                requestBody=request_body_spec,
                security=self._route_security(route),
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
        Convert sillo path format to OpenAPI format.
        Example: /users/{id:int} -> /users/{id}
        """
        return re.sub(r"\{(\w+):[^}]+\}", r"{\1}", path)

    def _build_request_body_spec(self, route: Route, method: str) -> RequestBody | None:
        """
        Build request body specification for the route.

        Form and multipart bodies are documented from the models compiled to
        validate them. JSON bodies come from ``request_model``, which is the
        single way to declare one, so its schema is likewise the schema that is
        enforced at runtime.
        """
        marker_body = self._build_marker_body_spec(route)
        if marker_body is not None:
            return marker_body

        if route.request_model:
            if isinstance(route.request_model, dict):
                # Extract the first model from the dict for schema generation
                first_val = next(iter(route.request_model.values()), None)
                if isinstance(first_val, dict):
                    # Nested dict — use the first inner dict value
                    inner_first = next(iter(first_val.values()), None)
                    if inner_first is None or not isinstance(inner_first, type):
                        return None
                    if isinstance(inner_first, type) and issubclass(
                        inner_first, BaseModel
                    ):
                        schema_dict = inner_first.model_json_schema()
                    else:
                        return None
                elif isinstance(first_val, type) and issubclass(first_val, BaseModel):
                    schema_dict = first_val.model_json_schema()
                else:
                    return None
            elif isinstance(route.request_model, type) and issubclass(
                route.request_model, BaseModel
            ):
                schema_dict = route.request_model.model_json_schema()
            else:
                return None
            processed_schema = self._extract_and_add_nested_schemas(schema_dict)
            return RequestBody(
                content={
                    getattr(
                        route, "request_content_type", "application/json"
                    ): MediaType(spec=Schema(**processed_schema))
                }
            )
        elif method.upper() not in ["GET", "DELETE", "HEAD", "OPTIONS"]:
            # Default request body for methods that typically have bodies
            return RequestBody(
                content={
                    "application/json": MediaType(
                        spec=Schema(
                            example={"example": "This is an example request body"},
                            type="object",
                        )
                    )
                }
            )
        return None

    def _build_marker_body_spec(self, route: Route) -> RequestBody | None:
        """
        Build a request body spec from ``Form`` and ``File`` markers.

        JSON bodies are documented from ``request_model`` instead; this covers
        only form-encoded and multipart payloads, which have no ``request_model``
        equivalent.

        Args:
            route: The route whose compiled validators should be inspected.

        Returns:
            A ``RequestBody`` describing the declared form payload, or ``None``
            when the route declares no form markers and the caller should fall
            back to the ``request_model`` path.
        """
        for validator in self._collect_validators(route):
            if validator.form_spec is None:
                continue

            spec = validator.form_spec
            raw = spec.model.model_json_schema(
                by_alias=True, ref_template="#/$defs/{model}"
            )
            schema_dict = self._extract_and_add_nested_schemas(raw)
            properties = dict(schema_dict.get("properties") or {})
            # File markers bypass Pydantic, so they are absent from the
            # generated model and must be described explicitly.
            for alias in spec.passthrough.values():
                properties[alias] = {"type": "string", "format": "binary"}
            schema_dict["properties"] = properties
            content_type = (
                "multipart/form-data"
                if spec.passthrough
                else "application/x-www-form-urlencoded"
            )
            return RequestBody(
                required=True,
                content={content_type: MediaType(spec=Schema(**schema_dict))},
            )

        return None

    def _build_responses_spec(
        self, route: Route
    ) -> dict[str, OpenAPIResponse | Reference]:
        """
        Build response specifications for the route.

        A declared ``response_model`` takes precedence over the ``responses``
        mapping for the success status, because it is the schema the framework
        actually enforces on the way out.
        """
        responses_spec = {}

        response_model = getattr(route, "response_model", None)
        if response_model is not None:
            model = (
                list[response_model]  # type: ignore[valid-type]
                if getattr(route, "response_model_many", False)
                else response_model
            )
            responses_spec["200"] = self._create_response_spec(model, 200)
            if route.responses and isinstance(route.responses, dict):
                for status_code, extra in route.responses.items():
                    if str(status_code) != "200":
                        responses_spec[str(status_code)] = self._create_response_spec(
                            extra, status_code
                        )
            return responses_spec

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
                        spec=Schema(
                            example={"example": "This is an example response"},
                            type="object",
                        )
                    )
                },
            )

        return responses_spec

    def _extract_and_add_nested_schemas(self, schema: dict[str, Any]) -> dict[str, Any]:
        """
        Extract nested schemas from Pydantic's $defs and add them to components.schemas.
        Returns the cleaned schema with updated references.
        """
        # Deep copy: _update_schema_references rewrites in place, and a shallow
        # copy shares its nested dicts with the caller's schema.
        cleaned_schema = copy.deepcopy(schema)
        nested = cleaned_schema.pop("$defs", None)

        if nested:
            for def_name, def_schema in nested.items():
                processed_schema = self._extract_and_add_nested_schemas(def_schema)
                self.config.add_schema(def_name, Schema(**processed_schema))

        # Rewrite references whether or not this schema had its own $defs.
        # Pydantic flattens every definition to the top level, so a model
        # lifted out of a parent's $defs has no $defs key itself while still
        # referring to its siblings as "#/$defs/X". Returning it untouched
        # put those dangling references into components.schemas, where
        # ReDoc stops with "Invalid reference token: $defs" and Scalar
        # renders nothing at all.
        self._update_schema_references(cleaned_schema)

        return cleaned_schema

    def _update_schema_references(self, schema: Any) -> None:
        """
        Recursively update #/$defs/ references to #/components/schemas/ format.
        """
        if isinstance(schema, dict):
            # A discriminator's mapping holds references as plain strings
            # under arbitrary keys — {"email": "#/$defs/EmailNotification"} —
            # so the "$ref" test below never sees them. Left alone, the
            # oneOf branches point into components while the mapping that
            # selects between them points at $defs, and a viewer using the
            # discriminator resolves nothing.
            discriminator = schema.get("discriminator")
            if isinstance(discriminator, dict):
                mapping = discriminator.get("mapping")
                if isinstance(mapping, dict):
                    for name, target in mapping.items():
                        if isinstance(target, str) and target.startswith("#/$defs/"):
                            mapping[name] = target.replace(
                                "#/$defs/", "#/components/schemas/"
                            )

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

            # Generate example from model
            try:
                # Create empty instance to get defaults
                example = model.model_validate({}).model_dump(exclude_none=True)
            except Exception:
                example = None

            if example:
                processed_schema["example"] = example

            return OpenAPIResponse(
                description=f"Response for status code {status_code}",
                content={
                    "application/json": MediaType(spec=Schema(**processed_schema))
                },
            )
        elif hasattr(model, "__origin__") and model.__origin__ is list:
            # Handle List[Model]
            item_model = model.__args__[0]
            if issubclass(item_model, BaseModel):
                schema_dict = item_model.model_json_schema()
                processed_schema = self._extract_and_add_nested_schemas(schema_dict)

                # Generate example from model
                try:
                    example = item_model.model_validate({}).model_dump(
                        exclude_none=True
                    )
                except Exception:
                    example = None

                if example:
                    processed_schema["example"] = [example]

                return OpenAPIResponse(
                    description=f"Response for status code {status_code}",
                    content={
                        "application/json": MediaType(
                            spec=Schema(
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
                        spec=Schema(type="object", example=model)
                    )
                },
            )

        # Fallback
        return OpenAPIResponse(
            description=f"Response for status code {status_code}",
            content={"application/json": MediaType(spec=Schema(type="object"))},
        )

    def _collect_validators(self, route: Route) -> list[Any]:
        """
        Collect every compiled validator reachable from a route.

        Parameters may be declared on the handler itself or on any dependency
        it pulls in, and all of them belong in the route's documentation. The
        pre-computed validator plan already lists them, so this is a lookup
        rather than a tree walk.

        Results are memoized for the duration of one document build, since the
        parameter, request-body, and response sections all need the same list.

        Args:
            route: The route whose handler and dependency tree to inspect.

        Returns:
            A list of ``CompiledValidator`` instances, one per callable in the
            tree that declared validated parameters.
        """
        key = id(route)
        cached = self._validator_memo.get(key)
        if cached is not None:
            return cached

        validators = []
        dependants = [getattr(route, "dependant", None)]
        dependants.extend(getattr(route, "_router_dependants", []) or [])

        for dependant in dependants:
            if dependant is None:
                continue
            for _, validator in getattr(dependant, "_validator_plan", ()):
                validators.append(validator)

        self._validator_memo[key] = validators
        return validators

    def _build_parameters_spec(self, route: Route) -> list[Parameter]:
        """
        Build parameter specifications for the route.

        Parameters come from two sources that are merged here: markers left on
        the legacy extraction path, whose schema is inferred from their default
        value, and markers compiled into Pydantic models, whose schema is the
        very JSON Schema used to validate them. The latter is why documented
        constraints cannot drift from enforced ones.
        """
        parameters = []
        documented: set = set()

        # Path parameters declared with a ``Path`` marker carry a real schema;
        # collect them first so the generic fallback below skips them.
        path_schemas: dict[str, Schema] = {}
        for validator in self._collect_validators(route):
            for spec in validator.specs:
                if spec.location is not ParameterLocation.PATH:
                    continue
                for name, schema in self._schemas_for_spec(spec).items():
                    path_schemas[name] = schema

        for param_name in route.param_names:
            parameters.append(
                OpenAPIPath(
                    name=param_name,
                    required=True,
                    spec=path_schemas.get(param_name, Schema(type="string")),
                )
            )
            documented.add(("path", param_name))

        # Add Query, Header, Cookie parameters from resolved_params
        if hasattr(route, "resolved_params") and route.resolved_params:
            for param_dep in route.resolved_params:
                openapi_param = self._convert_param_dependency(param_dep)
                if openapi_param:
                    parameters.append(openapi_param)
                    documented.add((openapi_param.in_, openapi_param.name))

        for validator in self._collect_validators(route):
            for spec in validator.specs:
                if spec.location is ParameterLocation.PATH:
                    continue
                parameters.extend(self._convert_location_spec(spec, documented))

        # Add any additional parameters defined on the route
        if hasattr(route, "parameters") and route.parameters:
            parameters.extend(route.parameters)

        return parameters

    def _schemas_for_spec(self, spec: Any) -> dict[str, Schema]:
        """
        Extract a per-parameter JSON Schema from a compiled location model.

        Args:
            spec: The ``LocationSpec`` whose synthetic Pydantic model should be
                converted to JSON Schema.

        Returns:
            A mapping of wire parameter name to its ``Schema``. Nested model
            definitions are lifted into ``components.schemas`` on the way out.
        """
        raw = spec.model.model_json_schema(
            by_alias=True, ref_template="#/$defs/{model}"
        )
        processed = self._extract_and_add_nested_schemas(raw)
        return {
            name: Schema(**prop)
            for name, prop in (processed.get("properties") or {}).items()
        }

    def _convert_location_spec(self, spec: Any, documented: set) -> list[Parameter]:
        """
        Convert one compiled location model into OpenAPI parameter entries.

        Args:
            spec: The ``LocationSpec`` to convert.
            documented: Already-emitted ``(location, name)`` pairs, used to
                avoid documenting a parameter twice when it is declared on both
                a handler and one of its dependencies.

        Returns:
            A list of OpenAPI ``Parameter`` objects for this location.
        """
        param_class = {
            ParameterLocation.QUERY: OpenAPIQuery,
            ParameterLocation.HEADER: OpenAPIHeader,
            ParameterLocation.COOKIE: OpenAPICookie,
        }.get(spec.location)
        if param_class is None:
            return []

        raw = spec.model.model_json_schema(
            by_alias=True, ref_template="#/$defs/{model}"
        )
        processed = self._extract_and_add_nested_schemas(raw)
        required_names = set(processed.get("required") or [])

        out: list[Parameter] = []
        for name, prop in (processed.get("properties") or {}).items():
            key = (spec.location.value, name)
            if key in documented:
                continue
            documented.add(key)
            out.append(
                param_class(
                    name=name,
                    spec=Schema(**prop),
                    required=name in required_names,
                )
            )
        return out

    def _convert_param_dependency(
        self, param_dep: SolvedParamDependency
    ) -> Parameter | None:
        """
        Convert a SolvedParamDependency to an OpenAPI Parameter.
        """
        extractor = param_dep.extractor
        param_name = param_dep.param_name
        alias = extractor.alias or param_name

        # Build schema from default value
        schema = self._infer_schema_from_default(extractor.default)

        # Determine required status
        required = extractor.required
        if extractor.default is ...:
            required = True

        if isinstance(extractor, Query):
            return OpenAPIQuery(
                name=alias,
                spec=schema,
                required=required if required is not None else False,
            )
        elif isinstance(extractor, Header):
            return OpenAPIHeader(
                name=alias,
                spec=schema,
                required=required if required is not None else False,
            )
        elif isinstance(extractor, Cookie):
            return OpenAPICookie(
                name=alias,
                spec=schema,
                required=required if required is not None else False,
            )

        return None

    def _infer_schema_from_default(self, default: Any) -> Schema:
        """
        Infer OpenAPI schema type from a default value.
        """
        if default is ... or default is None:
            return Schema(type="string")

        type_map = {
            int: "integer",
            float: "number",
            bool: "boolean",
            str: "string",
        }

        type_default = type(default)
        if type_default in type_map:
            schema_type = type_map[type_default]
            schema = Schema(type=schema_type)

            # Add default value to schema
            if default is not None:
                schema.default = default

            # Add format for specific types
            if type_default is float:
                schema.format = "float"

            return schema

        # Handle list types
        if isinstance(default, list):
            return Schema(type="array", items=Schema(type="string"))

        # Fallback to string
        return Schema(type="string")
