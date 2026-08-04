# type: ignore[overide]
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.networks import AnyUrl

try:
    import email_validator  # noqa f401
    from pydantic import EmailStr
except ImportError:
    EmailStr = str  # ty:ignore[invalid-assignment]


from typing import Annotated, Literal

ParameterLocations = Literal["header", "path", "query", "cookie"]
PathParamStyles = Literal["simple", "label", "matrix"]
QueryParamStyles = Literal["form", "spaceDelimited", "pipeDelimited", "deepObject"]
HeaderParamStyles = Literal["simple"]
CookieParamStyles = Literal["form"]
FormDataStyles = QueryParamStyles

Extension = Union[Dict[str, Any], List[Any], str, int, float, bool, None]


class Contact(BaseModel):
    """Contact

    Returns:
        [description]

    Raises:
        [description]
    """

    name: Optional[str] = None
    url: Optional[AnyUrl] = None
    email: Optional[EmailStr] = None


class License(BaseModel):
    """License

    Returns:
        [description]

    Raises:
        [description]
    """

    name: str
    url: Optional[AnyUrl] = None


class Info(BaseModel):
    """Info

    Returns:
        [description]

    Raises:
        [description]
    """

    title: str
    version: str
    description: Optional[str] = None
    termsOfService: Optional[str] = None
    contact: Optional[Contact] = None
    license: Optional[License] = None

    model_config = ConfigDict(extra="allow")


# for extensions


class ServerVariable(BaseModel):
    """Servervariable

    Returns:
        [description]

    Raises:
        [description]
    """

    default: str
    enum: Optional[List[str]] = None
    description: Optional[str] = None


class Server(BaseModel):
    """Server

    Returns:
        [description]

    Raises:
        [description]
    """

    url: Union[AnyUrl, str]
    description: Optional[str] = None
    variables: Optional[Dict[str, ServerVariable]] = None


class Reference(BaseModel):
    """Reference

    Returns:
        [description]

    Raises:
        [description]
    """

    ref: Annotated[str, Field(alias="$ref")]


class Discriminator(BaseModel):
    """Discriminator

    Returns:
        [description]

    Raises:
        [description]
    """

    propertyName: str
    mapping: Optional[Dict[str, str]] = None


class XML(BaseModel):
    """Xml

    Returns:
        [description]

    Raises:
        [description]
    """

    name: Optional[str] = None
    namespace: Optional[str] = None
    prefix: Optional[str] = None
    attribute: Optional[bool] = None
    wrapped: Optional[bool] = None


class ExternalDocumentation(BaseModel):
    """Externaldocumentation

    Returns:
        [description]

    Raises:
        [description]
    """

    url: Optional[AnyUrl] = None
    description: Optional[str] = None


