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
# ⚡ Concurrency Utilities

Nexios provides powerful concurrency utilities to handle common async patterns in web applications. These utilities help you build performant, scalable applications by efficiently managing concurrent operations, parallel processing, and resource utilization.

## 🎯 Why Use Concurrency in Web Applications?

Modern web applications often need to:
- Fetch data from multiple APIs simultaneously
- Process files or images without blocking other requests
- Handle redundant data sources with failover capabilities
- Cache expensive computations for better performance
- Manage background tasks efficiently

Nexios concurrency utilities make these patterns simple and reliable.

## 🚀 TaskGroup - Parallel API Calls

`TaskGroup` allows you to run multiple async operations concurrently and wait for all of them to complete. This is perfect for aggregating data from multiple sources, making parallel database queries, or calling multiple APIs simultaneously.

**Key Benefits:**
- Significantly reduces total response time
- Automatic error handling and cleanup
- Structured concurrency pattern
- Exception propagation from any failed task

```python
from nexios import NexiosApp
from nexios.utils.concurrency import TaskGroup
import httpx

app = NexiosApp()

@app.get("/dashboard")
async def get_dashboard(req, res):
    async with TaskGroup() as group:
        # Fetch different data sources in parallel
        user_task = group.create_task(fetch_user_data(req.query_params.get("user_id")))
        posts_task = group.create_task(fetch_user_posts(req.query_params.get("user_id")))
        stats_task = group.create_task(fetch_user_stats(req.query_params.get("user_id")))
        
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

## 🏭 Run in ThreadPool - Heavy Processing

`run_in_threadpool` moves CPU-intensive or blocking operations to a separate thread pool, preventing them from blocking the main event loop. This is essential for maintaining responsiveness in async applications.

**When to Use:**
- Image/video processing
- File I/O operations
- CPU-intensive computations
- Synchronous library calls
- Database operations with sync drivers

**Performance Impact:** Without thread pools, a single heavy operation can block all other requests. With thread pools, your application stays responsive.

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

## 🏆 Run Until First Complete - Redundancy

`run_until_first_complete` runs multiple async operations concurrently but returns as soon as the first one completes successfully. This pattern is excellent for implementing redundancy, failover mechanisms, and timeout handling.

**Use Cases:**
- Multiple database replicas (primary/backup)
- Redundant API endpoints
- Timeout implementations
- A/B testing different services
- Geographic load balancing

```python
from nexios.utils.concurrency import run_until_first_complete
import asyncio

@app.get("/search")
async def search(req, res):
    query = req.query_params.get("q")
    
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


## 🔄 Background Tasks

`create_background_task` creates and returns an asyncio task that runs independently. This is useful for fire-and-forget operations or when you need to start a task but don't want to wait for it immediately.

**Use Cases:**
- Sending notifications after a response
- Logging analytics data
- Background cleanup operations
- Periodic maintenance tasks

```python
from nexios.utils.concurrency import create_background_task
import asyncio

@app.post("/send-notification")
async def send_notification(req, res):
    data = await req.json()
    
    # Send immediate response
    response = {"status": "notification_queued", "recipient": data["recipient"]}
    
    # Start background task (don't await)
    task = create_background_task(send_email_notification(data))
    
    return response

async def send_email_notification(data: dict):
    """Background task for sending email"""
    try:
        await asyncio.sleep(2)  # Simulate email sending delay
        # Actual email sending logic here
        await log_notification_sent(data["recipient"])
    except Exception as e:
        await log_notification_error(data["recipient"], str(e))
```

**Task Management:**
```python
# Create and manage tasks manually
task = create_background_task(long_running_operation())

# Check if task is done
if task.done():
    result = task.result()

# Cancel if needed
task.cancel()

# Wait for completion when ready
await task
```

## 💾 AsyncLazy - Cached Computations

`AsyncLazy` provides lazy evaluation with caching for expensive async operations. The computation runs only once when first accessed, and subsequent calls return the cached result.

**Perfect For:**
- Expensive database aggregations
- Configuration loading
- External API calls for reference data
- Machine learning model loading
- File parsing and processing

**Memory Management:** Results are cached until explicitly reset, so consider memory usage for large datasets.

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

## ⚠️ Error Handling Best Practices

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

## �  Common Patterns and Combinations

### Parallel Processing with Fallback

Combine `TaskGroup` with `run_until_first_complete` for robust data fetching:

```python
@app.get("/user/{user_id}/profile")
async def get_user_profile(req, res):
    user_id = req.path_params["user_id"]
    
    async with TaskGroup() as group:
        # Try multiple sources for user data
        user_task = group.create_task(
            run_until_first_complete(
                lambda: fetch_from_primary_db(user_id),
                lambda: fetch_from_cache(user_id),
                lambda: fetch_from_backup_db(user_id)
            )
        )
        
        # Get preferences in parallel
        prefs_task = group.create_task(get_user_preferences(user_id))
        
        user_data = await user_task
        preferences = await prefs_task
        
    return {"user": user_data, "preferences": preferences}
```

### Background Processing with Thread Pools

Handle file uploads with immediate response and background processing:

