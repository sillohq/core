---
title: "Sillo Helpers Reference"
description: "Files, retry, crypto, JWT, network, HTML, strings, text utilities"
---

> Internal engineering reference for every module under `core/sillo/helpers/` and
> the adjacent `core/sillo/core/helpers/` and `core/sillo/hashing/` packages.

---

## Architecture Overview

The helpers package is a collection of **stateless utility modules** with no
framework coupling: none of them import `sillo.application`, `Request`, or any
ORM model. This makes them safe to use from CLI commands, background workers,
tests, and other non-request contexts.

```mermaid
graph TD
    subgraph "sillo.helpers"
        FILES["files.py<br/>15 functions"]
        RETRY["retry.py<br/>RetryError + 3 fns"]
        CRYPTO["crypto.py<br/>Fernet + HMAC"]
        JWT["jwt.py<br/>PyJWT wrapper"]
        NET["network.py<br/>12 IP utilities"]
        HTML["html.py<br/>7 functions"]
        STR["strings.py<br/>13 functions"]
        TEXT["text.py<br/>9 functions"]
        HASH["hashing.py<br/>compat wrapper"]
    end

    subgraph "sillo.core.helpers"
        ASYNC["async_helpers.py<br/>is_async_callable + protocols"]
    end

    subgraph "sillo.hashing"
        HCORE["core.py<br/>bcrypt/passlib"]
        HCONF["config.py<br/>SchemeConfig"]
        HEXC["exceptions.py"]
        HUT["utils.py<br/>validate_password"]
    end

    HASH -->|re-exports| HCORE
    HASH -->|re-exports| HUT
    HASH -->|re-exports| HEXC
    HCORE --> HCONF

    RETRY -.->|uses| ASYNC
    CRYPTO -.->|independent|
    JWT -.->|independent|
    FILES -.->|independent|
    NET -.->|independent|
    HTML -.->|independent|
    STR -.->|independent|
    TEXT -.->|independent|

    style ASYNC fill:#e8f4fd,stroke:#2196F3
    style HASH fill:#fff3e0,stroke:#FF9800
    style HCORE fill:#fff3e0,stroke:#FF9800
```

**Design principle:** Each helper module uses lazy imports for optional
dependencies (`cryptography`, `PyJWT`) and raises `ImportError` with a
descriptive message at call time rather than at import time.

---

## files.py: File Utilities

**File:** `core/sillo/helpers/files.py`
**Lines:** ~410
**Imports:** `mimetypes`, `os`, `re`, `time`, `unicodedata`, `pathlib.Path`

### Constants

| Name | Type | Value |
|------|------|-------|
| `_SIZE_UNITS` | `list[str]` | `["B", "KB", "MB", "GB", "TB", "PB"]` |
| `_DANGEROUS_EXTENSIONS` | `frozenset[str]` | 17 entries. See below |
| `_SAFE_NAME_RE` | `re.Pattern` | `r"[^\w.\-]"` |
| `_EXT_RE` | `re.Pattern` | `r"\.([a-zA-Z0-9]+)$"` |

#### Dangerous extensions (full set)

```
exe, dll, so, sh, bash, bat, cmd, com, php, py, rb, pl, js, vbs, ps1, msi, app
```

### Functions

#### `format_size(bytes_value: float) -> str`

Format a byte count using **SI decimal** unit names (KB, MB, …) but with
**base-1024** arithmetic (not base-1000).  This is the "OS convention" where
1 KB = 1024 bytes.

**Algorithm:**
1. Iterate `_SIZE_UNITS` from largest to smallest.
2. Find the first unit where `bytes_value >= 1024 ** index`.
3. Divide and format: whole number for bytes, one decimal place otherwise.

**Examples:**
```
format_size(0)        → "0 B"
format_size(1023)     → "1023 B"
format_size(1024)     → "1.0 KB"
format_size(1536)     → "1.5 KB"
format_size(1048576)  → "1.0 MB"
```

#### `format_size_binary(bytes_value: float) -> str`

Same algorithm as `format_size` but uses IEC binary unit names: B, KiB, MiB,
GiB, TiB, PiB. Arithmetic is still base-1024, only the labels differ.

#### `parse_size(size_str: str) -> int`

Parse a human-readable size string back to bytes.

**Supported units** (case-insensitive, whitespace-tolerant):
| Token | Multiplier |
|-------|-----------|
| `b`, `byte`, `bytes` | 1 |
| `k`, `kb`, `kib` | 1 024 |
| `m`, `mb`, `mib` | 1 048 576 |
| `g`, `gb`, `gib` | 1 073 741 824 |
| `t`, `tb`, `tib` | 1 099 511 627 776 |

