from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.networks import AnyUrl

try:
    import email_validator  # noqa f401
    from pydantic import EmailStr
except ImportError:
    # Rebinding a name to a second type is what an optional-dependency
    # fallback *is*, so both checkers are told about it here, on the line
    # itself. This file used to open with `# type: ignore[overide]` instead,
    # which silenced nothing twice over: a module-level ignore cannot carry an
    # error code -- mypy rejects the form outright -- and `overide` is not one
    # of its codes in any case.
    EmailStr = str  # type: ignore[misc]  # ty:ignore[invalid-assignment]


from typing import Annotated, Literal

ParameterLocations = Literal["header", "path", "query", "cookie"]
PathParamStyles = Literal["simple", "label", "matrix"]
QueryParamStyles = Literal["form", "spaceDelimited", "pipeDelimited", "deepObject"]
HeaderParamStyles = Literal["simple"]
CookieParamStyles = Literal["form"]
FormDataStyles = QueryParamStyles

Extension = Union[dict[str, Any], list[Any], str, int, float, bool, None]


class Contact(BaseModel):
    """Contact"""

    name: str | None = None
    url: AnyUrl | None = None
    email: EmailStr | None = None


class License(BaseModel):
    """License"""

    name: str
    url: AnyUrl | None = None


class Info(BaseModel):
    """Info"""

    title: str
    version: str
    description: str | None = None
    termsOfService: str | None = None
    contact: Contact | None = None
    license: License | None = None

    model_config = ConfigDict(extra="allow")


# for extensions


class ServerVariable(BaseModel):
    """Servervariable"""

    default: str
    enum: list[str] | None = None
    description: str | None = None


class Server(BaseModel):
    """Server"""

    url: AnyUrl | str
    description: str | None = None
    variables: dict[str, ServerVariable] | None = None


class Reference(BaseModel):
    """Reference"""

    ref: Annotated[str, Field(alias="$ref")]


class Discriminator(BaseModel):
    """Discriminator"""

    propertyName: str
    mapping: dict[str, str] | None = None


class XML(BaseModel):
    """Xml"""

    name: str | None = None
    namespace: str | None = None
    prefix: str | None = None
    attribute: bool | None = None
    wrapped: bool | None = None


class ExternalDocumentation(BaseModel):
    """Externaldocumentation"""

    url: AnyUrl | None = None
    description: str | None = None


class Schema(BaseModel):
    """Schema"""

    ref: Annotated[str | None, Field(alias="$ref")] = None
    title: str | None = None
    multipleOf: float | None = None
    maximum: float | None = None
    exclusiveMaximum: float | None = None
    minimum: float | None = None
    exclusiveMinimum: float | None = None
    maxLength: Annotated[int | None, Field(ge=0)] = None
    minLength: Annotated[int | None, Field(ge=0)] = None
    pattern: str | None = None
    maxItems: Annotated[int | None, Field(ge=0)] = None
    minItems: Annotated[int | None, Field(ge=0)] = None
    uniqueItems: bool | None = None
    maxProperties: Annotated[int | None, Field(ge=0)] = None
    minProperties: Annotated[int | None, Field(ge=0)] = None
    required: list[str] | None = None
    enum: list[Any] | None = None
    type: str | None = None
    allOf: list[Schema] | None = None
    oneOf: list[Schema] | None = None
    anyOf: list[Schema] | None = None
    not_: Annotated[Schema | None, Field(alias="not")] = None
    items: Schema | list[Schema] | None = None
    properties: dict[str, Schema] | None = None
    additionalProperties: Schema | Reference | bool | None = None
    description: str | None = None
    format: str | None = None
    default: Any = None
    nullable: bool | None = None
    discriminator: Discriminator | None = None
    readOnly: bool | None = None
    writeOnly: bool | None = None
    xml: XML | None = None
    externalDocs: ExternalDocumentation | None = None
    deprecated: bool | None = None
    example: Any | None = None
    # On a Schema Object, `examples` is an ARRAY of sample values — JSON
    # Schema draft 2020-12, carried into OpenAPI 3.1. The `{name: Example}`
    # mapping belongs to Parameter, MediaType and Header, not here.
    #
    # Typing it as the mapping made any pydantic model using
    # `Field(examples=[...])` fail validation, and because the whole
    # document is built at once, one such field turned /openapi.json into a
    # 422 for the entire API.
    examples: list[Any] | None = None

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, v, info):
        """Validate type field - if anyOf/oneOf/allOf is present, type should not be set"""
        if v is not None:
            return v

        # Only set default type "object" if no composition keywords are present
        data = info.data if hasattr(info, "data") else {}
        has_composition = any(
            data.get(key) is not None for key in ["anyOf", "oneOf", "allOf"]
        )

        if not has_composition:
            return "object"

        return None


