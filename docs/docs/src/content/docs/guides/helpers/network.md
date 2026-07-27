---
title: Network Helpers
description: Resolving the real client IP behind proxies and load balancers, classifying addresses, and subnet matching — including the spoofable default you must not ship with.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Network Helpers
  - tag: meta
    attrs:
      property: og:description
      content: Resolving the real client IP behind proxies and load balancers, classifying addresses, and subnet matching — including the spoofable default you must not ship with.
---

#  Network (`sillo.helpers.network`)

"What is this request's IP address?" sounds like it should have a one-line answer. In production it does not, because your application almost never talks to the client directly. A load balancer, a CDN, a reverse proxy, or all three sit in between, and the TCP connection your server sees comes from the last hop, not from the user.

The real address is carried in a header. Headers are supplied by whoever sent the request. That is the whole problem this module exists to solve, and getting it wrong means one of two failures: every user appears to share one IP (so per-IP rate limiting bans everybody at once), or any user can claim any IP (so rate limiting, geoblocking, and audit logs are all bypassable).

```python
from sillo.helpers import network
```

Stdlib-only, built on `ipaddress`. No installation step.

##  Getting the client IP

###  `get_client_ip(request_headers, remote_addr, trusted_proxies=None, proxy_headers=None) -> str`

Resolves the originating client address from proxy headers, but only when the immediate peer is one you trust.

```python
network.get_client_ip(
    request_headers={"x-forwarded-for": "203.0.113.1, 10.0.0.2"},
    remote_addr="10.0.0.1",
    trusted_proxies=["10.0.0.0/8"],
)
# '203.0.113.1'
```

The logic in order: if `remote_addr` is not in `trusted_proxies`, ignore the headers entirely and return `remote_addr`. If it is trusted, read the proxy headers and pick the client address out of the chain.

```python
# The peer is not a trusted proxy, so the header is ignored.
network.get_client_ip({"x-forwarded-for": "1.2.3.4"}, "203.0.113.5",
                      trusted_proxies=["10.0.0.0/24"])
# '203.0.113.5'  — the header claimed 1.2.3.4 and was disbelieved

# The peer is a trusted proxy, so the header is honoured.
network.get_client_ip({"x-forwarded-for": "1.2.3.4"}, "10.0.0.1",
                      trusted_proxies=["10.0.0.0/24"])
# '1.2.3.4'
```

:::danger[The default trusts every header from every peer]
`trusted_proxies` defaults to `None`, and `None` means "trust anyone":

```python
network.get_client_ip({"x-forwarded-for": "1.2.3.4"}, "10.0.0.1")
# '1.2.3.4'   — no trusted list, header believed anyway

network.is_trusted_proxy("10.0.0.1", None)
# True
```

Any client can send `X-Forwarded-For: 8.8.8.8` and your application will report `8.8.8.8`. That defeats per-IP rate limiting (a new IP every request), IP allowlists, geoblocking, fraud scoring, and any audit log that records an address.

**Always pass `trusted_proxies` in production.** The value is the address of *your own* infrastructure — the load balancer or proxy that sits directly in front of the app:

```python
TRUSTED_PROXIES = [
    "10.0.0.0/8",        # internal VPC
    "172.16.0.0/12",     # container network
]
```

If nothing sits in front of your app, pass an empty list. That makes `remote_addr` authoritative and ignores headers entirely, which is correct for a directly exposed server.
:::

By default it reads three headers, in order: `x-forwarded-for`, `x-real-ip`, `cf-connecting-ip`. Override with `proxy_headers` when your infrastructure uses something else:

```python
network.get_client_ip(headers, remote_addr,
                      trusted_proxies=["10.0.0.0/8"],
                      proxy_headers=["true-client-ip"])
```

###  How the chain is read

`X-Forwarded-For` accumulates as a request passes through proxies. Each hop appends the address it received from:

```
X-Forwarded-For: 203.0.113.1, 10.0.0.2, 10.0.0.1
                 ^client      ^proxy1    ^proxy2
```

The leftmost entry is the one the client claims, and a client can prepend anything before their request ever reaches you. This implementation scans **from the right** and returns the first address that is not private:

```python
network.get_client_ip({"x-forwarded-for": "1.2.3.4, 10.0.0.2, 10.0.0.1"},
                      "10.0.0.1", trusted_proxies=["10.0.0.0/24"])
# '1.2.3.4'
```

