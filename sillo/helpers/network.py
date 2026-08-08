from __future__ import annotations

import ipaddress
import typing

_LOOPBACK_V4 = ipaddress.ip_network("127.0.0.0/8")
_LOOPBACK_V6 = ipaddress.ip_network("::1/128")
_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fd00::/8"),
]


def normalize_ip(ip: str) -> str:
    """Normalize an IP address string to its canonical textual representation.

    Strips leading and trailing whitespace from the input and converts it
    to a standardized IP address format using Python's ``ipaddress`` module.
    Both IPv4 and IPv6 addresses are supported, with IPv6 addresses being
    compressed to their short form.

    Args:
        ip: A string containing an IP address, possibly with surrounding
            whitespace or in a non-canonical format.

    Returns:
        The canonical string representation of the IP address.

    Raises:
        ValueError: If the input string is not a valid IP address.
    """
    return str(ipaddress.ip_address(ip.strip()))


def is_valid_ip(ip: str) -> bool:
    """Check whether a string represents a valid IPv4 or IPv6 address.

    Attempts to parse the input as an IP address using Python's
    ``ipaddress`` module. Returns ``True`` if parsing succeeds and
    ``False`` if the string is not a valid address of either version.
    Leading and trailing whitespace is stripped before validation.

    Args:
        ip: A string to test for validity as an IPv4 or IPv6 address.

    Returns:
        ``True`` if the string is a valid IP address, ``False`` otherwise.
    """
    try:
        ipaddress.ip_address(ip.strip())
        return True
    except ValueError:
        return False


def is_ipv4(ip: str) -> bool:
    """Check whether a string represents a valid IPv4 address.

    Attempts to parse the input specifically as an IPv4 address. Returns
    ``True`` only if the string is a valid IPv4 address and ``False`` for
    IPv6 addresses or invalid strings. Leading and trailing whitespace is
    stripped before validation.

    Args:
        ip: A string to test for validity as an IPv4 address.

    Returns:
        ``True`` if the string is a valid IPv4 address, ``False`` otherwise.
    """
    try:
        return ipaddress.IPv4Address(ip.strip()) is not None
    except ValueError:
        return False


def is_ipv6(ip: str) -> bool:
    """Check whether a string represents a valid IPv6 address.

    Attempts to parse the input specifically as an IPv6 address. Returns
    ``True`` only if the string is a valid IPv6 address and ``False`` for
    IPv4 addresses or invalid strings. Leading and trailing whitespace is
    stripped before validation.

    Args:
        ip: A string to test for validity as an IPv6 address.

    Returns:
        ``True`` if the string is a valid IPv6 address, ``False`` otherwise.
    """
    try:
        return ipaddress.IPv6Address(ip.strip()) is not None
    except ValueError:
        return False


def is_loopback_ip(ip: str) -> bool:
    """Check whether an IP address is a loopback address.

    Determines if the given IP address refers to the local machine, such as
    ``127.0.0.1`` for IPv4 or ``::1`` for IPv6. Leading and trailing
    whitespace is stripped before validation. Returns ``False`` for
    invalid address strings.

    Args:
        ip: A string containing an IP address to test for loopback status.

    Returns:
        ``True`` if the address is a loopback address, ``False`` otherwise
        or if the string is not a valid IP address.
    """
    try:
        addr = ipaddress.ip_address(ip.strip())
        return addr.is_loopback
    except ValueError:
        return False


def is_private_ip(ip: str) -> bool:
    """Check whether an IP address belongs to a private network range.

    Determines if the given IP address falls within RFC 1918 private ranges
    for IPv4 (``10.0.0.0/8``, ``172.16.0.0/12``, ``192.168.0.0/16``) or
    unique local address ranges for IPv6 (``fc00::/7``). Leading and
    trailing whitespace is stripped before validation.

    Args:
        ip: A string containing an IP address to test for private status.

    Returns:
        ``True`` if the address is in a private range, ``False`` otherwise
        or if the string is not a valid IP address.
    """
    try:
        addr = ipaddress.ip_address(ip.strip())
        return addr.is_private
    except ValueError:
        return False


