---
title: Types
description: "What Pydantic understands (scalars, collections, dates, enums, unions and the library's own constrained types) plus the coercion rules and strict mode."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic Types in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: Scalars, collections, dates, enums, unions, special types and coercion.
---

An annotation is a contract about the value **after** validation. Pydantic
coerces where it can and rejects where it cannot.

## Scalars

| Annotation | Accepts | Notes |
| --- | --- | --- |
| `str` | strings | Not `int`; numbers are not coerced to text |
| `int` | ints, whole floats, numeric strings | `1.5` is rejected, `1.0` is not |
| `float` | numbers, numeric strings | |
| `bool` | bools, `0`/`1`, `"true"`, `"yes"`, `"on"`, `"n"`, … | |
| `bytes` | bytes, strings (UTF-8 encoded) | |
| `Decimal` | numbers and strings | The right type for money |
| `None` | `None` only | Almost always part of a union |

```python
class Order(BaseModel):
    quantity: int
    total: Decimal
    paid: bool
```

**Use `Decimal` for money.** `float` is binary floating point. `0.1 + 0.2` is
not `0.3`, and an invoice built on it will not add up. It pairs with
[`DecimalField`](/v1.0/orm/field-reference/#numbers) on the ORM side.

## Collections

```python
tags: list[str]
scores: dict[str, int]
coordinates: tuple[float, float]
unique_ids: set[int]
```

The parameter is validated too, item by item. `list[str]` rejects a list
containing an `int`, naming the index that failed.

`list` unparameterised accepts anything and validates nothing. It is almost
never what you want in an API model, because it becomes an untyped array in
your [OpenAPI schema](/v1.0/pydantic/openapi/).

:::caution[A mutable default is shared]
```python
tags: list[str] = []                          # dangerous elsewhere in Python
```

Pydantic deep-copies field defaults per instance, so this is actually safe
here: unlike a plain Python default argument, and unlike an [ORM field
default](/v1.0/orm/field-reference/#arguments-every-field-takes), where it is a real
bug.

`Field(default_factory=list)` is still clearer, and is required when the
default is expensive or must be genuinely fresh.
:::

## Dates and times

```python
from datetime import datetime, date, time, timedelta

published_at: datetime
birth_date: date
duration: timedelta
```

`datetime` accepts an ISO 8601 string, a `datetime`, or a Unix timestamp as
int or float. `"2026-08-15T10:30:00Z"` parses, and so does `1786000000`.

`timedelta` accepts a number of seconds or an ISO 8601 duration.

:::note[Naive and aware are both accepted]
`datetime` allows both. A string without an offset produces a naive datetime,
and comparing it with an aware one raises `TypeError`, usually much later,
somewhere unrelated.

Pin it when the value is going into a database:

```python
from pydantic import AwareDatetime

published_at: AwareDatetime
```

Which rejects an input with no timezone rather than accepting one you cannot
compare. `NaiveDatetime` is the opposite constraint.
:::

## UUID, paths, enums

```python
from enum import Enum
from pathlib import Path
from uuid import UUID


class Status(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class PostCreate(BaseModel):
    id: UUID
    status: Status
    attachment: Path
```

An enum annotation accepts a member or its value, and produces a member. In
OpenAPI it becomes an `enum` with the allowed values listed, so the
documentation shows exactly what a client may send.

Inheriting `str` makes the member JSON-serialisable and comparable to a plain
string, worth doing for anything that crosses the wire. It also lines up with
[`CharEnumField`](/v1.0/orm/field-reference/#enums) on the model.

## `Literal`

```python
from typing import Literal

sort: Literal["created_at", "title", "views"] = "created_at"
```

An inline enumeration. For a small fixed set that does not deserve a class (a
sort key, a mode flag) this is the shortest way to get validation *and* a
documented list of options.

It is also how you replace v1's `const=`.

## Unions and optionals

```python
author_id: int | None = None
identifier: int | str
```

**`| None` does not make a field optional in v2.** It allows `None` as a value;
the field is still required unless it has a default. This is the single most
common v1-to-v2 surprise. See [Models](/v1.0/pydantic/models/#v1-to-v2).

```python
x: int | None            # required, may be null
x: int | None = None     # optional, defaults to null
```

For a union of several models, use a [discriminated
union](/v1.0/pydantic/nested/#discriminated-unions). It is faster and produces far
better errors than trying each in turn.

## Pydantic's own types

```python
from pydantic import (
    EmailStr, HttpUrl, AnyUrl, IPvAnyAddress, Json, SecretStr, SecretBytes,
    PositiveInt, NonNegativeInt, NegativeInt, PositiveFloat,
    conint, confloat, constr, condecimal, conlist,
)
```

| Type | Validates |
| --- | --- |
| `EmailStr` | An email address. Needs `email-validator`. |
| `HttpUrl` | An `http`/`https` URL, and normalises it |
| `AnyUrl` | Any URL with a scheme |
| `IPvAnyAddress` | An IPv4 or IPv6 address |
| `Json` | A string containing JSON, parsed |
| `SecretStr` | A string that does not appear in `repr` or logs |
| `PositiveInt`, `NonNegativeInt`, … | Sign constraints |

```python
class SignUp(BaseModel):
    email: EmailStr
    website: HttpUrl | None = None
    password: SecretStr
```

`EmailStr` needs a dependency the starters already carry:

```bash
uv add email-validator
```

`SecretStr` is worth reaching for on anything sensitive. It keeps the value out
of `repr()`, out of tracebacks, and out of a `model_dump()` unless you ask,
which is the difference between a password appearing in an error report and
not.

```python
password.get_secret_value()      # explicit, and greppable
```

The `con*` constructors are the older way to attach constraints. Prefer
[`Field()`](/v1.0/pydantic/fields/) or `Annotated`, which read better and compose:

```python
from typing import Annotated
from annotated_types import Len

tags: Annotated[list[str], Len(min_length=1, max_length=10)]
```

## Coercion

Pydantic v2 is in **lax** mode by default: it converts where the conversion is
unambiguous and safe.

```python
class M(BaseModel):
    n: int
    flag: bool


M(n="42", flag="yes")        # n=42, flag=True
M(n="abc")                   # ValidationError
M(n=1.5)                     # ValidationError — would lose information
M(n=1.0)                     # n=1 — lossless
```

That behaviour is what makes query parameters work at all: everything arriving
in a URL is a string, and `Query(type=int)` needs `"5"` to become `5`.

### Strict mode

To turn coercion off:

```python
from pydantic import ConfigDict


class M(BaseModel):
    model_config = ConfigDict(strict=True)

    n: int


M(n="42")      # ValidationError — a string is not an int
```

Per field:

```python
from pydantic import Field

n: int = Field(strict=True)
```

Or on a [parameter marker](/v1.0/pydantic/parameters/):

```python
count = Query(type=int, strict=True)
```

Strict is right for a JSON body, where the client controls the types and
sending `"42"` for a number is a client bug worth surfacing. It is wrong for
query parameters, headers and form fields, which are strings by definition.
Strict mode there rejects every input.

## Any and no annotation

```python
metadata: Any                 # accepted unvalidated
```

`Any` accepts anything and validates nothing. Occasionally correct (a webhook
payload you store verbatim) and usually a sign that the shape has not been
decided yet.

In OpenAPI it becomes an empty schema, so a client generator produces
`unknown`. If the shape is known, declare it.

## Custom types

For a value with its own rules, `Annotated` plus a validator:

```python
from typing import Annotated
from pydantic import AfterValidator


def check_slug(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", value):
        raise ValueError("must be lowercase letters, digits and hyphens")
    return value


Slug = Annotated[str, AfterValidator(check_slug)]


class PostCreate(BaseModel):
    slug: Slug
```

`Slug` is now reusable across every model, and the rule lives in one place. See
[Validators](/v1.0/pydantic/validators/#reusable-annotated-validators).
