---
title: Queue System
description: Complete production guide — every concept, method, parameter, edge case, and architectural decision in sillo.work.queue.
---

# Queue System (`sillo.work.queue`)

## What Problem Does This Solve?

When a user hits your API, they expect a response in milliseconds — not
seconds.  But many operations take seconds: sending emails, generating
reports, resizing images, calling slow third-party APIs.  If your
handler waits for all of these, your user waits too.  Worse, if the
handler crashes mid-operation, the work is lost.

The queue system solves this by **decoupling work from the request**.
Instead of doing the work inside the handler, you describe what needs to
be done (a **Job**), push that description onto a **Connection**, and
respond to the user immediately.  A separate **Worker** process pulls
jobs and executes them — with automatic retry, timeout, and failure
logging.

This pattern is called "deferred execution" or "background processing."
Every major web framework has a version of it: Laravel Queues, Django-Q,
Celery, Sidekiq, Bull.  `sillo.work.queue` is Sillo's take — designed
to be deeply integrated with the framework's DI system, app lifecycle,
and typing conventions.

---

## System Architecture

### The Dispatch Path (Handler → Queue)

### The Worker Path (Queue → Execution)

┌─────────────────┐
│  HTTP Handler   │
│                 │
│  1. Build a Job instance
│  2. serializer.serialize(job) → JSON
│  3. connection.push("emails", json)
│  4. return 202 Accepted
└─────────────────┘
```

The handler never waits for the work to complete.  It builds a `Job`
object, converts it to a portable JSON string via the
`PayloadSerializer`, pushes it onto a `Connection`, and responds
immediately.  Total handler time: milliseconds.

### The Worker Path (Queue → Execution)

```
┌──────────────────┐
│  QueueWorker     │  Long-running process
│                  │
│  1. connection.pop("emails") → (id, json)
│  2. serializer.deserialize(json) → class + data
│  3. Import class, instantiate with **data
│  4. job.fire() → runs through middleware
│  5. connection.ack("emails", job_id)
└──────────────────┘
```

The worker loops forever: pop, decode, instantiate, execute through
middleware, ack.  If the job fails, retry with backoff.  If all retries
are exhausted, log to the failed job repository.

### Why Separate Processes?

You can run the worker in the same process as the HTTP server (using a
`SyncConnection`), but for production you run workers in separate
processes — or separate machines — connected by Redis.  This gives you:

- **Isolation** — a crashed worker doesn't take down the HTTP server
- **Scaling** — add more worker processes to handle more jobs
- **Resilience** — if a worker process dies, jobs stay safely in Redis

---

## Connections

A **Connection** is a named backend that stores serialized job payloads
between dispatch and execution.  Every connection must implement five
operations in the `QueueConnection` abstract class.

### The Five-Operation Contract

| Method | Args | Returns | Called By |
|---|---|---|---|
| `push` | `queue_name, payload, delay` | `str` (job ID) | Handler |
| `pop` | `queue_name, timeout` | `(str, str) \| None` | Worker |
| `size` | `queue_name` | `int` | Monitoring |
| `ack` | `queue_name, job_id` | `None` | Worker |
| `fail` | `queue_name, job_id, payload, exception` | `None` | Worker |

### SyncConnection — In-Process, Non-Persistent

Uses an `asyncio.PriorityQueue` internally.  Delayed jobs are held in a
time-sorted list and released when their delay expires.  All state is
lost on process restart.  Best for development and single-process
deployments.

```python
from sillo.work.queue import SyncConnection

conn = SyncConnection()

# Immediate:
job_id = await conn.push("emails", '{"to":"user@ex.com"}')

# Delayed 30 seconds:
await conn.push("emails", '{"to":"admin@ex.com"}', delay=30)

# Dequeue (blocks up to 5s):
result = await conn.pop("emails", timeout=5)
if result:
    popped_id, payload = result

