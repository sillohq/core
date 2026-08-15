---
title: Parameters
description: Query strings, headers, cookies, and path segments, declared with markers that carry their own type and constraints. Includes the full type catalog and every constraint Pydantic offers.
---

Every input except the JSON body is declared with a marker, placed as the parameter's default value:

```python
from sillo import SilloApp, Query, Header, Cookie, Path

app = SilloApp()

@app.get("/teams/{team_id}/items")
async def list_items(request, response,
                     team_id=Path(type=int),
                     page=Query(1, type=int, ge=1),
                     token=Header(type=str),
                     theme=Cookie("dark", type=str)):
    return {"team": team_id, "page": page}
```

| Marker | Reads from | Example |
| --- | --- | --- |
| `Query` | URL query string | `page=Query(1, type=int)` |
| `Header` | Request headers | `token=Header(type=str)` |
| `Cookie` | Cookies | `sid=Cookie(None, type=str)` |
| `Path` | URL path segments | `user_id=Path(type=int)` |

`Form` and `File` are covered in [Forms and file uploads](/guides/validation/forms-and-files/).

##  Declaring the type

The type goes on the marker, as `type=`:

```python
page = Query(1, type=int)
tags = Query([], type=List[str])
role = Query(None, type=UserRole)      # an enum
when = Query(None, type=datetime)      # anything Pydantic understands
```

