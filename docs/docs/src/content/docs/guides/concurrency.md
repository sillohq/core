---
title: Thread Pool
description: Offload blocking or CPU-intensive work to a thread pool with run_in_threadpool so the event loop stays responsive.
head:
- tag: meta
  attrs:
    property: og:title
    content: Thread Pool in sillo
- tag: meta
  attrs:
    property: og:description
    content: Offload blocking work with run_in_threadpool — sillo's thread pool utility for sync functions in async handlers.
---

# Thread Pool

`sillo.utils.concurrency` provides one utility: `run_in_threadpool`. It moves a synchronous function call to a shared thread pool so the event loop isn't blocked.

For all other async concurrency patterns — `asyncio.gather`, `asyncio.TaskGroup`, `asyncio.create_task`, `asyncio.Event`, `asyncio.Lock` — use Python's standard library directly. They're well-designed, well-tested, and already available.

---

## run_in_threadpool

```python
from sillo.utils.concurrency import run_in_threadpool
```

Moves a blocking or CPU-intensive function to a background thread and returns the result as an awaitable. The thread pool is shared globally and reused across calls.

### Basic usage

```python
from sillo.utils.concurrency import run_in_threadpool

def resize_image(image: bytes, width: int, height: int) -> bytes:
    # CPU-intensive work that would block the event loop
    ...

async def handler(request, response):
    thumbnail = await run_in_threadpool(resize_image, data, 200, 200)
    return {"thumbnail": thumbnail}
```

### With keyword arguments

```python
result = await run_in_threadpool(some_func, arg1, arg2, key="value")
```

### Error handling

Exceptions from the sync function propagate normally:

```python
from sillo.utils.concurrency import run_in_threadpool

def risky() -> str:
    raise ValueError("boom")

async def handler(request, response):
    try:
        result = await run_in_threadpool(risky)
    except ValueError as e:
        response.status_code = 400
        return {"error": str(e)}
```

### When to use

- File I/O (disk writes, uploads).
- CPU-bound work (image processing, PDF generation, data transformation).
- Calling synchronous libraries that don't offer an async interface.
- Any blocking call that would stall the event loop for more than a few milliseconds.

### When not to use

- Pure async I/O — just `await` directly.
- Very fast sync operations (dict lookups, string formatting) — the thread switch overhead costs more than just running them inline.
- `asyncio`-native libraries already handle this for you.
