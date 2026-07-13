---
title: Jobs
description: Dispatchable jobs with middleware, retry, batching, chaining, and failed job inspection.
---

# Jobs (`sillo.work.queue.job`)

A **Job** is a class that encapsulates one unit of deferred work.

## Defining a Job

```python
from sillo.work.queue import Job

class GenerateReport(Job):
    queue = "reports"; tries = 3; timeout = 300; backoff = 20

    def __init__(self, user_id: str, report_type: str):
        self.user_id = user_id; self.report_type = report_type

    async def handle(self):
        data = await query_builder(self.report_type).execute()
        pdf = await render_pdf(data)
        await storage.upload(f"reports/{self.user_id}/{self.report_type}.pdf", pdf)

    async def failed(self, exception):
        await notify_user(self.user_id, f"Report failed: {exception}")
```

## Class Attributes

| Attribute | Default | Description |
|---|---|---|
| `queue` | `"default"` | Target queue |
| `tries` | `1` | Max attempts |
| `timeout` | `30.0` | Seconds before kill |
| `backoff` | `0` | Retry delay (doubles) |
| `middleware` | `[]` | Middleware list |

## Dispatching

```python
GenerateReport.dispatch("user-42", "sales")
GenerateReport.dispatch_after(3600, "user-42", "inventory")
GenerateReport.dispatch_sync("user-42", "quick")
```

## Real-World: File Processing Pipeline

```python
class ValidateFile(Job):
    queue = "processing"; tries = 2; timeout = 30
    def __init__(self, file_id): self.file_id = file_id
    async def handle(self):
        file = await File.get(id=self.file_id)
        if file.size == 0: raise ValueError("Empty file")
        file.status = "validated"; await file.save()
        TransformFile.dispatch(self.file_id)

class TransformFile(Job):
    queue = "processing"; tries = 3; timeout = 120
    def __init__(self, file_id): self.file_id = file_id
    async def handle(self):
        file = await File.get(id=self.file_id)
        rows = await parser.parse(file.path, file.type)
        result = await File.create(data=json.dumps(await transformer.apply(rows)))
        LoadResult.dispatch(result.id)

class LoadResult(Job):
    queue = "processing"; tries = 2; timeout = 60
    def __init__(self, file_id): self.file_id = file_id
    async def handle(self):
        file = await File.get(id=self.file_id)
        await database.import_data(json.loads(file.data))
        file.status = "loaded"; await file.save()

@app.post("/upload")
async def upload(request, response):
    file = await File.create(...)
    ValidateFile.dispatch(file.id)
    return response.json({"file_id": file.id, "status": "queued"}, status_code=202)
```

## Middleware

```python
from sillo.work.queue import QRetryMiddleware, QTimeoutMiddleware

class MyJob(Job):
    middleware = [
        QRetryMiddleware(max_attempts=10, base_delay=5.0, max_delay=300),
        QTimeoutMiddleware(seconds=60),
    ]
```

## Batch & Chain

```python
from sillo.work.queue import Batch, JobChain

# Batch:
batch = Batch("import", on_complete=lambda b: notify(f"{b.completed_count}/{b.total}"))
for user in users: batch.add(ImportUser.dispatch(user.id))
await batch.wait(600)

# Chain:
chain = JobChain()
chain.then(ValidateFile.dispatch("data.csv"))
chain.then(TransformFile.dispatch("data.csv"))
results = await chain.run()
```

## Failed Jobs

```python
from sillo.work.queue import MemoryFailedRepository

repo = MemoryFailedRepository()
for fj in await repo.all(limit=50):
    print(f"{fj.job_class}: {fj.exception[:200]}")
await repo.forget("job-123"); await repo.flush()
```
