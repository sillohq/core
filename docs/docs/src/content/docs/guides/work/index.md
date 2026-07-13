---
title: Work — Tasks, Queues & Scheduling
description: Complete reference for sillo.work — background tasks, priority queues, worker pools, circuit breakers, cron scheduling, and custom backends.
---

# Work — Tasks, Queues & Scheduling

`sillo.work` is the background execution subsystem. It handles everything that
should not block an HTTP request: sending emails, processing uploads, calling
external APIs, running periodic cleanup, and fanning out work across worker
processes.

## Architecture

```
┌──────────────┐     put()      ┌──────────┐     dequeue     ┌──────────┐
│  Route       │ ─────────────→ │  Queue   │ ←───────────── │  Worker  │
│  Handler     │                │          │                │  (pool)  │
└──────────────┘                │ ┌──────┐ │                └──────────┘
                                │ │Backend│ │                     │
                                │ └──────┘ │                ┌────┴─────┐
                                └──────────┘                │ execute  │
                                                            │ retry    │
┌──────────────┐                                            │ DLQ      │
│  Scheduler   │── fires jobs ────────────────────────────→ │ circuit  │
│              │                                            └──────────┘
└──────────────┘
```

- **Queue** — accepts tasks from anywhere, stores them in a backend.
- **Backend** — persistence layer. `MemoryBackend` for dev, `RedisBackend` for prod.
- **Worker** — pool of concurrent consumers that pull from a queue and execute tasks.
- **Scheduler** — time-based trigger (cron/interval/one-shot) that fires functions.
- **BackgroundTask** — thin wrapper for fire-and-forget within a request handler.

All state lives in `app.state["work"]` after calling `setup_work(app)`.

---

## Setup

```python
from sillo import silloApp
from sillo.work import setup_work, MemoryBackend

app = silloApp()

work = setup_work(app)  # or with explicit backend:
work = setup_work(app, queue_backend=MemoryBackend(), queue_name="default")
```

`setup_work` is idempotent — calling it twice returns the same dict. It creates:

| Key | Value |
|---|---|
| `work["queue"]` | `Queue("default", backend=...)` |
| `work["scheduler"]` | `Scheduler()` (auto-started on app startup) |

From any handler: `request.app.state["work"]["queue"]`.

---

## Queue

The `Queue` is the entry point for all work. Every task passes through a queue
before execution.

### Creating a queue

```python
from sillo.work import Queue, MemoryBackend, RedisBackend, TaskPriority

# Development — in-process, no persistence
q = Queue("emails", backend=MemoryBackend())

# Development with bounded size
q = Queue("emails", backend=MemoryBackend(max_size=1000))

# Production — cross-process, persistent
q = Queue("emails", backend=RedisBackend("redis://localhost:6379"))

# With deduplication
q = Queue("emails", backend=RedisBackend(), dedup=True)
```

### Queue constructor parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | `"default"` | Logical queue name |
| `backend` | `MemoryBackend \| RedisBackend` | `MemoryBackend()` | Storage backend |
| `dedup` | `bool` | `False` | Enable task deduplication |
| `default_priority` | `TaskPriority` | `NORMAL` | Priority for tasks without explicit priority |

### Enqueuing tasks — `queue.put()`

```python
task = await queue.put(
    send_email,                   # async callable
    "user@example.com",           # *args forwarded to callable
    name="welcome-email",         # optional display name
    priority=TaskPriority.HIGH,   # CRITICAL | HIGH | NORMAL | LOW
    max_attempts=3,               # retry count (default 1 = no retry)
    dedup_key="email:42",         # dedup token if dedup=True
    timeout=30.0,                 # per-task timeout in seconds
    metadata={"user_id": "42"},   # arbitrary dict attached to result
    extra_arg="value",            # **kwargs forwarded to callable
)
```

`put()` returns a `Task` object immediately. The task has not executed yet —
it is merely enqueued. A Worker must call `await task.run()` later.

### Retrieving results — `queue.get_result()`

```python
result = await queue.get_result(task.id)
if result:
    print(result.ok, result.duration_ms, result.error)
```

Results are stored by the backend. `MemoryBackend` keeps them in a dict.
`RedisBackend` stores them with a 24-hour TTL.

### Queue stats — `queue.stats()`

```python
stats = await queue.stats()  # QueueStats
stats.size          # pending tasks
stats.completed     # total completed
stats.failed        # total failed
stats.oldest_age_ms # age of oldest pending task
```

### Queue lifecycle

```python
await queue.close()   # reject new tasks
await queue.flush()   # discard all pending tasks (Redis only)
```

---

## Worker

Workers are the engine. They pull tasks from a queue and execute them with
automatic retry, dead-letter routing, and circuit breaking.

### Creating a worker

