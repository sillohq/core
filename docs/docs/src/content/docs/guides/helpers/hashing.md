---
title: Hashing Helpers
description: Hashing utilities — password hashing (bcrypt), digests, HMAC, constant-time comparison, file hashing.
---

# Hashing (`sillo.helpers.hashing`)

Password hashing requires `bcrypt` (`pip install bcrypt`). Digest functions use stdlib only.

```python
from sillo.helpers import hashing

hashed = hashing.hash_password("my-password")
ok = hashing.verify_password("my-password", hashed)
needs_upgrade = hashing.needs_rehash(hashed, rounds=14)

hashing.md5("hello")
hashing.sha1("hello")
hashing.sha256("hello")
hashing.sha512("hello")
hashing.digest("hello", algorithm="sha256")

hashing.hmac_digest("secret-key", "data", algorithm="sha256")
hashing.constant_time_compare(token_a, token_b)

hashing.hash_file("large-file.bin", algorithm="sha256")
hashing.random_salt()
```
