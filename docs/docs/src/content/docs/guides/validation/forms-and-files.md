---
title: Forms and file uploads
description: Declare form fields and uploads with Form and File markers. sillo picks urlencoded or multipart from the client's Content-Type, so one declaration handles both.
---

Form fields and file uploads are parameter markers, like every other input except the JSON body:

```python
from sillo import SilloApp, Form, File

app = SilloApp()

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

##  When to use a form instead of JSON

Two situations call for it. The first is a browser `<form>` posting directly to your API without JavaScript — that always sends urlencoded or multipart, never JSON. The second is **any request carrying a file**, because JSON has no way to represent binary content; base64 in a JSON string works but inflates the payload by a third and buffers the whole thing in memory.

Everything else is usually better served by a JSON body, where you get nested structures and a single model describing the whole payload.

##  File uploads

```python
from sillo import SilloApp, Form, File, Path

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

##  Working with an uploaded file

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

###  Streaming rather than buffering

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

###  Optional uploads

```python
avatar = File(None)      # None when nothing was attached
```

A required `File(...)` with nothing attached returns 422:

```json
{"detail": [{"loc": ["form", "avatar"], "msg": "Field required", "type": "missing"}]}
```

##  urlencoded or multipart — you do not choose

Two separate decisions, and the distinction matters:

- **Your markers** decide *that* the body is parsed as a form.
- **The client's `Content-Type`** decides *which parser* runs — `multipart/form-data` or `application/x-www-form-urlencoded`.

So one set of `Form` declarations accepts both encodings. A route with only `Form` markers works whether the client posts a plain form or multipart.

If a client sends something else entirely — `application/json`, say — form parsing yields nothing and you get a clean 422 listing every required field as missing, rather than a crash.

##  Validating form fields

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

##  Repeated fields

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

##  Validating uploads yourself

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

##  Multiple files under one field

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

##  Reading the form directly

Mixing markers with manual access costs nothing:

```python
@app.post("/upload")
async def upload(request, response, caption=Form("", type=str)):
    form = await request.form        # served from cache
    files = await request.files      # {"avatar": UploadFile}
    return {"fields": list(form), "files": list(files)}
```

`request.form` returns a `FormData` multidict containing both text fields and files; `request.files` returns just the uploads.

##  Two more limits

**Field errors short-circuit file errors.** If a `Form` field fails validation, the response reports that and does not also check for missing files. Fix the fields and any file errors surface on the next attempt.

**Do not mix with `request_model=`.** A request has one body, and it is either JSON or a form. Declaring both on one route means one always receives nothing.


##  Uploads are the highest-risk input you accept

A file upload hands an attacker a byte stream, a filename, and a
content type, and asks your server to do something with all three. Every
one of those is attacker-controlled. Five defences, in order of how often
they are missed.

###  Never trust the filename

The client chooses `filename`, and it may contain path separators, null
bytes, unicode that normalises to `..`, or a name that overwrites
something important.

```python title="the traversal that works"
filename = "../../../etc/cron.d/backdoor"
open(f"/uploads/{filename}", "wb").write(content)     # writes outside /uploads
```

Never use the client's filename as a path component. Generate your own
name and keep theirs only as a display label:

```python title="safe storage"
import uuid
from pathlib import Path as FSPath

stored_name = f"{uuid.uuid4().hex}{FSPath(upload.filename).suffix.lower()[:10]}"
destination = FSPath("/var/uploads") / stored_name
```

Even the extension needs bounding — a `.suffix` from a filename of a
thousand dots is a thousand-character extension.

###  Never trust the content type

`Content-Type` on a multipart part is whatever the client wrote. A PHP
script uploaded as `image/png` is still a PHP script. Detect the type
from the bytes — a magic-number check on the first few bytes — and reject
anything whose real type is not on your allowlist.

Use an allowlist, never a blocklist. A blocklist of dangerous extensions
misses the one you did not think of; an allowlist of `png`, `jpeg`, `pdf`
is complete by construction.

###  Bound the size before reading

An upload with no size limit is a memory exhaustion bug waiting for
someone to notice. Check `upload.size` before reading the content, and
enforce a limit at the proxy as well — nginx's `client_max_body_size`
rejects the request before it reaches Python at all, which is the only
place a limit costs you nothing.

Bound the *count* too. Ten thousand small files in one multipart request
is as effective a denial of service as one enormous file.

