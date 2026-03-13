# Background Tasks

A robust background task management system for Nexios applications, providing a simple yet powerful way to run, monitor, and manage asynchronous tasks.

This system allows you to execute time-consuming operations without blocking your API responses, making your application more responsive and scalable.

## Features

Key capabilities that make background task management efficient and reliable:

-  Simple task creation and management
-  Built-in task status tracking
- Timeout and cancellation support
-  Seamless integration with Nexios dependency injection
-  Progress tracking and result handling
-  Thread-safe task management
-  Comprehensive logging

## Installation

Install the nexios-contrib package to access background task functionality:

```bash
pip install nexios-contrib
```

## Basic Usage

Follow these steps to integrate background tasks into your Nexios application:

### 1. Set Up Your Application

Initialize the task manager in your application to enable background task functionality:

```python
from nexios import NexiosApp
from nexios_contrib.tasks import setup_tasks, create_task

app = NexiosApp()

# Initialize the task manager
task_manager = setup_tasks(app)
```

### 2. Define a Background Task

Create async functions that will run as background tasks:

```python
import asyncio

async def process_data(data: dict) -> dict:
    """A sample background task that processes data."""
    await asyncio.sleep(2)  # Simulate work
    return {"status": "completed", "data": data}
```

### 3. Create and Run a Task

> [!WARNING]
> Passing `request` to `create_task` is deprecated and will be removed in a future version. The current context is now automatically resolved. Use `create_task(func, *args, **kwargs)` instead.

Start background tasks from your API endpoints and return immediately:

::: code-group

```python [New (Recommended)]
from nexios.http import Request, Response

@app.post("/process")
async def start_processing(request: Request, response: Response) -> dict:
    """Start a background processing task."""
    data = await request.json
    # The context is automatically resolved
    task = await create_task(
        func=process_data,
        data=data,
        name="data_processing"
    )
    return {"task_id": task.id}
```

```python [Legacy (Deprecated)]
from nexios.http import Request, Response

@app.post("/process")
async def start_processing(request: Request, response: Response) -> dict:
    """Start a background processing task."""
    data = await request.json
    # Explicitly passing request is deprecated
    task = await create_task(
        request=request,
        func=process_data,
        data=data,
        name="data_processing"
    )
    return {"task_id": task.id}
```

```python [Dependency Injection (Best Practice)]
from nexios_contrib.tasks import TaskDependency

@app.post("/process")
async def start_processing(
    request: Request, 
    response: Response,
    task_dep: TaskDependency = TaskDependency() 
) -> dict:
    """Start a background processing task using DI."""
    data = await request.json
    task = await task_dep.create(
        func=process_data,
        data=data,
        name="data_processing"
    )
    return {"task_id": task.id}
```

:::

### 4. Check Task Status

Monitor task progress and retrieve results through status endpoints:

::: code-group

```python [Dependency Injection (Recommended)]
from nexios_contrib.tasks import TaskDependency, TaskStatus

@app.get("/status/{task_id}")
async def get_status(
    request: Request, 
    response: Response, 
    task_id: str,
    task_dep: TaskDependency = TaskDependency()
) -> dict:
    """Get the status of a background task using DI."""
    task = task_dep.get_task(task_id)
    if not task:
        return {"error": "Task not found"}, 404
    
    return {
        "task_id": task.id,
        "status": task.status.value,
        "result": task.result if task.status == TaskStatus.COMPLETED else None,
        "error": str(task.error) if task.error else None
    }
```

```python [Alternative: Task Manager]
from nexios_contrib.tasks import TaskStatus

@app.get("/status/{task_id}")
async def get_status(request: Request, response: Response, task_id: str) -> dict:
    """Get the status of a background task using task manager."""
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": "Task not found"}, 404
    
    return {
        "task_id": task.id,
        "status": task.status.value,
        "result": task.result if task.status == TaskStatus.COMPLETED else None,
        "error": str(task.error) if task.error else None
    }
```

:::

## Using with Dependency Injection

Nexios Tasks integrates seamlessly with Nexios's dependency injection system for a more elegant solution.

Leverage dependency injection to simplify task creation and management in your endpoints.

### Create a Task with Dependencies

Use TaskDependency to inject task management capabilities directly into your handlers:

::: code-group

