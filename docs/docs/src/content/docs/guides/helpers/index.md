---
title: Helpers
description: The utility modules that ship with sillo — what each one is for, which need extra dependencies, and which have sharp edges worth reading about first.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Helpers
  - tag: meta
    attrs:
      property: og:description
      content: The utility modules that ship with sillo — what each one is for, which need extra dependencies, and which have sharp edges worth reading about first.
---

#  Helpers

Every backend rewrites the same utilities. Slugify a title. Hash a password. Work out the real client IP behind a load balancer. Retry a flaky API call. Format a file size. None of it is hard, all of it is fiddly, and each one has an edge case that bites in production six months later.

sillo ships eleven modules covering that ground, so you are not maintaining a `utils.py` that slowly accretes subtle bugs.

##  The modules

| Module | Use it for | Dependency |
|---|---|---|
| [Strings](/guides/helpers/strings/) | Slugs, case conversion, secret masking, secure random tokens | stdlib |
| [Text](/guides/helpers/text/) | Truncation, search excerpts, pluralization, URL/email extraction | stdlib |
| [HTML](/guides/helpers/html/) | Escaping, tag stripping, safe attributes, linkification | stdlib |
| [Hashing](/guides/helpers/hashing/) | Password hashing, digests, HMAC, constant-time comparison | `bcrypt` |
| [Crypto](/guides/helpers/crypto/) | Symmetric encryption, key derivation, signed values | `cryptography` |
| [JWT](/guides/helpers/jwt/) | Encoding, decoding, and verifying JSON Web Tokens | `pyjwt` |
| [Network](/guides/helpers/network/) | Client IP behind proxies, address classification, subnets | stdlib |
| [Files](/guides/helpers/files/) | Size formatting, extension checks, safe filenames | stdlib |
| [Retry](/guides/helpers/retry/) | Exponential backoff with jitter for transient failures | stdlib |
| [Async](/guides/helpers/async/) | Detecting async callables, awaitable context managers | stdlib |
| [Deprecation](/guides/helpers/deprecation/) | Deprecation warnings for functions and parameters | stdlib |

Eight of the eleven need nothing installed, so most of this is available the moment you install sillo. Three optional packages cover the rest, and each is only needed if you use that specific module:

```bash
uv add bcrypt          # password hashing
uv add cryptography    # encryption and key derivation
uv add pyjwt           # JSON Web Tokens
```

##  Import paths

Most modules live under `sillo.helpers`:

```python
from sillo.helpers import strings, text, html, files, network, retry
from sillo.helpers import hashing, crypto, jwt
```

Or import the functions directly, which is what most codebases settle on:

```python
from sillo.helpers.strings import slugify, random_token
from sillo.helpers.hashing import hash_password, verify_password
```

:::caution[Two modules live under `sillo.core.helpers`]
[Async](/guides/helpers/async/) and [Deprecation](/guides/helpers/deprecation/) are framework internals and sit one level deeper. The `sillo.helpers` path for these two does not exist and raises `ModuleNotFoundError`:

```python
from sillo.helpers import deprecation             # ModuleNotFoundError
from sillo.core.helpers import deprecation        # correct

from sillo.helpers.async_helpers import is_async_callable        # ModuleNotFoundError
from sillo.core.helpers.async_helpers import is_async_callable   # correct
```
:::

##  Read these before you ship

Four of these modules touch security directly. Every page has its own warnings section; these are the ones that most often cause real incidents.

**[HTML](/guides/helpers/html/) — `sanitize_html` is not safe for untrusted input.** It is a regex scanner, not a parser, and has verified bypasses including entity-encoded and whitespace-split `javascript:` URLs. Use `nh3` or `bleach` for anything a stranger typed. That page shows the exact payloads that get through.

**[Network](/guides/helpers/network/) — `get_client_ip` trusts every header by default.** `trusted_proxies` defaults to `None`, which means "believe anyone". Any client can then claim any IP, defeating rate limiting, geoblocking, and audit logs. Always pass the parameter.

**[Hashing](/guides/helpers/hashing/) — never store a password with a digest.** `sha256` is built to be fast, which is exactly wrong for password storage. Use `hash_password`. Also note bcrypt's hard 72-byte input limit, which raises rather than truncating.

**[Crypto](/guides/helpers/crypto/) — `unsign_value(max_age=...)` does nothing.** The parameter is accepted and never read; there is no timestamp in the token format. Tokens you believe expire do not. Put the expiry inside the signed payload, or use [JWT](/guides/helpers/jwt/).

##  Picking the right module

Some of these overlap, and choosing wrong is the usual source of bugs.

**Hiding a value.** Do you need it back?

- Never → [`hash_password`](/guides/helpers/hashing/)
- Yes, and it must stay secret → [`encrypt`](/guides/helpers/crypto/)
- The user may read it but must not change it → [`sign_value`](/guides/helpers/crypto/) or [JWT](/guides/helpers/jwt/)
- Only to show it back to its owner → [`mask_string`](/guides/helpers/strings/)

