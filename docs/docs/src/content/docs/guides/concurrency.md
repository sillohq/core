---
title: Concurrency
description: How one event loop serves many requests, what blocking it costs you, offloading sync work with run_in_threadpool, and the standard-library primitives sillo deliberately does not wrap.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Concurrency
  - tag: meta
    attrs:
      property: og:description
      content: How one event loop serves many requests, what blocking it costs you, offloading sync work with run_in_threadpool, and the standard-library primitives sillo deliberately does not wrap.
---

#  Thread Pool

`sillo.helpers.concurrency` provides one utility: `run_in_threadpool`. It moves a synchronous function call to a shared thread pool so the event loop isn't blocked.

For all other async concurrency patterns (`asyncio.gather`,
`asyncio.TaskGroup`, `asyncio.create_task`, `asyncio.Event`, `asyncio.Lock`)
use Python's standard library directly. They're well-designed, well-tested, and
already available.

---

##  run_in_threadpool

```python
from sillo.helpers.concurrency import run_in_threadpool
```

Moves a blocking or CPU-intensive function to a background thread and returns the result as an awaitable. The thread pool is shared globally and reused across calls.

###  Basic usage

```python
from sillo.helpers.concurrency import run_in_threadpool

def resize_image(image: bytes, width: int, height: int) -> bytes:
    # CPU-intensive work that would block the event loop
    ...

async def handler(request, response):
    thumbnail = await run_in_threadpool(resize_image, data, 200, 200)
    return {"thumbnail": thumbnail}
```

###  With keyword arguments

```python
result = await run_in_threadpool(some_func, arg1, arg2, key="value")
```

###  Error handling

Exceptions from the sync function propagate normally:

```python
from sillo.helpers.concurrency import run_in_threadpool

def risky() -> str:
    raise ValueError("boom")

async def handler(request, response):
    try:
        result = await run_in_threadpool(risky)
    except ValueError as e:
        response.status_code = 400
        return {"error": str(e)}
```

###  When to use

- File I/O (disk writes, uploads).
- CPU-bound work (image processing, PDF generation, data transformation).
- Calling synchronous libraries that don't offer an async interface.
- Any blocking call that would stall the event loop for more than a few milliseconds.

###  When not to use

- Pure async I/O: just `await` directly.
- Very fast sync operations (dict lookups, string formatting): the thread
  switch overhead costs more than just running them inline.
- `asyncio`-native libraries already handle this for you.


---

##  One loop, many requests

sillo runs on a single event loop per process. There is no thread per
request and no process per request; one loop interleaves thousands of
connections by switching between them at every `await`.

That is why an async framework handles high concurrency on modest hardware, a
request waiting on a database is a request costing nothing but memory. And it
is why one badly-behaved handler degrades everything: there is no other thread
to pick up the slack.

```python title="what await actually does"
async def handler(request, response):
    user = await User.get(id=1)      # loop runs other requests here
    rows = await fetch_orders()      # and here
    return response.json(...)        # and here
```

Between those `await`s, your code runs exclusively. That is the useful mental
model: **your handler is single-threaded until it awaits**, so you never need a
lock around code with no `await` in it, and you always need to think about
interleaving around code that does.

##  Blocking is the failure mode

Any synchronous call that takes real time stops the entire loop. Not that
request, every request in the process.

```python title="the arithmetic"
def resize(data):        # 200 ms of CPU
    ...

async def handler(request, response):
    thumb = resize(await request.body)      # blocks the loop for 200 ms
```

At 50 concurrent requests, the fiftieth waits ten seconds. Your metrics
show a slow endpoint; the cause is every *other* endpoint being slow at
the same time, which makes it look like an infrastructure problem.

The usual culprits are easy to spot once you know the shape: `requests`
instead of `httpx`, `time.sleep` instead of `asyncio.sleep`, a
synchronous database driver, `open()` on a large file, `json.loads` on a
very large payload, bcrypt hashing, image processing, and anything
importing `subprocess` without an async wrapper.

The rule of thumb: anything over about a millisecond of CPU, or any
blocking I/O at all, belongs off the loop.

