---
title: Network Helpers
description: Network utilities — IP normalization, private/detect, trusted proxies, client IP extraction.
---

# Network (`sillo.helpers.network`)

```python
from sillo.helpers import network

network.normalize_ip("  127.0.0.1  ")   # "127.0.0.1"
network.is_private_ip("10.0.0.1")       # True
network.is_loopback_ip("::1")            # True
network.is_trusted_proxy("10.0.0.1", ["10.0.0.0/8"])  # True
network.is_public_ip("8.8.8.8")         # True
network.is_valid_ip("192.168.1.1")      # True
network.is_ipv4("1.2.3.4")             # True
network.is_ipv6("::1")                 # True

ip = network.get_client_ip(
    request_headers={"x-forwarded-for": "203.0.113.1, 10.0.0.2"},
    remote_addr="10.0.0.1",
    trusted_proxies=["10.0.0.0/8"],
)  # "203.0.113.1"

network.ip_to_int("192.168.1.1")        # 3232235777
network.int_to_ip(3232235777)           # "192.168.1.1"
network.subnet_contains("10.0.0.0/8", "10.1.2.3")  # True
```
