---
title: Scheduler
description: Deep reference for sillo.work.scheduler — every trigger type, job lifecycle, manager API, middleware pattern, and custom extension point.
---

# Scheduler (`sillo.work.scheduler`)

The scheduler runs callables on time-based triggers inside your
application process.  Unlike the queue system which dispatches work to
separate worker processes, the scheduler runs jobs in-process using
asyncio — ideal for periodic maintenance, cache warming, data
sync, and health checks.

---

## Architecture

The scheduler has three layers:

1. **Triggers** — pure functions that answer "when should this fire next?"
2. **ScheduledJob** — binds a callable to a trigger with execution tracking
3. **SchedulerManager** — owns all jobs, runs the ticker loop, integrates
   with the app lifecycle via `app.state["scheduler"]`

The ticker never blocks — `create_task` spawns execution and returns
immediately.  Resolution is 1 second.

---

## Setup

```python
from sillo import silloApp
from sillo.work.scheduler import setup_scheduler

app = silloApp()
scheduler = setup_scheduler(app)
# Auto-starts on app startup. Stores in app.state["scheduler"]
```

---

## Triggers

Every trigger implements exactly one method:
`next_fire(last_fire: float) -> float | None`.  Given the timestamp of
the last execution, it returns the next fire time (epoch seconds) or
`None` if the trigger is exhausted.

Four triggers ship in the box.

### IntervalTrigger

Fires every `seconds` with optional `jitter` (random offset).  Jitter
spreads load when many jobs share the same interval — preventing
thundering herds.

```python
from sillo.work.scheduler import IntervalTrigger

# Every 5 minutes, ±30s jitter:
IntervalTrigger(seconds=300, jitter=30)

# Every hour, exactly:
IntervalTrigger(seconds=3600)

# Every 10 seconds, no jitter:
IntervalTrigger(seconds=10)
```

### CronTrigger

Standard 5-field cron expression with timezone support.  The parser
supports wildcards (`*`), ranges (`1-5`), steps (`*/15`, `1-30/5`),
lists (`1,3,5`), `L` (last of month/weekday), `W` (nearest weekday),
and `#` (nth weekday, e.g. `2#3` = 3rd Monday).

```python
from sillo.work.scheduler import CronTrigger

# Every weekday at 9 AM Eastern:
CronTrigger("0 9 * * 1-5", timezone="America/New_York")

# Every 15 minutes:
CronTrigger("*/15 * * * *")

# Midnight on the 1st of every month:
CronTrigger("0 0 1 * *")

# 8:30 AM and 5:30 PM daily:
CronTrigger("30 8,17 * * *")

# Every 2 hours between 8 AM and 6 PM, weekdays:
CronTrigger("0 8-18/2 * * 1-5")
```

**Cron field reference:**

| Position | Field | Range | Special characters |
|---|---|---|---|
| 1 | Minute | 0-59 | `*` `,` `-` `/` |
| 2 | Hour | 0-23 | `*` `,` `-` `/` |
| 3 | Day | 1-31 | `*` `,` `-` `/` `L` `W` |
| 4 | Month | 1-12 | `*` `,` `-` `/` |
| 5 | Weekday | 0-6 (Sun=0) | `*` `,` `-` `/` `L` `#` |

### DateTrigger

One-shot — fires once at the given epoch timestamp, then never again.
`next_fire()` returns `None` after the first fire, which causes the job
to transition to `JobStatus.COMPLETED`.

```python
from sillo.work.scheduler import DateTrigger
import time

# 5 minutes from now:
DateTrigger(at=time.time() + 300)

# Specific future date:
from datetime import datetime, timezone
target = datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp()
DateTrigger(at=target)
```

### CompoundTrigger

Combine multiple triggers with AND or OR logic:

- **OR** — fire whenever ANY child trigger is due.  Equivalent to a union
  of schedules.  Example: "weekday mornings OR weekend afternoons."