##  `run_in_threadpool` in practice

The pool is shared across the whole process and reused between calls, so there
is no per-call thread creation cost, but there is a fixed number of threads,
and saturating them queues everything behind them.

Two consequences for how you use it.

**It is not free.** A thread hop costs tens of microseconds plus GIL
contention. Wrapping a dictionary lookup makes it slower, not faster. The
threshold is roughly a millisecond of work.

**It is a shared resource.** `sillo.mail`, any `run_in_executor` call in a
library you depend on, and your own offloaded work all draw from the same
default pool. A burst of slow file writes can starve an unrelated subsystem,
and the symptom ("email got slow when we added image uploads") looks unrelated
to its cause.

For sustained heavy offloading, give that workload its own executor
rather than sharing the default:

```python title="an isolated pool for one workload"
from concurrent.futures import ThreadPoolExecutor

image_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="images")


async def make_thumbnail(data: bytes) -> bytes:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(image_pool, resize, data, 200, 200)
```

Naming the threads pays for itself the first time you read a stack dump.

##  Concurrency within one request

Independent awaits should not be sequential. Three 100 ms calls take
300 ms in a row and 100 ms gathered:

```python title="gather independent work"
import asyncio

user, orders, prefs = await asyncio.gather(
    fetch_user(user_id),
    fetch_orders(user_id),
    fetch_preferences(user_id),
)
```

`return_exceptions=True` when a partial result is better than a failure,
without it, the first exception cancels the rest and you lose results you
already had.

`asyncio.TaskGroup` is the better choice on Python 3.11+ when the tasks
are genuinely a unit: it cancels siblings on failure and propagates a
single grouped exception, which is usually what you want for "all of this
or none of it".

Bound the fan-out. `gather` over a list of unknown length opens as many
connections as the list is long. A semaphore turns that into a controlled
concurrency:

```python title="bounded concurrency"
sem = asyncio.Semaphore(10)


async def fetch_one(item):
    async with sem:
        return await client.get(f"/items/{item}")


results = await asyncio.gather(*(fetch_one(i) for i in items))
```

##  Timeouts belong on every await that crosses a network

An `await` with no timeout can wait forever, and a task waiting forever
holds a connection, a database session, and the client on the other end.

```python title="bounding an external call"
async with asyncio.timeout(5):
    return await upstream.get("/slow")
```

`asyncio.timeout` (3.11+) cancels the operation when the budget expires.
`asyncio.wait_for` does the same on older versions. Either way, the
cancellation surfaces inside the awaited code as `CancelledError`, so cleanup
in a `finally` still runs, and code that swallows `CancelledError` breaks
cancellation for everyone above it.

Never catch `CancelledError` and continue. Re-raise it after cleaning up;
suppressing it is how a task becomes unkillable.

##  Choosing where work runs

Four places work can happen, with genuinely different costs.

| Where | Good for | Cost |
|---|---|---|
| The event loop | Async I/O: database, HTTP, sockets | Nothing while awaiting |
| A thread (`run_in_threadpool`) | Blocking I/O, sync libraries, short CPU work | A thread switch, GIL contention |
| A process (queue worker) | Heavy CPU, anything durable | Serialization, latency |
| Another machine | Anything that scales independently | Network, operational complexity |

The GIL is why threads help less than expected for CPU work. A thread running
pure Python holds the interpreter lock, so two CPU-bound threads do not run
twice as fast. They take turns. Threads help most for *blocking I/O*, where the
lock is released while waiting, and for libraries that release it themselves
(numpy, Pillow, and most C extensions do).

For genuinely CPU-bound Python, a separate process is the only real
answer. That is what a [queue worker](/guides/work/queue/) gives you, and
it comes with durability as a side effect.

##  Measuring it

Two signals tell you whether the loop is healthy.

**Event loop lag**, the delay between when a callback was scheduled and when it
ran. Under a millisecond is healthy; tens of milliseconds means something is
blocking. It is measurable in a few lines:

```python title="a loop-lag probe"
async def measure_lag(interval: float = 1.0):
    while True:
        start = time.monotonic()
        await asyncio.sleep(interval)
        lag = time.monotonic() - start - interval
        metrics.gauge("loop.lag_seconds", lag)
```