**Algorithm:**
1. Strip whitespace, split numeric prefix from unit suffix via regex.
2. If no unit suffix, treat as raw bytes.
3. Lookup multiplier in unit map.
4. `int(float(numeric_part) * multiplier)`.

**Raises:** `ValueError` on unrecognised format.

**Examples:**
```
parse_size("10MB")   → 10485760
parse_size("1.5 GB") → 1610612736
parse_size("512")    → 512
```

#### `get_extension(filename: str) -> str`

Returns the file extension **including** the leading dot, lowercased.
Delegates to `os.path.splitext`.  Returns `""` if no extension.

```
get_extension("photo.JPEG")  → ".jpeg"
get_extension("Makefile")    → ""
```

#### `get_extension_clean(filename: str) -> str`

Same as `get_extension()` but strips the leading dot.

```
get_extension_clean("photo.JPEG")  → "jpeg"
```

#### `guess_mime_type(filename: str) -> str | None`

Guesses the MIME type using `mimetypes.guess_type`.  Returns `None` when
unrecognised (not an empty string).

#### `is_dangerous_extension(filename: str) -> bool`

Checks if the extension (extracted via `get_extension_clean`) is a member of
the `_DANGEROUS_EXTENSIONS` frozenset.  This is a **fast membership test**
(O(1) average) against a static set of known dangerous file types.

```python
is_dangerous_extension("script.exe")   # True
is_dangerous_extension("photo.jpg")    # False
is_dangerous_extension("README")       # False (no extension)
```

#### `safe_filename(filename: str, replacement: str = "_") -> str`

Sanitise a filename for safe storage on disk.

**Algorithm:**
1. Apply NFKD Unicode normalisation.
2. Encode to ASCII, ignoring non-ASCII characters.
3. Replace characters matching `[^\w.\-]` with `replacement`.
4. If the result is empty, `"."`, or `".."`, prepend `"file"`.

```
safe_filename("../../etc/passwd")  → ".._.._.._etc_passwd"
safe_filename("")                  → "file"
safe_filename("résumé.pdf")       → "rsum.pdf"
```

#### `unique_filename(directory: str | Path, filename: str) -> str`

Generate a unique filename by appending a counter suffix.

**Algorithm:**
1. Split filename into stem and extension.
2. Try the original name first.
3. If it exists in `directory`, try `stem(1).ext`, `stem(2).ext`, etc.
4. Return the first name that doesn't collide.

```
unique_filename("/tmp", "report.pdf")
# → "report.pdf"        (if available)
# → "report(1).pdf"     (if "report.pdf" exists)
# → "report(2).pdf"     (if both exist)
```

#### `is_image_extension(filename: str) -> bool`

Returns `True` if `guess_mime_type` starts with `"image/"`.

#### `is_media_extension(filename: str) -> bool`

Returns `True` if `guess_mime_type` starts with `"image/"`, `"audio/"`, or
`"video/"`.

#### `file_age(path: str | Path) -> float`

Returns the number of seconds since the file was last modified:
`time.time() - os.path.getmtime(path)`.

#### `file_age_human(path: str | Path) -> str`

Human-readable relative age string:
| Range | Format |
|-------|--------|
| < 60 s | `"Xs ago"` |
| < 3600 s | `"Xm ago"` |
| < 86400 s | `"Xh ago"` |
| ≥ 86400 s | `"Xd ago"` |

#### `ensure_directory(path: str | Path) -> Path`

`Path(path).mkdir(parents=True, exist_ok=True)`, creates the directory and all
parents. Returns the `Path` object for chaining.

#### `list_files(directory, pattern="*", recursive=False) -> list[Path]`

List files matching a glob pattern.  Uses `Path.rglob` when `recursive=True`,
otherwise `Path.glob`.  Returns a `list[Path]`.

---

## retry.py: Retry with Exponential Backoff

**File:** `core/sillo/helpers/retry.py`
**Lines:** ~284
**Imports:** `asyncio`, `functools`, `inspect`, `random`, `time`

### Class: `RetryError(Exception)`

```python
class RetryError(Exception):
    last_exception: BaseException | None
```

Raised when all retry attempts have been exhausted.  The `last_exception`
attribute preserves the final caught exception for diagnostic purposes.

### Internal: `_compute_delay`

```python
def _compute_delay(
    attempt: int,
    base: float,
    factor: float,
    cap: float,
    jitter: bool,
) -> float
```

**Algorithm:**
```
delay = min(base * (factor ** attempt), cap)
if jitter:
    delay = random.uniform(0, delay)
return delay
```

