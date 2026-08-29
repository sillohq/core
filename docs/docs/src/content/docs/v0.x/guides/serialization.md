---
title: JSON Serialization & Custom Encoders
description: How sillo serializes handler return values to JSON, the built-in type support, and how to register custom encoders at app, global, and per-response scope.
---

#  JSON Serialization & Custom Encoders

Every value a handler returns is turned into JSON before it leaves sillo. That
conversion is handled by `sillo.encoding.jsonable_encoder`, which runs
automatically inside `JSONResponse` and `response.json(...)`. For the common
Python types you already use (datetimes, `Decimal`, enums, UUIDs, pydantic
models) it works without any configuration. For your own types, sillo gives you
a registry you can extend in three scopes.

This page explains what gets serialized, how to teach sillo about a new type, what happens internally when an encoder runs, and how the scopes interact when more than one applies.

##  What sillo encodes by default

`jsonable_encoder` already handles these without registration:

| Input type | Encoded as |
| --- | --- |
| `datetime.date`, `datetime.datetime`, `datetime.time` | ISO-8601 string (`isoformat()`) |
| `datetime.timedelta` | seconds as a `float` |
| `decimal.Decimal` | `int` when integral, otherwise `float` |
| `enum.Enum` | its `.value` |
| `uuid.UUID` | string |
| `pathlib.Path` / `pathlib.PurePath` | string |
| `re.Pattern` | its pattern string |
| `SecretStr` / `SecretBytes` | string (never the raw secret object) |
| `AnyUrl`, `NameEmail` | string |
| `set` / `frozenset` / `deque` / `tuple` / generators | `list` |
| `bytes` | decoded UTF-8 string |
| pydantic `BaseModel`, dataclasses | recursively encoded `dict` |

Pydantic models and dataclasses are walked recursively, so nested structures serialize out of the box.

##  The smallest useful form

You usually need nothing at all. Return a value sillo already understands:

```python
from datetime import datetime

from sillo import SilloApp

app = SilloApp()


@app.get("/now")
async def now(request, response):
    return {"generated_at": datetime.now()}
```

Sillo encodes `datetime.now()` to an ISO string through the built-in `datetime.datetime` entry in its encoder table, sets `Content-Type: application/json`, and returns `200`. You did not register anything and did not call a serializer by hand.

##  Teaching sillo a new type

When you return a type sillo does not recognize (a `Money` value object, a
`Vector`, an ORM entity) the default encoder raises `TypeError` during
serialization. Register an encoder so sillo knows how to flatten it.

###  App-wide (recommended)

`app.add_encoder(type, encoder)` registers an encoder that applies to **every** JSON response the app produces, including values returned directly from handlers.

```python
from dataclasses import dataclass
from decimal import Decimal

from sillo import SilloApp

app = SilloApp()


@dataclass
class Money:
    amount: Decimal
    currency: str


app.add_encoder(Money, lambda m: {"amount": str(m.amount), "currency": m.currency})


@app.get("/price")
async def price(request, response):
    return {"total": Money(Decimal("19.99"), "USD")}
```

The response body is `{"total": {"amount": "19.99", "currency": "USD"}}`.
Internally, `add_encoder` stores the callable on `app.custom_encoders` **and**
writes it into the module-level `CUSTOM_ENCODERS` registry (via
`register_encoder`), so the encoder works no matter how the response is
produced: handler return, `response.json(...)`, or a manually built
`JSONResponse`.

<aside type="tip" title="Register at startup">
Register app-wide encoders before the app starts serving traffic, alongside other startup configuration. Encoders are consulted at serialization time, so registering them late still works, but doing it up front keeps behavior predictable.
</aside>

###  Global registry

For code that is not tied to a specific app instance (a shared library, a
plugin, a base model used across projects) register at the module level:

```python
from sillo.encoding import register_encoder


register_encoder(MyType, lambda obj: obj.to_dict())
```

Anything registered here is consulted by `jsonable_encoder` everywhere, including inside apps that never called `add_encoder`.

###  Per-response (one-off)

Pass `custom_encoder` to `response.json(...)` to override encoding for a single response only. This does **not** mutate global or app state:

```python
@app.get("/raw")
async def raw(request, response):
    return response.json(
        {"v": my_obj},
        custom_encoder={MyType: lambda o: o.to_dict()},
    )
```

##  How encoding resolves a type

