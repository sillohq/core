---
title: Handling Request Inputs
description: Read and validate incoming request data in sillo — JSON bodies, form data, uploaded files, and streaming bodies — with the Request object and Pydantic models.
head:
- tag: meta
  attrs:
    property: og:title
    content: Handling Request Inputs
- tag: meta
  attrs:
    property: og:description
    content: Read and validate incoming request data in sillo — JSON bodies, form data, uploaded files, and streaming bodies.
---

# Handling Request Inputs

sillo gives every handler a `Request` object (the first parameter) that lazily parses the incoming body the moment you ask for it. This guide covers the four input shapes you'll handle: JSON, form data, uploaded files, and raw/streaming bodies — plus how to validate them with Pydantic.

## The smallest useful form

```python
from sillo import silloApp

app = silloApp()

@app.post("/submit")
async def submit_data(req, res):
    data = await req.json          # parse the body as JSON
    return {"received": data}
```

`req.json` is an **awaitable property** — `await` it once and the body is cached for the rest of the request. It runs `json.loads` on the raw bytes, so it works for any body that is valid JSON regardless of the `Content-Type` header.

<aside type="tip" title="Content-Type is not enforced">
Unlike some frameworks, `req.json` does not check the `Content-Type` header — it just parses the bytes as JSON. If the body isn't valid JSON you'll get a `json.JSONDecodeError`. For typed, validated input, prefer Pydantic (see below).
</aside>

## JSON data

```python
@app.post("/submit")
async def submit_data(req, res):
    data = await req.json
    name = data.get("name")
    return {"hello": name}
```

Common accessors:

- `await req.json` — parsed JSON as a `dict`/`list` (raises on invalid JSON).
- `await req.text` — the raw body decoded as text (UTF-8, falling back to latin-1).
- `await req.body` — the raw body as `bytes`.

## Form data

sillo parses both `application/x-www-form-urlencoded` and `multipart/form-data` into a `FormData` object, accessible via `req.form` (awaitable property) or the `req.form_data` context manager.

```python
@app.post("/submit-form")
async def submit_form(req, res):
    form = await req.form          # FormData object
    username = form.get("username")
    return {"received": username}
```

For forms, use `req.form`. For multipart uploads (files), read on below.

## File uploads

Uploaded files ride along inside `multipart/form-data`. Access them through `req.files` (awaitable property), which returns a dict of `UploadedFile` objects keyed by field name.

```python
@app.post("/upload")
async def upload_file(req, res):
    files = await req.files
    document = files.get("document")
    if document is None:
        return res.json({"error": "no file"}, status_code=400)

    content = await document.read()           # bytes
    filename = document.filename
    return res.json({"saved": filename, "bytes": len(content)})
```

`UploadedFile` exposes `filename`, `content_type`, and an async `read()` coroutine. Always `await` `req.files` (and `document.read()`) — both are async.

## Streaming request bodies

For very large uploads you can consume the body in chunks instead of buffering it all. `req.stream` is an async generator of `bytes`:

```python
@app.post("/stream")
async def stream_data(req, res):
    total = 0
    async for chunk in req.stream:           # async generator, NOT a method call
        total += len(chunk)
    return {"bytes_received": total}
```

Because the body is consumed as you iterate, you cannot also call `await req.json` or `await req.form` on the same request afterward — pick one strategy per request.

## Validating inputs with Pydantic

For structured input, validate with a Pydantic v2 model. Parse the JSON yourself, then construct the model and let Pydantic handle coercion and errors.

```python
from pydantic import BaseModel, EmailStr, ValidationError

class UserSchema(BaseModel):
    name: str
    email: EmailStr

@app.post("/create-user")
async def create_user(req, res):
    try:
        payload = await req.json
        user = UserSchema(**payload)
    except ValidationError as e:
        return res.json({"error": e.errors()}, status_code=422)

    return res.json({"user": user.model_dump()})
```

sillo also ships the `request_model` hook on routes for automatic validation — see [Request Parameters](/guides/request-parameters/) and the dependency injection guides for that pattern.

## Works with

- [Request Parameters](/guides/request-parameters/) — `Query`, `Header`, `Cookie` extractors
- [Request Information](/guides/request-info/) — headers, cookies, client IP, type flags
- [Sending Responses](/guides/sending-responses/) — returning data, errors, files
- [File Uploads](/guides/file-upload/) — the dedicated file-upload guide

## Related topics

- [Error Handling](/guides/error-handling/) — returning structured 4xx/5xx responses
- [Middleware](/guides/middleware/) — reading the body inside middleware