- **AND** — fire only when ALL child triggers are simultaneously due.
  Rarely used but useful for precise alignment (e.g. "the 1st of the
  month AND a weekday").

```python
from sillo.work.scheduler import CompoundTrigger, CompoundLogic, CronTrigger

# Fire at 9 AM weekdays OR 2 PM weekends:
trigger = CompoundTrigger(
    triggers=[CronTrigger("0 9 * * 1-5"), CronTrigger("0 14 * * 0,6")],
    logic=CompoundLogic.OR,
)
```

---

## ScheduledJob

Binds a callable to a trigger with execution tracking and concurrency
control.

```python
from sillo.work.scheduler import ScheduledJob

job = ScheduledJob(
    my_async_func,
    CronTrigger("*/30 * * * *"),
    name="sync-api",
    args=(api_key,),
    kwargs={"endpoint": "/contacts"},
    max_instances=1,      # prevent overlapping runs
    coalesce=True,        # skip if previous run still active
    middleware=[timeout_mw, retry_mw],
)

job.compute_next()        # calculate first fire time
await job.run()           # execute manually
print(job.to_dict())      # serialized metadata
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `func` | `Callable` | required | Async callable to execute |
| `trigger` | `Trigger` | required | One of the trigger instances above |
| `name` | `str \| None` | `func.__name__` | Display name |
| `args` | `tuple` | `()` | Positional arguments |
| `kwargs` | `dict \| None` | `{}` | Keyword arguments |
| `max_instances` | `int` | `1` | Max concurrent runs. `0` = unlimited |
| `coalesce` | `bool` | `True` | Skip if previous run is still active |
| `middleware` | `list \| None` | `None` | Middleware factories |
| `id` | `str \| None` | auto | Explicit job ID |

**`max_instances` and `coalesce` work together:**  If a job takes 10
minutes but fires every 5 minutes, the second fire would queue up while
the first is still running.  With `max_instances=1, coalesce=True`, the
second fire is skipped entirely.

---

## SchedulerManager

The central coordinator.  Owns all jobs, runs a 1-second ticker loop,
and integrates with the app lifecycle.

### Registration

```python
from sillo.work.scheduler import SchedulerManager

s = SchedulerManager()

# Decorator style — concise and declarative:
@s.every(3600)
async def hourly_cleanup(): ...

@s.cron("0 9 * * 1-5")
async def weekday_report(): ...

# Imperative style — full control:
job = s.schedule(
    my_func,
    IntervalTrigger(60),
    name="refresh-cache",
    args=(arg1,),
    max_instances=1,
    coalesce=True,
    middleware=[retry_middleware],
)
```

### Managing Jobs

```python
s.pause(job.id)           # stop firing, preserve state
s.resume(job.id)          # resume a paused job
s.remove(job.id)          # permanently remove

job = s.get("some-id")    # lookup by ID
print(job.to_dict())

# List with filters:
s.list()                       # all jobs
s.list(JobStatus.ACTIVE)       # active only
s.list(JobStatus.PAUSED)       # paused only
```

### Stats

```python
s.stats.to_dict()
# {"jobs_total": 5, "jobs_active": 3, "jobs_paused": 1,
#  "runs": 1420, "errors": 3, "uptime": 86400}
```

### Real-World: Admin Dashboard

```python
@app.get("/admin/scheduler")
async def scheduler_dashboard(request, response):
    sched = request.app.state["scheduler"]
    return response.json({
        "stats": sched.stats.to_dict(),
        "jobs": [j.to_dict() for j in sched.list()],
    })

@app.post("/admin/scheduler/{job_id}/pause")
async def pause_job(request, response, job_id):
    sched = request.app.state["scheduler"]
    if not sched.pause(job_id):
        return response.json({"error": "Not found"}, status_code=404)
    return response.json({"paused": True})

@app.post("/admin/scheduler/{job_id}/resume")
async def resume_job(request, response, job_id):
    sched = request.app.state["scheduler"]
    if not sched.resume(job_id):
        return response.json({"error": "Not found"}, status_code=404)
    return response.json({"resumed": True})

@app.delete("/admin/scheduler/{job_id}")
async def remove_job(request, response, job_id):
    sched = request.app.state["scheduler"]
    if not sched.remove(job_id):
        return response.json({"error": "Not found"}, status_code=404)
    return response.json({"removed": True})
```

---

## Middleware

Per-job middleware factories receive `(handler, job)` and return a new
handler.

### Built-in

```python
from sillo.work.scheduler.middleware import (
    timeout_middleware, retry_middleware, rate_limit_middleware,
)

job = scheduler.schedule(
    fragile_api,
    IntervalTrigger(60),
    middleware=[timeout_middleware, retry_middleware],
)
```

### Custom

```python
async def logging_middleware(handler, job, *, extra=""):
    async def wrapper():
        logger.info("Job %s starting (run #%d)", job.name, job._runs + 1)
        try:
            return await handler()
        finally:
            logger.info("Job %s finished", job.name)
    return wrapper

job = scheduler.schedule(my_task, interval,
    middleware=[logging_middleware])
```

---

## Custom Trigger

Implement `next_fire(last_fire: float) -> float | None`:

```python
class BusinessHoursTrigger:
    """Fire every interval, but only 9 AM – 5 PM on weekdays."""
    def __init__(self, interval: int = 3600):
        self.interval = interval

    def next_fire(self, last_fire: float) -> float | None:
        from datetime import datetime, timedelta
        now = datetime.now()
        if 9 <= now.hour < 17 and now.weekday() < 5:
            return time.time() + self.interval
        # Skip to next business day at 9 AM:
        target = now.replace(hour=9, minute=0, second=0) + timedelta(days=1)
        while target.weekday() >= 5:
            target += timedelta(days=1)
        return target.timestamp()

scheduler.schedule(work_task, BusinessHoursTrigger(1800))
```
