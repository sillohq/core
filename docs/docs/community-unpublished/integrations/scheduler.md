---
title: Scheduler
description: A built-in job scheduling system for sillo applications with cron-like capabilities.
---

# Scheduler

A built-in job scheduling system for sillo applications, providing interval-based, cron-based, and one-time job execution integrated with the application lifecycle and dependency injection.

## Features

- ⏱ **Three Trigger Types**: Interval, Cron, and DateTime (one-shot) triggers
- 🔄 **Lifecycle Integration**: Automatic start on app startup, graceful shutdown
- 💉 **Dependency Injection**: Injectable `SchedulerDepends()` for clean route handlers
- 🎯 **Job Management**: Add, remove, pause, resume, and list jobs at runtime
- 🛡 **Safety Guards**: Misfire grace time, max concurrent instances, coalescing
- 📊 **Job Introspection**: Status tracking, run counts, last error, next run time

## Installation

The scheduler is included in the `sillo-contrib` package:

```bash
uv add sillo-contrib
```

## Quick Start

### 1. Set Up the Scheduler

Initialize the scheduler with your sillo application:

```python
from sillo import SilloApp
from sillo_contrib.scheduler import setup_scheduler

app = SilloApp()
scheduler = setup_scheduler(app)
```

`setup_scheduler()` attaches the scheduler to `app.scheduler` and registers it to start automatically on app startup.

### 2. Define a Job

Any async function can be a scheduled job:

```python
import asyncio

async def my_task():
    """A periodic task that runs every 30 seconds."""
    print("tick")
```

### 3. Schedule the Job

Register the job with a trigger:

```python
from sillo_contrib.scheduler import IntervalTrigger

scheduler.add_job(my_task, IntervalTrigger(seconds=30))
```

## Trigger Types

### IntervalTrigger

Runs a job at fixed intervals.

```python
from sillo_contrib.scheduler import IntervalTrigger

# Every 30 seconds
IntervalTrigger(seconds=30)

# Every 5 minutes
IntervalTrigger(minutes=5)

# Every 2 hours
IntervalTrigger(hours=2)

# Every 1 day
IntervalTrigger(days=1)

# Combined: every 1 hour and 15 minutes
IntervalTrigger(hours=1, minutes=15)
```

**Parameters:**
- `seconds` — Number of seconds between runs (default `0`)
- `minutes` — Number of minutes between runs (default `0`)
- `hours` — Number of hours between runs (default `0`)
- `days` — Number of days between runs (default `0`)
- `start_now` — If `True` (default), the job runs immediately upon scheduling. Otherwise, it waits for the first interval to elapse.

At least one time unit must be provided, and the total interval must be greater than 0.

### CronTrigger

Runs a job based on a standard 5-field cron expression.

```python
from sillo_contrib.scheduler import CronTrigger

# Every minute
CronTrigger("* * * * *")

# Every hour at minute 0
CronTrigger("0 * * * *")

# Daily at midnight
CronTrigger("0 0 * * *")

# Every weekday at 9 AM
CronTrigger("0 9 * * 1-5")

# Every 15 minutes
CronTrigger("*/15 * * * *")
```

**Special aliases:**

| Alias | Equivalent |
|---|---|
| `@every_minute` | `* * * * *` |
| `@hourly` | `0 * * * *` |
| `@daily` | `0 0 * * *` |
| `@weekly` | `0 0 * * 0` |
| `@monthly` | `0 0 1 * *` |
| `@yearly` | `0 0 1 1 *` |

Each cron field supports exact values, wildcards (`*`), ranges (`1-5`), step values (`*/5`), and lists (`1,3,5`).

### DateTimeTrigger

Runs a job once at a specific date and time.

```python
from sillo_contrib.scheduler import DateTimeTrigger

# Run on December 25, 2026 at 10:30 AM UTC
DateTimeTrigger("2026-12-25T10:30:00")
```

Supported formats:
- `2026-12-25T10:30:00` (UTC assumed)
- `2026-12-25T10:30:00+00:00` (explicit timezone)
- `2026-12-25 10:30:00` (space separator, UTC assumed)
- `2026-12-25` (midnight UTC)

After the job runs once, its status is set to `COMPLETED`.

## Job Management

### Add a Job with Options

```python
from sillo_contrib.scheduler import IntervalTrigger

scheduler.add_job(
    my_task,
    IntervalTrigger(seconds=30),
    name="my_periodic_task",
    args=("arg1",),
    kwargs={"key": "value"},
    max_instances=3,           # Max concurrent runs of this job
    misfire_grace_time=30,     # Seconds before a missed run is skipped
    coalesce=True,             # Merge missed firings into one
    id="my-job-id"             # Explicit ID (auto-generated if omitted)
)
```

### List Jobs

```python
# All jobs
all_jobs = scheduler.get_jobs()

# Filter by status
from sillo_contrib.scheduler import JobStatus
active_jobs = scheduler.get_jobs(status=JobStatus.ACTIVE)
```

### Get a Single Job

