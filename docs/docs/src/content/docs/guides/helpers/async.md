---
title: Async Helpers
description: Async introspection and awaitable utilities — detecting async callables and wrapping coroutines as async context managers.
---

# Async Helpers (`sillo.helpers.async_helpers`)

```python
from sillo.helpers.async_helpers import is_async_callable
from sillo.helpers.async_helpers import AwaitableOrContextManagerWrapper
from sillo.helpers.async_helpers import collapse_excgroups
```

These helpers are the smallest, most internal utilities in sillo. They solve two
problems that appear everywhere in an ASGI framework:

1. **Detecting** whether something is an async callable — not just a plain
   function, but also objects whose `__call__` is a coroutine function, and
   `functools.partial` wrappers around either.
2. **Adapting** a coroutine that produces a closeable resource into something
   you can both `await` *and* use as an `async with` block, so the resource is
   always closed when the block exits.

Nothing here depends on third-party packages. It is pure standard library
(`asyncio`, `functools`, `contextlib`) plus a guarded import of
`exceptiongroup` on Python < 3.11.

## `is_async_callable`

The most-used helper. It returns `True` when `obj` can be awaited as a call —
either because it is a coroutine function, or because calling it produces a
coroutine.

```python
from sillo.helpers.async_helpers import is_async_callable


async def handler():
    return "ok"


def sync_handler():
    return "ok"


print(is_async_callable(handler))       # True
print(is_async_callable(sync_handler))  # False
```

### Why this is not just `asyncio.iscoroutinefunction`

Two cases break a naive check:

- **Objects with an async `__call__`.** A class instance can be "callable and
  async" even though `asyncio.iscoroutinefunction(instance)` is `False`. sillo
  checks `obj.__call__` as a fallback.

  ```python
  from sillo.helpers.async_helpers import is_async_callable


  class Controller:
      async def __call__(self):
          return "dispatched"


  controller = Controller()
  print(is_async_callable(controller))  # True
  ```

- **`functools.partial`.** Wrapping an async function in `partial` (common for
  binding default arguments) hides the underlying coroutine function. sillo
  unwraps `partial` layers before testing.

  ```python
  from functools import partial
  from sillo.helpers.async_helpers import is_async_callable


  async def greet(name):
      return f"hi {name}"


  bound = partial(greet, "world")
  print(is_async_callable(bound))  # True
  ```

### Full signature and typing

```python
def is_async_callable(obj: typing.Any) -> TypeGuard[AwaitableCallable[typing.Any]]: ...
```

It is declared with `@typing.overload` so type checkers narrow correctly:
passing a known `AwaitableCallable` keeps the `AwaitableCallable` type;
passing `Any` narrows to the awaitable-callable type guard. Internally the
logic is:

```python
def is_async_callable(obj):
    while isinstance(obj, functools.partial):
        obj = obj.func
    return asyncio.iscoroutinefunction(obj) or (
        callable(obj) and asyncio.iscoroutinefunction(obj.__call__)
    )
```

### Where sillo uses it

- `sillo.application` — deciding whether a user-supplied handler runs in the
  async event loop or can be wrapped.
- `sillo.routing.router` — distinguishing async route endpoints from sync ones.
- `sillo.http.request` — checking whether request-dependent callables are
  awaitable before scheduling them.
- `sillo.testclient._internal.utils` — the test client reuses the exact same
  helper so test behavior matches production.

### A practical pattern

When you accept a callback from a user and must decide how to invoke it:

```python
from sillo.helpers.async_helpers import is_async_callable


async def run_maybe_async(fn, *args):
    if is_async_callable(fn):
        return await fn(*args)
    return fn(*args)
```

## `AwaitableOrContextManagerWrapper`

Some coroutines return a resource that must be closed (a connection, a session,
a stream). You want to write code that either:

```python
resource = await open_thing()      # await it directly
await resource.close()
```

or:

```python
async with open_thing() as resource:   # use it as a context manager
    ...
```