```python [Dependency Injection (Recommended)]
from nexios_contrib.tasks import TaskDependency

@app.post("/process-with-deps")
async def start_processing_with_deps(
    request: Request,
    response: Response,
    task_dep: TaskDependency = TaskDependency()
) -> dict:
    """Start a task with dependencies."""
    data = await request.json
    task = await task_dep.create(
        func=process_with_deps,
        data=data,
        name="data_processing_with_deps"
    )
    return {"task_id": task.id}
```

```python [Alternative: create_task]
from nexios_contrib.tasks import create_task

@app.post("/process-with-deps")
async def start_processing_with_deps_alt(
    request: Request,
    response: Response
) -> dict:
    """Start a task using create_task function."""
    data = await request.json
    task = await create_task(
        func=process_with_deps,
        data=data,
        name="data_processing_with_deps"
    )
    return {"task_id": task.id}
```

:::


## Task Management

Operations for monitoring and controlling background tasks.

### Listing All Tasks

Retrieve information about all tasks in the system:

::: code-group

```python [Dependency Injection]
from nexios_contrib.tasks import TaskDependency

@app.get("/tasks")
async def list_tasks(
    request: Request, 
    response: Response,
    task_dep: TaskDependency = TaskDependency()
) -> list:
    """List all tasks using dependency injection."""
    return [
        {
            "id": task.id,
            "name": task.name,
            "status": task.status.value,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }
        for task in task_dep.list_tasks()
    ]
```

```python [Alternative: Task Manager]
@app.get("/tasks")
async def list_tasks(request: Request, response: Response) -> list:
    """List all tasks using task manager."""
    return [
        {
            "id": task.id,
            "name": task.name,
            "status": task.status.value,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }
        for task in task_manager.list_tasks()
    ]
```

:::

### Canceling a Task

Stop running tasks when they're no longer needed:

::: code-group

```python [Dependency Injection]
from nexios_contrib.tasks import TaskDependency

@app.post("/tasks/{task_id}/cancel")
async def cancel_task(
    request: Request, 
    response: Response, 
    task_id: str,
    task_dep: TaskDependency = TaskDependency()
) -> dict:
    """Cancel a running task using dependency injection."""
    success = await task_dep.cancel_task(task_id)
    return {"success": success, "task_id": task_id}
```

```python [Alternative: Task Manager]
@app.post("/tasks/{task_id}/cancel")
async def cancel_task(request: Request, response: Response, task_id: str) -> dict:
    """Cancel a running task using task manager."""
    success = await task_manager.cancel_task(task_id)
    return {"success": success, "task_id": task_id}
```

:::

## Configuration

Customize the task manager behavior to match your application's requirements:

Customize the task manager with a configuration object:

```python
from nexios_contrib.tasks import TaskConfig, setup_tasks

config = TaskConfig(
    max_concurrent_tasks=50,  # Maximum number of concurrent tasks
    default_timeout=300,      # Default timeout in seconds (5 minutes)
    task_result_ttl=86400,    # How long to keep task results (24 hours)
    enable_task_history=True,  # Whether to keep completed tasks in history
    log_level="INFO"          # Logging level
)

task_manager = setup_tasks(app, config=config)
```

## Task Status and Lifecycle

Understanding how tasks progress through different states and accessing their properties.

### Task Status Enum

Available status values that indicate the current state of a task:

```python
from nexios_contrib.tasks import TaskStatus

# Available task statuses:
TaskStatus.PENDING    # Task created but not started
TaskStatus.RUNNING    # Task is currently executing
TaskStatus.COMPLETED  # Task finished successfully
TaskStatus.FAILED     # Task failed with an error
TaskStatus.CANCELLED  # Task was cancelled
TaskStatus.TIMEOUT    # Task exceeded timeout limit
```

### Task Lifecycle

Access detailed information about task execution and timing:

```python
from nexios_contrib.tasks import Task

# Task properties
task = task_manager.get_task(task_id)

print(f"Task ID: {task.id}")
print(f"Name: {task.name}")
print(f"Status: {task.status}")
print(f"Created: {task.created_at}")
print(f"Started: {task.started_at}")
print(f"Completed: {task.completed_at}")
print(f"Result: {task.result}")
print(f"Error: {task.error}")
print(f"Progress: {task.progress}")
```

## Advanced Features

Enhanced capabilities for complex task management scenarios.

### Progress Tracking

Monitor and report progress for long-running tasks:

