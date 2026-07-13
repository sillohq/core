---
title: Crypto Helpers
description: Cryptography utilities — encrypt/decrypt, key derivation, signed values.
---

# Crypto (`sillo.helpers.crypto`)

Requires `cryptography` (`pip install cryptography`).

```python
from sillo.helpers import crypto

key = crypto.generate_key()
ciphertext = crypto.encrypt("secret data", key)
plaintext = crypto.decrypt(ciphertext, key)

key, salt = crypto.derive_key("my-password")
key2, _ = crypto.derive_key("my-password", salt=salt)

signed = crypto.sign_value("important-data", secret="my-secret")
value = crypto.unsign_value(signed, secret="my-secret")

try:
    crypto.unsign_value(tampered, secret="my-secret")
except crypto.BadSignature:
    ...
```