```python
from nexios.utils.concurrency import run_in_threadpool
import asyncio

@app.post("/upload/document")
async def upload_document(req, res):
    files = await req.files
    document = files.get("document")
    
    # Save file immediately
    file_path = f"uploads/{document.filename}"
    await run_in_threadpool(save_file, document, file_path)
    
    # Start background processing (don't await)
    asyncio.create_task(process_document_background(file_path))
    
    return {"status": "uploaded", "file_id": file_path}

async def process_document_background(file_path: str):
    """Background task for document processing"""
    try:
        # Extract text in thread pool
        text = await run_in_threadpool(extract_text_from_pdf, file_path)
        
        # Generate embeddings
        embeddings = await run_in_threadpool(generate_embeddings, text)
        
        # Save to database
        await save_document_metadata(file_path, text, embeddings)
        
    except Exception as e:
        await log_processing_error(file_path, str(e))
```

### Smart Caching with Refresh

Use `AsyncLazy` with automatic refresh for dynamic data:

```python
from nexios.utils.concurrency import AsyncLazy
import time

class RefreshableCache:
    def __init__(self, refresh_interval: int = 300):  # 5 minutes
        self.refresh_interval = refresh_interval
        self.last_refresh = 0
        self.cache = AsyncLazy(self._fetch_data)
    
    async def get(self):
        current_time = time.time()
        if current_time - self.last_refresh > self.refresh_interval:
            self.cache.reset()
            self.last_refresh = current_time
        
        return await self.cache.get()
    
    async def _fetch_data(self):
        # Expensive data fetching
        return await fetch_latest_config_from_api()

# Global cache instance
config_cache = RefreshableCache(refresh_interval=600)  # 10 minutes

@app.get("/config")
async def get_config(req, res):
    config = await config_cache.get()
    return config
```

## 🚨 Error Handling and Resilience

### Timeout Management

```python
import asyncio

@app.get("/external-data")
async def get_external_data(req, res):
    try:
        # Set overall timeout for the request
        async with asyncio.timeout(5.0):  # 5 second timeout
            async with TaskGroup() as group:
                api1_task = group.create_task(fetch_from_api1())
                api2_task = group.create_task(fetch_from_api2())
                
                data1 = await api1_task
                data2 = await api2_task
                
        return {"api1": data1, "api2": data2}
        
    except asyncio.TimeoutError:
        return {"error": "Request timed out"}, 504
    except Exception as e:
        return {"error": "Service unavailable"}, 503
```

### Circuit Breaker Pattern

```python
from dataclasses import dataclass
import time

@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: int = 60
    failures: int = 0
    last_failure_time: float = 0
    state: str = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        else:  # half-open
            return True
    
    def record_success(self):
        self.failures = 0
        self.state = "closed"
    
    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "open"

# Global circuit breaker for external API
api_circuit_breaker = CircuitBreaker()

@app.get("/protected-api-call")
async def protected_api_call(req, res):
    if not api_circuit_breaker.can_execute():
        return {"error": "Service temporarily unavailable"}, 503
    
    try:
        result = await call_external_api()
        api_circuit_breaker.record_success()
        return result
    except Exception as e:
        api_circuit_breaker.record_failure()
        return {"error": "External service error"}, 502
```

## 📈 Performance Tips and Best Practices

### 1. Choose the Right Tool

- **TaskGroup**: Multiple independent async operations
- **run_in_threadpool**: CPU-bound or blocking I/O operations  
- **run_until_first_complete**: Redundancy and failover scenarios
- **create_background_task**: Fire-and-forget operations
- **AsyncLazy**: Expensive computations that can be cached

### 2. Resource Management

```python
# Good: Limit concurrent operations
semaphore = asyncio.Semaphore(10)  # Max 10 concurrent operations

@app.get("/batch-process")
async def batch_process(req, res):
    items = req.query_params.get("items", "").split(",")
    
    async def process_with_limit(item):
        async with semaphore:
            return await process_item(item)
    
    async with TaskGroup() as group:
        tasks = [group.create_task(process_with_limit(item)) for item in items]
        results = [await task for task in tasks]
    
    return {"results": results}
```

### 3. Memory Considerations

```python
# Good: Process large datasets in chunks
@app.post("/process-large-file")
async def process_large_file(req, res):
    files = await req.files
    large_file = files.get("data")
    
    # Process in chunks to avoid memory issues
    chunk_size = 1000
    results = []
    
    async def process_chunk(chunk_data):
        return await run_in_threadpool(expensive_processing, chunk_data)
    
    # Read and process file in chunks
    for chunk in read_file_chunks(large_file, chunk_size):
        result = await process_chunk(chunk)
        results.append(result)
    
    return {"processed_chunks": len(results)}
```

### 4. Monitoring and Observability

```python
import time
from contextlib import asynccontextmanager

@asynccontextmanager
async def measure_time(operation_name: str):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        await log_performance_metric(operation_name, duration)

@app.get("/monitored-operation")
async def monitored_operation(req, res):
    async with measure_time("parallel_api_calls"):
        async with TaskGroup() as group:
            task1 = group.create_task(api_call_1())
            task2 = group.create_task(api_call_2())
            
            result1 = await task1
            result2 = await task2
    
    return {"data": [result1, result2]}
```

## 🎯 Summary

Nexios concurrency utilities provide a robust foundation for building high-performance async applications:

- Use **TaskGroup** for parallel operations that must all complete
- Use **run_in_threadpool** for CPU-intensive or blocking operations
- Use **run_until_first_complete** for redundancy and failover
- Use **create_background_task** for fire-and-forget operations
- Use **AsyncLazy** for expensive operations that can be cached
- Always implement proper error handling and timeouts
- Monitor performance and resource usage
- Consider memory implications for large-scale operations