class Example(BaseModel):
    """Example"""

    summary: str | None = None
    description: str | None = None
    value: Any = None
    external_value: Annotated[str | None, Field(alias="externalValue")] = None


Examples = Mapping[str, Example | Reference]


class Encoding(BaseModel):
    """Encoding"""

    contentType: str | None = None
    headers: dict[str, Header | Reference] | None = None
    style: str | None = None
    explode: bool | None = None


class MediaType(BaseModel):
    """Mediatype"""

    spec: Schema | Reference | None = Field(default=None, serialization_alias="schema")
    examples: Examples | None = None
    encoding: dict[str, Encoding] | None = None


class ParameterBase(BaseModel):
    """Parameterbase"""

    description: str | None = None
    required: bool | None = None
    deprecated: bool | None = None
    style: str | None = None
    explode: bool | None = None
    spec: Annotated[
        Schema | Reference | None,
        Field(default=None, serialization_alias="schema"),
    ] = None
    examples: Examples | None = None
    content: dict[str, MediaType] | None = None


class ConcreteParameter(ParameterBase):
    """Concreteparameter"""

    name: str
    in_: ParameterLocations = Field(alias="in")


class Header(ConcreteParameter):
    """Header"""

    in_: Literal["header"] = Field(default="header", serialization_alias="in")
    style: HeaderParamStyles = "simple"
    explode: bool = False
    spec: Annotated[
        Schema | Reference | None,
        Field(default=None, serialization_alias="schema"),
    ] = Schema(type="string")


class Query(ConcreteParameter):
    """Query"""

    in_: Literal["query"] = Field(
        default="query",
        serialization_alias="in",
    )
    style: QueryParamStyles = "form"
    explode: bool = True
    spec: Annotated[
        Schema | Reference | None,
        Field(default=None, serialization_alias="schema"),
    ] = Schema(type="string")


class Path(ConcreteParameter):
    """Path"""

    in_: Literal["path"] = Field(default="path", alias="in")  # Explicit default
    style: PathParamStyles = "simple"
    explode: bool = False
    required: Literal[True] = True


class Cookie(ConcreteParameter):
    """Cookie"""

    in_: Literal["cookie"] = "cookie"
    style: CookieParamStyles = "form"
    explode: bool = True


Parameter = Union[Query, Header, Cookie, Path]


class RequestBody(BaseModel):
    """Requestbody"""

    content: dict[str, MediaType]
    description: str | None = None
    required: bool | None = None


class Link(BaseModel):
    """Link"""

    operationRef: str | None = None
    operationId: str | None = None
    parameters: dict[str, str] | None = None
    requestBody: str | None = None
    description: str | None = None
    server: Server | None = None


class ResponseHeader(BaseModel):
    """Responseheader"""

    description: str | None = None
    deprecated: bool | None = None
    style: HeaderParamStyles = "simple"
    explode: bool = False
    spec: Annotated[
        Schema | Reference | None,
        Field(default=None, serialization_alias="schema"),
    ] = None
    examples: Examples | None = None
    content: dict[str, MediaType] | None = None


class Response(BaseModel):
    """Response"""

    description: str
    headers: dict[str, ResponseHeader | Reference] | None = None
    content: dict[str, MediaType] | None = None
    links: dict[str, Link | Reference] | None = None


class Operation(BaseModel):
    """Operation"""

    responses: dict[str, Response | Reference]
    tags: list[str] | None = None
    summary: str | None = None
    description: str | None = None
    externalDocs: ExternalDocumentation | None = None
    operationId: str | None = None
    parameters: list[ConcreteParameter | Reference] | None = None
    requestBody: RequestBody | Reference | None = None
    # Using Any for Specification Extensions
    callbacks: dict[str, dict[str, PathItem] | Reference] | None = None
    deprecated: bool | None = None
    security: list[dict[str, list[str]]] | None = None
    servers: list[Server] | None = None

    model_config = ConfigDict(extra="allow")