class Schema(BaseModel):
    """Schema

    Returns:
        [description]

    Raises:
        [description]
    """

    ref: Annotated[Optional[str], Field(alias="$ref")] = None
    title: Optional[str] = None
    multipleOf: Optional[float] = None
    maximum: Optional[float] = None
    exclusiveMaximum: Optional[float] = None
    minimum: Optional[float] = None
    exclusiveMinimum: Optional[float] = None
    maxLength: Annotated[Optional[int], Field(ge=0)] = None
    minLength: Annotated[Optional[int], Field(ge=0)] = None
    pattern: Optional[str] = None
    maxItems: Annotated[Optional[int], Field(ge=0)] = None
    minItems: Annotated[Optional[int], Field(ge=0)] = None
    uniqueItems: Optional[bool] = None
    maxProperties: Annotated[Optional[int], Field(ge=0)] = None
    minProperties: Annotated[Optional[int], Field(ge=0)] = None
    required: Optional[List[str]] = None
    enum: Optional[List[Any]] = None
    type: Optional[str] = None
    allOf: Optional[List[Schema]] = None
    oneOf: Optional[List[Schema]] = None
    anyOf: Optional[List[Schema]] = None
    not_: Annotated[Optional[Schema], Field(alias="not")] = None
    items: Optional[Union[Schema, List[Schema]]] = None
    properties: Optional[Dict[str, Schema]] = None
    additionalProperties: Optional[Union[Schema, Reference, bool]] = None
    description: Optional[str] = None
    format: Optional[str] = None
    default: Any = None
    nullable: Optional[bool] = None
    discriminator: Optional[Discriminator] = None
    readOnly: Optional[bool] = None
    writeOnly: Optional[bool] = None
    xml: Optional[XML] = None
    externalDocs: Optional[ExternalDocumentation] = None
    deprecated: Optional[bool] = None
    example: Optional[Any] = None
    # On a Schema Object, `examples` is an ARRAY of sample values — JSON
    # Schema draft 2020-12, carried into OpenAPI 3.1. The `{name: Example}`
    # mapping belongs to Parameter, MediaType and Header, not here.
    #
    # Typing it as the mapping made any pydantic model using
    # `Field(examples=[...])` fail validation, and because the whole
    # document is built at once, one such field turned /openapi.json into a
    # 422 for the entire API.
    examples: Optional[List[Any]] = None

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
    """Example

    Returns:
        [description]

    Raises:
        [description]
    """

    summary: Optional[str] = None
    description: Optional[str] = None
    value: Any = None
    external_value: Annotated[Optional[str], Field(alias="externalValue")] = None


Examples = Mapping[str, Union[Example, Reference]]


class Encoding(BaseModel):
    """Encoding

    Returns:
        [description]

    Raises:
        [description]
    """

    contentType: Optional[str] = None
    headers: Optional[Dict[str, Union[Header, Reference]]] = None
    style: Optional[str] = None
    explode: Optional[bool] = None


class MediaType(BaseModel):
    """Mediatype

    Returns:
        [description]

    Raises:
        [description]
    """

    spec: Optional[Union[Schema, Reference]] = Field(
        default=None, serialization_alias="schema"
    )
    examples: Optional[Examples] = None
    encoding: Optional[Dict[str, Encoding]] = None


class ParameterBase(BaseModel):
    """Parameterbase

    Returns:
        [description]

    Raises:
        [description]
    """

    description: Optional[str] = None
    required: Optional[bool] = None
    deprecated: Optional[bool] = None
    style: Optional[str] = None
    explode: Optional[bool] = None
    spec: Annotated[
        Optional[Union[Schema, Reference]],
        Field(default=None, serialization_alias="schema"),
    ] = None
    examples: Optional[Examples] = None
    content: Optional[Dict[str, MediaType]] = None


class ConcreteParameter(ParameterBase):
    """Concreteparameter

    Returns:
        [description]

    Raises:
        [description]
    """

    name: str
    in_: ParameterLocations = Field(alias="in")


class Header(ConcreteParameter):
    """Header

    Returns:
        [description]

    Raises:
        [description]
    """

    in_: Literal["header"] = Field(default="header", serialization_alias="in")
    style: HeaderParamStyles = "simple"
    explode: bool = False
    spec: Annotated[
        Optional[Union[Schema, Reference]],
        Field(default=None, serialization_alias="schema"),
    ] = Schema(type="string")


class Query(ConcreteParameter):
    """Query

    Returns:
        [description]

    Raises:
        [description]
    """

    in_: Literal["query"] = Field(
        default="query",
        serialization_alias="in",
    )
    style: QueryParamStyles = "form"
    explode: bool = True
    spec: Annotated[
        Optional[Union[Schema, Reference]],
        Field(default=None, serialization_alias="schema"),
    ] = Schema(type="string")


class Path(ConcreteParameter):
    """Path

    Returns:
        [description]

    Raises:
        [description]
    """

    in_: Literal["path"] = Field(default="path", alias="in")  # Explicit default
    style: PathParamStyles = "simple"
    explode: bool = False
    required: Literal[True] = True


