# 🔄 Async Python

## 📖 Introduction

Modern web applications demand concurrency — the ability to handle thousands of tasks at the same time 🌊. Traditionally, Python's synchronous, blocking nature made this difficult. But with the advent of `asyncio`, Python now supports **asynchronous programming** 🔄, enabling it to handle I/O-bound tasks far more efficiently.

This guide dives deep into how asynchronous Python works, why it's necessary, and how to write scalable, non-blocking code using `async` and `await`. Understanding async programming is crucial for building high-performance web applications with Nexios.

## 🚫 The Problem with Synchronous Code

Python executes one line at a time. When it hits a long-running operation like a database query or an HTTP request, the whole program stops and waits. That's fine for scripts or small apps, but inefficient in systems that require concurrency — like servers or data pipelines.

### Synchronous Example

```python
import requests
import time

def fetch_data(url):
    print(f"Fetching {url}")
    response = requests.get(url)
    return response.json()

def main():
    start_time = time.time()
    
    # These run sequentially - each blocks until the previous completes
    data1 = fetch_data("https://api.example.com/data1")
    data2 = fetch_data("https://api.example.com/data2")
    data3 = fetch_data("https://api.example.com/data3")
    
    end_time = time.time()
    print(f"Total time: {end_time - start_time:.2f} seconds")
    print(f"Results: {data1}, {data2}, {data3}")

main()
```

This will block until each network request completes. During that time, Python cannot do anything else — no other tasks, no serving other users. If each request takes 1 second, the total time is 3 seconds.

Now imagine you're building a server that needs to serve 500 clients simultaneously. Blocking each call like this would kill performance.

## ✅ What Async Solves

Async Python doesn't use threads to solve this — it uses something called the **event loop** 🔄, which lets Python switch between multiple "tasks" during I/O waits.

This model is useful when your code spends a lot of time **waiting** — for HTTP responses, file reads, database queries, etc.

### Asynchronous Example

```python
import asyncio
import aiohttp
import time

async def fetch_data(session, url):
    print(f"Fetching {url}")
    async with session.get(url) as response:
        return await response.json()

async def main():
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        # These run concurrently - they all start at the same time
        tasks = [
            fetch_data(session, "https://api.example.com/data1"),
            fetch_data(session, "https://api.example.com/data2"),
            fetch_data(session, "https://api.example.com/data3")
        ]
        
        results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    print(f"Total time: {end_time - start_time:.2f} seconds")
    print(f"Results: {results}")

asyncio.run(main())
```

In this async version, all three requests start simultaneously. If each request takes 1 second, the total time is approximately 1 second instead of 3 seconds.

## ⚖️ Sync vs Async Execution Models

Let's illustrate the difference with a simple diagram.

### Synchronous Execution ⏳

```
Task A: [==== wait 3s ====]
Task B:                  [==== wait 3s ====]
Task C:                                  [==== wait 3s ====]
Total Time: 9s
```

### Asynchronous Execution 🚀

```
Task A: [== initiated ==]     [== continues ==]
Task B:       [== starts ==]     [== finishes ==]
Task C:             [== starts ==]     [== finishes ==]
Total Time: ~3s
```

In async mode, while Task A is waiting (e.g. for a network response), Task B and C run. We achieve **concurrency** 🌊, not through threads, but via **non-blocking I/O**.

## 🧠 Core Concepts of Async Python

### 1. Coroutines ⚙️

A coroutine is a function defined with `async def`. It's not executed immediately — instead, it returns a coroutine object. You need to **await** it.

```python
import asyncio

async def my_coroutine():
    print("Start")
    await asyncio.sleep(1)  # Non-blocking sleep
    print("End")
    return "Done"

# This doesn't run the coroutine, just creates it
coro = my_coroutine()
print(type(coro))  # <class 'coroutine'>

# To run it, we need to await it
async def main():
    result = await my_coroutine()
    print(result)

asyncio.run(main())
```

### 2. The Event Loop 🔄