**Removing markup.** Both `html.strip_tags` and `text.strip_html` remove tags. They are equivalent for ordinary content; use whichever module you already imported.

**Shortening text.** [`text.truncate`](/guides/helpers/text/) cuts by character, [`text.ellipsis`](/guides/helpers/text/) cuts by line, [`text.wrap_text`](/guides/helpers/text/) reflows without cutting.

**Making an identifier.** [`strings.slugify`](/guides/helpers/strings/) for URLs, [`html.generate_safe_id`](/guides/helpers/html/) for HTML anchors, [`files.safe_filename`](/guides/helpers/files/) for disk.

**Random values.** All of [`random_string`, `random_digits`, `random_token`](/guides/helpers/strings/) draw from `secrets`, so all are safe against guessing. Pick by output shape: alphanumeric, digits-only, or URL-safe base64.

##  A worked example

A registration endpoint touching five of these modules:

```python title="Registration, end to end"
from sillo import silloApp
from sillo.helpers.hashing import hash_password
from sillo.helpers.strings import random_token, slugify, mask_email
from sillo.helpers.network import get_client_ip

app = silloApp()
TRUSTED_PROXIES = ["10.0.0.0/8"]

@app.post("/register")
async def register(request, response):
    body = await request.json

    # bcrypt rejects anything over 72 bytes, so cap it before hashing.
    if len(body["password"].encode()) > 72:
        return response.json({"error": "Password too long"}, status_code=422)

    user = await User.create(
        email=body["email"],
        username_slug=slugify(body["display_name"]) or "user",
        password=hash_password(body["password"]),
        signup_ip=get_client_ip(
            request.headers, request.client.host, trusted_proxies=TRUSTED_PROXIES
        ),
        verify_token=random_token(32),
    )

    await send_verification_email(user)
    return response.json(
        {"message": f"Check {mask_email(user.email)} to confirm your account"},
        status_code=201,
    )
```

Five modules, five decisions: hash rather than encrypt the password because it never needs reading back, cap the length because bcrypt raises above 72 bytes, generate the token from `secrets` because a guessable verification link is an account takeover, resolve the IP through the trusted-proxy list because the raw header is forgeable, and mask the address in the response because the endpoint is unauthenticated.

##  Three mistakes that account for most bugs

Across all eleven modules, the same three misunderstandings cause most of the incidents.

**Confusing "encoded" with "encrypted".** Base64 is not encryption. A JWT payload, a `sign_value` token, and a `mask_string` output are all readable by whoever holds them. Signing proves nobody *changed* a value; it does nothing to stop them *reading* it. If the holder must not know the contents, encrypt.

**Trusting something the client sent.** An `X-Forwarded-For` header, a `Content-Length`, a filename, a file extension, and a JWT's unverified claims are all attacker-controlled. Each has a helper here that handles it safely, and each has a naive path that does not. The safe path always involves either a signature you verify or a list you control.

**Using a fast function where a slow one is required.** `sha256` for password storage and `==` for secret comparison are the two classic cases. Both are fast, both are wrong, and both fail silently: your tests pass, your logins work, and the weakness only surfaces when someone attacks it. Use `hash_password` and `constant_time_compare`.

If you internalize only those three, most of the warnings on the individual pages follow from them.

##  What is deliberately not here

Knowing what a utility package does *not* cover saves you looking for it.

**Input validation.** Nothing here validates a request body, coerces a query parameter, or produces a 422. That is [Validation](/guides/validation/), which is Pydantic-backed and integrated with routing and OpenAPI. `extract_emails` finding something that looks like an address is not validation, and `is_valid_ip` is a format check rather than a policy decision.

**Date and time handling.** No parsing, formatting, or timezone conversion. Python's `datetime` plus `zoneinfo` covers it, and for anything harder the ecosystem already has better answers than a framework should ship.

**Serialization.** Converting models to JSON is [Serialization](/guides/serialization/), which handles dataclasses, Pydantic models, `Decimal`, `datetime`, and UUIDs. Do not hand-roll it with the string helpers.

**HTTP requests.** Making outbound calls is the [HTTP Client](/guides/http/client/), which has its own retry, timeout, and connection-pooling configuration. The [Retry](/guides/helpers/retry/) helpers are for arbitrary callables, not specifically for HTTP.

**Caching.** [Cache](/guides/cache/) has backends, TTLs, and tag invalidation. `sha256` makes a good cache *key*, but the cache itself lives elsewhere.

**A real HTML sanitizer.** As noted above, `sanitize_html` is not one. This is a deliberate gap rather than an oversight: correct sanitization requires a full HTML parser, and that belongs in a dedicated, widely audited library rather than a framework's utility module.

##  Testing code that uses these

Two patterns come up constantly.

**Freeze the randomness.** Functions built on `secrets` return something different every call, which makes assertions awkward. Assert on shape rather than value, or patch the generator:

