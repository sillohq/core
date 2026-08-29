---
title: Attribute Casting
description: "Converting model attributes on the way in and out with _casts: the built-in casters, custom ones, how encoding happens at save time, and what the encrypted cast provides."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Attribute Casting
  - tag: meta
    attrs:
      property: og:description
      content: The _casts dict, built-in casters, custom casters, and the Fernet-backed encrypted cast.
---

A cast converts an attribute between the shape your code wants and the shape
the column holds.

```python
from sillo.record import Model


class User(Model):
    metadata = fields.TextField()
    last_login = fields.CharField(max_length=64, null=True)

    _casts = {
        "metadata": "json",
        "last_login": "datetime",
    }
```

```python
user.metadata = {"theme": "dark", "beta": True}
await user.save()          # stored as a JSON string
```

The base `Model` already includes `HasCasts`, so `_casts` is all you declare.

## Built-in casters

| Name | Encoded to the column | Decoded to Python |
| --- | --- | --- |
| `"json"` | `json.dumps(value, default=str)` | `json.loads` |
| `"datetime"` | `value.isoformat()` | `datetime.fromisoformat` |
| `"bool"` | `bool(value)` | `bool(value)` |
| `"int"` | `int(value)` | `int(value)`, `None` passes through |
| `"float"` | `float(value)` | `float(value)`, `None` passes through |
| `"encrypted"` | see [below](#the-encrypted-cast) | |

`None` is never passed to a caster. A null column stays null.

## When encoding happens

At **save time**, and only for the duration of the write.

`save()` encodes the cast attributes, calls Tortoise's save, then puts the
original Python values back. So your instance still holds the dict after
saving, not the JSON string it wrote:

```python
user.metadata = {"theme": "dark"}
await user.save()
user.metadata            # {'theme': 'dark'} — still a dict
```

That restoration is the part worth knowing. Without it, every save would
silently replace your attributes with their serialised forms, and the second
save in a request would encode the already-encoded value.

## Casting versus a JSON column

If your database has a JSON column type, use it (`fields.JSONField()`) and skip
the cast. The database can then index and query inside the document, which a
`TextField` full of JSON cannot.

The `"json"` cast is for the cases where you have a text column: SQLite in an
older schema, a column you cannot migrate yet, or a value that is JSON by
convention rather than by contract.

## Custom casters

Register one globally:

```python
from sillo.record.casting import CastRegistry

CastRegistry.register(
    "csv",
    lambda value: ",".join(value),
    lambda value: value.split(",") if value else [],
)
```

```python
class Post(Model):
    tags = fields.CharField(max_length=500)
    _casts = {"tags": "csv"}
```

Or inline, as a callable returning an `(encoder, decoder)` pair:

```python
def money():
    return (
        lambda value: int(value * 100),        # to cents
        lambda value: Decimal(value) / 100,    # from cents
    )


class Invoice(Model):
    total = fields.IntField()
    _casts = {"total": money}
```

The callable is invoked each time the cast is resolved, which is what lets it
close over configuration.

## The `encrypted` cast

```python
_casts = {"api_key": ("encrypted", {"key": "my-secret"})}
```

The value is encrypted with **Fernet** (AES-128-CBC with an HMAC-SHA256 tag).
The passphrase you pass is stretched into a key with PBKDF2-HMAC-SHA256 at
600,000 iterations, so an ordinary string is usable as the key without being
used as one directly.

Fernet is authenticated, so a tampered ciphertext fails to decrypt rather than
decrypting to something else. Each write carries its own IV, which means two
rows holding the same secret do not share a ciphertext.

:::caution[This needs the `cryptography` package]
```bash
uv add "sillo-framework[crypto]"
```
Without it the cast raises on first use. It does not fall back to anything
weaker, because a cast that quietly stops protecting a column is worse than one
that refuses to run.
:::

Keep the passphrase out of the database, and remember that changing it needs
every row re-encrypted: rows written under the old passphrase will not decrypt
under the new one.

Often the better answer is not to store the secret at all. Store a hash if you
only need to verify it, or a reference to a secrets manager if you need to use
it.

:::note[Changed in 0.1.0]
This caster used to be XOR against a repeating key, which gave a column named
`encrypted` no real confidentiality. Values written by that version cannot be
read by this one. They were not protected in the first place, so rewrite them
from plaintext.
:::

## The methods

```python
user.get_cast("metadata")             # (encoder, decoder), or (None, None)
user.cast_set("metadata", value)      # encode
user.cast_get("metadata", value)      # decode
```

Public, so a custom manager or serialiser can apply the same conversion the
model would.

## Limits

- **Casts are not queryable.** `User.filter(metadata__theme="dark")` does not
  work on a cast text column. The database sees a string. Use a real JSON
  column for that.
- **A field not in `_meta.fields` is skipped** at save time, so a cast naming a
  property rather than a column silently does nothing.

[Bulk operations](/v1.0/orm/bulk/) are covered too: `bulk_create`, `bulk_upsert` and
`upsert` all encode each instance before inserting, and `QuerySet.update()`
encodes the values it is handed, so `Post.filter(...).update(metadata={...})`
stores the same bytes a `save()` would.