# Monitoring:
pending = await conn.size("emails")
await conn.clear("emails")
```

### RedisConnection — Persistent, Cross-Process

Stores jobs in Redis.  Delayed jobs use sorted sets (scored by wake
time).  Active jobs use lists.  Workers block on `BRPOP` rather than
polling.  Jobs survive process restarts and can be consumed by workers
on different machines.

```python
from sillo.work.queue import RedisConnection

conn = RedisConnection(
    "redis://localhost:6379",
    prefix="myapp:queue:",    # all keys namespaced under this
)

await conn.push("critical", '{"priority":"high"}')
result = await conn.pop("critical", timeout=30)
```

**How Redis keys are structured:**

| Purpose | Key |
|---|---|
| Active jobs | `myapp:queue:emails` (Redis list) |
| Delayed jobs | `myapp:queue:emails:delayed` (sorted set) |

### ConnectionManager — The Broker

Registers named connections and provides access by name:

```python
from sillo.work.queue import ConnectionManager, SyncConnection, RedisConnection

mgr = ConnectionManager()
mgr.add("default", SyncConnection())
mgr.add("redis", RedisConnection("redis://localhost:6379"))

conn = mgr.connection("default")
conn = mgr.connection("redis")
# mgr.connection("unknown") → KeyError
```

---

## Jobs

A **Job** is a class that encapsulates one unit of work.

### Defining a Job

```python
from sillo.work.queue import Job

class SendWelcomeEmail(Job):
    queue = "emails"
    tries = 3
    timeout = 30
    backoff = 10
    delete_when_completed = True
    middleware = []

    def __init__(self, user_id: str, template: str = "welcome"):
        self.user_id = user_id
        self.template = template

    async def handle(self):
        user = await User.get(id=self.user_id)
        html = render_template(self.template, user=user)
        await mail_service.send(user.email, "Welcome!", html)

    async def failed(self, exception):
        await alert(f"Welcome email permanently failed for {self.user_id}: {exception}")
```

### Why Classes, Not Functions?

A class carries **state** (constructor arguments) and **metadata** (class
attributes) together.  When a worker deserializes a job from JSON, it
can reconstruct it completely: import the class, call the constructor
with the stored data, then call `handle()`.  Functions can't be
serialized portably.

### Class Attributes — Complete Reference

| Attribute | Type | Default | Description |
|---|---|---|---|
| `queue` | `str` | `"default"` | Which ConnectionManager name to dispatch to |
| `tries` | `int` | `1` | Total execution attempts. `1` = no retry |
| `timeout` | `float\|None` | `30.0` | Seconds before cancellation. `None` = no timeout |
| `backoff` | `int` | `0` | Seconds before first retry. Doubles each attempt |
| `delete_when_completed` | `bool` | `True` | Remove from queue after success |
| `middleware` | `list` | `[]` | Middleware instances, applied in list order |

### Dispatching

```python
# Immediate:
SendWelcomeEmail.dispatch("user-42")
SendWelcomeEmail.dispatch("user-42", template="vip")

# Delayed (seconds):
SendWelcomeEmail.dispatch_after(3600, "user-42")

# Synchronous — runs NOW, bypasses queue:
SendWelcomeEmail.dispatch_sync("user-42")

# Per-dispatch overrides:
SendWelcomeEmail.on_queue("critical").dispatch("user-1")
SendWelcomeEmail.on_connection(redis_conn).dispatch("user-2")

# Via helper:
from sillo.work.queue import dispatch
dispatch(SendWelcomeEmail, "user-99", template="beta")
```

### Real-World: Order Processing Pipeline

```python
class ValidateOrder(Job):
    queue = "orders"; tries = 2; timeout = 30
    def __init__(self, order_id): self.order_id = order_id
    async def handle(self):
        order = await Order.get(id=self.order_id)
        if not order.items: raise ValueError("Empty order")
        order.status = "validated"; await order.save()
        ProcessPayment.dispatch(order.id)  # chain to next step