```python
from sillo.work import Worker

worker = Worker(
    queue,
    concurrency=4,                    # parallel workers (goroutine-like)
    timeout=30.0,                     # per-task timeout
    graceful_timeout=10.0,            # shutdown grace period
    dead_letter_queue=Queue("dlq"),   # failed tasks go here
    circuit_breaker_threshold=10,     # failures before circuit opens
    circuit_breaker_window=60.0,      # rolling window for failure count
    circuit_breaker_recovery=30.0,    # seconds before testing recovery
)
```

### Worker constructor parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `queue` | `Queue` | required | Queue to pull from |
| `concurrency` | `int` | `4` | Number of parallel workers |
| `timeout` | `float` | `30.0` | Per-task execution timeout (seconds) |
| `graceful_timeout` | `float` | `10.0` | Seconds to wait for in-flight tasks on shutdown |
| `dead_letter_queue` | `Queue \| None` | `None` | Queue for permanently failed tasks |
| `circuit_breaker_threshold` | `int` | `10` | Failure count that trips the breaker |
| `circuit_breaker_window` | `float` | `60.0` | Rolling window in seconds |
| `circuit_breaker_recovery` | `float` | `30.0` | Seconds before attempting half-open |

### Lifecycle

```python
await worker.start()   # spawns concurrency workers
await worker.stop()    # graceful shutdown
await worker.stop(timeout=5.0)  # override grace period
```

Workers are typically started in `app.on_startup` and stopped in `app.on_shutdown`.
If `setup_work()` is used, only the worker needs manual lifecycle — the scheduler
is started/stopped automatically.

### Retry strategy

When a task fails (any exception), the worker:

1. Sleeps `2^(attempt-1)` seconds (capped at 60s).
2. Retries up to `task.max_attempts` total.
3. On final failure, increments `worker._failed` and optionally routes
   the task to `dead_letter_queue`.
4. The task's status transitions: `PENDING → RUNNING → RETRYING → RUNNING → ... → FAILED`.

### Circuit breaker state machine

```
CLOSED ──(failures >= threshold within window)──→ OPEN
  ↑                                                  │
  │                                   (recovery timeout elapsed)
  │                                                  ↓
  └──────────────────────(success)────── HALF_OPEN
```

- **CLOSED** — normal operation.
- **OPEN** — all tasks are immediately marked done (shedding load). No execution.
- **HALF_OPEN** — a single probe task is allowed through. If it succeeds, circuit
  returns to CLOSED. If it fails, circuit returns to OPEN and resets the timer.

```python
worker.stats  # WorkerStats(processed=142, failed=3, circuit=CircuitState.CLOSED, ...)
```

### Worker stats

```python
s = worker.stats
# WorkerStats:
#   processed: int       total successful executions
#   failed: int          total exhausted failures
#   active: int          currently executing tasks
#   workers: int         concurrency
#   circuit: CircuitState  CLOSED | OPEN | HALF_OPEN
#   uptime_seconds: float
s.to_dict()
```

---

## Scheduler

The scheduler runs functions on a time-based trigger. Three trigger types are
supported.

### Trigger types

**IntervalTrigger** — every N seconds.

```python
from sillo.work import IntervalTrigger

trigger = IntervalTrigger(seconds=3600)        # every hour
trigger = IntervalTrigger(seconds=60, jitter=5)  # every ~60s ± 5s jitter
```

**CronTrigger** — standard cron syntax.

```python
from sillo.work import CronTrigger

# ┌─ minute (0-59)
# │ ┌─ hour (0-23)
# │ │ ┌─ day (1-31)
# │ │ │ ┌─ month (1-12)
# │ │ │ │ ┌─ weekday (0-6, Sunday=0)
# │ │ │ │ │
trigger = CronTrigger("0 9 * * 1-5")     # 9 AM weekdays
trigger = CronTrigger("*/15 * * * *")     # every 15 minutes
trigger = CronTrigger("0 0 1 * *")        # midnight on the 1st
trigger = CronTrigger("30 8,12,18 * * *") # 8:30, 12:30, 18:30 daily
```

**DateTrigger** — fire once at a specific timestamp.

```python
from sillo.work import DateTrigger
import time

trigger = DateTrigger(at=time.time() + 300)  # 5 minutes from now
```

### Registering jobs

Decorator style:

```python
@scheduler.every(3600)
async def hourly_cleanup():
    ...

@scheduler.cron("0 9 * * 1-5")
async def weekday_report():
    ...
```

Imperative style:

```python
job = scheduler.schedule(
    my_func,
    IntervalTrigger(60),
    name="refresh-cache",
    args=(arg1,),
    kwargs={"key": "value"},
    max_instances=1,   # prevent overlapping runs
)

scheduler.pause(job.id)
scheduler.resume(job.id)
scheduler.remove(job.id)
```

