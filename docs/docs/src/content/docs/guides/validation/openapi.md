---
title: Generated documentation
description: Your OpenAPI schema is generated from the same models that validate the request, so what you publish is exactly what you enforce. Includes how Pydantic maps types and constraints to JSON Schema.
---

Parameter schemas, request bodies, and response schemas in `/openapi.json` are produced from the very models that perform validation. A constraint you declare is a constraint that appears in your docs **and** is enforced at runtime — there is no synchronization step to forget, and no way for the two to disagree.

##  Parameters

```python
page = Query(1, type=int, ge=1, le=99, description="Page number")
```

```json
{
  "name": "page",
  "in": "query",
  "required": false,
  "schema": {
    "type": "integer",
    "minimum": 1,
    "maximum": 99,
    "default": 1,
    "description": "Page number"
  }
}
```

##  How constraints map to JSON Schema

Pydantic translates each constraint to its JSON Schema equivalent, so tooling that reads your spec — client generators, mock servers, contract tests — sees the real rules:

| Constraint | JSON Schema |
| --- | --- |
| `ge` | `minimum` |
| `gt` | `exclusiveMinimum` |
| `le` | `maximum` |
| `lt` | `exclusiveMaximum` |
| `multiple_of` | `multipleOf` |
| `min_length` (string) | `minLength` |
| `max_length` (string) | `maxLength` |
| `min_length` (collection) | `minItems` |
| `max_length` (collection) | `maxItems` |
| `pattern` | `pattern` |

##  How types map to JSON Schema

| Python type | `type` | `format` |
| --- | --- | --- |
| `int` | `integer` | — |
| `float` | `number` | `double` |
| `str` | `string` | — |
| `bool` | `boolean` | — |
| `Decimal` | `string` | — |
| `datetime` | `string` | `date-time` |
| `date` | `string` | `date` |
| `time` | `string` | `time` |
| `timedelta` | `string` | `duration` |
| `UUID` | `string` | `uuid` |
| `EmailStr` | `string` | `email` |
| `HttpUrl` / `AnyUrl` | `string` | `uri` |
| `IPvAnyAddress` | `string` | `ipvanyaddress` |
| `bytes` | `string` | `binary` |
| `Enum` | `string` + `enum` | — |
| `Literal[...]` | `enum` | — |
| `list[T]` | `array` with `items` | — |
| `dict[str, T]` | `object` with `additionalProperties` | — |

An enum publishes its permitted values, so consumers see them without reading your source:

```python
class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"

order = Query(SortOrder.DESC, type=SortOrder)
```

```json
{"name": "order", "in": "query",
 "schema": {"$ref": "#/components/schemas/SortOrder", "default": "desc"}}
```

```json
"SortOrder": {"type": "string", "enum": ["asc", "desc"], "title": "SortOrder"}
```

A list parameter documents its element type:

```python
tags = Query([], type=List[str])
```

```json
{"name": "tags", "in": "query",
 "schema": {"type": "array", "items": {"type": "string"}}}
```

##  Path parameters

A `Path` marker types the segment. Without one, the parameter is still documented, just as a string:

```python
item_id = Path(type=int, ge=1)
```

```json
{"name": "item_id", "in": "path", "required": true,
 "schema": {"type": "integer", "minimum": 1}}
```

##  Request bodies

Generated from `request_model`, with nested models lifted into `components.schemas` and `$ref`s rewritten accordingly:

```python
class Address(BaseModel):
    city: str
    postcode: str

class UserCreate(BaseModel):
    name: str
    address: Address

@app.post("/users", request_model=UserCreate)
async def create_user(request, response): ...
```

```json
"requestBody": {
  "required": true,
  "content": {"application/json": {"schema": {
    "type": "object",
    "required": ["name", "address"],
    "properties": {
      "name":    {"type": "string", "title": "Name"},
      "address": {"$ref": "#/components/schemas/Address"}
    }}}}}
```

`Address` is emitted once under `components.schemas` and referenced wherever it appears, so a model used by twenty endpoints is documented once.

##  Enriching what gets published

###  Titles, descriptions, examples

On a marker:

```python
q = Query(type=str,
          title="Search",
          description="Full-text search across names and emails",
          example="widgets",
          deprecated=True)
```

On a model field:

```python
class UserCreate(BaseModel):
    email: str = Field(
        description="Primary contact address",
        examples=["ada@example.com"],
    )
```

Docstrings become schema descriptions automatically:

```python
class UserCreate(BaseModel):
    """A new user account."""
    name: str
```

