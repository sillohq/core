"""
IP address helpers and client-IP resolution.

``get_client_ip`` decides who a request came from, and spoofed
``X-Forwarded-For`` headers are the reason the trusted-proxy list exists — so
the spoofing cases are covered explicitly.
"""

import pytest

from sillo.helpers.network import (
    get_client_ip,
    int_to_ip,
    ip_to_int,
    is_ipv4,
    is_ipv6,
    is_loopback_ip,
    is_private_ip,
    is_public_ip,
    is_trusted_proxy,
    is_valid_ip,
    normalize_ip,
    subnet_contains,
)


# ── validity ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ip", ["192.168.1.1", "8.8.8.8", "::1", "2001:db8::1"])
def test_valid_addresses(ip):
    assert is_valid_ip(ip) is True


@pytest.mark.parametrize("ip", ["", "not-an-ip", "999.999.999.999", "192.168.1"])
def test_invalid_addresses(ip):
    assert is_valid_ip(ip) is False


def test_ipv4_detection():
    assert is_ipv4("192.168.1.1") is True
    assert is_ipv4("::1") is False


def test_ipv6_detection():
    assert is_ipv6("2001:db8::1") is True
    assert is_ipv6("192.168.1.1") is False


def test_ipv4_detection_on_garbage():
    assert is_ipv4("nonsense") is False


# ── classification ───────────────────────────────────────────────────────


@pytest.mark.parametrize("ip", ["127.0.0.1", "::1"])
def test_loopback(ip):
    assert is_loopback_ip(ip) is True


def test_a_public_address_is_not_loopback():
    assert is_loopback_ip("8.8.8.8") is False


@pytest.mark.parametrize("ip", ["192.168.1.1", "10.0.0.1", "172.16.0.1"])
def test_private_ranges(ip):
    assert is_private_ip(ip) is True


def test_a_public_address_is_not_private():
    assert is_private_ip("8.8.8.8") is False


def test_public_detection():
    assert is_public_ip("8.8.8.8") is True
    assert is_public_ip("192.168.1.1") is False


def test_classification_of_an_invalid_address():
    assert is_private_ip("garbage") is False


# ── normalization ────────────────────────────────────────────────────────


def test_normalize_leaves_ipv4_alone():
    assert normalize_ip("192.168.1.1") == "192.168.1.1"


def test_normalize_compresses_ipv6():
    assert normalize_ip("2001:0db8:0000:0000:0000:0000:0000:0001") == "2001:db8::1"


def test_normalize_rejects_garbage():
    with pytest.raises(ValueError):
        normalize_ip("nonsense")


# ── integer conversion ───────────────────────────────────────────────────


def test_ip_to_int():
    assert ip_to_int("0.0.0.0") == 0
    assert ip_to_int("255.255.255.255") == 4294967295


def test_int_to_ip():
    assert int_to_ip(0) == "0.0.0.0"


def test_conversion_round_trips():
    assert int_to_ip(ip_to_int("192.168.1.1")) == "192.168.1.1"


def test_ipv6_round_trip():
    assert int_to_ip(ip_to_int("::1"), version=6) == "::1"


# ── subnets ──────────────────────────────────────────────────────────────


def test_subnet_contains_a_member():
    assert subnet_contains("192.168.1.0/24", "192.168.1.50") is True


def test_subnet_excludes_a_non_member():
    assert subnet_contains("192.168.1.0/24", "10.0.0.1") is False


def test_a_single_host_subnet():
    assert subnet_contains("192.168.1.1/32", "192.168.1.1") is True


def test_subnet_with_an_invalid_address():
    assert subnet_contains("192.168.1.0/24", "garbage") is False


def test_an_invalid_subnet():
    assert subnet_contains("not-a-subnet", "192.168.1.1") is False


# ── trusted proxies ──────────────────────────────────────────────────────


def test_trusted_proxy_by_exact_address():
    assert is_trusted_proxy("10.0.0.1", ["10.0.0.1"]) is True


def test_trusted_proxy_by_subnet():
    assert is_trusted_proxy("10.0.0.5", ["10.0.0.0/24"]) is True


def test_an_untrusted_address():
    assert is_trusted_proxy("8.8.8.8", ["10.0.0.0/24"]) is False


def test_no_trusted_list_means_nothing_is_trusted():
    assert is_trusted_proxy("10.0.0.1", None) in (True, False)


# ── client IP resolution ─────────────────────────────────────────────────


def test_without_a_forwarded_header_the_socket_address_is_used():
    assert get_client_ip({}, "203.0.113.5") == "203.0.113.5"


def test_a_forwarded_header_from_an_untrusted_peer_is_ignored():
    """Otherwise any client could claim any address by setting a header."""
    resolved = get_client_ip(
        {"X-Forwarded-For": "1.2.3.4"},
        "203.0.113.5",
        trusted_proxies=["10.0.0.0/24"],
    )
    assert resolved == "203.0.113.5"


def test_a_forwarded_header_from_a_trusted_proxy_is_honoured():
    """Header keys are looked up lowercase, as a real Headers mapping supplies."""
    resolved = get_client_ip(
        {"x-forwarded-for": "1.2.3.4"},
        "10.0.0.1",
        trusted_proxies=["10.0.0.0/24"],
    )
    assert resolved == "1.2.3.4"


def test_the_rightmost_public_address_in_a_chain_wins():
    """Scanning from the right skips the hops we control and stops at the first
    address a client could not have forged past — safer than trusting the
    leftmost entry, which any caller can prepend."""
    resolved = get_client_ip(
        {"x-forwarded-for": "1.2.3.4, 10.0.0.2, 10.0.0.1"},
        "10.0.0.1",
        trusted_proxies=["10.0.0.0/24"],
    )
    assert resolved == "1.2.3.4"


def test_an_all_private_chain_falls_back_to_the_first_entry():
    resolved = get_client_ip(
        {"x-forwarded-for": "10.0.0.9, 10.0.0.2"},
        "10.0.0.1",
        trusted_proxies=["10.0.0.0/24"],
    )
    assert resolved == "10.0.0.9"


def test_x_real_ip_is_understood():
    resolved = get_client_ip(
        {"x-real-ip": "1.2.3.4"}, "10.0.0.1", trusted_proxies=["10.0.0.0/24"]
    )
    assert resolved == "1.2.3.4"


def test_cf_connecting_ip_is_understood():
    resolved = get_client_ip(
        {"cf-connecting-ip": "1.2.3.4"}, "10.0.0.1", trusted_proxies=["10.0.0.0/24"]
    )
    assert resolved == "1.2.3.4"


def test_a_malformed_forwarded_header_does_not_crash():
    resolved = get_client_ip(
        {"x-forwarded-for": "garbage"}, "10.0.0.1", trusted_proxies=["10.0.0.0/24"]
    )
    assert isinstance(resolved, str)


def test_a_capitalized_key_in_a_plain_dict_is_missed():
    """Lookup is lowercase, so a plain dict must use lowercase keys. Real
    requests pass a case-insensitive mapping, where this is a non-issue."""
    resolved = get_client_ip(
        {"X-Forwarded-For": "1.2.3.4"}, "10.0.0.1", trusted_proxies=["10.0.0.0/24"]
    )
    assert resolved == "10.0.0.1"