```python
from nexios_contrib.tasks import update_task_progress

async def long_running_task(task_id: str, items: list) -> dict:
    """A task that reports progress."""
    total_items = len(items)
    processed = 0
    
    for item in items:
        # Process item
        await process_item(item)
        processed += 1
        
        # Update progress
        progress = (processed / total_items) * 100
        await update_task_progress(task_id, progress)
    
    return {"processed": processed, "total": total_items}

@app.get("/tasks/{task_id}/progress")
async def get_task_progress(request: Request, response: Response, task_id: str):
    """Get task progress."""
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": "Task not found"}, 404
    
    return {
        "task_id": task_id,
        "progress": task.progress,
        "status": task.status.value
    }
```

## Error Handling

Properly handle and respond to task failures and exceptions.

Handle task errors by checking the task's error attribute:

```python
@app.get("/task-result/{task_id}")
async def get_task_result(request: Request, response: Response, task_id: str):
    """Get the result of a completed task."""
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": "Task not found"}, 404
    
    if task.error:
        return {
            "error": "Task failed",
            "message": str(task.error),
            "traceback": task.error.traceback if hasattr(task.error, 'traceback') else None
        }, 500
        
    return {"result": task.result}
```

### Custom Error Handling

Define and handle application-specific task errors:

```python
from nexios_contrib.tasks import TaskError

async def task_with_custom_error(data: dict) -> dict:
    """A task that raises custom errors."""
    if not data.get("valid"):
        raise TaskError(
            code="INVALID_DATA",
            message="Data validation failed",
            details={"received": data}
        )
    
    return {"processed": data}

@app.add_exception_handler(TaskError)
async def handle_task_error(request, response, exc):
    """Handle custom task errors."""
    return {
        "error": exc.code,
        "message": exc.message,
        "details": exc.details
    }, 400
```

## Examples

Real-world implementations demonstrating common background task patterns.

### File Processing Service

Process files asynchronously with progress tracking:

::: code-group

```python [Dependency Injection Approach]
from nexios import NexiosApp
from nexios_contrib.tasks import setup_tasks, TaskDependency
import asyncio
import os

app = NexiosApp()
task_manager = setup_tasks(app)

async def process_file(file_path: str, task_id: str) -> dict:
    """Process a file in the background."""
    from nexios_contrib.tasks import update_task_progress
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    file_size = os.path.getsize(file_path)
    processed_bytes = 0
    
    # Simulate file processing
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(1024)  # Read 1KB chunks
            if not chunk:
                break
            
            # Simulate processing time
            await asyncio.sleep(0.1)
            
            processed_bytes += len(chunk)
            progress = (processed_bytes / file_size) * 100
            await update_task_progress(task_id, progress)
    
    return {
        "file_path": file_path,
        "file_size": file_size,
        "processed_bytes": processed_bytes,
        "status": "completed"
    }

@app.post("/process-file")
async def start_file_processing(
    request: Request, 
    response: Response,
    task_dep: TaskDependency = TaskDependency()
):
    """Start file processing task using dependency injection."""
    data = await request.json
    file_path = data.get("file_path")
    
    if not file_path:
        return {"error": "file_path is required"}, 400
    
    task = await task_dep.create(
        func=process_file,
        file_path=file_path,
        name=f"process_file_{os.path.basename(file_path)}"
    )
    
    return {"task_id": task.id, "file_path": file_path}
```

```python [create_task Approach]
from nexios import NexiosApp
from nexios_contrib.tasks import setup_tasks, create_task
import asyncio
import os

app = NexiosApp()
task_manager = setup_tasks(app)

async def process_file(file_path: str, task_id: str) -> dict:
    """Process a file in the background."""
    from nexios_contrib.tasks import update_task_progress
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    file_size = os.path.getsize(file_path)
    processed_bytes = 0
    
    # Simulate file processing
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(1024)  # Read 1KB chunks
            if not chunk:
                break
            
            # Simulate processing time
            await asyncio.sleep(0.1)
            
            processed_bytes += len(chunk)
            progress = (processed_bytes / file_size) * 100
            await update_task_progress(task_id, progress)
    
    return {
        "file_path": file_path,
        "file_size": file_size,
        "processed_bytes": processed_bytes,
        "status": "completed"
    }

@app.post("/process-file")
async def start_file_processing(request: Request, response: Response):
    """Start file processing task using create_task."""
    data = await request.json
    file_path = data.get("file_path")
    
    if not file_path:
        return {"error": "file_path is required"}, 400
    
    task = await create_task(
        func=process_file,
        file_path=file_path,
        name=f"process_file_{os.path.basename(file_path)}"
    )
    
    return {"task_id": task.id, "file_path": file_path}
```

:::

### Email Sending Service