def is_trusted_proxy(ip: str, trusted_proxies: list[str] | None = None) -> bool:
    """Check whether an IP address belongs to a trusted proxy.

    If no explicit trusted proxy list is provided, the address is considered
    trusted when it is a loopback or private network address. When a custom
    list is provided, each entry is treated as a CIDR network and the address
    is checked for membership in any of those networks.

    Args:
        ip: A string containing the IP address to check.
        trusted_proxies: An optional list of CIDR network strings defining
            trusted proxy ranges. Defaults to ``None``, which falls back
            to loopback and private address checks.

    Returns:
        ``True`` if the address is within a trusted proxy range,
        ``False`` otherwise.
    """
    if trusted_proxies is None:
        return is_loopback_ip(ip) or is_private_ip(ip)
    try:
        addr = ipaddress.ip_address(ip.strip())
        for proxy in trusted_proxies:
            net = ipaddress.ip_network(proxy.strip())
            if addr in net:
                return True
    except ValueError:
        pass
    return False


def get_client_ip(
    request_headers: typing.Mapping[str, str],
    remote_addr: str,
    trusted_proxies: list[str] | None = None,
    proxy_headers: list[str] | None = None,
) -> str:
    """Extract the real client IP address from request headers or remote address.

    When the immediate connection comes from a trusted proxy, this function
    inspects standard forwarding headers such as ``X-Forwarded-For``,
    ``X-Real-IP``, and ``CF-Connecting-IP`` to determine the original client
    address. It walks the header chain in reverse and returns the first
    non-private IP found. If the proxy is not trusted, the ``remote_addr``
    is returned directly to prevent header spoofing.

    Args:
        request_headers: A mapping of HTTP request header names to values.
        remote_addr: The direct connection IP address of the client or proxy.
        trusted_proxies: An optional list of CIDR network strings defining
            which proxy addresses are trusted to forward headers.
        proxy_headers: An optional list of header names to inspect for the
            real client IP. Defaults to common forwarding headers.

    Returns:
        The best-guess real client IP address as a string.
    """
    if proxy_headers is None:
        proxy_headers = ["x-forwarded-for", "x-real-ip", "cf-connecting-ip"]

    if is_trusted_proxy(remote_addr, trusted_proxies):
        for header in proxy_headers:
            value = request_headers.get(header)
            if value:
                ips = [ip.strip() for ip in value.split(",")]
                for ip in reversed(ips):
                    if ip and not is_private_ip(ip):
                        return ip
                return ips[0] if ips else remote_addr

    return remote_addr


def is_public_ip(ip: str) -> bool:
    """Check whether an IP address is a publicly routable internet address.

    Returns ``True`` only if the address is not private, loopback, link-local,
    reserved, or unspecified. This is useful for determining whether an IP
    can be reached from the public internet or is only accessible within a
    local network. Leading and trailing whitespace is stripped before validation.

    Args:
        ip: A string containing an IP address to test for public status.

    Returns:
        ``True`` if the address is publicly routable, ``False`` otherwise
        or if the string is not a valid IP address.
    """
    try:
        addr = ipaddress.ip_address(ip.strip())
        return not (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_unspecified
        )
    except ValueError:
        return False


def ip_to_int(ip: str) -> int:
    """Convert an IP address string to its integer representation.

    Translates an IPv4 or IPv6 address into its equivalent unsigned integer
    value. This is useful for efficient IP range comparisons, database storage,
    or mathematical operations on addresses. Leading and trailing whitespace
    is stripped before conversion.

    Args:
        ip: A string containing a valid IPv4 or IPv6 address.

    Returns:
        The integer representation of the IP address.

    Raises:
        ValueError: If the input string is not a valid IP address.
    """
    return int(ipaddress.ip_address(ip.strip()))


def int_to_ip(value: int, version: int = 4) -> str:
    """Convert an integer back to its IP address string representation.

    Reverses the ``ip_to_int`` operation by converting an unsigned integer
    into the corresponding IPv4 or IPv6 address string. The IP version must
    be specified to determine the correct address format.

    Args:
        value: The integer value to convert to an IP address.
        version: The IP version to use. ``4`` for IPv4, ``6`` for IPv6.
            Defaults to ``4``.

    Returns:
        The canonical string representation of the IP address.

    Raises:
        ValueError: If the integer is out of range for the specified version.
    """
    if version == 4:
        return str(ipaddress.IPv4Address(value))
    return str(ipaddress.IPv6Address(value))


def subnet_contains(subnet: str, ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip.strip()) in ipaddress.ip_network(subnet.strip())
    except ValueError:
        return False