class Cookie(ConcreteParameter):
    """Cookie

    Returns:
        [description]

    Raises:
        [description]
    """

    in_: Literal["cookie"] = "cookie"
    style: CookieParamStyles = "form"
    explode: bool = True


Parameter = Union[Query, Header, Cookie, Path]


class RequestBody(BaseModel):
    """Requestbody

    Returns:
        [description]

    Raises:
        [description]
    """

    content: Dict[str, MediaType]
    description: Optional[str] = None
    required: Optional[bool] = None


class Link(BaseModel):
    """Link

    Returns:
        [description]

    Raises:
        [description]
    """

    operationRef: Optional[str] = None
    operationId: Optional[str] = None
    parameters: Optional[Dict[str, str]] = None
    requestBody: Optional[str] = None
    description: Optional[str] = None
    server: Optional[Server] = None


class ResponseHeader(BaseModel):
    """Responseheader

    Returns:
        [description]

    Raises:
        [description]
    """

    description: Optional[str] = None
    deprecated: Optional[bool] = None
    style: HeaderParamStyles = "simple"
    explode: bool = False
    spec: Annotated[
        Optional[Union[Schema, Reference]],
        Field(default=None, serialization_alias="schema"),
    ] = None
    examples: Optional[Examples] = None
    content: Optional[Dict[str, MediaType]] = None


class Response(BaseModel):
    """Response

    Returns:
        [description]

    Raises:
        [description]
    """

    description: str
    headers: Optional[Dict[str, Union[ResponseHeader, Reference]]] = None
    content: Optional[Dict[str, MediaType]] = None
    links: Optional[Dict[str, Union[Link, Reference]]] = None


class Operation(BaseModel):
    """Operation

    Returns:
        [description]

    Raises:
        [description]
    """

    responses: Dict[str, Union[Response, Reference]]
    tags: Optional[List[str]] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    externalDocs: Optional[ExternalDocumentation] = None
    operationId: Optional[str] = None
    parameters: Optional[List[Union[ConcreteParameter, Reference]]] = None
    requestBody: Optional[Union[RequestBody, Reference]] = None
    # Using Any for Specification Extensions
    callbacks: Optional[Dict[str, Union[Dict[str, PathItem], Reference]]] = None
    deprecated: Optional[bool] = None
    security: Optional[List[Dict[str, List[str]]]] = None
    servers: Optional[List[Server]] = None

    model_config = ConfigDict(extra="allow")


# for extensions


class PathItem(BaseModel):
    """Pathitem

    Returns:
        [description]

    Raises:
        [description]
    """

    ref: Annotated[Optional[str], Field(alias="$ref")] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    get: Optional[Operation] = None
    put: Optional[Operation] = None
    post: Optional[Operation] = None
    delete: Optional[Operation] = None
    options: Optional[Operation] = None
    head: Optional[Operation] = None
    patch: Optional[Operation] = None
    trace: Optional[Operation] = None
    servers: Optional[List[Server]] = None
    parameters: Optional[List[Union[Parameter, Reference]]] = None

    model_config = ConfigDict(extra="allow")


# for extensions


SecuritySchemeName = Literal["apiKey", "http", "oauth2", "openIdConnect"]


class SecurityBase(BaseModel):
    """Securitybase

    Returns:
        [description]

    Raises:
        [description]
    """

    type: SecuritySchemeName
    description: Optional[str] = None


APIKeyLocation = Literal["query", "header", "cookie"]


class APIKey(SecurityBase):
    """Apikey

    Returns:
        [description]

    Raises:
        [description]
    """

    name: str
    in_: Annotated[APIKeyLocation, Field(alias="in")]
    type: Literal["apiKey"] = "apiKey"


class HTTPBase(SecurityBase):
    """Httpbase

    Returns:
        [description]

    Raises:
        [description]
    """

    scheme: str
    type: Literal["http"] = "http"