###  Store uploads outside the web root

A file inside a directory your server serves statically is a file the
attacker can request back. If the upload was a script and the directory
is executed by anything, that is remote code execution. Store uploads
outside any served path and serve them through a handler that checks
authorization and sets `Content-Disposition: attachment` and
`X-Content-Type-Options: nosniff`.

Serving user uploads from your main domain also means an uploaded HTML
file runs with your origin's cookies. A separate domain for user content
is the standard mitigation.

###  Scan what you keep

If uploads are shared between users, they are a malware distribution
channel. Scan asynchronously through the [queue](/guides/work/queue/) and
keep files quarantined until the scan returns — a synchronous scan in the
request handler adds seconds to an upload and blocks the event loop.

##  Streaming large uploads

`upload.read()` with no argument loads the whole file into memory. For a
50 MB video and ten concurrent uploads, that is 500 MB of resident memory
in a process that also has to serve requests.

Read in chunks instead, and write as you go:

```python title="constant memory regardless of file size"
async def store_streaming(upload, destination, chunk_size=64 * 1024):
    total = 0
    with open(destination, "wb") as out:
        while chunk := await upload.read(chunk_size):
            total += len(chunk)
            if total > MAX_BYTES:
                out.close()
                destination.unlink(missing_ok=True)
                raise ValueError("file too large")
            out.write(chunk)
    return total
```

Checking the running total inside the loop matters: `upload.size` comes
from the client's `Content-Length` and a client may lie, so the only
limit you can trust is the one you count yourself.

The `open()` call is synchronous and blocks the event loop for the
duration of each write. At 64 KB chunks that is microseconds and
tolerable; for sustained high-volume uploads, offload the whole store
operation with `asyncio.to_thread`.

##  Forms and CSRF

A browser will submit a form to your endpoint from any origin unless you
stop it. That is what CSRF protection is for, and it applies to form
endpoints far more than to JSON APIs, because a cross-origin form POST
needs no JavaScript and no CORS permission.

A JSON endpoint has partial protection by accident: sending
`Content-Type: application/json` cross-origin triggers a preflight, which
CORS will refuse. A form endpoint accepting
`application/x-www-form-urlencoded` triggers no preflight at all.

If your form endpoints authenticate with cookies, they need CSRF tokens.
See [CSRF](/guides/csrf/) for the middleware and the template integration
— the token is available as `csrf_token` in any template rendered with
`request=request`.


##  A complete upload endpoint

Everything above, applied.

```python title="an upload endpoint that holds up"
import uuid
from pathlib import Path as FSPath

from sillo import File, Form, SilloApp

UPLOAD_ROOT = FSPath("/var/lib/app/uploads")     # outside any served path
MAX_BYTES = 10 * 1024 * 1024
ALLOWED = {
    b"\x89PNG\r\n\x1a\n": ".png",
    b"\xff\xd8\xff": ".jpg",
    b"%PDF-": ".pdf",
}


def detect(head: bytes) -> str | None:
    for magic, ext in ALLOWED.items():
        if head.startswith(magic):
            return ext
    return None


@app.post("/documents")
async def upload_document(
    request,
    response,
    title: str = Form(type=str, min_length=1, max_length=200),
    document=File(),
):
    if document.size and document.size > MAX_BYTES:
        return response.json({"error": "file too large"}, status_code=413)

    head = await document.read(8)
    await document.seek(0)
    extension = detect(head)
    if extension is None:
        return response.json({"error": "unsupported file type"}, status_code=415)

    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_ROOT / stored_name
    await document.save(destination)

    record = await Document.create(
        owner_id=request.user.id,
        title=title,
        stored_name=stored_name,
        original_name=document.filename[:255],   # kept for display only
        size=document.size,
        status="scanning",
    )
    await enqueue(ScanUpload, record.id)

    return response.json({"id": record.id, "status": "scanning"}, status_code=202)
```

Six decisions in there, each corresponding to a section above: size
checked before reading, type detected from bytes, name generated rather
than accepted, storage outside the web root, the original name kept only
as a truncated label, and scanning deferred to a worker with the record
marked `scanning` until it passes.

The `413` and `415` status codes are worth using precisely — `413 Payload
Too Large` and `415 Unsupported Media Type` tell a client exactly which
rule it broke, where a generic 400 makes them guess.