When `jsonable_encoder` meets a value, it picks an encoder in this order:

1. **Per-call `custom_encoder`**: merged on top of everything else, so it wins.
2. **App/global registry match**: first an *exact* `type(obj)` lookup, then an
   `isinstance` walk over registered base classes (so registering `Base` also
   encodes `Derived`).
3. **Built-in `ENCODERS_BY_TYPE`**: the table shown above.

The merge is concrete: `custom_encoder = {**CUSTOM_ENCODERS, **(custom_encoder or {})}`. Because the per-call dict is spread last, a per-call entry for the same type shadows a globally registered one. The exact-type branch is checked before the `isinstance` branch, so a specific encoder for `Derived` beats a general one for `Base`.

##  A realistic scenario: pricing responses

An e-commerce API returns order totals as a `Money` value object in several endpoints. Registering one app-wide encoder means every handler can return `Money` directly instead of manually mapping it to a dict at each call site:

```python
from dataclasses import dataclass
from decimal import Decimal

from sillo import SilloApp

app = SilloApp()


@dataclass
class Money:
    amount: Decimal
    currency: str


app.add_encoder(Money, lambda m: {"amount": str(m.amount), "currency": m.currency})


@app.get("/orders/{order_id}")
async def order(request, response, order_id: int):
    total = compute_total(order_id)  # returns Money(...)
    return {"order_id": order_id, "total": total}
```

The encoder runs once per `Money` value during serialization, so handlers stay focused on domain logic. If a single endpoint needs a different shape, pass `custom_encoder=` to that `response.json(...)` call without disturbing the others.

##  Works with

- **Handlers**: encoder return values automatically. No import or call needed
  in the handler body beyond `app.add_encoder` at setup.
- **Dependency injection.** A dependency that returns a custom type benefits
  from the same registry; register the encoder once and inject the value
  anywhere.
- **Tests.** `TestClient` serializes responses through the same path, so an
  encoder registered on the app under test is exercised end-to-end (see below).
- **Security / sessions**: JSON error and auth responses flow through
  `jsonable_encoder` too, so custom types inside those payloads are encoded
  consistently.

##  Errors and edge cases

- **Unregistered type.** If a returned value is not JSON-native and no encoder
  matches, `jsonable_encoder` raises `TypeError` while building the response.
  The error surfaces as a `500` from sillo's error handling. Register the type
  (or convert it in the handler) to fix it.
- **Encoder raises.** An encoder that throws becomes a `500` at serialization
  time. Keep encoders pure and defensive; never do I/O or network calls inside
  one.
- **Mutating global state.** `register_encoder` writes to a process-wide dict.
  In tests or multi-app processes, clear it afterward (see Testing) to avoid
  leaking encoders between cases.
- **Subclass ambiguity.** If both `Base` and `Derived` are registered, the
  *exact* `Derived` match wins. If only `Base` is registered, `Derived`
  instances use the `Base` encoder via `isinstance`.

##  Testing

Use `TestClient` to assert the serialized shape. This mirrors sillo's own suite:

```python
from dataclasses import dataclass
from decimal import Decimal

from sillo import SilloApp
from sillo.testclient import TestClient


@dataclass
class Money:
    amount: Decimal
    currency: str


def test_money_encoder():
    app = SilloApp()
    app.add_encoder(Money, lambda m: {"amount": str(m.amount), "currency": m.currency})

    @app.get("/price")
    async def price(request, response):
        return {"total": Money(Decimal("19.99"), "USD")}

    client = TestClient(app)
    assert client.get("/price").json() == {"total": {"amount": "19.99", "currency": "USD"}}
```

Assert the **per-call override** separately, since it is the highest-precedence path:

```python
from sillo.encoding import register_encoder


def test_per_call_overrides_global():
    register_encoder(Vector, lambda v: [v.x, v.y])  # global
    app = SilloApp()

    @app.get("/override")
    async def override(request, response):
        return response.json(
            Vector(7, 8),
            custom_encoder={Vector: lambda v: {"x": v.x, "y": v.y}},
        )

    assert TestClient(app).get("/override").json() == {"x": 7, "y": 8}
```

Because `register_encoder` mutates a global dict, clean it up in `teardown_module` so later tests are not affected:

```python
from sillo.encoding import CUSTOM_ENCODERS


def teardown_module(module):
    CUSTOM_ENCODERS.pop(Money, None)
    CUSTOM_ENCODERS.pop(Vector, None)
```