If that `sleep(1)` regularly takes 1.05 seconds, something is holding the
loop for 50 ms at a time.

**`asyncio` debug mode** logs any callback taking longer than 100 ms,
with a traceback pointing at the culprit. Run it in development:

```bash
PYTHONASYNCIODEBUG=1 uvicorn main:app --reload
```

It is too noisy and too slow for production, and it will find blocking
calls in an afternoon that would otherwise take a production incident to
notice.

##  What sillo deliberately does not wrap

Everything above is standard library. sillo provides `run_in_threadpool` and
nothing else, on purpose: `asyncio.gather`, `TaskGroup`, `create_task`,
`Semaphore`, `Lock`, `Event`, and `Queue` are well designed, well documented,
and already present. A framework wrapper would add a name to learn and a layer
to debug through.

The one exception is worth knowing: `asyncio.Lock` and friends are **not**
shared across processes. With multiple workers, a lock coordinates one
process's tasks and nothing else. Cross-process coordination needs Redis
or the database.

##  Fire-and-forget, carefully

`asyncio.create_task` schedules work without waiting for it, and has two
sharp edges.

**A task with no reference can be garbage collected mid-flight.** Keep
the reference somewhere that outlives the function:

```python
_background: set[asyncio.Task] = set()


def fire(coro):
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)
    return task
```

**Exceptions vanish silently** unless something retrieves them. Attach a done
callback that logs, or use [`BackgroundTask`](/guides/work/background/), which
handles both, and read that page's note about its registry before using it at
high volume.

##  What not to do

**Do not call blocking code in a handler.** It stalls every concurrent
request in the process.

**Do not use `time.sleep`.** Use `asyncio.sleep`.

**Do not use `requests`.** Use an async client.

**Do not `gather` an unbounded list.** Bound it with a semaphore.

**Do not await independent calls in sequence.** Gather them.

**Do not omit timeouts on network calls.** A hung call is a held
connection.

**Do not swallow `CancelledError`.** Re-raise after cleanup.

**Do not create a task without keeping a reference.** It can be collected.

**Do not use `asyncio.Lock` for cross-process coordination.** It is
per-process.

##  Related

- [Background Tasks](/guides/work/background/): managed fire-and-forget with
  result tracking
- [Work Overview](/guides/work/): moving heavy work out of the web process
  entirely
- [HTTP Client](/guides/http/client/): timeouts, pooling, and gathering
  upstream calls
- [Async helpers](/guides/helpers/async/): the utilities that complement these
  primitives
- [Middleware](/guides/middleware/): where a blocking call hurts most


##  Common mistakes and what they look like in production

**A sync database driver.** Every query blocks the loop for its full
duration. The symptom is throughput that does not improve with
concurrency: ten concurrent requests take ten times as long as one.

**`requests` in a handler.** Same shape, worse, because network latency
is longer than query latency. A 200 ms upstream call blocks 200 ms of
everyone's time.

**A `for` loop of awaits.** Correct, and often ten times slower than it
needs to be. Gather them.

**An unbounded `gather`.** Correct until the list gets long, then it
opens five thousand connections and something upstream starts refusing
them.

**A missing timeout.** Works until the day the upstream hangs instead of
erroring, and then every worker is stuck on it.

The through-line: none of these fail in development, where concurrency is
one. They all fail under load, which is why loop-lag monitoring earns its
place before you need it.


##  Testing concurrent code

Two tests catch most concurrency bugs before production does.

**A blocking-call detector.** Run your test suite with
`PYTHONASYNCIODEBUG=1` and fail the build on the warnings it emits. It
finds the synchronous library somebody imported without noticing.

**A concurrency test on shared state.** Anything mutated by more than one
request needs a test that mutates it from several tasks at once:

```python
async def test_counter_is_not_racy():
    await asyncio.gather(*(increment() for _ in range(100)))
    assert await get_count() == 100
```

A test that runs requests one at a time proves nothing about
interleaving, which is where these bugs live.
