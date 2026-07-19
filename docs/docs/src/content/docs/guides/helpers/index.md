---
title: Helpers
description: Utility modules for common backend tasks.
---

# Helpers

sillo ships with a collection of helper modules. Import from `sillo.helpers.*`.

| Module | Description | Dependencies |
|---|---|---|
| [JWT](/guides/helpers/jwt) | Encode, decode, sign, verify JWTs | `pyjwt` |
| [Network](/guides/helpers/network) | IP normalization, private detection, trusted proxies | stdlib |
| [Text](/guides/helpers/text) | Truncate, excerpt, strip HTML, pluralize | stdlib |
| [Retry](/guides/helpers/retry) | Decorator and functions with exponential backoff | stdlib |
| [Strings](/guides/helpers/strings) | Slugify, camel/snake, masking, random generation | stdlib |
| [HTML](/guides/helpers/html) | Escape, sanitize, safe attributes, linkify | stdlib |
| [Files](/guides/helpers/files) | Size formatting, extension detection, safe filenames | stdlib |
| [Hashing](/guides/helpers/hashing) | Password hashing (bcrypt), digests, HMAC | `bcrypt` |
| [Crypto](/guides/helpers/crypto) | Encrypt/decrypt, key derivation, signed values | `cryptography` |
| [Deprecation](/guides/helpers/deprecation) | Framework deprecation warnings and decorators | stdlib |
| [Async](/guides/helpers/async) | Detect async callables, wrap coroutines as async context managers | stdlib |

## Quick Import

```python
from sillo.helpers import jwt, network, text, strings
from sillo.helpers import html, files, hashing, crypto, deprecation
```
