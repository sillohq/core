from typing import Dict, List, Optional, Type, Union

from pydantic import BaseModel

from .models import (
    Components,
    Contact,
    Example,
    ExternalDocumentation,
    Info,
    License,
    OpenAPI,
    Parameter,
)
from .models import Response as OpenAPIResponse
from .models import (
    Schema,
    SecurityScheme,
    Server,
    Tag,
)


class OpenAPIConfig:
    def __init__(
        self,
        title: str = "API Documentation",
        version: str = "1.0.0",
        description: str = "",
        servers: Optional[List[Server]] = [],
        contact: Optional[Contact] = None,
        license: Optional[License] = None,
        openapi_version: str = "3.0.0",
    ):
        self.openapi_spec = OpenAPI(
            openapi=openapi_version,
            info=Info(
                title=title,
                version=version,
                description=description,
                contact=contact,
                license=license,
            ),
            paths={},
            servers=servers ,
            components=Components(),
        )
        self.security_schemes: Dict[str, SecurityScheme] = {}

    def add_security_scheme(self, name: str, scheme: SecurityScheme):
        """Add a security scheme to the OpenAPI specification"""
        if not self.openapi_spec.components:
            self.openapi_spec.components = Components()

        if not self.openapi_spec.components.securitySchemes:
            self.openapi_spec.components.securitySchemes = {}

        self.openapi_spec.components.securitySchemes[name] = scheme

    def add_schema(self, name: str, schema: Union[Type[BaseModel], Schema]):
        """Add a schema to the OpenAPI components section"""
        if not self.openapi_spec.components:
            self.openapi_spec.components = Components()

        if not self.openapi_spec.components.schemas:
            self.openapi_spec.components.schemas = {}

        if isinstance(schema, type) and issubclass(schema, BaseModel):  # type: ignore
            self.openapi_spec.components.schemas[name] = Schema(
                **schema.model_json_schema()
            )
        else:
            self.openapi_spec.components.schemas[name] = schema

    def add_parameter(self, name: str, parameter: Parameter):
        """Add a reusable parameter to the OpenAPI components section"""
        if not self.openapi_spec.components:
            self.openapi_spec.components = Components()

        if not self.openapi_spec.components.parameters:
            self.openapi_spec.components.parameters = {}

        self.openapi_spec.components.parameters[name] = parameter

    def add_response(self, name: str, response: OpenAPIResponse):
        """Add a reusable response to the OpenAPI components section"""
        if not self.openapi_spec.components:
            self.openapi_spec.components = Components()

        if not self.openapi_spec.components.responses:
            self.openapi_spec.components.responses = {}

        self.openapi_spec.components.responses[name] = response

    def add_example(self, name: str, example: Example):
        """Add an example to the OpenAPI components section"""
        if not self.openapi_spec.components:
            self.openapi_spec.components = Components()

        if not self.openapi_spec.components.examples:
            self.openapi_spec.components.examples = {}

        self.openapi_spec.components.examples[name] = example  # type: ignore

    def add_tag(self, tag: Tag):
        """Add a tag to the OpenAPI specification"""
        if not self.openapi_spec.tags:
            self.openapi_spec.tags = []

        # Check if tag already exists
        existing_tags = [t.name for t in self.openapi_spec.tags]
        if tag.name not in existing_tags:
            self.openapi_spec.tags.append(tag)

    def add_server(self, server: Server):
        """Add a server to the OpenAPI specification"""
        if not self.openapi_spec.servers:
            self.openapi_spec.servers = []

        self.openapi_spec.servers.append(server)

    def set_external_docs(self, external_docs: ExternalDocumentation):
        """Set external documentation for the OpenAPI specification"""
        self.openapi_spec.externalDocs = external_docs

    def set_global_security(self, security: List[Dict[str, List[str]]]):
        """Set global security requirements for all operations"""
        self.openapi_spec.security = security

    def get_schema_ref(self, name: str) -> str:
        """Get a reference to a schema in the components section"""
        return f"#/components/schemas/{name}"

    def get_parameter_ref(self, name: str) -> str:
        """Get a reference to a parameter in the components section"""
        return f"#/components/parameters/{name}"

    def get_response_ref(self, name: str) -> str:
        """Get a reference to a response in the components section"""
        return f"#/components/responses/{name}"

    def get_example_ref(self, name: str) -> str:
        """Get a reference to an example in the components section"""
        return f"#/components/examples/{name}"