### Job lifecycle

```python
job = scheduler.get("job-id")
job.status            # ACTIVE | PAUSED | COMPLETED | CANCELLED
job.next_run_time     # epoch float or None (one-shot completed)
job.to_dict()         # {id, name, status, runs, errors, next_run}
```

### Scheduler stats

```python
scheduler.stats
# SchedulerStats:
#   jobs_total, jobs_active, jobs_paused
#   runs_total, errors_total
```

---

## BackgroundTask

For fire-and-forget work within a request handler. Lighter than a Queue+Worker
but provides the same Task lifecycle and result tracking.

```python
from sillo.work import BackgroundTask

bt = BackgroundTask.run(send_email, user.email, user.name)
await bt.wait(timeout=30)
bt.cancel()
bt.done      # bool
bt.result    # TaskResult or None

# With completion callback
bt = BackgroundTask.run(process_file, path, on_done=lambda r: notify_user(r))
```

`BackgroundTask.instance` — class-level tracking:

```python
await BackgroundTask.drain(timeout=10.0)  # wait for all pending backgrounds
```

Multiple `BackgroundTask.run()` calls are tracked globally. `drain()` waits for
all currently registered tasks to finish within the timeout, then cancels any
remaining.

---

## Task Hooks

Every `Task` instance has four hook points. Hooks are called in registration order.
Exceptions in hooks are logged but never propagated — a broken hook does not
kill the worker.

```python
from sillo.work.task import Task

t = Task(send_email, "user@ex.com", name="welcome")

t.before(lambda task: logger.info("Starting %s", task.name))
t.after(lambda task: metrics.record("task.duration", task.result.duration_ms))

t.on_success(lambda result: notify_user(result))
t.on_failure(lambda result: sentry.capture(result.error))

await t.run()
```

---

## Middleware

Middleware wraps every task execution on a queue. Attach via `queue.use()`.

### Built-in middleware

```python
from sillo.work import TimeoutMiddleware, RateLimitMiddleware, LoggingMiddleware

queue.use(TimeoutMiddleware(30.0))
queue.use(RateLimitMiddleware(max_per_second=50, burst=10))
queue.use(LoggingMiddleware())
```

### Writing custom middleware

Any class implementing these methods qualifies:

```python
class MetricsMiddleware:
    def __init__(self, registry):
        self.registry = registry

    async def before_enqueue(self, task):
        self.registry.counter("task.enqueued").inc()

    async def before_execute(self, task):
        task.metadata["start_wall"] = time.time()

    async def after_execute(self, result):
        self.registry.counter("task.completed").inc()
        self.registry.histogram("task.duration_ms").observe(result.duration_ms)

    async def on_error(self, task, error):
        self.registry.counter("task.error").inc()
        self.registry.counter(f"task.error.{type(error).__name__}").inc()
```

---

## Backends

### MemoryBackend

Single-process, non-persistent. Uses a lock-protected min-heap. Tasks survive
as long as the process does. Perfect for development and single-process deployments.

```python
b = MemoryBackend(max_size=10000)  # optional cap
```

### RedisBackend

Persistent, multi-process. Uses Redis sorted sets. Workers block on `BZPOPMAX`
for efficient polling. Requires a task registry for cross-process function
reconstruction.

```python
b = RedisBackend(
    "redis://localhost:6379",
    prefix="myapp:work:",
    task_registry={"send_email": send_email, "process_file": process_file},
)
```

### Writing a custom backend

Implement the following async methods:

```python
class MyBackend:
    async def enqueue(self, task: Task) -> None: ...
    async def dequeue(self, queue_name: str, timeout: float | None = None) -> Task | None: ...
    async def store_result(self, result: TaskResult) -> None: ...
    async def get_result(self, task_id: str) -> TaskResult | None: ...
    async def queue_size(self, name: str) -> int: ...
    async def queue_stats(self, name: str) -> QueueStats: ...
    async def is_duplicate(self, queue_name: str, dedup_key: str) -> bool: ...
    async def clear_dedup(self, queue_name: str, dedup_key: str) -> None: ...
```

Then pass it to a Queue:

```python
queue = Queue("my-queue", backend=MyBackend())
```

---

## The `@task` Decorator

Tags an async function with metadata so `Queue.put` can introspect it.

```python
from sillo.work import task, TaskPriority

@task(name="send-welcome", priority=TaskPriority.HIGH, max_attempts=3, queue="emails", timeout=30.0)
async def send_welcome_email(email: str, name: str):
    ...
```

The decorator attaches: `_work_name`, `_work_priority`, `_work_max_attempts`,
`_work_queue`, `_work_timeout`, `_is_task`. These are read by `Queue.put` when
no explicit arguments are given.

---

## Production Patterns

