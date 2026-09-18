"""Tests for RateLimitConfig validation and defaults."""

from __future__ import annotations

import pytest

from sillo.core.http import HttpContext
from sillo.security.ratelimit.config import RateLimitConfig


class TestRateLimitConfigDefaults:
    def test_default_values(self):
        config = RateLimitConfig()
        assert config.limit == 60
        assert config.window == 60
        assert config.strategy == "token"
        assert config.backend == "memory"
        assert config.namespace == "sillo_rl"
        assert config.cost == 1
        assert config.include_headers is True
        assert config.fail_open is True
        assert config.on_exceed == "deny"

    def test_custom_values(self):
        config = RateLimitConfig(
            limit=100,
            window=30,
            strategy="fixed",
            backend="redis",
            namespace="my_ns",
            cost=2,
            include_headers=False,
            fail_open=False,
            on_exceed="custom",
        )
        assert config.limit == 100
        assert config.window == 30
        assert config.strategy == "fixed"
        assert config.backend == "redis"
        assert config.namespace == "my_ns"
        assert config.cost == 2
        assert config.include_headers is False
        assert config.fail_open is False
        assert config.on_exceed == "custom"


class TestRateLimitConfigValidation:
    def test_zero_limit_rejected(self):
        with pytest.raises(ValueError, match="limit"):
            RateLimitConfig(limit=0)

    def test_negative_limit_rejected(self):
        with pytest.raises(ValueError, match="limit"):
            RateLimitConfig(limit=-1)

    def test_zero_window_rejected(self):
        with pytest.raises(ValueError, match="window"):
            RateLimitConfig(window=0)

    def test_negative_window_rejected(self):
        with pytest.raises(ValueError, match="window"):
            RateLimitConfig(window=-1)

    def test_zero_cost_rejected(self):
        with pytest.raises(ValueError, match="cost"):
            RateLimitConfig(cost=0)

    def test_negative_cost_rejected(self):
        with pytest.raises(ValueError, match="cost"):
            RateLimitConfig(cost=-1)


class TestRateLimitConfigDefaultKey:
    def test_key_from_client(self):
        ctx = HttpContext(
            scope={
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [],
                "client": ("1.2.3.4", 1234),
            },
            receive=None,
        )
        config = RateLimitConfig()
        assert config._default_key(ctx) == "1.2.3.4"

    def test_key_from_x_forwarded_for(self):
        ctx = HttpContext(
            scope={
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [(b"x-forwarded-for", b"5.6.7.8")],
                "client": None,
            },
            receive=None,
        )
        config = RateLimitConfig()
        assert config._default_key(ctx) == "5.6.7.8"

    def test_key_returns_none_without_client_or_header(self):
        ctx = HttpContext(
            scope={
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [],
                "client": None,
            },
            receive=None,
        )
        config = RateLimitConfig()
        assert config._default_key(ctx) is None
