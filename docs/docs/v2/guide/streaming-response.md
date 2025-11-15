---
title: Streaming Responses in Nexios
description: Nexios provides powerful streaming capabilities for handling large datasets, real-time data, and long-polling scenarios. This guide covers how to implement and work with
head:
  - - meta
    - property: og:title
      content: Streaming Responses in Nexios
  - - meta
    - property: og:description
      content: Nexios provides powerful streaming capabilities for handling large datasets, real-time data, and long-polling scenarios. This guide covers how to implement and work with
---

# Streaming Responses in Nexios

Nexios provides powerful streaming capabilities for handling large datasets, real-time data, and long-polling scenarios. This guide covers how to implement and work with

Streaming responses allow you to send data to the client as it becomes available, rather than buffering everything in memory first. This is particularly useful for:

- Large file downloads
- Real-time data feeds
- Long-polling implementations
- Server-Sent Events (SSE)
- Progress reporting

## Basic Streaming

## Understanding Async Generators for Streaming

Before diving into the code, it's important to understand how async generators work in Python. An async generator is a special type of function that yields values asynchronously, allowing you to process and send data in chunks rather than all at once. This is particularly useful for streaming scenarios where you want to send data as it becomes available.

### Key Characteristics of Async Generators:

1. Defined using `async def` and contains at least one `yield` statement
2. Returns an async generator object when called
3. Can use `await` to wait for other coroutines
4. Maintains its state between yields
5. Must be consumed using `async for` or `anext()`

### Basic Streaming Example

Here's how to create a simple streaming endpoint using an async generator. This example demonstrates the basic pattern you'll use for most streaming responses:

```python
from nexios import NexiosApp

app = NexiosApp()

@app.get("/stream")
async def stream_data(request, response):
    async def generate():
        for i in range(5):
            yield f"Data chunk {i}\n"
            await asyncio.sleep(1)  # Simulate work

    return response.stream(generate(), content_type="text/plain")
```

## Understanding Chunked Transfer Encoding

Chunked transfer encoding is a streaming data transfer mechanism available in HTTP/1.1. It allows a server to start sending the response before knowing its total size, which is perfect for streaming scenarios where the total size might not be known in advance.

### How Chunked Encoding Works:

1. The server breaks the response into a series of chunks
2. Each chunk is preceded by its size in hexadecimal
3. A zero-length chunk marks the end of the response
4. The client receives and processes each chunk as it arrives

### Implementing Chunked Responses

In Nexios, you don't need to manually implement chunking - it's handled automatically when you use the `stream()` method. Here's how to create a chunked response:

```python
@app.get("/chunked")
async def chunked_response(request, response):
    async def generate():
        yield "First chunk\n"
        await asyncio.sleep(1)
        yield "Second chunk\n"
        await asyncio.sleep(1)
        yield "Final chunk\n"

    return response.stream(
        generate(),
        content_type="text/plain",
        headers={"X-Streaming": "enabled"}
    )
```

## Understanding Server-Sent Events (SSE)

Server-Sent Events (SSE) is a standard that allows a web server to push real-time updates to the client over HTTP. Unlike WebSockets, SSE is a one-way communication channel from server to client, making it simpler and more efficient for certain use cases.

### Key Features of SSE:

- Simple text-based protocol
- Automatic reconnection
- Built-in event IDs for tracking
- Browser EventSource API for easy client-side handling
- Works over standard HTTP/HTTPS

### SSE Message Format:

Each message consists of one or more lines of text in the format:

```
event: <event_name>
data: <message>
id: <message_id>
retry: <milliseconds>
```

### Implementing SSE in Nexios

Here's how to implement an SSE endpoint. The key is to use the `text/event-stream` content type and follow the SSE message format:

```python
@app.get("/events")
async def sse_events(request, response):
    async def event_stream():
        try:
            while True:
                data = await get_latest_event()  # Your event source
                yield f"data: {data}\n\n"
                # Keep the connection alive
                await asyncio.sleep(1)
                yield ":keepalive\n\n"
        except asyncio.CancelledError:
            # Handle client disconnection
            pass

    return response.stream(
        event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
```

## Understanding File Streaming

Streaming files is essential when dealing with large files that shouldn't be loaded entirely into memory. This approach is memory-efficient and provides a better user experience as the client can start processing the file before the entire download is complete.

### Benefits of File Streaming:

- Memory efficiency: Only a small portion of the file is in memory at any time
- Faster time-to-first-byte: Clients can start processing data immediately
- Better handling of large files: No memory limits based on file size
- Support for resumable downloads

### How File Streaming Works:

1. File is opened in binary read mode
2. Data is read in fixed-size chunks (e.g., 8KB)
3. Each chunk is yielded to the client
4. Process continues until the entire file is sent

### Implementing File Downloads with Streaming

Here's how to implement a file download endpoint that streams the file efficiently:

```python
import aiofiles
from pathlib import Path

@app.get("/download/{filename}")
async def download_file(request, response, filename: str):
    file_path = Path("uploads") / filename

    if not file_path.is_file():
        return response.json(
            {"error": "File not found"},
            status_code=404
        )

    async def file_sender():
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(8192):  # 8KB chunks
                yield chunk

    return response.stream(
        file_sender(),
        content_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(file_path.stat().st_size)
        }
    )
```

## Performance Considerations

1. **Chunk Size**: Choose an appropriate chunk size (typically 4KB-16KB) for your use case.
2. **Backpressure**: Be mindful of slow clients and implement backpressure handling.
3. **Timeouts**: Set appropriate timeouts for long-running streams.
4. **Connection Pooling**: Reuse connections for better performance.
5. **Compression**: Consider using compression for text-based streams.

## Understanding Error Handling in Streams

Error handling in streaming responses requires special consideration because the response is sent incrementally. Unlike regular HTTP responses where you can return an error status code at the beginning, with streaming, you need to handle errors that might occur mid-stream.

### Key Considerations for Error Handling:

1. **Immediate vs. Graceful Errors**: Some errors (like invalid authentication) should fail immediately, while others (like data processing errors) might allow for graceful degradation.
2. **Client-Side Handling**: Clients must be prepared to handle partial responses and error conditions that occur mid-stream.
3. **Resource Cleanup**: Ensure all resources (files, database connections) are properly cleaned up if an error occurs.
4. **Error Signaling**: Decide how to signal errors to the client (e.g., special error messages, HTTP trailers).

### Implementing Error Handling

Here's how to implement robust error handling in a streaming endpoint:

```python
@app.get("/safe-stream")
async def safe_stream(request, response):
    async def generate():
        try:
            for i in range(10):
                if i == 5:
                    raise ValueError("Simulated error")
                yield f"Data {i}\n"
                await asyncio.sleep(0.5)
        except Exception as e:
            # Log the full error for debugging
            app.logger.error(f"Error in safe_stream: {str(e)}")
            # Send a user-friendly error message to the client
            yield f"Error: {str(e)}\n"
        finally:
            # Always send completion message
            yield "Stream completed\n"
            # Any cleanup code would go here

    return response.stream(generate())
```

## Building a Real-time Data Pipeline

A real-time data pipeline processes and delivers data as it's generated, making it ideal for analytics, monitoring, and live dashboards. This example demonstrates how to build such a pipeline using Nexios streaming capabilities.

### Pipeline Architecture

1. **Data Ingestion**: Continuously fetch data from a source
2. **Processing**: Transform or analyze the data
3. **Delivery**: Stream processed data to clients in real-time
4. **Monitoring**: Track pipeline health and performance

### Implementation Details

This example shows a complete data pipeline that:

- Streams data in real-time
- Handles errors gracefully
- Provides status updates
- Uses newline-delimited JSON for easy parsing

```python
import asyncio
import json
from datetime import datetime

@app.get("/data-pipeline")
async def data_pipeline(request, response):
    """
    Real-time data processing pipeline endpoint.
    Streams processed data as it becomes available.
    """
    async def process_data():
        try:
            # Initial status update
            yield json.dumps({
                "status": "starting",
                "timestamp": str(datetime.utcnow())
            }) + "\n"

            # Process data in chunks
            async for chunk in fetch_data_chunks():
                try:
                    # Process each chunk asynchronously
                    processed = await process_chunk(chunk)

                    # Yield the processed data
                    yield json.dumps({
                        "status": "processing",
                        "data": processed,
                        "timestamp": str(datetime.utcnow())
                    }) + "\n"

                    # Simulate work (remove in production)
                    await asyncio.sleep(0.1)

                except Exception as chunk_error:
                    # Log chunk processing error but continue with next chunk
                    app.logger.error(f"Error processing chunk: {chunk_error}")
                    yield json.dumps({
                        "status": "chunk_error",
                        "error": str(chunk_error),
                        "timestamp": str(datetime.utcnow())
                    }) + "\n"

        except Exception as e:
            # Handle fatal errors
            app.logger.error(f"Pipeline error: {e}")
            yield json.dumps({
                "status": "error",
                "message": str(e),
                "timestamp": str(datetime.utcnow())
            }) + "\n"

        finally:
            # Always send completion message
            yield json.dumps({
                "status": "complete",
                "timestamp": str(datetime.utcnow())
            }) + "\n"

    # Return the streaming response with appropriate content type
    return response.stream(
        process_data(),
        content_type="application/x-ndjson"  # Newline-delimited JSON
    )
```

### Client-Side Processing

Clients can consume this stream using libraries like `aiohttp` or the browser's `EventSource` API. The newline-delimited JSON format makes it easy to parse each message individually as it arrives.