class ProcessPayment(Job):
    queue = "payments"; tries = 3; timeout = 60
    def __init__(self, order_id): self.order_id = order_id
    async def handle(self):
        order = await Order.get(id=self.order_id)
        charge = await gateway.charge(order.total, order.currency,
            idempotency_key=f"order-{order.id}")
        order.payment_id = charge.id; order.status = "paid"
        await order.save()
        FulfillOrder.dispatch(order.id)

class FulfillOrder(Job):
    queue = "fulfillment"; tries = 5; timeout = 300
    def __init__(self, order_id): self.order_id = order_id
    async def handle(self):
        order = await Order.get(id=self.order_id)
        label = await shipping.create_label(order)
        order.status = "fulfilled"; order.tracking = label.tracking
        await order.save()

@app.post("/orders", request_model=CreateOrderForm)
async def create_order(request, response):
    order = await Order.create(...)
    ValidateOrder.dispatch(order.id)
    return response.json({"order_id": order.id, "status": "pending"}, status_code=202)
```

**Why three jobs instead of one?**  Each step can be retried
independently.  If the payment gateway is temporarily down, only
`ProcessPayment` fails and retries — validated orders aren't affected.
If fulfillment takes 5 minutes, it has its own timeout.  This is
"separation of concerns at the job level."

---

## Payload Serializer

### Why It Exists

Jobs are code.  Code can't be sent over a network.  The
`PayloadSerializer` converts a Job into a JSON string (for the queue)
and back (for the worker).  It encodes:

1. The fully-qualified class name (`"mymodule.SendWelcomeEmail"`)
2. Constructor keyword arguments (`{"user_id": "42", ...}`)
3. Metadata: `max_tries`, `timeout`, `delay`, `priority`, `queue`

### Why JSON, Not Pickle?

Pickle is Python-specific, unsafe (arbitrary code execution on
deserialization), and fragile across Python versions.  JSON is portable,
safe, and human-readable.  The trade-off: constructor arguments must be
simple types (strings, numbers, dicts, lists).  Complex objects should
be looked up by ID inside `handle()`.

```python
from sillo.work.queue import PayloadSerializer

serializer = PayloadSerializer()

# Encode:
payload = serializer.serialize(
    "mymodule.SendWelcomeEmail",
    {"user_id": "42", "template": "welcome"},
    max_tries=3, timeout=30, queue="emails",
)

# Decode:
data = serializer.deserialize(payload)
# → {"job_class": "mymodule.SendWelcomeEmail", "data": {...}, "max_tries": 3, ...}
```

---

## Workers

### QueueWorker

```python
from sillo.work.queue import QueueWorker, WorkerOptions, PayloadSerializer, MemoryFailedRepository

worker = QueueWorker(
    mgr,              # ConnectionManager — where to find queues
    PayloadSerializer(),
    MemoryFailedRepository(),
    options=WorkerOptions(
        concurrency=4,
        queues=["critical", "default", "emails"],
        timeout=60.0,
        sleep=3.0,
        max_jobs=1000,
        backoff=2.0,
    ),
)

await worker.run()
worker.pause(); worker.resume(); worker.stop()
```

### WorkerOptions — Every Parameter

| Parameter | Default | Meaning |
|---|---|---|
| `concurrency` | `4` | Parallel asyncio tasks pulling jobs |
| `queues` | `["default"]` | Queue names in priority order — index 0 checked first |
| `timeout` | `60.0` | Default per-job deadline. Job's `timeout` attr overrides |
| `sleep` | `3.0` | Wait when ALL queues empty before re-checking |
| `max_jobs` | `0` | Exit after N jobs (0 = unlimited). Use with process supervisor |
| `max_exec_time` | `0` | Exit after N seconds (0 = unlimited) |
| `backoff` | `0.0` | Default base retry delay. Job's `backoff` overrides |
| `memory_limit` | `128` | Exit if RSS exceeds N MB. Mitigates slow leaks |

### WorkerPool

Manages multiple QueueWorker instances:

```python
from sillo.work.queue import WorkerPool

email_worker = QueueWorker(mgr, serializer, repo,
    options=WorkerOptions(queues=["emails"], concurrency=4))