Scanning right-to-left skips the hops you control and stops at the first address that could not have been forged past them. Taking the leftmost value instead — which many hand-rolled implementations do — means trusting whatever the client typed.

When every entry is private, the first is returned as a fallback:

```python
network.get_client_ip({"x-forwarded-for": "10.0.0.9, 10.0.0.2"},
                      "10.0.0.1", trusted_proxies=["10.0.0.0/24"])
# '10.0.0.9'
```

That is the normal shape for internal service-to-service traffic.

:::caution[Header lookup is lowercase]
Headers are looked up in lowercase. A real `Headers` mapping from a sillo request is case-insensitive, so this never comes up in a handler. A plain `dict` in a test or a script does not:

```python
network.get_client_ip({"X-Forwarded-For": "1.2.3.4"}, "10.0.0.1",
                      trusted_proxies=["10.0.0.0/24"])
# '10.0.0.1'   — the header was not found
```

Use lowercase keys when constructing headers by hand.
:::

:::caution[The result is not validated]
A malformed header value is returned as-is rather than rejected:

```python
network.get_client_ip({"x-forwarded-for": "garbage"}, "10.0.0.1",
                      trusted_proxies=["10.0.0.0/24"])
# 'garbage'
```

If you store the result in an `INET` column or feed it to something that parses addresses, check it with `is_valid_ip` first.
:::

```python title="Rate limiting by real client IP"
from sillo.helpers.network import get_client_ip, is_valid_ip

TRUSTED_PROXIES = ["10.0.0.0/8"]

async def rate_limit(request, response, call_next):
    client = get_client_ip(
        request.headers,
        request.client.host,
        trusted_proxies=TRUSTED_PROXIES,
    )
    if not is_valid_ip(client):
        return response.json({"error": "Bad request"}, status_code=400)

    if await too_many_requests(client):
        return response.json({"error": "Rate limited"}, status_code=429)
    return await call_next()
```

For production rate limiting use the built-in middleware in [Rate Limiting](/guides/rate-limiting/) rather than writing your own; the example above is to show where the IP comes from.

##  Classifying addresses

Seven predicates, all returning `bool` and none raising on bad input.

```python
network.is_valid_ip("192.168.1.1")   # True
network.is_valid_ip("999.999.999.999")  # False
network.is_valid_ip("")              # False

network.is_ipv4("192.168.1.1")       # True
network.is_ipv6("2001:db8::1")       # True
network.is_ipv4("nonsense")          # False

network.is_loopback_ip("127.0.0.1")  # True
network.is_loopback_ip("::1")        # True

network.is_private_ip("10.0.0.1")    # True
network.is_private_ip("192.168.1.1") # True
network.is_private_ip("172.16.0.1")  # True
network.is_private_ip("8.8.8.8")     # False
network.is_private_ip("garbage")     # False

network.is_public_ip("8.8.8.8")      # True
network.is_public_ip("192.168.1.1")  # False
```

Invalid input returns `False` rather than raising, which means `is_private_ip("garbage")` and `is_public_ip("garbage")` are both `False`. They are not each other's complement. Validate first if the distinction matters.

The private ranges are RFC 1918 for IPv4 (`10/8`, `172.16/12`, `192.168/16`) and the equivalents for IPv6.

The highest-value use of `is_public_ip` is blocking server-side request forgery. When your application fetches a URL a user supplied, an attacker points it at your own internal network:

```python title="Blocking SSRF on a user-supplied URL"
import socket
from urllib.parse import urlparse
from sillo.helpers.network import is_public_ip

async def fetch_user_url(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https are allowed")

    # Resolve first: the hostname may point anywhere.
    resolved = socket.gethostbyname(parsed.hostname)
    if not is_public_ip(resolved):
        raise ValueError("Refusing to fetch a non-public address")

    return await http_client.get(url)
```

Without that check, `http://169.254.169.254/latest/meta-data/` reads your cloud instance's credentials, and `http://localhost:6379` talks to your Redis.

:::caution[Resolve-then-fetch is still racy]
The example above resolves the hostname, checks the address, then fetches by URL — and the fetch resolves again. An attacker controlling the DNS record can return a public address for the first lookup and an internal one for the second. This is DNS rebinding.