With defaults (`base=1.0`, `factor=2.0`, `cap=60.0`):
| Attempt | Raw delay | Cap applied |
|---------|-----------|-------------|
| 0 | 1.0 s | 1.0 s |
| 1 | 2.0 s | 2.0 s |
| 2 | 4.0 s | 4.0 s |
| 3 | 8.0 s | 8.0 s |
| 4 | 16.0 s | 16.0 s |
| 5 | 32.0 s | 32.0 s |
| 6 | 64.0 s | **60.0 s** |

### Decorator: `retry`

```python
def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: type[Exception] | tuple[type[Exception], ...] = Exception,
) -> F
```

A decorator that works on **both sync and async** functions.  Auto-detection
uses `inspect.iscoroutinefunction` (with `functools.partial` unwrapping).

**Behaviour:**
1. Call the wrapped function.
2. On success, return the result.
3. On `retryable_exceptions`, compute delay via `_compute_delay`, sleep
   (`time.sleep` or `asyncio.sleep`), then retry.
4. After `max_attempts` failures, raise `RetryError` with `last_exception`.

```python
@retry(max_attempts=5, backoff_factor=3.0, jitter=True)
async def fetch_remote(url: str) -> bytes:
    ...
```

### Standalone: `async_retry`

```python
async def async_retry(
    coro: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: ... = Exception,
    **kwargs: Any,
) -> Any
```

Standalone async retry (not a decorator).  Calls `coro(*args, **kwargs)` with
retry logic using `asyncio.sleep`.

### Standalone: `sync_retry`

```python
def sync_retry(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    ...
    **kwargs: Any,
) -> Any
```

Same as `async_retry` but synchronous, using `time.sleep`.

---

## crypto.py: Symmetric Encryption & Signing

**File:** `core/sillo/helpers/crypto.py`
**Lines:** ~255
**Imports:** `base64`, `hmac`, `secrets`, and optionally
`cryptography.fernet.Fernet`, `cryptography.hazmat.primitives.hashes`,
`cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC`

### Optional dependency guard

```python
_crypto_available: bool  # True if cryptography is importable
```

Every public function that needs `cryptography` calls `_ensure_crypto()` first,
which raises `ImportError("cryptography is required for ...")` if unavailable.

### Class: `BadSignature(Exception)`

Raised when HMAC verification of a signed value fails (tampered or incorrect
secret).

### Functions

#### `generate_key() -> bytes`

Generate a new Fernet key: `Fernet.generate_key()`.  Returns a 32-byte
URL-safe base64-encoded `bytes` object.

#### `encrypt(value: str, key: bytes) -> str`

```python
Fernet(key).encrypt(value.encode()).decode()
```

Returns a URL-safe base64-encoded ciphertext string.  Fernet uses AES-128-CBC
with HMAC-SHA256 authentication.

#### `decrypt(token: str, key: bytes) -> str`

```python
Fernet(key).decrypt(token.encode()).decode()
```

Raises `cryptography.fernet.InvalidToken` on tampered or expired tokens.

#### `derive_key`

```python
def derive_key(
    password: str,
    salt: bytes | None = None,
    length: int = 32,
    iterations: int = 600_000,
) -> tuple[bytes, bytes]
```

Derives a key from a password using **PBKDF2-HMAC-SHA256**.

| Parameter | Default | Notes |
|-----------|---------|-------|
| `password` |  | UTF-8 encoded before derivation |
| `salt` | `None` | Auto-generated 16-byte random salt if `None` |
| `length` | 32 | Derived key length in bytes |
| `iterations` | 600 000 | OWASP-recommended minimum for SHA-256 |

Returns `(derived_key, salt)`. The caller must **store the salt** alongside the
ciphertext.

#### `sign_value`

```python
def sign_value(
    value: str,
    secret: str,
    algorithm: str = "sha256",
) -> str
```

Creates an HMAC signature: `"<base64url_payload>.<hex_signature>"`.

**Algorithm:**
1. `payload = base64.urlsafe_b64encode(value.encode()).rstrip(b"=")`
2. `sig = hmac.new(secret.encode(), payload, hashlib.<algorithm>).hexdigest()`
3. Return `f"{payload.decode()}.{sig}"`

#### `unsign_value`

```python
def unsign_value(
    signed: str,
    secret: str,
    algorithm: str = "sha256",
    max_age: int | None = None,
) -> str
```

Verifies an HMAC signature using **`hmac.compare_digest`** (constant-time
comparison to prevent timing attacks).

**Algorithm:**
1. Split on `.`: expect exactly 2 parts.
2. Recompute the expected signature.
3. Compare with `hmac.compare_digest(actual, expected)`.
4. On mismatch, raise `BadSignature`.
5. Decode and return the original value.

**Note:** `max_age` is accepted for API compatibility but is reserved for
future timestamp-based expiry.

---