class HTTPBearer(HTTPBase):
    """Httpbearer

    Returns:
        [description]

    Raises:
        [description]
    """

    scheme: Literal["bearer"] = "bearer"
    bearerFormat: Optional[str] = None
    type: Literal["http"] = "http"


class OAuthFlow(BaseModel):
    """Oauthflow

    Returns:
        [description]

    Raises:
        [description]
    """

    refreshUrl: Optional[AnyUrl] = None
    scopes: Annotated[Optional[Mapping[str, str]], Field(default_factory=dict)]


class OAuthFlowImplicit(OAuthFlow):
    """Oauthflowimplicit

    Returns:
        [description]

    Raises:
        [description]
    """

    authorizationUrl: str


class OAuthFlowPassword(OAuthFlow):
    """Oauthflowpassword

    Returns:
        [description]

    Raises:
        [description]
    """

    tokenUrl: str


class OAuthFlowClientCredentials(OAuthFlow):
    """Oauthflowclientcredentials

    Returns:
        [description]

    Raises:
        [description]
    """

    tokenUrl: str


class OAuthFlowAuthorizationCode(OAuthFlow):
    """Oauthflowauthorizationcode

    Returns:
        [description]

    Raises:
        [description]
    """

    authorizationUrl: str
    tokenUrl: str


class OAuthFlows(BaseModel):
    """Oauthflows

    Returns:
        [description]

    Raises:
        [description]
    """

    implicit: Optional[OAuthFlowImplicit] = None
    password: Optional[OAuthFlowPassword] = None
    clientCredentials: Optional[OAuthFlowClientCredentials] = None
    authorizationCode: Optional[OAuthFlowAuthorizationCode] = None


class OAuth2(SecurityBase):
    """Oauth2

    Returns:
        [description]

    Raises:
        [description]
    """

    flows: OAuthFlows
    type: Literal["oauth2"] = "oauth2"


class OpenIdConnect(SecurityBase):
    """Openidconnect

    Returns:
        [description]

    Raises:
        [description]
    """

    openIdConnectUrl: str
    type: Literal["openIdConnect"] = "openIdConnect"


SecurityScheme = Union[APIKey, HTTPBase, OAuth2, OpenIdConnect, HTTPBearer]


class Components(BaseModel):
    """Components

    Returns:
        [description]

    Raises:
        [description]
    """

    schemas: Optional[Dict[str, Union[Schema, Reference]]] = None
    responses: Optional[Dict[str, Union[Response, Reference]]] = None
    parameters: Optional[Dict[str, Union[Parameter, Reference]]] = None
    examples: Optional[Examples] = None
    requestBodies: Optional[Dict[str, Union[RequestBody, Reference]]] = None
    headers: Optional[Dict[str, Union[Header, Reference]]] = None
    securitySchemes: Optional[Dict[str, Union[SecurityScheme, Reference]]] = None
    links: Optional[Dict[str, Union[Link, Reference]]] = None
    callbacks: Optional[Dict[str, Union[Dict[str, PathItem], Reference]]] = None


class Tag(BaseModel):
    """Tag

    Returns:
        [description]

    Raises:
        [description]
    """

    name: str
    description: Optional[str] = None
    externalDocs: Optional[ExternalDocumentation] = None


class OpenAPI(BaseModel):
    """Openapi

    Returns:
        [description]

    Raises:
        [description]
    """

    openapi: str
    info: Info
    paths: Annotated[Dict[str, Union[PathItem, Extension]], Field(default_factory=dict)]
    servers: Optional[List[Server]] = None
    # Using Any for Specification Extensions
    components: Components = Components()
    security: Optional[List[Dict[str, List[str]]]] = None
    tags: Optional[List[Tag]] = None
    externalDocs: Optional[ExternalDocumentation] = None


Schema.model_rebuild()
Operation.model_rebuild()
Encoding.model_rebuild()
