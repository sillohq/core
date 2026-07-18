---
title: JSON Serialization & Custom Encoders
description: How sillo serializes responses to JSON and how to register custom type encoders.
---

# JSON Serialization & Custom Encoders

When a handler returns a value, sillo serializes it to JSON using `sillo.encoding.jsonable_encoder`. This built-in encoder already handles the common types you'll encounter:

- `datetime.date`, `datetime.datetime`, `datetime.time`, `datetime.timedelta` → ISO strings / seconds
- `decimal.Decimal` → `int` or `float`
- `enum.Enum` → its value
- `uuid.UUID` → string
- `pathlib.Path` / `pathlib.PurePath` → string
- `re.Pattern` → its pattern string
- `pydantic` models, dataclasses, `SecretStr`/`SecretBytes`, `AnyUrl`, `NameEmail`
- `set` / `frozenset` / `deque` / generators / `tuple` → lists
- `bytes` → decoded string

Pydantic models and dataclasses are serialized recursively, so nested structures work out of the box.

## Custom Encoders

Sometimes you have your own types — a `Money` value object, a `Vector`, a `Decimal` subclass — that aren't JSON-serializable by default. sillo lets you teach the encoder how to handle them in three scopes.

### 1. App-wide (recommended)

Register an encoder once with `app.add_encoder(type, encoder)`. It then applies automatically to **every** JSON response, including values returned directly from handlers.

```python
from decimal import Decimal
from dataclasses import dataclass
from sillo import silloApp

app = silloApp()

@dataclass
class Money:
    amount: Decimal
    currency: str

app.add_encoder(Money, lambda m: {"amount": str(m.amount), "currency": m.currency})

@app.get("/price")
async def price(request, response):
    return {"total": Money(Decimal("19.99"), "USD")}
```

```json
{ "total": { "amount": "19.99", "currency": "USD" } }
```

The encoder is also stored on `app.custom_encoders` and merged into the global `sillo.encoding` registry, so it works no matter how the response is produced.

### 2. Global registry

For library/framework-level code that isn't tied to a specific app instance, use the module-level registry:

```python
from sillo.encoding import register_encoder

register_encoder(MyType, lambda obj: obj.to_dict())
```

Anything registered here is consulted by `jsonable_encoder` everywhere.

### 3. Per-response (one-off)

Pass `custom_encoder` to `response.json(...)` to override just for that response:

```python
@app.get("/raw")
async def raw(request, response):
    return response.json(
        {"v": my_obj},
        custom_encoder={MyType: lambda o: o.to_dict()},
    )
```

## Precedence

If multiple encoders target the same type, the most specific wins:

1. **Per-call** `custom_encoder` (highest priority)
2. **Exact type match** over a base-class match
3. **Subclass / `isinstance`** fallback (e.g. registering `Base` also encodes `Derived`)
4. **Built-in** `ENCODERS_BY_TYPE`

## Accessing encoders programmatically

```python
from sillo.encoding import get_custom_encoders

snapshot = get_custom_encoders()  # returns a copy of registered encoders
```

## Best Practices

- Register app-wide encoders at startup, before routes handle traffic.
- Prefer returning plain dicts/pydantic models from handlers; use custom encoders for types that recur across many endpoints.
- Keep encoder callables pure and cheap — they run on every matching value during serialization.
- For per-request exceptions, use `response.json(data, custom_encoder={...})` rather than mutating global state.

Built with ❤️ by the [@sillo-labs](https://github.com/sillo-labs) community.
