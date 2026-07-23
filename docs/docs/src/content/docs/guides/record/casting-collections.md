---
title: Casting & Collections
description: Attribute casting (json, datetime, bool, int, float, encrypted) and chainable result collections with map, filter, pluck, group_by, sort_by, sum, avg, chunk, unique.
---

# Casting & Collections

## Attribute Casting

Attribute casting transforms values when reading from or writing to the
database.  Define a `_casts` dict on your model using the `HasCasts`
mixin.  Inspired by Laravel's attribute casting.

```python
from sillo.record import Model, HasCasts
from tortoise import fields

class User(Model, HasCasts):
    email = fields.CharField(max_length=255)

    _casts = {
        "metadata": "json",
        "last_login": "datetime",
        "is_admin": "bool",
        "login_count": "int",
        "balance": "float",
        "secret_key": ("encrypted", {"key": "my-32-byte-secret-key-here!!"}),
    }
```

### How Casting Works

When you **read** a field (e.g., `user.metadata`), the decoder transforms
the database value before returning it.  When you **write** (`user.metadata
= {"theme": "dark"}`), the encoder transforms the Python value before it
hits the database.  This is Python-side logic — there is NO database-level
casting.  The database column must be a compatible type (TEXT for JSON and
encrypted, DATETIME for datetime, BOOLEAN for bool, etc.).

### Accessors and Mutators

Define `get_<field>_attribute(self, value)` to transform a value when it is
read, and `set_<field>_attribute(self, value)` to normalize a value when it
is assigned. Mutators run before persistence; accessors run after casts.

```python
class User(Model):
    email = fields.CharField(max_length=255, unique=True)
    name = fields.CharField(max_length=100)

    def set_email_attribute(self, value: str) -> str:
        return value.strip().lower()

    def get_name_attribute(self, value: str) -> str:
        return value.title()

user = await User.create(email="  ALICE@EXAMPLE.COM ", name="alice smith")
user.email  # "alice@example.com"
user.name   # "Alice Smith"
```

### Built-in Cast Types

| Type | Encoder | Decoder | Best DB Column |
|---|---|---|---|
| `"json"` | `json.dumps` | `json.loads` | TEXT or JSONB |
| `"datetime"` | `.isoformat()` | `datetime.fromisoformat()` | TEXT or DATETIME |
| `"bool"` | `bool()` | `bool()` | BOOLEAN or INTEGER |
| `"int"` | `int()` | `int()` | INTEGER |
| `"float"` | `float()` | `float()` | REAL or FLOAT |
| `"encrypted"` | XOR + base64 | base64 + XOR | TEXT |

The encrypted caster uses simple XOR + base64 encoding for demonstration.
For production, use `cryptography.fernet.Fernet` by registering a custom
caster.

### Custom Casters

```python
from sillo.record.casting import CastRegistry

def upper_encoder(value):
    return value.upper()

def lower_decoder(value):
    return value.lower()

CastRegistry.register("uppercase", upper_encoder, lower_decoder)

class Product(Model, HasCasts):
    _casts = {"sku": "uppercase"}
```

## Collections

A `Collection` wraps a list of model instances and provides chainable
functional methods.  Every method returns a **new** Collection — the
original is never mutated.  This is inspired by Laravel's Collection
class.

```python
from sillo.record import Collection

users = await User.active().all()
collection = Collection(users)
```

### Full Method Reference

| Method | Returns | Description |
|---|---|---|
| `map(callback)` | Collection | Transform each item via callback |
| `filter(callback)` | Collection | Keep items where callback returns True |
| `reject(callback)` | Collection | Remove items where callback returns True |
| `pluck(key)` | Collection | Extract a single attribute from each item |
| `group_by(key)` | Dict[str, Collection] | Group items into nested Collections |
| `key_by(key)` | Dict[Any, Any] | Index items by attribute into a dict |
| `sort_by(key, descending)` | Collection | Sort by attribute |
| `chunk(size)` | Iterator[Collection] | Yield sub-collections of given size |
| `first(default)` | Any | First item or default |
| `last(default)` | Any | Last item or default |
| `take(count)` | Collection | First N items |
| `skip(count)` | Collection | Skip first N items |
| `sum(key)` | float | Sum of attribute values |
| `avg(key)` | float | Average of attribute values |
| `min(key)` / `max(key)` | Any | Min / max of attribute values |
| `count()` | int | Number of items |
| `unique(key)` | Collection | Deduplicate by attribute |
| `contains(callback)` | bool | True if any item matches |
| `is_empty()` / `is_not_empty()` | bool | Boolean checks |
| `to_list()` | List | Convert to plain list |
| `to_dict()` | List[dict] | Serialize all items to dicts |
| `to_json(indent)` | str | Serialize to JSON string |

### Usage Examples

```python
# Extract email addresses:
emails = Collection(users).pluck("email").to_list()

# Filter active VIPs:
vips = Collection(users).filter(lambda u: u.plan == "vip")

# Group by role:
by_role = Collection(users).group_by("role")
for role, members in by_role.items():
    print(f"{role}: {members.count()} members")

# Sort by creation date, newest first:
recent = Collection(users).sort_by("created_at", descending=True).take(10)

# Aggregate:
total_balance = Collection(users).sum("balance")
avg_age = Collection(users).avg("age")
oldest = Collection(users).max("created_at")

# Serialize for API:
return response.json({"users": Collection(users).take(20).to_dict()})

# Deduplicate plans:
plans = Collection(users).pluck("plan").unique().to_list()
```

### Performance

Collections load ALL rows into memory.  For large datasets (10k+ rows),
use Tortoise querysets with `.offset().limit()` or the pagination system.
Collections excel at in-memory transformations on already-fetched result
sets — typically after a paginated query or a filtered query returning a
manageable number of rows.