## jwt.py: JSON Web Tokens

**File:** `core/sillo/helpers/jwt.py`
**Lines:** ~424
**Imports:** `datetime`, `json`, and optionally `jwt` (PyJWT)

### Exception hierarchy

```
TokenError(Exception)
├── ExpiredTokenError
└── InvalidTokenError_     (trailing underscore — avoids clash with PyJWT)
```

### Key constants

| Constant | Value |
|----------|-------|
| Default access token TTL | **15 minutes** |
| Default refresh token TTL | **7 days** |
| Default algorithm | `HS256` |

### Functions

#### `encode`

```python
def encode(
    payload: dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
    headers: dict[str, Any] | None = None,
) -> str
```

Delegates to `pyjwt.encode`.  Returns a JWT string.

#### `decode`

```python
def decode(
    token: str,
    secret: str,
    algorithms: list[str] | None = None,
    options: dict[str, Any] | None = None,
    audience: str | None = None,
    issuer: str | None = None,
    leeway: int = 0,
) -> dict[str, Any]
```

Delegates to `pyjwt.decode`.  Catches PyJWT exceptions and re-raises as
Sillo's own hierarchy:
- `ExpiredSignatureError` → `ExpiredTokenError`
- `InvalidTokenError` / `DecodeError` → `InvalidTokenError_`

#### `sign` / `verify`

```python
def sign(payload, secret, algorithm="HS256", headers=None) -> bytes
def verify(token, secret, algorithms=None) -> bool
```

`sign` is like `encode` but returns UTF-8 `bytes`.  `verify` returns `True` if
the token decodes without error, `False` otherwise.

#### `get_unverified_header(token: str) -> dict[str, Any]`

Parses the JWT header without verification.  Delegates to
`pyjwt.get_unverified_header`.

#### `get_unverified_claims(token: str) -> dict[str, Any] | None`

Manually base64url-decodes the middle segment and parses JSON.  Returns `None`
on any failure (instead of raising).  Useful for inspecting expired tokens.

#### `create_access_token`

```python
def create_access_token(
    data: dict[str, Any],
    secret: str,
    expires_delta: timedelta | None = None,
    algorithm: str = "HS256",
    issuer: str | None = None,
) -> str
```

Adds claims:
- `exp`: `datetime.utcnow() + expires_delta` (default 15 min)
- `iat`: `datetime.utcnow()`
- `iss`: only if `issuer` is provided

#### `create_refresh_token`

```python
def create_refresh_token(
    data: dict[str, Any],
    secret: str,
    expires_delta: timedelta | None = None,
    algorithm: str = "HS256",
) -> str
```

Same as `create_access_token` but with a 7-day default TTL and no `iss` claim.

#### `decode_without_verification(token: str) -> dict[str, Any]`

Decodes a JWT without verifying the signature:
```python
pyjwt.decode(token, options={"verify_signature": False})
```
Raises `InvalidTokenError_` on structural failure.

#### `validate_claims`

```python
def validate_claims(
    payload: dict[str, Any],
    audience: str | None = None,
    issuer: str | None = None,
    leeway: int = 0,
) -> bool
```

Manually validates standard claims against current UTC time:
- `exp`: must not be in the past (with leeway)
- `nbf`: must not be in the future (with leeway)
- `aud`: must match if `audience` is provided
- `iss`: must match if `issuer` is provided

---

## network.py: IP Address Utilities

**File:** `core/sillo/helpers/network.py`
**Lines:** ~292
**Imports:** `ipaddress`, `typing`

### Constants

| Name | Value |
|------|-------|
| `_LOOPBACK_V4` | `127.0.0.0/8` |
| `_LOOPBACK_V6` | `::1/128` |
| `_PRIVATE_NETS` | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `fc00::/7`, `fd00::/8` |

### Functions

#### `normalize_ip(ip: str) -> str`

Normalises an IP string via `str(ipaddress.ip_address(ip.strip()))`.  Handles
IPv4-mapped IPv6 addresses (e.g. `::ffff:127.0.0.1` → `127.0.0.1`).
**Raises** `ValueError` on invalid input.

#### `is_valid_ip(ip: str) -> bool`

Try-parse wrapper.  Returns `True`/`False` instead of raising.

#### `is_ipv4(ip: str) -> bool` / `is_ipv6(ip: str) -> bool`

Try-parse as `IPv4Address` / `IPv6Address` only.

#### `is_loopback_ip(ip: str) -> bool`

`ipaddress.ip_address(ip).is_loopback`

#### `is_private_ip(ip: str) -> bool`

`ipaddress.ip_address(ip).is_private`

#### `is_public_ip(ip: str) -> bool`

`True` if not private, loopback, link-local, reserved, or unspecified.