The event loop runs in the background, managing coroutines and deciding when to pause or resume them. It's the heart of async programming.

```python
import asyncio

async def task1():
    print("Task 1 started")
    await asyncio.sleep(2)
    print("Task 1 finished")
    return "Task 1 result"

async def task2():
    print("Task 2 started")
    await asyncio.sleep(1)
    print("Task 2 finished")
    return "Task 2 result"

async def main():
    # Create tasks (they start running immediately)
    t1 = asyncio.create_task(task1())
    t2 = asyncio.create_task(task2())
    
    # Wait for both to complete
    result1 = await t1
    result2 = await t2
    
    print(f"Results: {result1}, {result2}")

# Run the event loop
asyncio.run(main())
```

**Output:**
```
Task 1 started
Task 2 started
Task 2 finished
Task 1 finished
Results: Task 1 result, Task 2 result
```

### 3. Awaitables 📋

An object is *awaitable* if it can be used with the `await` keyword. These include:

- **Coroutines** ⚙️: Functions defined with `async def`
- **Tasks** 📝: Created with `asyncio.create_task()` or `asyncio.ensure_future()`
- **Futures** 🔮: Low-level awaitable objects
- **Custom awaitables** 🛠️: Objects that implement `__await__()`

```python
import asyncio

async def coroutine():
    return "coroutine result"

async def main():
    # Coroutine
    result1 = await coroutine()
    
    # Task
    task = asyncio.create_task(coroutine())
    result2 = await task
    
    # Future
    future = asyncio.Future()
    future.set_result("future result")
    result3 = await future
    
    print(f"{result1}, {result2}, {result3}")

asyncio.run(main())
```

## Practical Examples

### Concurrent HTTP Requests

```python
import asyncio
import aiohttp

async def fetch_url(session, url):
    async with session.get(url) as response:
        return await response.text()

async def fetch_multiple_urls(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        return results

# Usage
urls = [
    "https://httpbin.org/delay/1",
    "https://httpbin.org/delay/2",
    "https://httpbin.org/delay/3"
]

results = asyncio.run(fetch_multiple_urls(urls))
print(f"Fetched {len(results)} URLs concurrently")
```

### Database Operations

```python
import asyncio
import asyncpg

async def get_user(db_pool, user_id):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, email FROM users WHERE id = $1", 
            user_id
        )
        return dict(row) if row else None

async def get_multiple_users(db_pool, user_ids):
    tasks = [get_user(db_pool, user_id) for user_id in user_ids]
    return await asyncio.gather(*tasks)

async def main():
    # Connect to database
    db_pool = await asyncpg.create_pool(
        "postgresql://user:password@localhost/dbname"
    )
    
    # Fetch multiple users concurrently
    user_ids = [1, 2, 3, 4, 5]
    users = await get_multiple_users(db_pool, user_ids)
    
    print(f"Retrieved {len(users)} users")
    
    await db_pool.close()

asyncio.run(main())
```

### File Operations

```python
import asyncio
import aiofiles

async def read_file(filename):
    async with aiofiles.open(filename, 'r') as f:
        return await f.read()

async def write_file(filename, content):
    async with aiofiles.open(filename, 'w') as f:
        await f.write(content)

async def process_files(filenames):
    # Read all files concurrently
    read_tasks = [read_file(filename) for filename in filenames]
    contents = await asyncio.gather(*read_tasks)
    
    # Process contents
    processed = [content.upper() for content in contents]
    
    # Write processed files concurrently
    write_tasks = [
        write_file(f"processed_{filename}", content)
        for filename, content in zip(filenames, processed)
    ]
    await asyncio.gather(*write_tasks)

# Usage
filenames = ["file1.txt", "file2.txt", "file3.txt"]
asyncio.run(process_files(filenames))
```

## Advanced Async Patterns

### `asyncio.gather()`

Runs multiple coroutines in parallel and returns their results.

