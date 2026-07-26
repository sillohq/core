---
title: Forms and file uploads
description: Declare form fields and uploads with Form and File markers. sillo picks urlencoded or multipart from the client's Content-Type, so one declaration handles both.
---

Form fields and file uploads are parameter markers, like every other input except the JSON body:

```python
from sillo import silloApp, Form, File

app = silloApp()

@app.post("/login")
async def login(request, response,
                username=Form(type=str),
                password=Form(type=str, min_length=8)):
    return {"user": username}
```

```bash
curl -X POST localhost:8000/login -d 'username=ada&password=hunter22'
```

Declaring any `Form` or `File` parameter switches the route to parsing its body as a form.

## When to use a form instead of JSON

Two situations call for it. The first is a browser `<form>` posting directly to your API without JavaScript — that always sends urlencoded or multipart, never JSON. The second is **any request carrying a file**, because JSON has no way to represent binary content; base64 in a JSON string works but inflates the payload by a third and buffers the whole thing in memory.

Everything else is usually better served by a JSON body, where you get nested structures and a single model describing the whole payload.

## File uploads

```python
from sillo import silloApp, Form, File, Path

@app.post("/users/{user_id}/avatar")
async def upload_avatar(request, response,
                        user_id=Path(type=int),
                        caption=Form("", type=str, max_length=140),
                        avatar=File(...)):
    content = await avatar.read()
    return {
        "filename": avatar.filename,
        "content_type": avatar.content_type,
        "size": len(content),
        "caption": caption,
    }
```

```bash
curl -X POST localhost:8000/users/5/avatar \
  -F 'caption=my pic' \
  -F 'avatar=@photo.png'
```

Mix `File` with `Form` for the text fields that accompany an upload.

## Working with an uploaded file

A `File` parameter arrives as an `UploadFile`:

```python
avatar.filename          # "photo.png" — as supplied by the client
avatar.content_type      # "image/png" — as claimed by the client
avatar.size              # bytes, when the client declared it
avatar.headers           # the multipart part's headers

await avatar.read()      # read the whole file as bytes
await avatar.read(1024)  # read at most 1 KB
await avatar.seek(0)     # rewind
await avatar.write(b)    # write into the spooled file
await avatar.close()     # release the handle
```

Large uploads spool to disk automatically instead of being held in memory, and the async methods delegate disk work to a thread so the event loop is never blocked.

### Streaming rather than buffering

`await avatar.read()` pulls the entire file into memory. For large uploads, copy in chunks:

```python
import aiofiles

@app.post("/upload")
async def upload(request, response, document=File(...)):
    async with aiofiles.open(f"/uploads/{document.filename}", "wb") as out:
        while chunk := await document.read(64 * 1024):
            await out.write(chunk)
    return {"stored": document.filename}
```

### Optional uploads

```python
avatar = File(None)      # None when nothing was attached
```

A required `File(...)` with nothing attached returns 422:

```json
{"detail": [{"loc": ["form", "avatar"], "msg": "Field required", "type": "missing"}]}
```

## urlencoded or multipart — you do not choose

Two separate decisions, and the distinction matters:

- **Your markers** decide *that* the body is parsed as a form.
- **The client's `Content-Type`** decides *which parser* runs — `multipart/form-data` or `application/x-www-form-urlencoded`.

So one set of `Form` declarations accepts both encodings. A route with only `Form` markers works whether the client posts a plain form or multipart.

If a client sends something else entirely — `application/json`, say — form parsing yields nothing and you get a clean 422 listing every required field as missing, rather than a crash.

## Validating form fields

`Form` fields are validated exactly like query parameters — same types, same constraints, same coercion rules. Everything on the wire is text, so `type=` is what turns it into a usable value:

```python
from datetime import date
from decimal import Decimal
from enum import Enum

class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"

@app.post("/signup")
async def signup(request, response,
                 email=Form(type=str, pattern=r".+@.+\..+"),
                 age=Form(type=int, ge=13, le=120),
                 birthday=Form(None, type=date),
                 plan=Form(Plan.FREE, type=Plan),
                 amount=Form(type=Decimal, ge=0),
                 accepted_terms=Form(False, type=bool)):
    ...
```

Checkbox semantics deserve a note. An unchecked HTML checkbox sends **nothing at all** rather than `false`, so give it a default:

```python
subscribe = Form(False, type=bool)      # absent -> False
```

A checked box typically sends `on`, which Pydantic reads as `True` along with `true`, `1`, `yes`, `t`, and `y`.

Errors are reported under the `form` location:

```json
{"detail": [{"loc": ["form", "age"], "msg": "Input should be greater than or equal to 13",
             "type": "greater_than_equal"}]}
```

For the full type catalog and every constraint, see [Parameters](/guides/validation/parameters/).

## Repeated fields

Form data is a multidict, so a list-typed field collects every occurrence:

```python
from typing import List

@app.post("/tags")
async def add_tags(request, response, tag=Form([], type=List[str])):
    return {"tags": tag}
```

```bash
curl -X POST localhost:8000/tags -d 'tag=red&tag=blue'   # -> ["red", "blue"]
```

This is how multi-select inputs and checkbox groups arrive from a browser.

## Validating uploads yourself

An `UploadFile` bypasses Pydantic — the object wraps a spooled file handle rather than data, so there is nothing meaningful for a validator to check. Constraints on a `File(...)` are silently inert. Enforce the rules that matter in your handler:

```python
from sillo.exceptions import HTTPException

MAX_BYTES = 5 * 1024 * 1024
ALLOWED = {"image/png", "image/jpeg", "image/webp"}

@app.post("/avatar")
async def upload(request, response, avatar=File(...)):
    if avatar.content_type not in ALLOWED:
        raise HTTPException(status_code=415,
                            detail=f"Unsupported type: {avatar.content_type}")

    content = await avatar.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    return {"size": len(content)}
```

Two cautions on trusting client-supplied metadata:

**`content_type` is a claim, not a fact.** It comes from the client and can say anything. If the distinction matters — if you will serve the file back, or process it — verify the actual bytes:

```python
import imghdr

content = await avatar.read()
if imghdr.what(None, h=content) not in {"png", "jpeg", "webp"}:
    raise HTTPException(status_code=415, detail="Not a valid image")
```

**`filename` is attacker-controlled.** Never join it onto a path directly — a filename of `../../etc/passwd` does exactly what it looks like. Generate your own name and keep the original only as a label:

```python
import uuid, pathlib

suffix = pathlib.Path(avatar.filename or "").suffix.lower()
if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
    raise HTTPException(status_code=415, detail="Unsupported extension")

stored_as = f"{uuid.uuid4()}{suffix}"
```

## Multiple files under one field

The marker binds a single file per field name. For a multi-upload input, read the form directly:

```python
@app.post("/gallery")
async def gallery(request, response, album=Form(type=str)):
    files = (await request.form).getlist("photos")
    for f in files:
        content = await f.read()
        ...
    return {"album": album, "count": len(files)}
```

The `album` marker still validates normally — the parsed form is cached, so reading it again is free.

## Reading the form directly

Mixing markers with manual access costs nothing:

```python
@app.post("/upload")
async def upload(request, response, caption=Form("", type=str)):
    form = await request.form        # served from cache
    files = await request.files      # {"avatar": UploadFile}
    return {"fields": list(form), "files": list(files)}
```

`request.form` returns a `FormData` multidict containing both text fields and files; `request.files` returns just the uploads.

## Two more limits

**Field errors short-circuit file errors.** If a `Form` field fails validation, the response reports that and does not also check for missing files. Fix the fields and any file errors surface on the next attempt.

**Do not mix with `request_model=`.** A request has one body, and it is either JSON or a form. Declaring both on one route means one always receives nothing.