report_worker = QueueWorker(mgr, serializer, repo,
    options=WorkerOptions(queues=["reports"], concurrency=2, timeout=300))

pool = WorkerPool().add(email_worker).add(report_worker)
await pool.start()
await pool.shutdown()
```

---

## Middleware

Middleware wraps every execution attempt.  Each middleware is a class
with `__call__(self, handler)` returning a new async handler.

### Built-in

```python
from sillo.work.queue import QRetryMiddleware, QTimeoutMiddleware, QRateLimitMiddleware

class MyJob(Job):
    middleware = [
        QRetryMiddleware(max_attempts=10, base_delay=5.0, max_delay=300),
        QTimeoutMiddleware(seconds=60),
        QRateLimitMiddleware(max_jobs=5, per_seconds=60),
    ]
```

### Custom Middleware

```python
class TimingMiddleware:
    def __init__(self, registry): self.registry = registry
    def __call__(self, handler):
        async def wrapper():
            start = time.monotonic()
            try:
                result = await handler()
                self.registry.counter("job.success").inc()
                return result
            except Exception:
                self.registry.counter("job.failure").inc()
                raise
            finally:
                elapsed = (time.monotonic() - start) * 1000
                self.registry.histogram("job.duration_ms").observe(elapsed)
        return wrapper
```

---

## Failed Jobs

### MemoryFailedRepository

```python
from sillo.work.queue import MemoryFailedRepository

repo = MemoryFailedRepository()
await repo.log("emails", "job-123", "SendEmail", payload, traceback)
for fj in await repo.all(limit=20):
    print(f"{fj.job_class}: {fj.exception[:200]}")
await repo.forget("job-123")
await repo.flush()
```

### Batching & Chaining

```python
from sillo.work.queue import Batch, JobChain

# Batch — track a group of jobs:
batch = Batch("import", on_complete=lambda b: notify(f"{b.completed_count}/{b.total}"))
for user in users: batch.add(ImportUser.dispatch(user.id))
await batch.wait(timeout=600)

# Chain — run sequentially:
chain = JobChain()
chain.then(ValidateFile.dispatch("data.csv"))
chain.then(TransformFile.dispatch("data.csv"))
results = await chain.run()
```

---

## Custom Backend

Implement `QueueConnection` for any storage:

```python
from sillo.work.queue import QueueConnection

class PostgresBackend(QueueConnection):
    async def push(self, queue_name, payload, *, delay=0):
        await db.execute(
            "INSERT INTO jobs (queue, payload, available_at) "
            "VALUES ($1, $2, NOW() + interval '$3 seconds')",
            queue_name, payload, str(delay),
        )
        return str(uuid4())

    async def pop(self, queue_name, *, timeout=0):
        row = await db.fetchrow(
            "DELETE FROM jobs WHERE queue = $1 AND available_at <= NOW() "
            "ORDER BY available_at FOR UPDATE SKIP LOCKED LIMIT 1 "
            "RETURNING id, payload",
            queue_name,
        )
        return (row["id"], row["payload"]) if row else None

    async def size(self, queue_name):
        return await db.fetchval("SELECT COUNT(*) FROM jobs WHERE queue = $1", queue_name)

    async def clear(self, queue_name):
        await db.execute("DELETE FROM jobs WHERE queue = $1", queue_name)

    async def ack(self, queue_name, job_id): pass  # deleted on pop

    async def fail(self, queue_name, job_id, payload, exception):
        await db.execute("INSERT INTO failed_jobs (...) VALUES (...)")
```

**Key design:**
- `pop()` uses `DELETE ... RETURNING` + `FOR UPDATE SKIP LOCKED` to
  atomically claim a job — no two workers can get the same one.
- `ack()` is a no-op because the job was deleted on pop.  If the worker
  crashes before ack, the job is lost — but the `DELETE` was committed.
- For "at-least-once" delivery, move the job to a "processing" list on
  pop and delete on ack.
