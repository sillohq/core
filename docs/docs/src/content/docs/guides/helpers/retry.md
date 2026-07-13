---
title: Retry Helpers
description: Retry with exponential backoff — decorator, async, and sync functions.
---

# Retry (`sillo.helpers.retry`)

```python
from sillo.helpers import retry

# Decorator
@retry.retry(max_attempts=5, base_delay=1.0, backoff_factor=2.0, jitter=True)
async def call_external_api():
    return await http_client.get("https://api.example.com")

# Async one-shot
result = await retry.async_retry(
    call_external_api,
    max_attempts=3,
    base_delay=0.5,
    retryable_exceptions=(ConnectionError, TimeoutError),
)

# Sync one-shot
result = retry.sync_retry(
    lambda: requests.get("https://api.example.com"),
    max_attempts=3,
)
```

| Parameter | Default | Description |
|---|---|---|
| `max_attempts` | 3 | Total attempts before giving up |
| `base_delay` | 1.0 | Initial delay in seconds |
| `max_delay` | 60.0 | Cap on delay |
| `backoff_factor` | 2.0 | Multiplier per attempt |
| `jitter` | True | Randomize delay to avoid thundering herd |
| `retryable_exceptions` | `Exception` | Tuple of exception types to retry on |

Delay progression with defaults (jitter off): `0s → 2s → 4s → 8s → 16s → 32s → 60s (capped)`
