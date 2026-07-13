from __future__ import annotations

import ipaddress
import typing
from typing import List, Optional


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
    return str(ipaddress.ip_address(ip.strip()))


def is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip.strip())
        return True
    except ValueError:
        return False


def is_ipv4(ip: str) -> bool:
    try:
        return ipaddress.IPv4Address(ip.strip()) is not None
    except ValueError:
        return False


def is_ipv6(ip: str) -> bool:
    try:
        return ipaddress.IPv6Address(ip.strip()) is not None
    except ValueError:
        return False


def is_loopback_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip.strip())
        return addr.is_loopback
    except ValueError:
        return False


def is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip.strip())
        return addr.is_private
    except ValueError:
        return False


def is_trusted_proxy(ip: str, trusted_proxies: Optional[List[str]] = None) -> bool:
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
    trusted_proxies: Optional[List[str]] = None,
    proxy_headers: Optional[List[str]] = None,
) -> str:
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
    try:
        addr = ipaddress.ip_address(ip.strip())
        return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_unspecified)
    except ValueError:
        return False


def ip_to_int(ip: str) -> int:
    return int(ipaddress.ip_address(ip.strip()))


def int_to_ip(value: int, version: int = 4) -> str:
    if version == 4:
        return str(ipaddress.IPv4Address(value))
    return str(ipaddress.IPv6Address(value))


def subnet_contains(subnet: str, ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip.strip()) in ipaddress.ip_network(subnet.strip())
    except ValueError:
        return False