Closing it properly means resolving once and connecting to the resolved address directly with the `Host` header set by hand, or using an HTTP client that supports pinning the resolved address. If you accept URLs from strangers, do it properly or route the fetch through an egress proxy that enforces the policy.
:::

##  Subnets and trusted proxies

###  `subnet_contains(subnet, ip) -> bool`

CIDR membership:

```python
network.subnet_contains("192.168.1.0/24", "192.168.1.50")   # True
network.subnet_contains("192.168.1.0/24", "10.0.0.1")       # False
network.subnet_contains("192.168.1.1/32", "192.168.1.1")    # True
network.subnet_contains("not-a-subnet", "192.168.1.1")      # False
network.subnet_contains("192.168.1.0/24", "garbage")        # False
```

Malformed input on either side returns `False` rather than raising, so a typo in a config file silently fails closed. That is the safer direction, but it also means a broken allowlist entry never announces itself. Validate your CIDR strings at startup.

###  `is_trusted_proxy(ip, trusted_proxies=None) -> bool`

Checks an address against a list of exact addresses and CIDR ranges:

```python
network.is_trusted_proxy("10.0.0.1", ["10.0.0.1"])       # exact match
network.is_trusted_proxy("10.0.0.5", ["10.0.0.0/24"])    # CIDR match
network.is_trusted_proxy("8.8.8.8", ["10.0.0.0/24"])     # False
network.is_trusted_proxy("10.0.0.1", None)               # True — see the warning above
```

##  Configuring for real infrastructure

What belongs in `trusted_proxies` depends entirely on what sits in front of your application. Getting this list wrong in either direction is a bug: too narrow and every user shares the proxy's address, too wide and headers become forgeable.

**Directly exposed server, no proxy.** Pass an empty list. `remote_addr` is the truth and no header should ever override it.

```python
TRUSTED_PROXIES: list[str] = []
```

**nginx or Caddy on the same host.** The proxy connects over loopback, so that is the only address to trust. Make sure the proxy actually sets the header:

```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Real-IP $remote_addr;
```

```python
TRUSTED_PROXIES = ["127.0.0.1", "::1"]
```

`$proxy_add_x_forwarded_for` appends to any existing header rather than replacing it, which preserves the chain through multiple hops. Using `$remote_addr` alone would discard everything upstream of nginx.

**A load balancer inside a private network.** Trust the subnet the balancer lives in, not the whole VPC:

```python
TRUSTED_PROXIES = ["10.0.1.0/24"]   # the load balancer subnet only
```

Trusting the entire VPC means any compromised container in your account can forge client addresses.

**A CDN such as Cloudflare or Fastly.** These publish their egress ranges, and `cf-connecting-ip` is set by Cloudflare on every request. The ranges change, so fetch them at deploy time rather than pasting a snapshot that silently rots.

```python
TRUSTED_PROXIES = load_cdn_ranges()   # refreshed on deploy
```

:::danger[A CDN in `trusted_proxies` is only safe if the origin is locked down]
Once you trust your CDN's ranges, anyone who can reach your origin server directly and spoof a source address inside those ranges can forge any client IP. More practically: an attacker who finds your origin's real address bypasses the CDN entirely, and whether their forged headers are believed now depends on your firewall, not your code.

Restrict the origin at the network layer so only the CDN can reach it — a security group, a firewall rule, or an authenticated origin pull. The header trust is only as strong as that restriction.
:::

**Multiple layers.** With a CDN in front of a load balancer in front of your app, the peer your application sees is the load balancer, so that is what needs to be in the list. The CDN's address appears inside the header chain and is handled by the right-to-left scan.

Verify your configuration rather than assuming it. Log the resolved address alongside `remote_addr` for a day and confirm they differ in the way you expect:

```python
client = get_client_ip(request.headers, request.client.host, trusted_proxies=TRUSTED_PROXIES)
logger.info("peer=%s resolved=%s xff=%s",
            request.client.host, client, request.headers.get("x-forwarded-for"))
```

If `resolved` always equals `peer`, your proxy is not setting the header or its address is missing from the list. If `resolved` varies wildly for a single known user, you are trusting a header you should not.

##  Integer conversion

```python
network.ip_to_int("192.168.1.1")        # 3232235777
network.int_to_ip(3232235777)           # '192.168.1.1'
network.int_to_ip(0)                    # '0.0.0.0'
network.ip_to_int("255.255.255.255")    # 4294967295

# IPv6 needs the version argument on the way back
network.int_to_ip(network.ip_to_int("::1"), version=6)   # '::1'
```