If you omit `type=`, sillo infers it from the default value. `Query(1)` is an
integer, `Query("")` a string. See [Both declaration
styles](#both-declaration-styles) at the end of this page.

##  Why coercion matters here

Everything in a URL is text. `?page=2` gives you the string `"2"`, never the number `2`; a header is a string; a cookie is a string. Declaring `type=int` is what turns that text into the value you actually want, and rejects the text that cannot become one.

Pydantic's *lax mode* (the default) does this conversion where intent is unambiguous:

```
?page=2      type=int    ->  2
?page=abc    type=int    ->  422, "Input should be a valid integer"
?page=       type=int    ->  422
(absent)     type=int    ->  the default, or 422 if there is none
```

Set `strict=True` to switch a parameter to strict mode, where no conversion
happens at all. For query parameters this is rarely what you want. The incoming
value is always a string, so `Query(type=int, strict=True)` rejects every
request. It is useful mainly for JSON body fields, where the client can send a
real number.

##  The type catalog

Anything Pydantic can validate works as a `type=`. The types that come up in URLs, headers, and cookies:

###  Numbers and text

```python
count  = Query(0, type=int)
price  = Query(0.0, type=float)
name   = Query("", type=str)
active = Query(False, type=bool)
```

Booleans accept `true`, `1`, `yes`, `on`, `t`, `y` (and their false
counterparts), case-insensitively. Anything else is a `bool_parsing` error, so
`?active=maybe` is rejected rather than silently treated as false.

###  Dates and times

```python
from datetime import datetime, date, time, timedelta

since  = Query(None, type=datetime)   # 2024-01-02T03:04:05, or with a timezone
day    = Query(None, type=date)       # 2024-01-02
at     = Query(None, type=time)       # 03:04:05
window = Query(None, type=timedelta)  # PT1H (ISO 8601 duration), or seconds
```

ISO 8601 is parsed natively. `datetime` also accepts a Unix timestamp.

###  Identifiers and precise numbers

```python
from uuid import UUID
from decimal import Decimal

order_id = Query(None, type=UUID)      # 123e4567-e89b-12d3-a456-426614174000
amount   = Query(None, type=Decimal)   # "1.10" stays exactly 1.10
```

Use `Decimal` for money. A `float` cannot represent `0.1` exactly; `Decimal` can, and Pydantic parses it from the string without ever going through a float.

###  Enums

An enum restricts a parameter to a fixed set and documents those values in your OpenAPI schema:

```python
from enum import Enum

class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"

order = Query(SortOrder.DESC, type=SortOrder)
```

`?order=asc` produces `SortOrder.ASC`; `?order=sideways` is a 422 listing the permitted values. Inheriting from `str` as well as `Enum` means the member behaves like a string everywhere else in your code.

###  Literals

For a small fixed set with no enum class:

```python
from typing import Literal

mode = Query("compact", type=Literal["compact", "full"])
```

###  Optional values

```python
from typing import Optional

q = Query(None, type=Optional[str])
```

`Optional[str]` means "a string or null". In practice a marker with a `None` default already behaves this way, so you rarely need it explicitly for query parameters.

###  Network and web types

```python
from pydantic import AnyUrl, HttpUrl, EmailStr, IPvAnyAddress

callback = Query(None, type=HttpUrl)        # must be a valid http(s) URL
contact  = Query(None, type=EmailStr)       # requires: pip install email-validator
client   = Header(None, type=IPvAnyAddress) # IPv4 or IPv6
```

`EmailStr` needs the optional `email-validator` package. The others are built in.

###  Secrets

```python
from pydantic import SecretStr

token = Header(type=SecretStr)
```

A `SecretStr` renders as `**********` in logs, tracebacks, and `repr()`. Call `token.get_secret_value()` to read it. Useful for anything you do not want appearing in an error report.

##  Constraints

Constraints are plain keyword arguments on the marker.

###  Numeric

```python
page  = Query(1, type=int, ge=1)              # >= 1
page  = Query(1, type=int, gt=0)              # > 0
limit = Query(20, type=int, ge=1, le=100)     # between 1 and 100
step  = Query(5, type=int, multiple_of=5)     # 5, 10, 15, …
```

`ge`/`le` are inclusive, `gt`/`lt` exclusive. They work on `int`, `float`, `Decimal`, and dates.

```python
from datetime import date
after = Query(None, type=date, ge=date(2020, 1, 1))
```

###  Strings

```python
name = Query(type=str, min_length=2, max_length=50)
slug = Query(type=str, pattern=r"^[a-z0-9-]+$")
```

`pattern` is a regular expression, searched from the start of the string.
Anchor it with `$` if you mean the whole string, as above, without the `$`,
`pattern=r"^[a-z]+"` would accept `"abc123"`.

###  Collections

`min_length` and `max_length` apply to lists too:

```python
tags = Query([], type=List[str], min_length=1, max_length=10)
```

###  Strictness

```python
count = Query(type=int, strict=True)     # rejects "5"; requires a real int
```

###  The complete set

| Constraint | Applies to | Meaning |
| --- | --- | --- |
| `gt` | numbers, dates | strictly greater than |
| `ge` | numbers, dates | greater than or equal |
| `lt` | numbers, dates | strictly less than |
| `le` | numbers, dates | less than or equal |
| `multiple_of` | numbers | divisible by |
| `min_length` | strings, collections | minimum length |
| `max_length` | strings, collections | maximum length |
| `pattern` | strings | regular expression |
| `strict` | any | disable coercion |

Supplying any constraint opts the parameter into full validation, so bad values return 422 rather than a server error.

##  Documentation keywords

These enrich the generated OpenAPI entry and **never** change validation behavior:

```python
q = Query(type=str,
          title="Search",
          description="Full-text search across names",
          example="widgets",
          deprecated=True)
```

The separation is deliberate: adding a description to a live endpoint can never alter how it validates.

##  Required and optional

A marker with a default is optional; one without is required.

```python
page = Query(1, type=int)      # optional, defaults to 1
q    = Query(type=str)         # required -> 422 when absent
sid  = Cookie(None, type=str)  # optional, None when absent
```

```json
GET /items
{"detail": [{"loc": ["query", "q"], "msg": "Field required", "type": "missing"}]}
```

An absent parameter is not the same as an empty one. `?q=` supplies an empty string, which passes a plain `type=str` but fails `min_length=1`.

##  Aliases

When the wire name is not a valid Python identifier, or you simply want a different one:

```python
page_num = Query(1, type=int, alias="page")     # reads ?page=
```

Errors report the **wire** name, since that is what the client sent:

```json
{"detail": [{"loc": ["query", "page"], "msg": "...", "type": "int_parsing"}]}
```

###  Header casing is automatic

Header parameters convert snake_case to Header-Case, so you rarely need an alias:

```python
x_api_key = Header(type=str)      # reads the X-Api-Key header
```

Header lookup is case-insensitive regardless, per the HTTP specification.

##  Lists and repeated parameters

A list-typed parameter collects every occurrence of the key:

```python
from typing import List

@app.get("/items")
async def search(request, response, tags=Query([], type=List[str])):
    return {"tags": tags}
```

```
GET /items?tags=red&tags=blue   ->   tags == ["red", "blue"]
```

This is the standard HTTP convention for repeated keys.

Element types are validated too:

```python
ids   = Query([], type=List[int])         # ?ids=1&ids=2  -> [1, 2]
                                          # ?ids=abc      -> 422
roles = Query([], type=List[SortOrder])   # enum members
```

Errors index into the list so you know which element failed:

```json
{"detail": [{"loc": ["query", "ids", 1], "msg": "Input should be a valid integer",
             "type": "int_parsing"}]}
```

Other collection types work as well:

```python
tags = Query(type=Set[str])              # deduplicated
pair = Query(type=Tuple[int, int])       # fixed length
```

##  Path parameters

`Path` layers declared types and constraints onto a URL segment:

```python
@app.get("/items/{item_id}")
async def get_item(request, response, item_id=Path(type=int, ge=1)):
    return {"id": item_id}
```

This is independent of the `{item_id:int}` convertor syntax in the route pattern. The convertor decides whether a URL *matches* the route at all; `Path` validates the value once matched and publishes its schema. Using `Path` lets a plain `/items/{item_id}` route validate without embedding the type in the URL, and lets you attach constraints a convertor cannot express.

A path parameter is always required (a request lacking it could not have
matched the route) so any default is ignored.

##  Parameters in dependencies

Markers work in any injected callable, not only handlers:

```python
from sillo import Depend, Query

def pagination(page=Query(1, type=int, ge=1),
               size=Query(20, type=int, ge=1, le=100)):
    return {"page": page, "size": size}

@app.get("/items")
async def list_items(request, response, pager=Depend(pagination)):
    return pager
```

They are validated with the rest of the request and documented on every route that uses the dependency, which makes shared concerns like pagination or filtering a single definition.

##  Reusing a marker

A marker held in a module constant binds independently per handler, so this is safe:

```python
PAGE = Query(1, type=int, ge=1)

@app.get("/a")
async def a(request, response, page=PAGE): ...

@app.get("/b")
async def b(request, response, offset=PAGE):   # reads ?offset=, not ?page=
    ...
```

##  Both declaration styles

sillo has always let you declare a parameter with only a default, inferring the type from it. That still works:

```python
page   = Query(1)        # int, inferred from the default
q      = Query()         # raw string; None when absent
tags   = Query([])       # comma-split: ?tags=a,b,c -> ["a", "b", "c"]
active = Query(False)    # accepts "yes" as well as "true"
```

Adding a `type=` or any constraint moves the parameter onto the fully validated path. Both styles coexist freely, including within one handler:

```python
async def handler(request, response,
                  page=Query(1),                    # inferred
                  limit=Query(20, type=int, le=100)):  # validated
    ...
```

Two differences are worth knowing when you add a type to an existing parameter:

**Lists.** The inferred form splits on commas; the typed form reads repeated keys.

```python
tags = Query([])                  # ?tags=a,b,c    -> ["a","b","c"]
tags = Query([], type=List[str])  # ?tags=a&tags=b -> ["a","b"]
```

**Failure handling.** Without a type, a value that cannot convert raises inside the handler and surfaces as a 500. With one, it returns a 422 naming the parameter.

To validate everything in an application, including parameters written the short way:

```python
app = SilloApp(strict_validation=True)
```


##  Parameters are attacker-controlled

Every value on this page arrives from outside. Validation bounds the
shape; it does not make the value safe to use. Four places where that
distinction matters.

**Sort and order parameters.** A `sort` parameter interpolated into a
query is SQL injection whether or not it validated as a string. Map it
through an allowlist:

```python title="the only safe way to accept a sort field"
SORTABLE = {"created": "created_at", "name": "name", "price": "price_cents"}


@app.get("/products")
async def products(request, response, sort: str = Query("created", type=str)):
    column = SORTABLE.get(sort)
    if column is None:
        return response.json({"error": "unknown sort field"}, status_code=422)
    return response.json(await Product.all().order_by(column))
```

A `pattern=` constraint that permits `[a-z_]+` still permits `password`,
`is_admin`, and any other column name. The allowlist is the control; the
pattern is a convenience.

**Redirect targets.** A `next` or `return_to` parameter that you redirect to is
an open redirect. An attacker sends a link to your domain that lands on theirs,
which is the front half of most phishing. Accept only relative paths, and
reject anything containing `//` or a scheme.

**Identifiers you look up.** `Path(type=int)` guarantees `user_id` is an
integer. It does not guarantee the caller may see that user. An `IDOR` (reading
someone else's record by changing a number) passes every validator you can
write. Scope the query by the authenticated user rather than checking after the
fetch.

**Anything reaching a filesystem path.** A `Query(type=str)` for a
filename validates fine and still contains `../`. Resolve and confirm
containment before opening anything.

##  Cost and cardinality

Two parameter-design decisions have outsized operational effects.

**Unbounded page sizes.** `Query(20, type=int)` with no `le=` lets a
client ask for a million rows. Always cap:
`Query(20, type=int, ge=1, le=100)`. The `le=` is what stands between a
curious client and an out-of-memory kill.

**High-cardinality filters.** A parameter that becomes part of a cache
key multiplies your cache entries by its cardinality. A `timestamp`
filter with second precision produces a distinct cache entry per second,
which is a cache with a zero percent hit rate and the memory cost of one
that works. Round to a bucket, or exclude the parameter from the key.

Similarly, every distinct parameter combination is a distinct query plan
for the database. Six optional filters means sixty-four possible
`WHERE` shapes; the ones that are rare are also the ones the query
planner has never optimised. Fewer, better-chosen filters beat a
combinatorial surface.

##  Naming that survives a version bump

Parameter names are permanent in a way handler code is not: clients hard-code
them, and changing one breaks every caller silently, because a query parameter
nobody sends is just a default.

Use lowercase with underscores or hyphens, consistently. Pick one and
never mix, because `page_size` and `page-size` are different parameters
and supporting both accidentally is worse than supporting either.

Use `alias=` when the public name should differ from the Python identifier. A
parameter named `from` cannot be a Python variable:

```python
start: str = Query(None, type=str, alias="from")
```

Prefer additive change. Adding an optional parameter is safe; renaming
one is not. When a rename is unavoidable, accept both for a release with
the old one marked `deprecated=True`, so the generated documentation
tells clients before the removal does.