```json
"UserCreate": {"description": "A new user account.", "type": "object", ...}
```

###  Whole-model examples

```python
from pydantic import ConfigDict

class UserCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "examples": [{"name": "Ada", "email": "ada@example.com", "age": 36}]
    })
    name: str
    email: str
    age: int
```

Swagger UI pre-fills its "Try it out" form from this, which makes an endpoint genuinely explorable rather than requiring the reader to invent valid input.

###  Arbitrary schema keys

Anything JSON Schema supports but Pydantic has no dedicated argument for:

```python
class Item(BaseModel):
    sku: str = Field(json_schema_extra={
        "x-internal-id": True,
        "externalDocs": {"url": "https://wiki.example.com/skus"},
    })
```

Vendor extensions (`x-…`) pass through untouched, which is how you feed hints to code generators and gateways.

##  Discriminated unions

A discriminated union produces a proper `oneOf` with a discriminator mapping, so generated clients build a correct tagged type rather than an opaque union:

```python
class Payment(BaseModel):
    method: Union[Card, BankTransfer] = Field(discriminator="kind")
```

```json
"method": {
  "oneOf": [{"$ref": "#/components/schemas/Card"},
            {"$ref": "#/components/schemas/BankTransfer"}],
  "discriminator": {"propertyName": "kind",
                    "mapping": {"card": "…/Card", "bank": "…/BankTransfer"}}}
```

##  Forms and uploads

Files are documented as binary, and the content type reflects whether any upload is declared:

```python
title  = Form(type=str)
avatar = File(...)
```

```json
"requestBody": {"required": true, "content": {
  "multipart/form-data": {"schema": {
    "properties": {
      "title":  {"type": "string"},
      "avatar": {"type": "string", "format": "binary"}
    }}}}}
```

With no `File` marker the content type is `application/x-www-form-urlencoded` instead.

##  Responses

`response_model` documents and enforces the success response. Other status codes come from `responses=`:

```python
@app.get("/users/{user_id}",
         response_model=UserOut,
         responses={404: {"description": "Not found"},
                    403: {"description": "Forbidden"}})
async def get_user(request, response): ...
```

The `200` entry is generated from `UserOut`; the others are passed through as written. With `response_model_many=True` the schema becomes an array of the model.

Computed fields are included, so a derived value is documented like any other:

```python
@computed_field
@property
def full_name(self) -> str: ...
```

The return annotation is what determines the published type, which is why it is required.

##  Dependencies are documented too

Parameters declared on an injected callable belong to every route that uses it, and appear there:

```python
def pagination(page=Query(1, type=int, ge=1), size=Query(20, type=int, le=100)):
    return {"page": page, "size": size}

@app.get("/items")
async def list_items(request, response, pager=Depend(pagination)):
    ...
```

`/items` documents both `page` and `size`. A parameter declared on both a handler and one of its dependencies is documented once.

##  Documentation-only parameters

For an input consumed by middleware, or one you read manually, `parameters=` adds an entry with no runtime behavior:

```python
from sillo.openapi.models import Query as OpenAPIQuery, Schema

@app.get("/items", parameters=[
    OpenAPIQuery(name="legacy_flag", spec=Schema(type="boolean"), required=False)
])
async def items(request, response):
    flag = request.query_params.get("legacy_flag")     # you extract it yourself
```

Nothing validates these — they are claims, not contracts, and the only entries in your document that can drift from reality. They are appended without deduplication, so declaring the same name via both a marker and `parameters=` produces two entries.

The same caveat applies to `responses=`: those schemas are decoration. Only `response_model` is enforced.

##  Excluding a route

```python
@app.get("/internal/metrics", exclude_from_schema=True)
async def metrics(request, response):
    ...
```

##  When the document is built

The OpenAPI document is generated **once**, at application startup, after all routes are registered, and the serialized result is stored. Serving `/openapi.json` writes that stored string — no generation and no encoding happens per request.

Because routes are registered before the application starts serving, there is nothing to invalidate.

If you need the document outside a request — to write it to a file in CI, or to generate a client:

```python
doc = app.build_openapi()      # the serialized JSON string

with open("openapi.json", "w") as f:
    f.write(doc)
```

Checking that file into version control turns an unintended API change into a visible diff during review.

##  The interactive UIs

Three routes are mounted by default, all configurable on `silloApp`:

