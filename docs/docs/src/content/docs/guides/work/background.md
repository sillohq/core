---
title: Background Tasks
description: Fire-and-forget tasks with result tracking, callbacks, drain, supervision, and sync wrapping.
---

# Background Tasks (`sillo.work.background`)

## Basic Usage

```python
from sillo.work.background import BackgroundTask

@app.post("/signup")
async def signup(request, response):
    user = await create_user(...)
    BackgroundTask.run(send_welcome_email, user.email, user.name)
    return response.json({"ok": True}, status_code=201)
```

## Result Tracking & Callbacks

```python
bt = BackgroundTask.run(
    process_upload, file_id,
    on_success=lambda r: notify(f"Done in {r.duration_ms}ms"),
    on_failure=lambda r: alert(f"Failed: {r.error}"),
    timeout=120,
    metadata={"file_id": file_id, "user_id": user_id},
)

await bt.wait(timeout=120)
bt.cancel()
print(bt.id, bt.name, bt.done, bt.elapsed, bt.to_dict())
```

## Monitoring & Drain

```python
BackgroundTask.count()   # {"total": 12, "running": 3, "done": 8, "pending": 1}

@app.on_shutdown
async def cleanup():
    result = await BackgroundTask.drain(timeout=10, cancel_remaining=True)
    logger.info("Drain: %r", result)
```

## Real-World: Bulk Export

```python
@app.post("/export", request_model=ExportForm)
async def start_export(request, response):
    export_id = await create_export(request.validated_data)

    BackgroundTask.run(
        execute_export, export_id,
        name=f"export-{export_id}",
        on_success=lambda r: mark_complete(export_id),
        on_failure=lambda r: mark_failed(export_id, r.error),
    )
    return response.json({"export_id": export_id, "status": "processing"}, status_code=202)

@app.get("/admin/tasks")
async def task_overview(request, response):
    return response.json(BackgroundTask.count())
```

## Supervisor — Auto-Restart

```python
from sillo.work.background import Supervisor, RestartPolicy

supervisor = Supervisor(
    fragile_api_call,
    RestartPolicy.EXPONENTIAL_BACKOFF,
    max_restarts=5, base_delay=1.0, max_delay=60.0,
)
await supervisor.start(api_key="secret")
supervisor.stop()
await supervisor.wait(5)
```

| Policy | Behavior |
|---|---|
| `NEVER` | Run once, never restart |
| `ALWAYS` | Always restart |
| `ON_FAILURE` | Restart on exception |
| `EXPONENTIAL_BACKOFF` | Restart with increasing delays |

## Sync Functions

```python
def heavy(x): return x * 2
bt = BackgroundTask.run_sync(heavy, 42)
result = await bt.wait()  # 84
```