#### `is_trusted_proxy`

```python
def is_trusted_proxy(
    ip: str,
    trusted_proxies: list[str] | None = None,
) -> bool
```

- If `trusted_proxies` is `None`, returns `is_loopback_ip(ip) or is_private_ip(ip)`.
- If provided, checks whether the IP falls within any of the listed CIDR networks.

#### `get_client_ip`

```python
def get_client_ip(
    request_headers: Mapping[str, str],
    remote_addr: str,
    trusted_proxies: list[str] | None = None,
    proxy_headers: list[str] | None = None,
) -> str
```

Resolves the real client IP behind proxies.

**Default proxy headers** (checked in order):
1. `x-forwarded-for`
2. `x-real-ip`
3. `cf-connecting-ip`

**Algorithm for `x-forwarded-for`:**
1. Parse the comma-separated chain (leftmost = original client, rightmost = last proxy).
2. Walk the chain **in reverse** (from rightmost to leftmost).
3. Return the first IP that is **not** a private/loopback address.
4. Fall back to `remote_addr` if no public IP is found.

#### `ip_to_int(ip: str) -> int` / `int_to_ip(value: int, version=4) -> str`

Convert between IP address strings and integer representations.
`int_to_ip` defaults to IPv4; pass `version=6` for IPv6.

#### `subnet_contains(subnet: str, ip: str) -> bool`

```python
ipaddress.ip_address(ip) in ipaddress.ip_network(subnet)
```
Returns `False` on `ValueError` (invalid input) instead of raising.

---

## html.py: HTML Sanitisation & Escape

**File:** `core/sillo/helpers/html.py`
**Lines:** ~251
**Imports:** `html`, `re`, `html.parser.HTMLParser`

### Constants

| Name | Value |
|------|-------|
| `_ALLOWED_TAGS_DEFAULT` | `b, i, em, strong, a, p, br, ul, ol, li, code, pre, span` |
| `_ALLOWED_ATTRS_DEFAULT` | `href, title, class, id, target, rel` |
| `_XSS_PATTERNS` | `javascript\s*:`, `on\w+\s*=`, `data\s*:`, `vbscript\s*:` (all case-insensitive) |
| `_ATTR_RE` | `(\w+)\s*=\s*["']([^"']*)["']` |

### Functions

#### `escape_html(text: str) -> str`

`html.escape(text, quote=True)`: escapes `&`, `<`, `>`, `"`, `'`.

#### `unescape_html(text: str) -> str`

`html.unescape(text)`, reverses HTML entity encoding.

#### `strip_tags(html: str) -> str`

Uses an internal `Stripper(HTMLParser)` class that collects `handle_data`
fragments.  Returns the concatenated text content.

#### `sanitize_html`

```python
def sanitize_html(
    html: str,
    allowed_tags: set[str] | frozenset[str] | None = None,
    allowed_attrs: set[str] | frozenset[str] | None = None,
    strip: bool = True,
) -> str
```

**Two-phase algorithm:**
1. **XSS pattern removal:** Applies `_XSS_PATTERNS` regex substitutions to
   strip `javascript:`, `on*=`, `data:`, `vbscript:` from the entire input.
2. **Tag filtering** (when `strip=True`): Parses tags character-by-character:
   - Allowed tags are kept, but their attributes are filtered against the
     allowed attribute set and re-scanned for XSS patterns.
   - Disallowed tags are stripped entirely (opening and closing tags removed,
     content preserved).

#### `safe_attrs(attrs: dict[str, str]) -> str`

Renders a dict to HTML attribute pairs: `key="escaped_value"`.  Keys are
lowercased; values are HTML-escaped.

#### `generate_safe_id(text: str) -> str`

Slug-style ID generation:
1. Lowercase.
2. Replace spaces with hyphens.
3. Strip `[^\w\-]`.
4. Collapse consecutive hyphens.
5. If empty or starts with a digit, prepend `"id-"`.

#### `linkify(text: str) -> str`

Wraps `https?://` URLs in anchor tags:
```html
<a href="..." rel="noopener noreferrer" target="_blank">...</a>
```

The `rel="noopener noreferrer"` prevents tab-napping attacks.

---

## strings.py: String Transformations

**File:** `core/sillo/helpers/strings.py`
**Lines:** ~319
**Imports:** `re`, `secrets`, `string`, `unicodedata`

### Constants

| Name | Pattern |
|------|---------|
| `_CAMEL_TO_SNAKE_RE` | `([A-Z]+)([A-Z][a-z])` |
| `_CAMEL_TO_SNAKE_RE2` | `([a-z\d])([A-Z])` |
| `_SNAKE_TO_CAMEL_RE` | `_([a-zA-Z\d])` |
| `_SLUG_RE` | `[^\w\s-]` |
| `_SLUG_SPACE_RE` | `[-\s]+` |

