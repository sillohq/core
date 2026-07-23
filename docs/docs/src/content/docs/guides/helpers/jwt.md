---
title: JWT Helpers
description: JWT utilities — encode, decode, sign, verify, and create access/refresh tokens.
---

# JWT (`sillo.helpers.jwt`)

Requires `pyjwt`: `uv add pyjwt`

```python
from sillo.helpers import jwt

token = jwt.encode({"sub": "user-1"}, secret="my-secret")
payload = jwt.decode(token, secret="my-secret")

access = jwt.create_access_token({"sub": "user-1"}, secret="my-secret")
refresh = jwt.create_refresh_token({"sub": "user-1"}, secret="my-secret")

is_valid = jwt.verify(token, secret="my-secret")
claims = jwt.get_unverified_claims(token)
header = jwt.get_unverified_header(token)
ok = jwt.validate_claims(payload, audience="my-api", issuer="my-issuer")
signature = jwt.sign({"data": "hello"}, secret="my-secret")
```

| Function | Description |
|---|---|
| `encode(payload, secret, algorithm)` | Encode a JWT |
| `decode(token, secret, algorithms, ...)` | Decode and verify a JWT |
| `sign(payload, secret, algorithm)` | Sign and return bytes |
| `verify(token, secret, algorithms)` | Return True if valid |
| `create_access_token(data, secret, expires_delta)` | Create with `exp` and `iat` claims |
| `create_refresh_token(data, secret, expires_delta)` | Same, defaults to 7-day expiry |
| `get_unverified_header(token)` | Get header without verifying |
| `get_unverified_claims(token)` | Get claims without verifying |
| `validate_claims(payload, audience, issuer)` | Validate exp, nbf, aud, iss |
| `decode_without_verification(token)` | Decode without signature check |