```python
job = scheduler.get_job("my-job-id")
if job:
    print(f"Status: {job.status}")
    print(f"Last run: {job.last_run_time}")
    print(f"Next run: {job.next_run_time}")
    print(f"Run count: {job.total_run_count}")
```

### Pause and Resume

```python
scheduler.pause_job("my-job-id")   # Suspends execution
scheduler.resume_job("my-job-id")  # Resumes and recomputes next run
```

### Remove a Job

```python
removed = scheduler.remove_job("my-job-id")  # Returns True/False
```

## Dependency Injection

For a cleaner pattern in route handlers, use the injectable dependency:

```python
from sillo_contrib.scheduler import SchedulerDepends, IntervalTrigger

@app.post("/schedule-task")
async def schedule_task(
    request, response,
    scheduler_dep = SchedulerDepends()
):
    """Schedule a new task from an API endpoint."""

    data = await request.json

    async def process():
        # Your background logic here
        pass

    job = scheduler_dep.add_job(
        process,
        IntervalTrigger(seconds=data.get("interval", 60)),
        name=data.get("name", "api-scheduled-task")
    )

    return response.json({
        "job_id": job.id,
        "next_run": job.next_run_time
    })
```

The `SchedulerDepends()` exposes the same operations as `SchedulerManager`:
- `add_job(func, trigger, ...)` — Register a new job
- `remove_job(job_id)` — Remove a job
- `get_job(job_id)` — Look up a job
- `get_jobs(status=None)` — List jobs
- `pause_job(job_id)` / `resume_job(job_id)` — Pause/resume

## Configuration

Customize scheduler behavior with `SchedulerConfig`:

```python
from sillo_contrib.scheduler import setup_scheduler, SchedulerConfig

config = SchedulerConfig(
    timezone="UTC",
    max_concurrent_jobs=10,               # Global limit
    log_level=logging.INFO,
    job_defaults={
        "max_instances": 3,               # Per-job default
        "misfire_grace_time": 30,         # Seconds
        "coalesce": True,                 # Merge missed firings
    }
)

scheduler = setup_scheduler(app, config=config)
```

## Job Status Lifecycle

A job can be in one of the following states:

```python
from sillo_contrib.scheduler import JobStatus

JobStatus.ACTIVE     # Running and eligible to fire
JobStatus.PAUSED     # Temporarily suspended
JobStatus.COMPLETED  # Finished (one-shot DateTimeTrigger jobs)
JobStatus.FAILED     # Last execution raised an exception
JobStatus.CANCELLED  # Permanently removed
```

## Complete Example

```python
import asyncio
import logging
from sillo import SilloApp
from sillo.core.http import Request, Response
from sillo_contrib.scheduler import (
    setup_scheduler,
    SchedulerDepends,
    IntervalTrigger,
    CronTrigger,
    DateTimeTrigger,
)

app = SilloApp()

# --- Setup ---
scheduler = setup_scheduler(app)

# --- Jobs ---

async def every_minute():
    print("Runs every minute")

async def hourly_cleanup():
    print("Runs at the top of every hour")

async def one_off_greeting():
    print("Hello from the past!")

# --- Schedule ---
scheduler.add_job(every_minute, IntervalTrigger(seconds=60), name="minute_ticker")
scheduler.add_job(hourly_cleanup, CronTrigger("0 * * * *"), name="hourly_cleanup")
scheduler.add_job(one_off_greeting, DateTimeTrigger("2026-12-25T10:30:00"), name="xmas_greeting")

# --- Routes ---

@app.get("/jobs")
async def list_jobs(request: Request, response: Response, sd = SchedulerDepends()):
    jobs = sd.get_jobs()
    return response.json([
        {
            "id": j.id,
            "name": j.name,
            "status": j.status.value,
            "next_run": j.next_run_time,
            "run_count": j.total_run_count,
        }
        for j in jobs
    ])

@app.post("/jobs/{job_id}/pause")
async def pause_job(request: Request, response: Response, job_id: str, sd = SchedulerDepends()):
    ok = sd.pause_job(job_id)
    return response.json({"success": ok})

@app.post("/jobs/{job_id}/resume")
async def resume_job(request: Request, response: Response, job_id: str, sd = SchedulerDepends()):
    ok = sd.resume_job(job_id)
    return response.json({"success": ok})

@app.delete("/jobs/{job_id}")
async def remove_job(request: Request, response: Response, job_id: str, sd = SchedulerDepends()):
    ok = sd.remove_job(job_id)
    return response.json({"success": ok})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Best Practices

1. **Keep jobs short** — Long-running jobs block the scheduler tick from checking other jobs. Offload heavy work to [Background Tasks](/community/integrations/tasks).
2. **Handle errors** — Wrap job logic in try/except. Unhandled exceptions mark the job as `FAILED`.
3. **Use `coalesce`** — When a job misses multiple firings (e.g., system was down), coalescing prevents a backlog of redundant runs.
4. **Set `misfire_grace_time`** — Prevents stale jobs from running if the scheduler was delayed.
5. **Name your jobs** — Meaningful names make debugging and monitoring easier.

Built with ❤️ by the [@sillohq](https://github.com/sillohq) community.