### Functions

#### `slugify(text: str, separator: str = "-") -> str`

1. NFKD normalise.
2. Encode to ASCII (ignore non-ASCII).
3. Strip non-alphanumeric/non-space/non-hyphen characters.
4. Lowercase.
5. Replace runs of spaces/hyphens with `separator`.

#### `camel_to_snake(name: str) -> str`

Two-pass regex substitution:
1. `([A-Z]+)([A-Z][a-z])` → `\1_\2` (handles `HTTPServer` → `HTTP_Server`)
2. `([a-z\d])([A-Z])` → `\1_\2` (handles `myVar` → `my_Var`)
3. `.lower()`

```
"HTTPServer"    → "http_server"
"getHTTPResponse" → "get_http_response"
```

#### `snake_to_camel(name: str, capitalize_first: bool = False) -> str`

Regex `_([a-zA-Z\d])` → uppercase group.  Optionally capitalises the first
character (PascalCase variant).

```
snake_to_camel("http_server")              → "httpServer"
snake_to_camel("http_server", capitalize_first=True) → "HttpServer"
```

#### `pascal_case(name: str) -> str`

Shortcut for `snake_to_camel(name, capitalize_first=True)`.

#### `kebab_case(name: str) -> str`

Same two-pass regex as `camel_to_snake` but joins with `-` instead of `_`.

#### `mask_string`

```python
def mask_string(
    value: str,
    visible_start: int = 4,
    visible_end: int = 4,
    mask_char: str = "*",
) -> str
```

Shows the first `visible_start` and last `visible_end` characters, masks
everything in between.  If the string is too short, masks entirely.

```
mask_string("1234567890")      → "1234******7890"
mask_string("abc")             → "***"
```

#### `mask_email(email: str) -> str`

Preserves the first and last character of the local part, masks the middle
with `*`.  Domain is unchanged.

```
mask_email("john.doe@example.com") → "j******e@example.com"
mask_email("ab@c.com")            → "a*@c.com"
```

#### `random_string(length=32, chars=None) -> str`

`secrets.choice` from `chars` (default: `ascii_letters + digits`).

#### `random_digits(length=6) -> str`

`secrets.choice(string.digits)` repeated `length` times.

#### `random_token(length=64) -> str`

`secrets.token_urlsafe(length)`, returns a URL-safe base64-encoded token.

#### `strip_accents(text: str) -> str`

NFKD normalise, filter out combining characters (`unicodedata.combining`).

```
strip_accents("café résumé") → "cafe resume"
```

#### `is_camel_case(text: str) -> bool`

`text != text.lower() and text != text.upper() and "_" not in text`

#### `is_snake_case(text: str) -> bool`

`text == text.lower() and "_" in text and not text.startswith("_")`

---

## text.py: Text Processing

**File:** `core/sillo/helpers/text.py`
**Lines:** ~260
**Imports:** `re`

### Constants

| Name | Pattern |
|------|---------|
| `_HTML_TAG_RE` | `<[^>]*>` |
| `_MULTI_SPACE_RE` | `\s+` |
| `_WORD_RE` | `\w+` |
| `_PLURAL_IRREGULARS` | 14 English irregular plurals |

### `_PLURAL_IRREGULARS` (full dict)

```python
{
    "child": "children", "man": "men", "woman": "women",
    "person": "people", "mouse": "mice", "goose": "geese",
    "tooth": "teeth", "foot": "feet", "ox": "oxen",
    "crisis": "crises", "analysis": "analyses",
    "phenomenon": "phenomena", "criterion": "criteria",
    "datum": "data",
}
```

### Functions

#### `truncate(text: str, max_length: int, suffix: str = "...") -> str`

If `len(text) > max_length`, cut to `max_length - len(suffix)`, rstrip
whitespace, append `suffix`.  Otherwise return as-is.

#### `excerpt`

```python
def excerpt(text: str, query: str, radius: int = 50) -> str
```

Extracts a contextual window around a query match.

**Algorithm:**
1. Strip HTML from `text`.
2. Find `query` (case-insensitive) in the stripped text.
3. Return `radius` characters on each side of the match, with `"..."` markers.
4. If query not found, fall back to `truncate(stripped, radius * 2)`.

#### `strip_html(text: str) -> str`

Regex-based: `_HTML_TAG_RE.sub(" ", text)` then `_MULTI_SPACE_RE.sub(" ",
...).strip()`. Lighter than `html.strip_tags`, doesn't need `HTMLParser`.

#### `pluralize(word: str, count: int) -> str`