```python
import asyncio

async def get_data(x):
    await asyncio.sleep(1)
    return f"Result {x}"

async def main():
    # Run multiple coroutines concurrently
    results = await asyncio.gather(
        get_data(1), 
        get_data(2), 
        get_data(3)
    )
    print(results)  # ['Result 1', 'Result 2', 'Result 3']

asyncio.run(main())
```

### `asyncio.wait()`

More flexible than `gather()`, allows you to handle tasks as they complete.

```python
import asyncio

async def get_data(x):
    await asyncio.sleep(x)
    return f"Result {x}"

async def main():
    tasks = [
        asyncio.create_task(get_data(1)),
        asyncio.create_task(get_data(2)),
        asyncio.create_task(get_data(3))
    ]
    
    # Wait for all tasks to complete
    done, pending = await asyncio.wait(tasks)
    
    for task in done:
        print(await task)

asyncio.run(main())
```

### `asyncio.as_completed()`

Process tasks as they complete, in completion order.

```python
import asyncio

async def get_data(x):
    await asyncio.sleep(x)
    return f"Result {x}"

async def main():
    tasks = [get_data(1), get_data(2), get_data(3)]
    
    # Process results as they complete
    for coro in asyncio.as_completed(tasks):
        result = await coro
        print(f"Completed: {result}")

asyncio.run(main())
```

### Timeouts

```python
import asyncio

async def slow_operation():
    await asyncio.sleep(5)
    return "Operation completed"

async def main():
    try:
        # Wait for operation with timeout
        result = await asyncio.wait_for(slow_operation(), timeout=3.0)
        print(result)
    except asyncio.TimeoutError:
        print("Operation timed out")

asyncio.run(main())
```

## Mixing Async and Sync Code

You **cannot** use `await` in a regular (non-async) function.

```python
def wrong():
    await asyncio.sleep(1)  # SyntaxError: 'await' outside async function
```

### Running Sync Code in Async Context

Use `asyncio.to_thread()` to run blocking functions in a thread pool:

```python
import asyncio
import time

def blocking_function():
    time.sleep(2)  # Blocking operation
    return "Blocking result"

async def main():
    # Run blocking function in thread pool
    result = await asyncio.to_thread(blocking_function)
    print(result)

asyncio.run(main())
```

### Running Async Code from Sync Context

```python
import asyncio

async def async_function():
    await asyncio.sleep(1)
    return "Async result"

def sync_function():
    # Run async function from sync context
    return asyncio.run(async_function())

result = sync_function()
print(result)
```

## Error Handling in Async Code

### Exception Handling

```python
import asyncio

async def risky_operation():
    await asyncio.sleep(1)
    raise ValueError("Something went wrong")

async def main():
    try:
        result = await risky_operation()
    except ValueError as e:
        print(f"Caught error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

asyncio.run(main())
```

### Error Handling with gather()

```python
import asyncio

async def operation(x):
    if x == 2:
        raise ValueError(f"Error in operation {x}")
    await asyncio.sleep(1)
    return f"Result {x}"

async def main():
    tasks = [operation(i) for i in range(5)]
    
    # Option 1: Return exceptions as results
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Task {i} failed: {result}")
        else:
            print(f"Task {i} succeeded: {result}")
    
    # Option 2: Handle exceptions individually
    for i in range(5):
        try:
            result = await operation(i)
            print(f"Task {i} succeeded: {result}")
        except Exception as e:
            print(f"Task {i} failed: {e}")

asyncio.run(main())
```

## Real-World Applications

### Web Applications

Async programming is essential for modern web frameworks:

1. **Web frameworks**: FastAPI, Nexios, Sanic — all use async to handle thousands of HTTP requests concurrently
2. **WebSocket servers**: Real-time systems like chat, stock dashboards
3. **API gateways**: Handling multiple backend services
4. **Microservices**: Inter-service communication

### Data Processing

```python
import asyncio
import aiohttp

async def fetch_and_process_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            # Process data
            return processed_data

async def process_multiple_sources(urls):
    tasks = [fetch_and_process_data(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results
```

