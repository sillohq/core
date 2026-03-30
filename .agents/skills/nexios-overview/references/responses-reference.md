# Nexios Responses Reference

Use this reference when the request is mainly about how Nexios sends HTTP responses.

## Table of Contents

1. [Plain Return Values](#plain-return-values)
2. [Using The Response Object](#using-the-response-object)
3. [Response Types](#response-types)
4. [Status Headers And Cookies](#status-headers-and-cookies)
5. [Streaming And Files](#streaming-and-files)
6. [Teaching Rules](#teaching-rules)

## Plain Return Values

Nexios can serialize simple JSON-compatible return values:

```python
@app.get("/users")
async def get_users(request, response):
    return [{"name": "Ada"}, {"name": "Linus"}]
```

Teach this as a convenience feature, not as the only response style.

## Using The Response Object

Prefer the response object when the example needs control:

```python
@app.get("/users")
async def get_users(request, response):
    return response.json([{"name": "Ada"}])
```

Important documented rule:

- Set the response type first before calling `.set_cookie()`, `.set_header()`, or similar helpers.

## Response Types

### JSON

```python
return response.json({"ok": True})
```

### HTML

```python
return response.html("<h1>Hello</h1>")
```

### Text

```python
return response.text("Service is running")
```

### Redirect

```python
return response.redirect("/new-path")
```

### Empty

```python
return response.empty(status_code=204)
```

## Status Headers And Cookies

Sequential style:

```python
@app.get("/api/data")
async def get_data(request, response):
    response.json({"data": "success"})
    response.set_cookie("session", "abc123")
    response.set_header("X-API-Version", "1.0")
    response.status(200)
    return response
```

Compact chained style:

```python
@app.get("/api/data")
async def get_data(request, response):
    return (
        response
        .json({"data": "success"})
        .set_cookie("session", "abc123")
        .set_header("X-API-Version", "1.0")
        .status(200)
    )
```

## Streaming And Files

### File Response

```python
@app.get("/download")
async def download(request, response):
    return response.file("report.pdf")
```

### Streaming Response

```python
@app.get("/numbers")
async def numbers(request, response):
    async def stream():
        for i in range(5):
            yield f"{i}\n"
    return response.stream(stream())
```

## Teaching Rules

- Use `response.json(...)` in beginner examples for clarity
- Use chained or sequential response configuration when headers, cookies, or status matter
- Mention the response-type-first rule when teaching cookies or headers
- Prefer explicit responses over implicit serialization for public examples