If `count == 1`, return the word.  Otherwise, apply English pluralisation rules
in order:

1. **Irregular lookup.** Check `_PLURAL_IRREGULARS` dict.
2. **Sibilant endings**: words ending in `s`, `x`, `z`, `ch`, `sh` → add
   `"es"`.
3. **Consonant + y**: replace `y` with `"ies"` (e.g. `city` → `cities`).
4. **f/fe endings**: replace `f`/`fe` with `"ves"` (e.g. `knife` → `knives`).
5. **Default.** Add `"s"`.

#### `word_count(text: str) -> int`

`len(_WORD_RE.findall(text))`, counts sequences of word characters.

#### `ellipsis(text: str, max_lines: int) -> str`

Line-level truncation.  Splits on `\n`, keeps the first `max_lines` lines,
appends `"\n..."` if truncated.

#### `wrap_text(text: str, width: int = 80) -> str`

Word-wrap: assembles lines not exceeding `width` characters per line.  Words
are never split mid-word.

#### `extract_urls(text: str) -> list[str]`

Regex: `https?://[^\s<>"'\)\[\]{}|\\^`]+`

#### `extract_emails(text: str) -> list[str]`

Regex: `[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}`

---

## hashing.py: Hashing (Compat Wrapper)

**File:** `core/sillo/helpers/hashing.py`
**Lines:** ~194
**Imports:** `hashlib`, plus re-exports from `sillo.hashing`

This module is a **backward-compatibility layer** that re-exports functions
from the top-level `sillo.hashing` package while adding a few local utilities.

### Re-exported from `sillo.hashing`

| Function | Delegates to |
|----------|-------------|
| `hash_password(password, scheme="bcrypt")` | `sillo.hashing.core.hash_password` |
| `verify_password(password, hashed)` | `sillo.hashing.core.verify_password` |
| `md5(data)` | `sillo.hashing.utils.md5` |
| `sha256(data)` | `sillo.hashing.utils.sha256` |
| `constant_time_compare(val1, val2)` | `sillo.hashing.utils.constant_time_compare` |

### Local implementations

#### `sha512(data: str | bytes) -> str`

```python
hashlib.sha512(data.encode() if isinstance(data, str) else data).hexdigest()
```

#### `digest(data: str | bytes, algorithm: str = "sha256") -> str`

Generic digest: `hashlib.new(algorithm).update(data).hexdigest()`.  Supports
any algorithm available in the system OpenSSL.

#### `hash_file(path: str, algorithm: str = "sha256", chunk_size: int = 65536) -> str`

Reads the file in `chunk_size` (default 64 KB) byte chunks, streaming the
data through `hashlib.new(algorithm)`.  Memory-efficient for large files.

#### `random_salt(length: int = 16) -> str`

`secrets.token_hex(length)`, returns `length * 2` hex characters.

#### `sha1(data: str | bytes) -> str`

`hashlib.sha1(...).hexdigest()`.  **Note:** SHA-1 is cryptographically weak;
use only for non-security purposes (e.g. cache keys, ETags).

#### `hmac_digest(key, data, algorithm="sha256") -> str`

```python
hmac.new(
    key.encode() if isinstance(key, str) else key,
    data.encode() if isinstance(data, str) else data,
    hashlib.new(algorithm),
).hexdigest()
```

---

## sillo.hashing: Top-Level Hashing Package

**File:** `core/sillo/hashing/`
**Submodules:** `__init__.py`, `config.py`, `core.py`, `exceptions.py`, `utils.py`

### `config.py`: Scheme Configuration

```python
@dataclass
class SchemeConfig:
    name: str
    package: str | None = None
    default: bool = False
    deprecated: bool = False