### Pattern 1: Email worker

```python
email_queue = Queue("emails", backend=RedisBackend(), dedup=True)
email_worker = Worker(email_queue, concurrency=8, timeout=30.0)

@app.on_startup
async def start_email(): await email_worker.start()
@app.on_shutdown
async def stop_email(): await email_worker.stop()

@app.post("/signup")
async def signup(request, response):
    user = await create_user(...)
    await email_queue.put(
        send_welcome_email, user.email, user.name,
        dedup_key=f"welcome:{user.id}",
        metadata={"user_id": user.id},
    )
    return response.status(201)
```

### Pattern 2: Nightly cleanup with scheduler

```python
@scheduler.cron("0 3 * * *")  # 3 AM daily
async def nightly_cleanup():
    expired = await db.expire_sessions()
    orphaned = await db.clean_uploads()
    logger.info(f"Cleaned {expired} sessions, {orphaned} uploads")
```

### Pattern 3: Fan-out processing

```python
@app.post("/bulk-import")
async def bulk_import(request, response):
    data = await request.json()
    count = 0
    for row in data["items"]:
        await queue.put(process_row, row, metadata={"batch": data["batch_id"]})
        count += 1
    return response.json({"queued": count})
```

### Pattern 4: Circuit breaker with alerting

```python
worker = Worker(queue, circuit_breaker_threshold=5, circuit_breaker_window=30.0)

# In a health-check endpoint:
@app.get("/health")
async def health(request, response):
    s = worker.stats
    if s.circuit == CircuitState.OPEN:
        await alerting.send("Worker circuit is OPEN")
        return response.json({"status": "degraded"}, status_code=503)
    return response.json({"status": "ok"})
```

---

## Priority Reference

| Priority | Value | Use case |
|---|---|---|
| `CRITICAL` | 3 | Payment processing, security events |
| `HIGH` | 2 | User-facing notifications, webhooks |
| `NORMAL` | 1 | Default — data processing, emails |
| `LOW` | 0 | Analytics, cleanup, non-urgent work |

---

## Exception Reference

| Exception | When raised |
|---|---|
| `TaskError` / `WorkError` | Base class. Invalid state, missing result. |
| `TaskTimeout` | Task exceeded its time budget. |
| `TaskCancelled` | Task was explicitly cancelled. |
| `TaskRejected` | Queue refused the task (duplicate, full). |
| `QueueFull` | Backend capacity reached. |
| `BackendUnavailable` | Cannot reach Redis or other backend. |
| `CircuitBreakerOpen` | Worker circuit is open — requests shed. |
| `InvalidTrigger` | Cron expression is malformed. |

All exceptions carry `task_id` and `queue_name` attributes for structured logging.

---

## Stats Types

### QueueStats

```python
stats = await queue.stats()
# QueueStats:
#   name: str
#   size: int
#   completed: int
#   failed: int
#   oldest_age_ms: int
#   status: QueueHealth (HEALTHY | DEGRADED | STALLED)
stats.to_dict()
```

### WorkerStats

```python
s = worker.stats
# WorkerStats:
#   processed: int
#   failed: int
#   active: int
#   workers: int
#   circuit: CircuitState
#   uptime_seconds: float
s.to_dict()
```

### SchedulerStats

```python
s = scheduler.stats
# SchedulerStats:
#   jobs_total: int
#   jobs_active: int
#   jobs_paused: int
#   runs_total: int
#   errors_total: int
s.to_dict()
```

---

## Extending

### Custom Middleware

Implement any subset of the four hooks:

```python
class DistributedTracingMiddleware:
    async def before_enqueue(self, task): ...
    async def before_execute(self, task): ...
    async def after_execute(self, result): ...
    async def on_error(self, task, error): ...
```

### Custom Backend

Subclass or duck-type the backend protocol. Must be async. See the "Writing a
custom backend" section above.

### Custom Trigger

Implement a class with `next_fire(last_fire: float) -> float | None`:

```python
class DaylightTrigger:
    def __init__(self, hour):
        self.hour = hour
    def next_fire(self, last_fire):
        # complex logic...
        return next_timestamp
```

Then: `scheduler.schedule(my_job, DaylightTrigger(6))`

### Custom Priority Levels

`TaskPriority` is an `IntEnum`. Add new levels by subclassing or using raw ints
(higher = more urgent). The backend scoring formula uses `-priority * 1e12 + created_at`
to order tasks.

---

## Thread Safety

`sillo.work` is designed for `asyncio` event loops. `MemoryBackend` uses
`asyncio.Lock` for concurrent safety within a single loop. `RedisBackend` is
safe across processes via Redis atomic operations.

Do NOT share a `MemoryBackend` across multiple event loops or threads.
Use `RedisBackend` for multi-process deployments.