# for extensions


class PathItem(BaseModel):
    """Pathitem"""

    ref: Annotated[str | None, Field(alias="$ref")] = None
    summary: str | None = None
    description: str | None = None
    get: Operation | None = None
    put: Operation | None = None
    post: Operation | None = None
    delete: Operation | None = None
    options: Operation | None = None
    head: Operation | None = None
    patch: Operation | None = None
    trace: Operation | None = None
    servers: list[Server] | None = None
    parameters: list[Parameter | Reference] | None = None

    model_config = ConfigDict(extra="allow")


# for extensions


SecuritySchemeName = Literal["apiKey", "http", "oauth2", "openIdConnect"]


class SecurityBase(BaseModel):
    """Securitybase"""

    type: SecuritySchemeName
    description: str | None = None


APIKeyLocation = Literal["query", "header", "cookie"]


class APIKey(SecurityBase):
    """Apikey"""

    name: str
    in_: Annotated[APIKeyLocation, Field(alias="in")]
    type: Literal["apiKey"] = "apiKey"


class HTTPBase(SecurityBase):
    """Httpbase"""

    scheme: str
    type: Literal["http"] = "http"


class HTTPBearer(HTTPBase):
    """Httpbearer"""

    scheme: Literal["bearer"] = "bearer"
    bearerFormat: str | None = None
    type: Literal["http"] = "http"


class OAuthFlow(BaseModel):
    """Oauthflow"""

    refreshUrl: AnyUrl | None = None
    scopes: Annotated[Mapping[str, str] | None, Field(default_factory=dict)]


class OAuthFlowImplicit(OAuthFlow):
    """Oauthflowimplicit"""

    authorizationUrl: str


class OAuthFlowPassword(OAuthFlow):
    """Oauthflowpassword"""

    tokenUrl: str


class OAuthFlowClientCredentials(OAuthFlow):
    """Oauthflowclientcredentials"""

    tokenUrl: str


class OAuthFlowAuthorizationCode(OAuthFlow):
    """Oauthflowauthorizationcode"""

    authorizationUrl: str
    tokenUrl: str


class OAuthFlows(BaseModel):
    """Oauthflows"""

    implicit: OAuthFlowImplicit | None = None
    password: OAuthFlowPassword | None = None
    clientCredentials: OAuthFlowClientCredentials | None = None
    authorizationCode: OAuthFlowAuthorizationCode | None = None


class OAuth2(SecurityBase):
    """Oauth2"""

    flows: OAuthFlows
    type: Literal["oauth2"] = "oauth2"


class OpenIdConnect(SecurityBase):
    """Openidconnect"""

    openIdConnectUrl: str
    type: Literal["openIdConnect"] = "openIdConnect"


SecurityScheme = Union[APIKey, HTTPBase, OAuth2, OpenIdConnect, HTTPBearer]


class Components(BaseModel):
    """Components"""

    schemas: dict[str, Schema | Reference] | None = None
    responses: dict[str, Response | Reference] | None = None
    parameters: dict[str, Parameter | Reference] | None = None
    examples: Examples | None = None
    requestBodies: dict[str, RequestBody | Reference] | None = None
    headers: dict[str, Header | Reference] | None = None
    securitySchemes: dict[str, SecurityScheme | Reference] | None = None
    links: dict[str, Link | Reference] | None = None
    callbacks: dict[str, dict[str, PathItem] | Reference] | None = None


class Tag(BaseModel):
    """Tag"""

    name: str
    description: str | None = None
    externalDocs: ExternalDocumentation | None = None


class OpenAPI(BaseModel):
    """Openapi"""

    openapi: str
    info: Info
    paths: Annotated[dict[str, PathItem | Extension], Field(default_factory=dict)]
    servers: list[Server] | None = None
    # Using Any for Specification Extensions
    components: Components = Components()
    security: list[dict[str, list[str]]] | None = None
    tags: list[Tag] | None = None
    externalDocs: ExternalDocumentation | None = None


Schema.model_rebuild()
Operation.model_rebuild()
Encoding.model_rebuild()
