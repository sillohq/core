---
title: Concurrency in Nexios
description: Learn how to use concurrency utilities in Nexios
head:
  - - meta
    - property: og:title
      content: Concurrency in Nexios
  - - meta
    - property: og:description
      content: Learn how to use concurrency utilities in Nexios
---
# Concurrency Utilities

Nexios provides concurrency utilities to handle common async patterns in web applications. Here's how to use them effectively in your route handlers.

## TaskGroup - Parallel API Calls

Perfect for aggregating data from multiple sources:

```python
from nexios import NexiosApp
from nexios.utils.concurrency import TaskGroup
import httpx

app = NexiosApp()

@app.get("/dashboard")
async def get_dashboard(req, res):
    async with TaskGroup() as group:
        # Fetch different data sources in parallel
        user_task = group.create_task(fetch_user_data(req.query.get("user_id")))
        posts_task = group.create_task(fetch_user_posts(req.query.get("user_id")))
        stats_task = group.create_task(fetch_user_stats(req.query.get("user_id")))
        
        # All API calls run concurrently
        user = await user_task
        posts = await posts_task
        stats = await stats_task
        
        return {
            "user": user,
            "recent_posts": posts,
            "statistics": stats
        }

async def fetch_user_data(user_id: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.example.com/users/{user_id}")
        return r.json()
```

## Run in ThreadPool - Heavy Processing

Use for CPU-intensive operations in your handlers:

```python
from nexios.utils.concurrency import run_in_threadpool
from PIL import Image
import io

@app.post("/upload")
async def upload_image(req, res):
    file_data = await req.files
    image = Image.open(io.BytesIO(file_data.get("image")))
    
    # Process image in thread pool to avoid blocking
    thumbnail = await run_in_threadpool(
        create_thumbnail, 
        image, 
        size=(200, 200)
    )
    
    # Save and return URL
    await run_in_threadpool(
        thumbnail.save,
        f"static/thumbnails/{file_data.filename}"
    )
    
    return {"thumbnail_url": f"/thumbnails/{file_data.filename}"}

def create_thumbnail(image: Image.Image, size: tuple):
    return image.resize(size, Image.LANCZOS)
```

## Run Until First Complete - Redundancy

Great for failover and timeout scenarios:

```python
from nexios.utils.concurrency import run_until_first_complete
import asyncio

@app.get("/search")
async def search(req, res):
    query = req.query.get("q")
    
    try:
        # Try multiple search services, use first response
        result = await run_until_first_complete(
            lambda: search_primary_db(query),
            lambda: search_backup_db(query),
            (lambda: search_fallback(query), {"timeout": 2.0})
        )
        return {"results": result}
    except TimeoutError:
        return {"error": "Search timed out"}, 504

async def search_primary_db(query: str):
    # Simulate primary database search
    await asyncio.sleep(0.5)  # Network delay
    return ["result1", "result2"]

async def search_backup_db(query: str):
    # Backup database might be slower
    await asyncio.sleep(1)
    return ["backup1", "backup2"]

async def search_fallback(query: str, timeout: float):
    # Last resort, with timeout
    await asyncio.sleep(timeout + 0.1)  # Will timeout
    return ["fallback"]
```

## Background Tasks - Async Processing

Perfect for handling long-running tasks without blocking the response:

```python
from nexios.utils.concurrency import create_background_task

@app.post("/send-newsletter")
async def send_newsletter(req, res):
    newsletter_data = await req.json
    
    async def process_newsletter():
        subscribers = await fetch_subscribers()
        for subscriber in subscribers:
            try:
                await send_email(subscriber, newsletter_data)
                await update_status(subscriber, "sent")
            except Exception as e:
                await log_error(subscriber, e)
    
    # Start processing in background
    task = asyncio.create_task(process_newsletter())
    app._background_tasks.add(task)
    task.add_done_callback(app._background_tasks.discard)
    
    return {"status": "Newsletter sending started"}

@app.get("/tasks/status")
async def get_tasks_status(req, res):
    if not hasattr(app, '_background_tasks'):
        return {"active_tasks": 0}
    
    return {
        "active_tasks": len([t for t in app._background_tasks if not t.done()])
    }
```

## AsyncLazy - Cached Computations

Useful for expensive operations that can be reused:

```python
from nexios.utils.concurrency import AsyncLazy
import pandas as pd

# Create lazy loaded analytics
daily_stats = AsyncLazy(lambda: run_in_threadpool(calculate_daily_stats))

@app.get("/analytics/daily")
async def get_daily_analytics(req, res):
    try:
        # Will compute only once and cache
        stats = await daily_stats.get()
        return stats
    except Exception as e:
        return {"error": str(e)}, 500

def calculate_daily_stats():
    # Expensive computation
    df = pd.read_csv("large_dataset.csv")
    return df.groupby('date').agg({
        'views': 'sum',
        'clicks': 'sum',
        'conversions': 'sum'
    }).to_dict()

# Reset cache every day
@app.on_startup
async def setup_cache_reset():
    async def reset_daily():
        while True:
            await asyncio.sleep(86400)  # 24 hours
            daily_stats.reset()
    
    task = asyncio.create_task(reset_daily())
    app._background_tasks.add(task)
    task.add_done_callback(app._background_tasks.discard)
```

## Error Handling Best Practices

Always handle errors appropriately in your handlers:

```python
@app.get("/protected-operation")
async def protected_operation(req, res):
    try:
        async with TaskGroup() as group:
            task1 = group.create_task(risky_operation1())
            task2 = group.create_task(risky_operation2())
            
            result1 = await task1
            result2 = await task2
            
        return {"status": "success", "data": [result1, result2]}
        
    except asyncio.CancelledError:
        # Handle cancellation
        await cleanup_resources()
        return {"error": "Operation cancelled"}, 499
        
    except Exception as e:
        # Log error and return appropriate response
        await log_error(e)
        return {"error": "Internal error"}, 500
```

## Performance Tips

1. Use `TaskGroup` for parallel API calls or database queries
2. Move image/video processing to `run_in_threadpool`
3. Implement caching with `AsyncLazy` for expensive database queries
4. Use `run_until_first_complete` for redundant data sources
5. Handle long-running tasks with background processing 