Send bulk emails without blocking API responses:

::: code-group

```python [Dependency Injection Approach]
from nexios_contrib.tasks import setup_tasks, TaskDependency
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = NexiosApp()
task_manager = setup_tasks(app)

async def send_bulk_emails(recipients: list, subject: str, body: str, task_id: str) -> dict:
    """Send emails to multiple recipients."""
    from nexios_contrib.tasks import update_task_progress
    
    total_recipients = len(recipients)
    sent_count = 0
    failed_count = 0
    
    for i, recipient in enumerate(recipients):
        try:
            # Send email (implement your email sending logic)
            await send_single_email(recipient, subject, body)
            sent_count += 1
        except Exception as e:
            print(f"Failed to send email to {recipient}: {e}")
            failed_count += 1
        
        # Update progress
        progress = ((i + 1) / total_recipients) * 100
        await update_task_progress(task_id, progress)
    
    return {
        "total_recipients": total_recipients,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "status": "completed"
    }

async def send_single_email(recipient: str, subject: str, body: str):
    """Send a single email."""
    # Implement your email sending logic here
    await asyncio.sleep(0.5)  # Simulate email sending delay

@app.post("/send-bulk-emails")
async def start_bulk_email_sending(
    request: Request, 
    response: Response,
    task_dep: TaskDependency = TaskDependency()
):
    """Start bulk email sending task using dependency injection."""
    data = await request.json
    
    task = await task_dep.create(
        func=send_bulk_emails,
        recipients=data["recipients"],
        subject=data["subject"],
        body=data["body"],
        name="bulk_email_sending"
    )
    
    return {"task_id": task.id, "recipient_count": len(data["recipients"])}
```

```python [create_task Approach]
from nexios_contrib.tasks import setup_tasks, create_task
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = NexiosApp()
task_manager = setup_tasks(app)

async def send_bulk_emails(recipients: list, subject: str, body: str, task_id: str) -> dict:
    """Send emails to multiple recipients."""
    from nexios_contrib.tasks import update_task_progress
    
    total_recipients = len(recipients)
    sent_count = 0
    failed_count = 0
    
    for i, recipient in enumerate(recipients):
        try:
            # Send email (implement your email sending logic)
            await send_single_email(recipient, subject, body)
            sent_count += 1
        except Exception as e:
            print(f"Failed to send email to {recipient}: {e}")
            failed_count += 1
        
        # Update progress
        progress = ((i + 1) / total_recipients) * 100
        await update_task_progress(task_id, progress)
    
    return {
        "total_recipients": total_recipients,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "status": "completed"
    }

async def send_single_email(recipient: str, subject: str, body: str):
    """Send a single email."""
    # Implement your email sending logic here
    await asyncio.sleep(0.5)  # Simulate email sending delay

@app.post("/send-bulk-emails")
async def start_bulk_email_sending(request: Request, response: Response):
    """Start bulk email sending task using create_task."""
    data = await request.json
    
    task = await create_task(
        func=send_bulk_emails,
        recipients=data["recipients"],
        subject=data["subject"],
        body=data["body"],
        name="bulk_email_sending"
    )
    
    return {"task_id": task.id, "recipient_count": len(data["recipients"])}
```

:::

### Data Export Service

Generate and export large datasets in various formats:

::: code-group

```python [Dependency Injection Approach]
from nexios_contrib.tasks import setup_tasks, TaskDependency
import csv
import json
from datetime import datetime

app = NexiosApp()
task_manager = setup_tasks(app)

async def export_data(format: str, filters: dict, task_id: str) -> dict:
    """Export data in specified format."""
    from nexios_contrib.tasks import update_task_progress
    
    # Fetch data (implement your data fetching logic)
    data = await fetch_data_from_database(filters)
    total_records = len(data)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"export_{timestamp}.{format}"
    
    if format == "csv":
        await export_to_csv(data, filename, task_id)
    elif format == "json":
        await export_to_json(data, filename, task_id)
    else:
        raise ValueError(f"Unsupported format: {format}")
    
    return {
        "filename": filename,
        "format": format,
        "total_records": total_records,
        "status": "completed"
    }

async def fetch_data_from_database(filters: dict) -> list:
    """Fetch data from database."""
    # Implement your database query logic
    await asyncio.sleep(1)  # Simulate database query
    return [{"id": i, "name": f"Record {i}"} for i in range(1000)]

async def export_to_csv(data: list, filename: str, task_id: str):
    """Export data to CSV format."""
    from nexios_contrib.tasks import update_task_progress
    
    with open(filename, 'w', newline='') as csvfile:
        if data:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, row in enumerate(data):
                writer.writerow(row)
                
                # Update progress every 100 records
                if i % 100 == 0:
                    progress = (i / len(data)) * 100
                    await update_task_progress(task_id, progress)

async def export_to_json(data: list, filename: str, task_id: str):
    """Export data to JSON format."""
    from nexios_contrib.tasks import update_task_progress
    
    with open(filename, 'w') as jsonfile:
        json.dump(data, jsonfile, indent=2)
    
    await update_task_progress(task_id, 100)

@app.post("/export-data")
async def start_data_export(
    request: Request, 
    response: Response,
    task_dep: TaskDependency = TaskDependency()
):
    """Start data export task using dependency injection."""
    data = await request.json
    
    task = await task_dep.create(
        func=export_data,
        format=data.get("format", "csv"),
        filters=data.get("filters", {}),
        name=f"data_export_{data.get('format', 'csv')}"
    )
    
    return {"task_id": task.id, "format": data.get("format", "csv")}
```

