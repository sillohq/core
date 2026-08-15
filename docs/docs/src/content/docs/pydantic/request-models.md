---
title: Request Models
description: "Validating a JSON body with request_model: how the payload reaches your handler, what happens on failure, form bodies, and the models a real endpoint wants."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Request Models
  - tag: meta
    attrs:
      property: og:description
      content: request_model, body injection, and validating what a client sends.
---

```python
from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str
    published: bool = False


@app.post("/posts", request_model=PostCreate)
async def create_post(request, response, payload):
    post = await Post.create(**payload.model_dump())
    return response.json(post.to_dict(), status_code=201)
```

The body is read, parsed, validated and injected. By the time the handler runs,
`payload` is a valid `PostCreate`. There is no branch to write and no state in
which it is not.

## Why the body is on the decorator

Every other input has a marker: `Query`, `Path`, `Header`, `Cookie`, `Form`,
`File`. The JSON body is the one declared as `request_model=` instead.

A request has exactly one body, so there is exactly one place to declare it,
and putting it on the decorator is what lets the [OpenAPI
document](/pydantic/openapi/) describe the request without introspecting the
handler's annotations. Sillo handlers are not required to annotate anything.

## Where the payload lands

The rule is name-agnostic, so you can call the parameter whatever reads best:

```python
async def create_post(request, response, payload): ...
async def create_post(request, response, data): ...
async def create_post(request, response, post): ...
```

Sillo looks at the parameters **after** `request` and `response`, skips any
that something else fills (a `Depend`, a parameter marker, a path parameter)
and injects into the **first remaining one with no default**.

That means it composes with everything:

```python
@app.post("/teams/{team_id:int}/posts", request_model=PostCreate)
async def create_post(
    request, response, payload,
    team_id=Path(type=int),
    notify=Query(False, type=bool),
    db=Depend(get_db),
):
    ...
```

`team_id`, `notify` and `db` are all filled by other mechanisms, so `payload`
is unambiguous.

If no parameter qualifies, the payload is still available:

```python
@app.post("/posts", request_model=PostCreate)
async def create_post(request, response):
    payload = request.validated_data
```

## What happens on failure

A body that does not validate never reaches the handler. The client gets
[422 with every failure listed](/pydantic/errors/):

```json
{
  "detail": [
    {"loc": ["body", "title"], "msg": "String should have at least 1 character",
     "type": "string_too_short", "input": ""}
  ]
}
```

Malformed JSON is the same shape, with `type: "json_invalid"`.

## Writing the model

The mechanics above are the easy half. The model is where the work is.

```python
from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    slug: str = Field(pattern=r"^[a-z0-9-]+$", max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=10)
    published: bool = False
```

Five things that are easy to leave out and worth putting in:

- **`min_length=1` on required strings.** A bare `str` accepts `""`.
- **`max_length` on everything a client controls**, including lists. Without
  it, a request can carry a hundred thousand tags.
- **`extra="forbid"`**, so a client's typo is an error rather than silence.
- **`str_strip_whitespace=True`**, so `"  "` fails `min_length` as it should.
- **`frozen=True`**, so nothing downstream edits what the client sent.

Set the config once on a base and inherit. See
[Configuration](/pydantic/config/#defaults-worth-adopting).

## What the model must not do

A request model validates **shape**. It cannot validate facts about your
database, because [Pydantic validators are synchronous](/pydantic/validators/#where-validation-belongs):

```python
@field_validator("email")
@classmethod
def unique(cls, value):
    if await User.exists(email=value):     # not possible — no async validators
        ...
```

Uniqueness belongs to a database constraint plus a caught `IntegrityError`,
which the [exception handlers](/orm/exceptions/) already turn into a 409. That
is also the only version that does not race.

## Never accept what you do not mean to

```python
class PostCreate(BaseModel):
    title: str
    body: str
    author_id: int          # a client can now write on anyone's behalf
```

The model is the boundary. Anything it declares, a client can send.

Take identity from the request, not the body:

```python
post = await Post.create(**payload.model_dump(), author_id=request.user.id)
```

The same reasoning as [mass assignment](/orm/mass-assignment/) on the ORM side,
one layer out, and this is the layer where it is cheapest to get right.

## Partial updates

```python
class PostUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    published: bool | None = None


@app.patch("/posts/{id:int}", request_model=PostUpdate)
async def update_post(request, response, payload, id=Path(type=int)):
    post = await Post.get(id=id)
    await post.update_from_dict(payload.model_dump(exclude_unset=True))
    return response.json(post.to_dict())
```

`exclude_unset=True` is what makes this a real PATCH. Without it, a client
sending only `{"title": "New"}` also writes `body = None` (because that is the
model's default) and the endpoint silently destroys data.

Note that both parts are needed on each field: `| None` to allow null, `= None`
to make it optional. See [Types](/pydantic/types/#unions-and-optionals).

## Form and multipart bodies

`request_model` is for JSON. A form body uses markers instead:

```python
from sillo import File, Form


@app.post("/upload")
async def upload(
    request, response,
    title=Form(type=str, min_length=1),
    document=File(),
):
    ...
```

Declare the content type so the documentation is right:

```python
@app.post("/upload", request_content_type="multipart/form-data")
```

See [Parameters](/pydantic/parameters/#form-and-file).

## Documenting it

```python
class PostCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"title": "Async Python in practice", "body": "…", "tags": ["python"]}
            ]
        }
    )

    title: str = Field(description="Shown in listings.", min_length=1, max_length=200)
```

Both go straight into the [OpenAPI document](/pydantic/openapi/). A single
worked example at the model level is the most useful thing you can add to an
API reference, more useful than per-field descriptions, because it shows a
whole valid request.

## Testing

```python
def test_rejects_a_blank_title(client):
    response = client.post("/posts", json={"title": "", "body": "…"})
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(e["loc"] == ["body", "title"] for e in errors)


def test_ignores_a_client_supplied_author(client, auth_headers):
    response = client.post(
        "/posts",
        json={"title": "Hello", "body": "…", "author_id": 999},
        headers=auth_headers,
    )
    assert response.status_code == 422       # extra="forbid"
```

That second test is the one worth writing. It asserts that the boundary holds,
which is the thing a future refactor is most likely to break quietly.