### Task Pipelines

```python
import asyncio

async def stage1(data):
    await asyncio.sleep(1)
    return f"Stage 1: {data}"

async def stage2(data):
    await asyncio.sleep(1)
    return f"Stage 2: {data}"

async def stage3(data):
    await asyncio.sleep(1)
    return f"Stage 3: {data}"

async def pipeline(input_data):
    # Sequential pipeline
    result1 = await stage1(input_data)
    result2 = await stage2(result1)
    result3 = await stage3(result2)
    return result3

async def parallel_pipeline(input_data):
    # Parallel processing
    tasks = [
        stage1(input_data),
        stage2(input_data),
        stage3(input_data)
    ]
    results = await asyncio.gather(*tasks)
    return results
```

## When Async is NOT Helpful

Async is **not** helpful when:

- **CPU-bound tasks**: Image processing, machine learning, complex calculations. Use multiprocessing or native threads for that
- **Simple scripts**: If you're writing a simple script that doesn't need concurrency
- **Complex call stacks**: When async/await makes the code harder to reason about
- **Libraries without async support**: When dealing with libraries that don't support `asyncio`

### CPU-Bound vs I/O-Bound

```python
import asyncio
import time

# I/O-bound task (good for async)
async def io_bound_task():
    await asyncio.sleep(1)  # Simulating I/O
    return "I/O result"

# CPU-bound task (not good for async)
def cpu_bound_task():
    # Simulating CPU-intensive work
    result = 0
    for i in range(10**7):
        result += i
    return result

# For CPU-bound tasks, use multiprocessing
import multiprocessing

def run_cpu_bound():
    with multiprocessing.Pool() as pool:
        results = pool.map(cpu_bound_task, range(4))
    return results
```

## Comparison: Threads vs Async

| Feature           | Threads         | Asyncio (Async/Await)    |
| ----------------- | --------------- | ------------------------ |
| Concurrency model | Pre-emptive     | Cooperative (event loop) |
| Memory usage      | Higher          | Lower                    |
| Complexity        | Medium          | Low to Medium            |
| Best for          | CPU-bound tasks | I/O-bound tasks          |
| Scalability       | Limited by threads | Limited by memory       |
| Debugging         | More complex    | Easier                   |
| Context switching | OS controlled   | Explicit (await)         |

## Best Practices

### 1. Keep Coroutines Focused

```python
# Good: Focused coroutine
async def fetch_user_data(user_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"/api/users/{user_id}") as response:
            return await response.json()

# Bad: Doing too much
async def fetch_and_process_user_data(user_id):
    # Too many responsibilities
    pass
```

### 2. Use Appropriate Concurrency

```python
# Good: Use gather for independent tasks
async def fetch_all_users(user_ids):
    tasks = [fetch_user_data(user_id) for user_id in user_ids]
    return await asyncio.gather(*tasks)

# Good: Use sequential for dependent tasks
async def process_user_pipeline(user_id):
    user_data = await fetch_user_data(user_id)
    processed_data = await process_user_data(user_data)
    return await save_user_data(processed_data)
```

### 3. Handle Exceptions Properly

```python
async def robust_fetch(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.json()
    except aiohttp.ClientError as e:
        print(f"Network error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
```

### 4. Use Timeouts

```python
async def fetch_with_timeout(url, timeout=5.0):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await asyncio.wait_for(response.json(), timeout=timeout)
    except asyncio.TimeoutError:
        print(f"Request to {url} timed out")
        return None
```

## External References

- [Python Official asyncio Docs](https://docs.python.org/3/library/asyncio.html)
- [RealPython – Async Python](https://realpython.com/async-io-python/)
- [aiohttp Documentation](https://docs.aiohttp.org/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)

Understanding async programming is fundamental to building high-performance applications with Nexios. The framework is built around async/await, so mastering these concepts will help you write more efficient and scalable code.