```python [create_task Approach]
from nexios_contrib.tasks import setup_tasks, create_task
import csv
import json
from datetime import datetime

app = NexiosApp()
task_manager = setup_tasks(app)

async def export_data(format: str, filters: dict, task_id: str) -> dict:
    """Export data in specified format."""
    from nexios_contrib.tasks import update_task_progress
    
    # Fetch data (implement your data fetching logic)
    data = await fetch_data_from_database(filters)
    total_records = len(data)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"export_{timestamp}.{format}"
    
    if format == "csv":
        await export_to_csv(data, filename, task_id)
    elif format == "json":
        await export_to_json(data, filename, task_id)
    else:
        raise ValueError(f"Unsupported format: {format}")
    
    return {
        "filename": filename,
        "format": format,
        "total_records": total_records,
        "status": "completed"
    }

async def fetch_data_from_database(filters: dict) -> list:
    """Fetch data from database."""
    # Implement your database query logic
    await asyncio.sleep(1)  # Simulate database query
    return [{"id": i, "name": f"Record {i}"} for i in range(1000)]

async def export_to_csv(data: list, filename: str, task_id: str):
    """Export data to CSV format."""
    from nexios_contrib.tasks import update_task_progress
    
    with open(filename, 'w', newline='') as csvfile:
        if data:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, row in enumerate(data):
                writer.writerow(row)
                
                # Update progress every 100 records
                if i % 100 == 0:
                    progress = (i / len(data)) * 100
                    await update_task_progress(task_id, progress)

async def export_to_json(data: list, filename: str, task_id: str):
    """Export data to JSON format."""
    from nexios_contrib.tasks import update_task_progress
    
    with open(filename, 'w') as jsonfile:
        json.dump(data, jsonfile, indent=2)
    
    await update_task_progress(task_id, 100)

@app.post("/export-data")
async def start_data_export(request: Request, response: Response):
    """Start data export task using create_task."""
    data = await request.json
    
    task = await create_task(
        func=export_data,
        format=data.get("format", "csv"),
        filters=data.get("filters", {}),
        name=f"data_export_{data.get('format', 'csv')}"
    )
    
    return {"task_id": task.id, "format": data.get("format", "csv")}
```

:::

## Best Practices

Guidelines for building reliable and maintainable background task systems.

1. **Task Granularity**: Keep tasks focused on a single responsibility
2. **Error Handling**: Always implement proper error handling in your tasks
3. **Timeouts**: Set appropriate timeouts for your tasks
4. **Resource Management**: Clean up resources in a `finally` block
5. **Logging**: Use the provided logger for task-related logs
6. **Progress Updates**: Update progress for long-running tasks
7. **Testing**: Write comprehensive tests for your background tasks

### Production Configuration

Optimize task manager settings for production environments:

```python
from nexios_contrib.tasks import TaskConfig, setup_tasks
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Production task configuration
config = TaskConfig(
    max_concurrent_tasks=100,
    default_timeout=1800,  # 30 minutes
    task_result_ttl=604800,  # 7 days
    enable_task_history=True,
    log_level="INFO",
    cleanup_interval=3600,  # Clean up every hour
    max_task_history=10000  # Keep last 10k completed tasks
)

task_manager = setup_tasks(app, config=config)
```

Built with ❤️ by the [@nexios-labs](https://github.com/nexios-labs) community.