`AwaitableOrContextManagerWrapper` lets one object support **both** forms.
`__await__` returns the underlying resource; `__aenter__`/`__aexit__` enter the
context and call `.close()` on exit.

```python
from sillo.helpers.async_helpers import AwaitableOrContextManagerWrapper


class Connection:
    async def close(self):
        print("connection closed")


async def open_connection():
    return Connection()


# Wrap the coroutine so it is both awaitable and an async context manager
awaiter = AwaitableOrContextManagerWrapper(open_connection())

# Form 1: await directly
conn = await awaiter
print(type(conn).__name__)  # Connection

# Form 2: async with (re-wrap a fresh coroutine)
async with AwaitableOrContextManagerWrapper(open_connection()) as conn2:
    print(type(conn2).__name__)  # Connection
# "connection closed" printed automatically on exit
```

### The supporting protocols

Two `typing.Protocol` types describe the contract so type checkers understand
the dual nature:

```python
class AwaitableOrContextManager(Awaitable[T_co], AsyncContextManager[T_co], Protocol[T_co]): ...
```

This is the *static* type of "something you can await and use as an async
context manager." `AwaitableOrContextManagerWrapper` is the *runtime* adapter
that turns a plain `Awaitable[Closeable]` into that shape.

There is also:

```python
class SupportsAsyncClose(Protocol):
    async def close(self) -> None: ...
```

Used as the bound for the wrapper's generic parameter, so the wrapper only
accepts awaitables that resolve to something with an async `close()`.

### Implementation notes

- Uses `__slots__ = ("aw", "entered")` to keep wrapper instances light.
- `__aexit__` always calls `self.entered.close()` and returns `None`, meaning
  it does **not** suppress exceptions — any error raised inside the `async with`
  block propagates after the resource is closed.
- If you `await` the wrapper and then also want the context-manager form, you
  must wrap a *fresh* coroutine; the same wrapper instance tracks its entered
  resource once.

### Where sillo uses it

`AwaitableOrContextManager` and its wrapper appear in request/response handling
where a body stream may be consumed either by awaiting it or by entering it as
a context manager. `sillo.http.request` imports `AwaitableOrContextManager` and
`AwaitableOrContextManagerWrapper` directly.

## `collapse_excgroups`

On Python 3.11+, `BaseExceptionGroup` lets multiple exceptions be raised
together. In some paths sillo would rather surface the *single* underlying
exception than a group that wraps exactly one item. `collapse_excgroups` is a
context manager that unwraps single-element exception groups.

```python
from sillo.helpers.async_helpers import collapse_excgroups


try:
    with collapse_excgroups():
        raise BaseExceptionGroup("one", [ValueError("boom")])
except ValueError as exc:
    print(exc)  # ValueError: boom  (not the group)
```

### How it works

```python
@contextmanager
def collapse_excgroups():
    try:
        yield
    except BaseException as exc:
        if has_exceptiongroups:
            while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
                exc = exc.exceptions[0]
        raise exc
```

`has_exceptiongroups` is `True` on Python 3.11+, and on older versions it is
`True` only if the `exceptiongroup` backport is installed (otherwise `False`,
and the group is re-raised untouched). The unwrap loop continues while the group
contains exactly one exception, so a group-of-one-of-one collapses fully.

### Where sillo uses it

`sillo._internals._middleware` wraps middleware execution in `collapse_excgroups`
so that a middleware raising a single exception is reported as that exception,
not as a noisy `BaseExceptionGroup`.

## Summary

| Helper | Purpose | Returns / Type |
|---|---|---|
| `is_async_callable(obj)` | Detect async callables (incl. `partial`, async `__call__`) | `bool` (type-guarded) |
| `AwaitableOrContextManager[T]` | Protocol: awaitable **and** async context manager | `Protocol` |
| `SupportsAsyncClose` | Protocol: has `async def close()` | `Protocol` |
| `AwaitableOrContextManagerWrapper(aw)` | Adapter: coroutine → awaitable + async CM | wrapper instance |
| `collapse_excgroups()` | Context manager unwrapping single-exception groups | context manager |