##  Production considerations

- **Keep encoders cheap.** They run on every matching value, recursively, during response serialization. A slow encoder adds latency to every request that returns the type.
- **Prefer app-wide or global registration** over per-call `custom_encoder` for
  types that recur, per-call dicts allocate a new map on every response.
- **Isolation in multi-app processes.** The global `CUSTOM_ENCODERS` is shared across every app in the process. If two apps register different encoders for the same type, the last write wins process-wide. Use `app.custom_encoders` + per-call overrides, or namespaced types, to avoid cross-app leakage.
- **Large payloads.** Encoding walks the whole object graph. For very large responses, consider streaming or returning a pre-built `dict` instead of relying on a deep custom encoder.
- **Determinism.** Encoders should be pure functions of their input. Non-deterministic output (timestamps, randomness) makes responses and tests harder to reason about.

##  Related topics

- [Sending Responses](/v0.x/guides/sending-responses/): `response.json(...)` and
  other response builders
- [Dependency Injection](/v0.x/guides/dependency-injection/): injecting custom-typed
  values
- [Request Inputs](/v0.x/guides/request-inputs/): parsing incoming data before you
  serialize the outgoing response


##  What the encoder handles

`jsonable_encoder` converts Python objects to JSON-compatible structures
before they are serialized. It handles the types the standard `json`
module refuses: `datetime`, `date`, `time`, `Decimal`, `UUID`, `Enum`,
`set`, `bytes`, dataclasses, Pydantic models, and ORM instances.

Knowing what it does with each prevents surprises in your API contract.

`datetime` becomes an ISO 8601 string. Always include the timezone. A naive
datetime serializes without an offset, and every client will guess differently
about what it means.

`Decimal` becomes a float by default, which loses precision. For money,
serialize integer cents or an explicit string; a float cannot represent
`19.99` and a client doing arithmetic on it will produce
`19.989999999999998`.

`Enum` becomes its value, not its name. That makes the value part of your
public contract. Renaming the member is safe, changing the value is not.

`set` becomes a list in unspecified order. If the order matters to a
client, sort it before returning.

##  Custom encoders

Register a converter for any type the encoder does not know:

```python title="teaching the encoder a new type"
from decimal import Decimal

app.add_encoder(Decimal, str)               # money as an exact string
app.add_encoder(MyDomainType, lambda v: v.to_public_dict())
```

Registering one is a contract decision, not a formatting one, every endpoint
returning that type changes shape at once. Do it early, and prefer an explicit
conversion in the response model when only one endpoint needs it.

##  Serialization is where data leaks

Returning an object rather than a shaped dict means returning every
attribute it has, including the ones added later by someone who did not
know your endpoint existed.

The two defences, in order of strength: declare a
[`response_model`](/v0.x/guides/validation/response-models/), which drops
undeclared fields by construction; or project explicitly with
`include=`. Both are better than `exclude=`, which requires you to
remember every sensitive field forever, including the ones that do not
exist yet.

This is the single most common way private data reaches an API response,
and it is entirely preventable at the point where the response is built.


##  Encoding is not free

Serializing a large response is CPU work on the event loop, and it is
frequently the slowest part of an endpoint that looks fast in the
database.

Three things reduce it. Return fewer fields (the response model that protects
you from leaks also halves the encoding cost. Return fewer rows) pagination is
a performance feature before it is a UX one. And avoid re-encoding: a response
cached as a serialized string skips both the query and the encode.

For genuinely large payloads, streaming a generated body avoids holding
the whole serialized result in memory at once. See
[Streaming Responses](/v0.x/guides/streaming-response/).

##  Deserialization is where trust ends

Everything above is about output. On the way in, the same machinery is
an attack surface: a JSON body is parsed before any of your constraints
apply, so a deeply nested or enormous payload consumes CPU and memory
before validation has a chance to reject it.

Bound the request body at the proxy, and bound collection sizes in your
models. See [Request Bodies](/v0.x/guides/validation/request-bodies/) for the
specific limits worth setting.


##  Consistency across an API

The choices on this page are per-application, not per-endpoint. A
`datetime` serialized as ISO 8601 on one route and a Unix timestamp on
another forces every client to special-case, and the inconsistency
usually arrives one endpoint at a time.

Decide once for the common types (timestamps, money, identifiers, nullable
fields) write it down, and enforce it through shared base models rather than
convention.
