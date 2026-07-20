---
title: Cache
description: Advanced caching subsystem — pluggable backends, a @cache decorator, TTLs, tags, versioning, LRU eviction, and stats.
---

# Cache (`sillo.cache`)

sillo ships an advanced, backend-agnostic caching subsystem. It is deliberately
**decoupled from the application object** — you configure a backend at the
*domain* level and use it from anywhere (handlers, services, plain functions),
not just inside a request.

```python
from sillo.cache import MemoryCache, configure_cache, cache

configure_cache(MemoryCache(default_ttl=300))

@cache(ttl=120, tags=["catalog"])
async def get_product(product_id: int):
    return await db.products.get(product_id)
```

## Installation & backends

Two backends ship today:

| Backend | Dependency | Notes |
|---|---|---|
| `MemoryCache` | none (stdlib) | In-process, thread-safe, full feature set. |
| `RedisCache` | `redis>=5` (`pip install sillo[cache]`) | Async Redis; mirrors the memory feature set. |

```bash
pip install "sillo[cache]"   # installs the optional redis driver
```

If `redis` is not installed, `RedisCache` still imports — the `redis.asyncio`
dependency is loaded lazily and only errors when you actually construct a
`RedisCache`.

## Configuring a default backend

Call `configure_cache()` once at startup to register a process-wide default.
Any `@cache()` with no `backend=` argument uses it:

```python
from sillo.cache import MemoryCache, configure_cache, RedisCache

# For production: a shared Redis instance.
configure_cache(RedisCache(url="redis://localhost:6379/0", default_ttl=600))

# Or keep it simple/in-process for tests and small apps:
# configure_cache(MemoryCache(default_ttl=300))
```

If you never call `configure_cache()`, the first `@cache()` call creates an
implicit in-process `MemoryCache` for you. You can always override per
function with `backend=`.

```python
from sillo.cache import cache, MemoryCache

local = MemoryCache(namespace="session", default_ttl=60)

@cache(backend=local, ttl=30)
def expensive(x):
    return compute(x)
```

::: tip Domain-level, not app-level
Unlike response/cookie/session config which is tied to `silloApp`, caching is
configured independently. This keeps cached functions testable and reusable
outside the web layer (CLI commands, workers, background tasks).
:::

## The `@cache` decorator

Decorate any callable — sync or async, function or bound method.

### Async function

```python
from sillo.cache import cache

@cache(ttl=120, tags=["users"])
async def get_user(user_id: int):
    return await db.users.get(user_id)
```

### Sync function

The decorator bridges to the async backend automatically, so you can use the
same `@cache` on a plain function:

```python
@cache(ttl=60)
def price_lookup(sku: str):
    return catalog.lookup(sku)
```

### Bound methods

`self` / `cls` are **excluded from the cache key**, so all instances of a class
share one cache for the same arguments. Be careful: the cached value does not
depend on instance state.

```python
class ReportService:
    @cache(namespace="reports", ttl=300)
    def build(self, quarter: str):
        return self.run_query(quarter)
```

### Decorator options

| Option | Effect |
|---|---|
| `backend` | Explicit backend; defaults to the configured default. |
| `ttl` | Seconds until expiry (absolute or sliding). |
| `namespace` | Groups keys; used by `clear()` and versioning. |
| `version` | Key version; bump to invalidate a whole namespace at once. |
| `key_prefix` | Extra literal in the key (e.g. a role name). |
| `tags` | Tuple of invalidation tags attached to every entry. |
| `sliding` | Refresh TTL on each read instead of fixed expiry. |
| `skip_cache_if` | Predicate `(*args, **kwargs) -> bool`; when `True`, runs the call without caching. |
| `serializer` | `"json"` (default) or `"pickle"` for this function's values. |
| `settings` | A `CacheSettings` object providing shared defaults. |

### Manual invalidation

Every decorated function gains an `.invalidate(*args, **kwargs)` coroutine that
deletes just that call's key:

```python
await get_user.invalidate(42)   # drop the cached entry for user 42
```

### Skipping the cache conditionally

```python
@cache(ttl=60, skip_cache_if=lambda x: x < 0)
async def compute(x):
    return slow(x)
```

When `skip_cache_if` returns `True`, the function runs and its result is
returned **without** being stored.

## Using a backend directly (on the fly)

You don't need the decorator — the `BaseCache` API works as a key-value store:

```python
from sillo.cache import MemoryCache

cache = MemoryCache(namespace="sessions", default_ttl=3600)

await cache.set("token:abc", user_id, tags=["token:abc"])
value = await cache.get("token:abc")      # returns _MISSING on miss
exists = await cache.exists("token:abc")
await cache.delete("token:abc")
await cache.touch("token:abc", ttl=7200)  # extend lifetime
await cache.clear()                        # drop keys in this namespace
```