```

| Scheme | Package | Default |
|--------|---------|---------|
| `bcrypt` | `bcrypt` | ✅ |
| `argon2` | `argon2-cffi` | |
| `scrypt` | `scrypt` | |
| `pbkdf2_sha256` | `None` (built-in) | |
| `pbkdf2_sha512` | `None` (built-in) | |

Functions: `get_default_scheme()`, `is_scheme_available(scheme)`, `get_available_schemes()`.

### `exceptions.py`

```
HashingError(Exception)
├── InvalidSchemeError
└── VerificationError
```

### `core.py`: Password Hashing Engine

Uses `passlib.context.CryptContext` as a lazy singleton.

| Function | Signature | Notes |
|----------|-----------|-------|
| `hash_password` | `(password, scheme=None, salt=None, **kwargs) -> str` | Fast-path for bcrypt via `bcrypt.hashpw`; falls back to passlib |
| `verify_password` | `(password, hashed) -> bool` | Fast-path for bcrypt hashes (`$2a$`/`$2b$`/`$2x$`/`$2y$` prefixes) |
| `needs_update` | `(hashed) -> bool` | `context.needs_update(hashed)` |
| `needs_rehash` | `(hashed, rounds=12) -> bool` | Checks if bcrypt rounds < specified |
| `set_default_scheme` | `(scheme) -> None` | |
| `get_available_schemes_list` | `() -> list[str]` | |

### `utils.py`: Utility Functions

| Function | Signature |
|----------|-----------|
| `make_unusable_password` | `() -> str`: `"!" + secrets.token_hex(40)` |
| `is_password_usable` | `(encoded) -> bool`: not starting with `"!"` |
| `validate_password` | `(password, user=None, min_length=8) -> list[str]`: checks length, upper, lower, digit, special |
| `password_strength` | `(password) -> dict`: score 0-6 with "weak"/"medium"/"strong" |
| `constant_time_compare` | `(val1, val2) -> bool`: `secrets.compare_digest` |
| `md5` | `(value) -> str` |
| `sha256` | `(value) -> str` |

---

## async_helpers.py: Async Utilities

**File:** `core/sillo/core/helpers/async_helpers.py`
**Lines:** ~256
**Imports:** `asyncio`, `functools`, `sys`, `typing`, `contextlib`, and
optionally `exceptiongroup` (backport for Python < 3.11)

### Protocols

#### `AwaitableOrContextManager[T_co]`

```python
class AwaitableOrContextManager(
    Awaitable[T_co],
    AsyncContextManager[T_co],
    Protocol[T_co],
): ...
```

A structural type for objects that are **both** awaitable **and** usable as
async context managers.  Used for dependency-injection factories that return
objects needing both `await` and `async with` semantics.

#### `SupportsAsyncClose`

```python
class SupportsAsyncClose(Protocol):
    async def close(self) -> None: ...
```

### Class: `AwaitableOrContextManagerWrapper`

```python
class AwaitableOrContextManagerWrapper[SupportsAsyncCloseType]:
    __slots__ = ("aw", "entered")

    def __init__(self, aw: Awaitable[SupportsAsyncCloseType]) -> None: ...
    def __await__(self) -> Generator[..., SupportsAsyncCloseType]: ...
    async def __aenter__(self) -> SupportsAsyncCloseType: ...
    async def __aexit__(self, *args) -> bool | None: ...
```

Wraps an `Awaitable[T]` where `T` has `.close()` into a value that satisfies
`AwaitableOrContextManager[T]`.

- `__await__`: delegates to `self.aw.__await__()`.
- `__aenter__`: `self.entered = await self.aw; return self.entered`.
- `__aexit__`: `await self.entered.close(); return None`.

### Function: `is_async_callable`

```python
@overload
def is_async_callable(obj: Callable[..., Awaitable[T]]) -> TypeGuard[AwaitableCallable[T]]: ...
@overload
def is_async_callable(obj: Any) -> TypeGuard[AwaitableCallable[Any]]: ...

def is_async_callable(obj: Any) -> Any:
    ...
```

**Algorithm:**
1. If `obj` is a `functools.partial`, unwrap to `obj.func`.
2. Check `asyncio.iscoroutinefunction(obj)`.
3. If not, check `callable(obj)` and `asyncio.iscoroutinefunction(obj.__call__)`.

This is critical for the DI system. It determines whether a dependency should
be `await`ed or called synchronously.

### Context Manager: `collapse_excgroups`

```python
@contextmanager
def collapse_excgroups() -> Generator[None, None, None]: ...
```

Catches `BaseException`; if it's a `BaseExceptionGroup` with **exactly 1**
exception, unwraps to the inner exception and re-raises it directly.  This
simplifies stack traces from `asyncio.TaskGroup` usage.

---

## Cross-Reference Matrix

| Module | Used by | Depends on |
|--------|---------|-----------|
| `files.py` | Upload handlers, CLI, admin | stdlib only |
| `retry.py` | HTTP clients, DB reconnect, queue workers | stdlib only |
| `crypto.py` | Session signing, token encryption, key derivation | `cryptography` (optional) |
| `jwt.py` | Auth backends, token factories, API auth | `PyJWT` (optional) |
| `network.py` | Proxy detection, rate limiting, logging, admin | stdlib only |
| `html.py` | Template rendering, user content sanitisation, admin | stdlib only |
| `strings.py` | Slug generation, model naming, secret generation | stdlib only |
| `text.py` | Template filters, search excerpts, admin display | stdlib only |
| `hashing.py` | Auth, password storage, API key hashing | `sillo.hashing`, `passlib`, `bcrypt` |
| `async_helpers.py` | DI system, middleware, ASGI bridge | stdlib + `exceptiongroup` (optional) |