Integer form is useful for storing addresses in a plain integer column and for range queries — `WHERE ip_int BETWEEN ? AND ?` uses an index, whereas string comparison on dotted quads does not sort correctly (`"9.0.0.0"` sorts after `"10.0.0.0"`).

`int_to_ip` defaults to `version=4`. An IPv6 address converted to an integer and back without `version=6` produces a wrong IPv4 address or raises, depending on the magnitude. Store the version alongside the integer if you handle both families.

##  Normalization

###  `normalize_ip(ip) -> str`

Returns the canonical form:

```python
network.normalize_ip("  127.0.0.1  ")                            # '127.0.0.1'
network.normalize_ip("2001:0db8:0000:0000:0000:0000:0000:0001")  # '2001:db8::1'
```

Unlike the predicates, this **raises `ValueError`** on invalid input:

```python
network.normalize_ip("nonsense")   # ValueError
```

IPv6 has many textual spellings of the same address. Comparing them as strings gives wrong answers, so normalize before storing or comparing:

```python
# These are the same address and compare unequal as strings.
a = "2001:0db8:0000:0000:0000:0000:0000:0001"
b = "2001:db8::1"
a == b                                              # False
network.normalize_ip(a) == network.normalize_ip(b)  # True
```

Normalize on write. An allowlist storing one spelling will not match a request carrying another.

##  What not to do

**Do not call `get_client_ip` without `trusted_proxies` in production.** The default believes any header from any peer.

**Do not put your CDN's egress ranges in `trusted_proxies` unless traffic cannot reach you any other way.** If an attacker can hit your origin directly, they can forge headers that your origin now trusts.

**Do not take the leftmost `X-Forwarded-For` entry.** That is the client-supplied value.

**Do not use uppercase header keys with a plain dict.** Lookup is lowercase.

**Do not store the result without validating it.** Malformed values pass through unchanged.

**Do not compare IPv6 addresses as strings.** Normalize first.

**Do not treat `is_private_ip` and `is_public_ip` as complements.** Invalid input is `False` for both.

**Do not rely on a single `is_public_ip` check to stop SSRF.** DNS rebinding defeats resolve-then-fetch.

**Do not treat an IP as identity.** Users share addresses behind carrier-grade NAT and change them on every mobile handover. IP is a signal, not a login.

##  Performance

Every function parses its input with the stdlib `ipaddress` module, which allocates an object per call. That is microseconds — irrelevant once per request, noticeable in a loop over a million rows.

`subnet_contains` reparses the subnet on every call. Checking one address against fifty CIDRs reparses all fifty every time. If that runs per request, parse the networks once at startup:

```python
import ipaddress

TRUSTED = [ipaddress.ip_network(c) for c in TRUSTED_PROXY_CIDRS]   # once

def is_trusted(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return any(addr in net for net in TRUSTED)
```

##  Function reference

| Function | Signature | Returns |
|---|---|---|
| `get_client_ip` | `(request_headers, remote_addr, trusted_proxies=None, proxy_headers=None)` | Client address. **Pass `trusted_proxies`.** |
| `normalize_ip` | `(ip: str)` | Canonical form; **raises `ValueError`** |
| `is_valid_ip` | `(ip: str)` | `bool` |
| `is_ipv4` | `(ip: str)` | `bool` |
| `is_ipv6` | `(ip: str)` | `bool` |
| `is_loopback_ip` | `(ip: str)` | `bool` |
| `is_private_ip` | `(ip: str)` | `bool`, RFC 1918 and IPv6 equivalents |
| `is_public_ip` | `(ip: str)` | `bool` |
| `is_trusted_proxy` | `(ip: str, trusted_proxies=None)` | `bool`. `None` means trust everything. |
| `subnet_contains` | `(subnet: str, ip: str)` | `bool`, `False` on malformed input |
| `ip_to_int` | `(ip: str)` | `int` |
| `int_to_ip` | `(value: int, version: int = 4)` | Address string |

##  Related

- [Rate Limiting](/guides/rate-limiting/) — the main consumer of client IP
- [Request Information](/guides/request-info/) — reading headers and the peer address
- [Security](/guides/security/) — trusted hosts and the wider hardening story
- [Middleware](/guides/middleware/) — where IP resolution usually belongs