`get` returns the module-level sentinel `_MISSING` on a miss or expiry (not
`None`), so caching `None` as a real value is safe.

## Advanced features

### TTL — absolute vs sliding

* **Absolute** (default): the entry expires `ttl` seconds after it was written.
* **Sliding**: each read resets the expiry window to `ttl` seconds, so an
  entry that is read frequently stays alive while a forgotten one expires.

```python
await cache.set("hot", data, ttl=300, sliding=True)
```

### Tag-based invalidation

Attach one or more tags to entries, then drop every key with a tag at once:

```python
await cache.set("u:1", user1, tags=["user:1", "directory"])
await cache.set("u:2", user2, tags=["user:2", "directory"])

await cache.invalidate_tags("directory")   # removes both entries
```

This is ideal for "invalidate all cached views of entity X" patterns:

```python
@cache(tags=("product",))
async def get_product(product_id: int):
    ...

# after an admin edit:
await product_cache.invalidate_tags("product")
```

### Versioning

Bump `version` to expire an entire key space instantly without tracking tags:

```python
@cache(namespace="catalog", version="v2")
async def list_catalog():
    ...
```

Changing `version="v2"` to `version="v3"` produces different keys, so old
entries are effectively dead (and eventually evicted by TTL).

### LRU & max-size eviction (MemoryCache)

Set `max_size` to bound memory. When the store exceeds `max_size`, the
least-recently-used entry is evicted first. Reading an entry marks it recently
used, so hot keys survive.

```python
cache = MemoryCache(max_size=1024)
await cache.set("a", 1)
await cache.set("b", 2)
await cache.set("c", 3)   # evicts "a" (oldest)
```

### Serialization: JSON vs pickle

* `serializer="json"` (default) is safe and cross-language but only handles
  JSON-compatible data. Complex Python objects are best-effort converted.
* `serializer="pickle"` stores arbitrary Python objects, at the cost of being
  Python-only and unsafe for untrusted input.

```python
pickle_cache = MemoryCache(serializer="pickle")
await pickle_cache.set("obj", {"set": {1, 2, 3}})
```

### Hit/miss statistics

Every backend tracks `hits`, `misses`, `sets`, `deletes`, and `evictions`,
exposed via `.stats()`:

```python
stats = cache.stats()
print(stats.hit_rate)        # 0.0–1.0
print(stats.as_dict())
cache.reset_stats()
```

## Redis backend

The async Redis backend maps concepts onto Redis primitives:

* Keys are stored verbatim (already namespaced/versioned by `make_key`).
* TTL uses Redis `SETEX` / `EXPIRE`.
* Tags are Redis sets (`tag:<ns>:<tag>`) of member keys; `invalidate_tags`
  deletes all members and the set.
* Sliding TTL re-issues `EXPIRE` on each read.

```python
from sillo.cache import RedisCache

redis_cache = RedisCache(
    url="redis://localhost:6379/0",
    namespace="myapp",
    default_ttl=600,
    serializer="json",
)

await redis_cache.set("k", value, tags=["t1"])
value = await redis_cache.get("k")
await redis_cache.invalidate_tags("t1")
```

Use `RedisCache` as a shared backend across multiple processes/workers so they
cooperate on one cache.

## Full example

```python
from sillo import silloApp
from sillo.cache import MemoryCache, configure_cache, cache

configure_cache(MemoryCache(default_ttl=300))

app = silloApp()

@app.get("/products/{product_id:int}")
async def product(request, response, product_id: int):
    data = await get_product(product_id)   # cached
    return response.json(data)

@cache(namespace="catalog", ttl=600, tags=("catalog",))
async def get_product(product_id: int):
    # ... expensive lookup ...
    return {"id": product_id}
```

## API reference

| Symbol | Kind | Purpose |
|---|---|---|
| `BaseCache` | class | Abstract backend contract. |
| `MemoryCache` | class | In-process backend (TTL, LRU, tags, version). |
| `RedisCache` | class | Async Redis backend (optional `redis`). |
| `CacheStats` | dataclass | Hit/miss/eviction counters. |
| `CacheSettings` | dataclass | Reusable decorator defaults. |
| `configure_cache(backend)` | function | Register the default backend. |
| `get_default_backend()` | function | Return (or lazily create) the default. |
| `reset_cache_config()` | function | Clear the default (useful in tests). |
| `cache(...)` | decorator | Cache a function/method's result. |
| `build_key(...)` | function | Deterministic key construction. |
| `tag_key(...)` | function | Storage key for a tag set. |