```python
def test_reset_token_is_long_enough():
    token = random_token(32)
    assert len(token) >= 40          # shape, not value

def test_reset_link(monkeypatch):
    monkeypatch.setattr("myapp.auth.random_token", lambda n=64: "fixed-token")
    assert build_reset_link(user) == "https://example.com/reset?t=fixed-token"
```

**Do not hash passwords in tests you run thousands of times.** `hash_password` costs 250 ms. A fixture that creates fifty users spends over ten seconds inside bcrypt. Hash once at module scope and reuse the string:

```python
import pytest
from sillo.helpers.hashing import hash_password

KNOWN_HASH = hash_password("test-password")   # computed once per session

@pytest.fixture
def user():
    return User(email="a@example.com", password=KNOWN_HASH)
```

Never lower the bcrypt cost factor to speed up tests by changing production configuration — you will eventually ship the reduced value.

**Pin the clock, not the helper, for time-dependent behaviour.** `file_age` and the JWT expiry checks read the current time. Rather than patching them, use a library like `freezegun` or inject the timestamp, so you are testing your logic rather than your mocking.

##  Performance in one paragraph

Almost everything here is a pure in-memory string operation costing microseconds, and you can ignore the cost. Three exceptions matter. `hash_password` and `verify_password` take roughly 250 ms each and occupy a full CPU core — that is deliberate, and it caps how many logins you serve per core. `derive_key` costs the same for the same reason. Anything that touches the disk (`hash_file`, `list_files`, `file_age`) is blocking I/O and stalls the entire event loop if called directly from an async handler; push it to a thread or a [background task](/guides/work/background/).

##  Common tasks, and where to look

A quick index by problem rather than by module, for when you know what you need and not what it is called.

| I need to... | Function | Page |
|---|---|---|
| Turn a title into a URL segment | `slugify` | [Strings](/guides/helpers/strings/) |
| Store a password | `hash_password` | [Hashing](/guides/helpers/hashing/) |
| Check a password at login | `verify_password` | [Hashing](/guides/helpers/hashing/) |
| Generate a session or reset token | `random_token` | [Strings](/guides/helpers/strings/) |
| Generate a six-digit OTP | `random_digits` | [Strings](/guides/helpers/strings/) |
| Show part of an API key in a UI | `mask_string` | [Strings](/guides/helpers/strings/) |
| Confirm an email without printing it | `mask_email` | [Strings](/guides/helpers/strings/) |
| Verify an inbound webhook signature | `hmac_digest` + `constant_time_compare` | [Hashing](/guides/helpers/hashing/) |
| Compare two secrets safely | `constant_time_compare` | [Hashing](/guides/helpers/hashing/) |
| Deduplicate uploaded files | `sha256` or `hash_file` | [Hashing](/guides/helpers/hashing/) |
| Store a third-party API key | `encrypt` / `decrypt` | [Crypto](/guides/helpers/crypto/) |
| Make a tamper-proof unsubscribe link | `sign_value` / `unsign_value` | [Crypto](/guides/helpers/crypto/) |
| Issue a stateless auth token | `create_access_token` | [JWT](/guides/helpers/jwt/) |
| Find the real client IP | `get_client_ip` | [Network](/guides/helpers/network/) |
| Block SSRF on a user-supplied URL | `is_public_ip` | [Network](/guides/helpers/network/) |
| Check an IP against an allowlist | `subnet_contains` | [Network](/guides/helpers/network/) |
| Make an upload filename safe to write | `safe_filename` | [Files](/guides/helpers/files/) |
| Read a size limit from config | `parse_size` | [Files](/guides/helpers/files/) |
| Show a file size to a user | `format_size_binary` | [Files](/guides/helpers/files/) |
| Escape user text for a page | `escape_html` | [HTML](/guides/helpers/html/) |
| Build a meta description from rich text | `strip_html` + `truncate` | [Text](/guides/helpers/text/) |
| Show search results with context | `excerpt` | [Text](/guides/helpers/text/) |
| Say "1 item" or "3 items" | `pluralize` | [Text](/guides/helpers/text/) |
| Estimate reading time | `word_count` | [Text](/guides/helpers/text/) |
| Survive a flaky upstream API | `@retry` | [Retry](/guides/helpers/retry/) |
| Accept a sync or async callback | `is_async_callable` | [Async](/guides/helpers/async/) |
| Remove a public function safely | `@deprecated` | [Deprecation](/guides/helpers/deprecation/) |

##  Related

- [Authentication](/guides/authentication/) — the full auth stack built on hashing and JWT
- [Rate Limiting](/guides/rate-limiting/) — the main consumer of `get_client_ip`
- [File Uploads](/guides/file-upload/) — where the file helpers get used
- [Validation](/guides/validation/) — input validation, which these helpers do not do
- [Security](/guides/security/) — headers and hardening beyond these utilities