| Path | What it serves |
| --- | --- |
| `/docs` | [Atlas](/guides/openapi/documentation-ui/#atlas) — sillo's own reference, with a request builder |
| `/redoc` | ReDoc — a cleaner read, no runner |
| `/openapi.json` | The raw document |

Swagger UI and Scalar ship too; which viewers are mounted is the `docs`
argument. See [Documentation UI](/guides/openapi/documentation-ui/).

```python
app = silloApp(
    title="My API",
    version="2.1.0",
    description="What this service does",
    swagger_docs="/docs",
    redoc_docs="/redoc",
    openapi_url="/openapi.json",
)
```


##  Why generated documentation is different in kind

Hand-written API documentation is a second source of truth, and second
sources of truth drift. Someone adds a constraint and forgets the docs;
someone renames a field in the docs to be clearer and the code disagrees;
a parameter is removed and its documentation outlives it by two years.

Generation removes the possibility. The schema published at `/openapi.json`
is built from the same models that reject requests, so a documented
constraint is an enforced constraint by construction. When they would
disagree, there is nothing to disagree — the constraint exists once.

The practical consequence is that improving your documentation means
improving your models. A `description=` on a marker, a `Field(examples=...)`
on a model, a `title=` on a parameter: each is a change to the thing that
validates, and each appears in the published schema without a second
edit.

##  What generated schemas cannot tell a client

Generation covers shape. Four things it does not cover, which is why an
OpenAPI document alone is not sufficient documentation.

**Semantics.** The schema says `amount_cents` is an integer. It does not
say the currency, whether it includes tax, or whether negative values
mean refunds. Put that in `description=`.

**Sequencing.** The schema documents each endpoint independently. It does
not say you must create a session before you can create an order. That
belongs in prose.

**Rate limits and quotas.** The schema does not know that you allow ten
requests a minute. Document limits alongside the auth scheme, since both
are things a client must handle before their first successful call.

**Failure semantics.** The schema lists status codes; it does not say
which are retryable. A client that retries a 409 forever is following
your documentation exactly.

The generated document is a contract for machines. The prose around it is
the contract for the humans writing the machines, and you need both.

##  Keeping the published schema reviewable

Two habits make an OpenAPI document useful rather than merely present.

**Check it into version control and diff it in review.** A change to a
model that silently changes the public schema is exactly the change that
should get a second pair of eyes. A committed `openapi.json` regenerated
in CI turns "did this break a client" into a visible diff.

**Fail the build on unintended changes.** If the regenerated schema
differs from the committed one and nobody updated the committed copy,
that is either an unintentional breaking change or an out-of-date file.
Both are worth stopping for.

```bash title="the check that catches accidental breakage"
python -c "import json; from myapp.app import app; print(json.dumps(app.openapi(), indent=2))" > /tmp/openapi.json
diff -u openapi.json /tmp/openapi.json
```

The same document drives client generation, contract testing, mock
servers, and the interactive UIs — so keeping it accurate pays off in
more places than documentation alone.


##  Documenting authentication so clients can actually call you

The single most common reason a generated document fails a new integrator
is that it describes every endpoint perfectly and never says how to
authenticate. A client can see `GET /orders` requires no parameters, try
it, and get a 401 with no idea what to do next.

Declare the security scheme once and attach it to the routes that need
it. That makes the "Authorize" button in the interactive UI work, which
turns the published document into something someone can succeed with in
their first five minutes rather than their first afternoon.

Document the token lifecycle in the scheme description — where to get
one, how long it lasts, how to refresh it, and what happens when it
expires. None of that is inferable from the endpoints, and all of it is
needed before the first successful request.

If different endpoints need different scopes, say so per endpoint. A
client that discovers scope requirements by trial and error will
over-request scopes, which is a security outcome you caused with a
documentation gap.

##  Examples do more work than descriptions

A field described as "the customer reference" is less useful than one
with `examples=["CUST-00042"]`. An example answers format, length,
casing, and prefix in one glance, and it flows into the interactive UI as
a prefilled value someone can actually send.

```python title="examples on fields and models"
class OrderCreate(BaseModel):
    customer_ref: str = Field(examples=["CUST-00042"])
    amount_cents: int = Field(ge=1, examples=[1999])

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"customer_ref": "CUST-00042", "amount_cents": 1999},
            ]
        }
    }
```

A whole-model example is worth more than field examples when fields
interact — when `type: "card"` implies `card_token` is required and
`type: "invoice"` implies it is not, one realistic example of each
communicates more than any prose.

Keep examples valid. An example that fails your own validation is worse
than none, because someone will copy it, and the interactive UI will send
it. If examples are checked in CI against the model that publishes them,
they stay honest.
