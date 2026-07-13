---
title: Work Overview
description: Complete background processing in sillo — queues, jobs, events, scheduling, and background tasks.
---

# Work — Background Processing & Scheduling

`sillo.work` is the background execution layer of the framework.  Every
operation that should not block an HTTP response lives here.

## When to Use Each Component

| Need | Component | Module |
|---|---|---|
| Defer work to a separate process | Queue + Worker | `sillo.work.queue` |
| Run on a schedule | Scheduler | `sillo.work.scheduler` |
| Decouple side effects | Event dispatcher | `sillo.work.queue.events` |
| Fire-and-forget in handler | BackgroundTask | `sillo.work.background` |
| Track a group of jobs | Batch | `sillo.work.queue` |
| Run jobs sequentially | JobChain | `sillo.work.queue` |

## Architecture

```
HTTP Handler → Job.dispatch() → Connection (Sync/Redis) → QueueWorker → Job.handle()
                                                              ↓
SchedulerManager → ScheduledJob → trigger.next_fire() → func()
EventDispatcher → Event → listeners (priority ordered)
BackgroundTask.run() → asyncio task (fire-and-forget)
```

## Quick Start

```python
from sillo import silloApp
from sillo.work import setup_work
from sillo.work.scheduler import setup_scheduler
from sillo.work.background import BackgroundTask

app = silloApp()
work = setup_work(app)
scheduler = setup_scheduler(app)

@app.post("/signup")
async def signup(request, response):
    user = await create_user(...)
    BackgroundTask.run(send_welcome_email, user.email)
    return response.json({"ok": True}, status_code=201)

@scheduler.cron("0 9 * * 1-5")
async def daily_report(): ...

# DI access from any handler:
sched = request.app.state["scheduler"]
```

## Guides

- [Queue System](/guides/work/queue/) — connections, jobs, serializers, workers, middleware, batches, chains, failed jobs, custom backends
- [Scheduler](/guides/work/scheduler/) — triggers, jobs, manager, middleware, custom triggers
- [Events](/guides/work/events/) — typed pub/sub, priority, wildcards, propagation
- [Jobs](/guides/work/jobs/) — dispatchable jobs, middleware, batching, chaining
- [Background Tasks](/guides/work/background/) — fire-and-forget, callbacks, drain, supervisor
