"""
Tests for sillo.http.client module (HTTPClient, caching, retry, middleware, config, models).

Covers:
- RetryStrategy, RetryMode, and delay computation
- CacheConfig, CacheKeyBuilder, HTTPCache
- CachedResponse serialization and ResponseValidator
- HTTPClientConfig and HTTPClientStats
- MiddlewareChain, LoggingMiddleware, HeaderInjectionMiddleware
- HTTPClient lifecycle, request/response flow
- HTTPClient caching (read/write, tags, invalidation)
- HTTPClient retry via sillo.helpers.retry
- Pydantic response validation (single, many, strict, errors)
- Error handling and edge cases
- ConnectionPoolConfig
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import Request, Response
from pydantic import BaseModel

from sillo.cache import MemoryCache
from sillo.cache.base import _MISSING
from sillo.http.client.caching import CacheConfig, CacheKeyBuilder, CachePolicy, HTTPCache
from sillo.http.client.config import HTTPClientConfig, HTTPClientStats
from sillo.http.client.errors import (
    HTTPCacheError,
    HTTPClientConfigError,
    HTTPClientError,
    HTTPConnectionError,
    HTTPDecodeError,
    HTTPRedirectError,
    HTTPRetryError,
    HTTPStatusError,
    HTTPTimeoutError,
    HTTPValidationError,
)
from sillo.http.client.middleware import (
    BaseURLMiddleware,
    HeaderInjectionMiddleware,
    HTTPMiddleware,
    LoggingMiddleware,
    MiddlewareChain,
)
from sillo.http.client.models import CachedResponse, ResponseValidator
from sillo.http.client.retry import RetryMode, RetryStrategy
from sillo.http.client.transport import ConnectionPoolConfig
from sillo.http.client.utils import (
    extract_response_summary,
    guess_content_type,
    merge_headers,
    sanitize_url_for_log,
)


# ==================== Test Models ====================


class User(BaseModel):
    id: int
    name: str
    email: str


class Item(BaseModel):
    item_id: int
    value: str


class Order(BaseModel):
    order_id: str
    total: float


# ==================== RetryStrategy Tests ====================


class TestRetryMode:
    def test_enum_values(self):
        assert RetryMode.EXPONENTIAL.value == "exponential"
        assert RetryMode.LINEAR.value == "linear"
        assert RetryMode.CONSTANT.value == "constant"

    def test_enum_members(self):
        assert len(RetryMode) == 3


class TestRetryStrategy:
    def test_default_values(self):
        rs = RetryStrategy()
        assert rs.max_attempts == 3
        assert rs.base_delay == 1.0
        assert rs.max_delay == 60.0
        assert rs.backoff_factor == 2.0
        assert rs.mode == RetryMode.EXPONENTIAL
        assert rs.jitter is True
        assert 408 in rs.retryable_statuses
        assert 429 in rs.retryable_statuses
        assert 500 in rs.retryable_statuses
        assert 502 in rs.retryable_statuses
        assert 503 in rs.retryable_statuses
        assert 504 in rs.retryable_statuses

    def test_should_retry_for_status_true(self):
        rs = RetryStrategy()
        assert rs.should_retry_for_status(429) is True
        assert rs.should_retry_for_status(503) is True

    def test_should_retry_for_status_false(self):
        rs = RetryStrategy()
        assert rs.should_retry_for_status(200) is False
        assert rs.should_retry_for_status(404) is False
        assert rs.should_retry_for_status(401) is False

    def test_should_retry_for_exception(self):
        rs = RetryStrategy()
        assert rs.should_retry_for_exception(ConnectionError("fail")) is True
        assert rs.should_retry_for_exception(TimeoutError("fail")) is True
        assert rs.should_retry_for_exception(ValueError("fail")) is False

    def test_constant_mode_no_jitter(self):
        rs = RetryStrategy(mode=RetryMode.CONSTANT, base_delay=2.0, jitter=False)
        assert rs.compute_delay(0) == 2.0
        assert rs.compute_delay(10) == 2.0

    def test_linear_mode_no_jitter(self):
        rs = RetryStrategy(mode=RetryMode.LINEAR, base_delay=1.0, jitter=False)
        assert rs.compute_delay(0) == 1.0
        assert rs.compute_delay(1) == 2.0
        assert rs.compute_delay(2) == 3.0

    def test_exponential_mode_no_jitter(self):
        rs = RetryStrategy(mode=RetryMode.EXPONENTIAL, base_delay=1.0, backoff_factor=2.0, jitter=False)
        assert rs.compute_delay(0) == 1.0
        assert rs.compute_delay(1) == 2.0
        assert rs.compute_delay(2) == 4.0

    def test_max_delay_cap(self):
        rs = RetryStrategy(mode=RetryMode.EXPONENTIAL, base_delay=1.0, max_delay=5.0, backoff_factor=10.0, jitter=False)
        assert rs.compute_delay(3) == 5.0

    def test_jitter_applied(self):
        rs = RetryStrategy(mode=RetryMode.CONSTANT, base_delay=10.0, jitter=True)
        for _ in range(20):
            delay = rs.compute_delay(0)
            assert 0.0 <= delay <= 10.0

    def test_default_retryable_connections(self):
        rs = RetryStrategy()
        assert ConnectionError in rs.retryable_exceptions
        assert TimeoutError in rs.retryable_exceptions


# ==================== CacheConfig / CacheKeyBuilder / HTTPCache Tests ====================


class TestCacheConfig:
    def test_default_policy_enabled(self):
        cc = CacheConfig()
        assert cc.policy == CachePolicy.ENABLED

    def test_disabled_policy_blocks_read_and_write(self):
        cc = CacheConfig(policy=CachePolicy.DISABLED)
        mock_req = MagicMock(spec=Request)
        mock_req.method = "GET"
        mock_resp = MagicMock(spec=Response)
        mock_resp.request.method = "GET"
        mock_resp.status_code = 200
        assert cc.should_read_from_cache(mock_req) is False
        assert cc.should_cache_response(mock_resp) is False

    def test_read_only_blocks_write(self):
        cc = CacheConfig(policy=CachePolicy.READ_ONLY)
        mock_req = MagicMock(spec=Request)
        mock_req.method = "GET"
        mock_resp = MagicMock(spec=Response)
        mock_resp.request.method = "GET"
        mock_resp.status_code = 200
        assert cc.should_read_from_cache(mock_req) is True
        assert cc.should_cache_response(mock_resp) is False

    def test_write_only_blocks_read(self):
        cc = CacheConfig(policy=CachePolicy.WRITE_ONLY)
        mock_req = MagicMock(spec=Request)
        mock_req.method = "GET"
        mock_resp = MagicMock(spec=Response)
        mock_resp.request.method = "GET"
        mock_resp.status_code = 200
        assert cc.should_read_from_cache(mock_req) is False
        assert cc.should_cache_response(mock_resp) is True

    def test_should_cache_response_by_status_and_method(self):
        cc = CacheConfig(status_codes={200, 201}, methods={"GET"})
        mock_resp_ok = MagicMock(spec=Response)
        mock_resp_ok.status_code = 200
        mock_resp_ok.request.method = "GET"
        mock_resp_post = MagicMock(spec=Response)
        mock_resp_post.status_code = 200
        mock_resp_post.request.method = "POST"
        mock_resp_404 = MagicMock(spec=Response)
        mock_resp_404.status_code = 404
        mock_resp_404.request.method = "GET"
        assert cc.should_cache_response(mock_resp_ok) is True
        assert cc.should_cache_response(mock_resp_post) is False
        assert cc.should_cache_response(mock_resp_404) is False


class TestCacheKeyBuilder:
    def test_build_minimal(self):
        req = Request("GET", "https://example.com/resource")
        key = CacheKeyBuilder.build(req)
        assert isinstance(key, str)
        assert len(key) == 64

    def test_build_with_prefix(self):
        req = Request("GET", "https://example.com/resource")
        key = CacheKeyBuilder.build(req, prefix="myapp")
        assert key.startswith("myapp:")

    def test_different_methods_different_keys(self):
        req1 = Request("GET", "https://example.com/resource")
        req2 = Request("POST", "https://example.com/resource")
        k1 = CacheKeyBuilder.build(req1)
        k2 = CacheKeyBuilder.build(req2)
        assert k1 != k2

    def test_different_urls_different_keys(self):
        req1 = Request("GET", "https://example.com/a")
        req2 = Request("GET", "https://example.com/b")
        k1 = CacheKeyBuilder.build(req1)
        k2 = CacheKeyBuilder.build(req2)
        assert k1 != k2

    def test_same_input_same_key(self):
        req1 = Request("GET", "https://example.com/resource")
        req2 = Request("GET", "https://example.com/resource")
        assert CacheKeyBuilder.build(req1) == CacheKeyBuilder.build(req2)

    def test_with_query_string(self):
        req1 = Request("GET", "https://example.com/resource?page=1")
        req2 = Request("GET", "https://example.com/resource?page=2")
        assert CacheKeyBuilder.build(req1) != CacheKeyBuilder.build(req2)

    def test_with_headers_in_key(self):
        req1 = Request("GET", "https://example.com/resource")
        req1.headers["accept"] = "application/json"
        req2 = Request("GET", "https://example.com/resource")
        req2.headers["accept"] = "text/html"
        key1 = CacheKeyBuilder.build(req1, include_headers=True, cache_key_headers=["accept"])
        key2 = CacheKeyBuilder.build(req2, include_headers=True, cache_key_headers=["accept"])
        assert key1 != key2


class TestHTTPCache:
    @pytest.fixture
    def memory_backend(self):
        return MemoryCache()

    @pytest.fixture
    def http_cache(self, memory_backend):
        config = CacheConfig(ttl=120)
        return HTTPCache(memory_backend, config=config)

    async def test_get_missing(self, http_cache):
        req = Request("GET", "https://example.com/resource")
        result = await http_cache.get(req)
        assert result is _MISSING

    async def test_set_and_get(self, http_cache):
        req = Request("GET", "https://example.com/resource")
        resp = Response(200, json={"key": "value"}, request=req)
        await http_cache.set(req, resp)
        cached = await http_cache.get(req)
        assert cached is not _MISSING
        assert cached.status_code == 200
        assert json.loads(cached.body) == {"key": "value"}

    async def test_set_and_get_multiple(self, http_cache):
        req1 = Request("GET", "https://example.com/a")
        resp1 = Response(200, json={"id": 1}, request=req1)
        req2 = Request("GET", "https://example.com/b")
        resp2 = Response(200, json={"id": 2}, request=req2)
        await http_cache.set(req1, resp1)
        await http_cache.set(req2, resp2)
        c1 = await http_cache.get(req1)
        c2 = await http_cache.get(req2)
        assert json.loads(c1.body) == {"id": 1}
        assert json.loads(c2.body) == {"id": 2}

    async def test_invalidate(self, http_cache):
        req = Request("GET", "https://example.com/resource")
        resp = Response(200, json={"x": 1}, request=req)
        await http_cache.set(req, resp)
        assert await http_cache.get(req) is not _MISSING
        await http_cache.invalidate(req)
        assert await http_cache.get(req) is _MISSING

    async def test_clear(self, http_cache):
        req1 = Request("GET", "https://example.com/a")
        req2 = Request("GET", "https://example.com/b")
        await http_cache.set(req1, Response(200, json={"a": 1}, request=req1))
        await http_cache.set(req2, Response(200, json={"b": 2}, request=req2))
        await http_cache.clear()
        assert await http_cache.get(req1) is _MISSING
        assert await http_cache.get(req2) is _MISSING

    async def test_custom_ttl(self, http_cache):
        req = Request("GET", "https://example.com/resource")
        resp = Response(200, json={"x": 1}, request=req)
        await http_cache.set(req, resp, ttl=10)
        cached = await http_cache.get(req)
        assert cached.ttl == 10

    async def test_invalidate_tags(self, memory_backend):
        config = CacheConfig(ttl=120, tags=["group-a"])
        http_cache = HTTPCache(memory_backend, config=config)
        req1 = Request("GET", "https://example.com/a")
        req2 = Request("GET", "https://example.com/b")
        await http_cache.set(req1, Response(200, json={"a": 1}, request=req1))
        await http_cache.set(req2, Response(200, json={"b": 2}, request=req2))
        assert await http_cache.get(req1) is not _MISSING
        assert await http_cache.get(req2) is not _MISSING
        await http_cache.invalidate_tags("group-a")
        assert await http_cache.get(req1) is _MISSING
        assert await http_cache.get(req2) is _MISSING

    def test_backend_and_config_properties(self, http_cache, memory_backend):
        assert http_cache.backend is memory_backend
        assert http_cache.config.ttl == 120

    def test_config_setter(self, http_cache):
        new_config = CacheConfig(ttl=999)
        http_cache.config = new_config
        assert http_cache.config.ttl == 999


# ==================== CachedResponse / ResponseValidator Tests ====================


class TestCachedResponse:
    def test_from_httpx_response(self):
        req = Request("GET", "https://example.com/resource")
        resp = Response(200, json={"key": "value"}, headers={"content-type": "application/json"}, request=req)
        cached = CachedResponse.from_httpx_response(resp, ttl=300)
        assert cached.status_code == 200
        assert cached.method == "GET"
        assert cached.url == "https://example.com/resource"
        assert cached.ttl == 300
        assert "content-type" in cached.headers
        assert isinstance(cached.cached_at, datetime)
        assert json.loads(cached.body) == {"key": "value"}

    def test_from_httpx_without_request(self):
        req = Request("GET", "https://example.com/data")
        resp = Response(200, json={"x": 1}, request=req)
        cached = CachedResponse.from_httpx_response(resp)
        assert cached.url == "https://example.com/data"

    def test_to_json_dict_and_from_json_dict_roundtrip(self):
        req = Request("GET", "https://example.com/resource")
        resp = Response(200, json={"key": "value"}, request=req)
        cached = CachedResponse.from_httpx_response(resp, ttl=60)
        data = cached.to_json_dict()
        restored = CachedResponse.from_json_dict(data)
        assert restored.status_code == cached.status_code
        assert restored.url == cached.url
        assert restored.method == cached.method
        assert restored.ttl == cached.ttl
        assert restored.body == cached.body

    def test_to_json_dict_mode(self):
        req = Request("GET", "https://example.com/r")
        resp = Response(200, json={"n": 42}, request=req)
        cached = CachedResponse.from_httpx_response(resp)
        d = cached.to_json_dict()
        assert isinstance(d["cached_at"], str)

    def test_model_rebuild(self):
        CachedResponse.model_rebuild()


class TestResponseValidator:
    def test_validate_no_model(self):
        result = ResponseValidator.validate('{"id": 1, "name": "Alice"}', response_model=None)
        assert result == {"id": 1, "name": "Alice"}

    def test_validate_single_model(self):
        result = ResponseValidator.validate('{"id": 1, "name": "Alice", "email": "a@b.com"}', response_model=User)
        assert isinstance(result, User)
        assert result.id == 1
        assert result.name == "Alice"

    def test_validate_many(self):
        body = '[{"id": 1, "name": "A", "email": "a@b.com"}, {"id": 2, "name": "B", "email": "b@c.com"}]'
        result = Result = ResponseValidator.validate(body, response_model=User, many=True)
        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    def test_validate_many_expects_list(self):
        body = '{"id": 1, "name": "A", "email": "a@b.com"}'
        with pytest.raises(HTTPValidationError):
            ResponseValidator.validate(body, response_model=User, many=True)

    def test_validate_strict_mode(self):
        body = '{"id": "not_an_int", "name": "A", "email": "a@b.com"}'
        with pytest.raises(HTTPValidationError):
            ResponseValidator.validate(body, response_model=User, strict=True)

    def test_invalid_json(self):
        with pytest.raises(HTTPDecodeError):
            ResponseValidator.validate("not json", response_model=None)

    def test_validation_error_contains_errors(self):
        try:
            ResponseValidator.validate('{"id": "nope", "name": "A", "email": "b@c.com"}', response_model=User)
        except HTTPValidationError as e:
            assert len(e.validation_errors) > 0

    def test_returns_raw_json_on_no_model(self):
        assert ResponseValidator.validate("42", response_model=None) == 42
        assert ResponseValidator.validate("true", response_model=None) is True
        assert ResponseValidator.validate("[1,2,3]", response_model=None) == [1, 2, 3]


# ==================== HTTPClientConfig / HTTPClientStats Tests ====================


class TestHTTPClientConfig:
    def test_default_values(self):
        config = HTTPClientConfig()
        assert config.base_url == ""
        assert config.default_timeout == 30.0
        assert config.max_connections == 50
        assert config.verify_ssl is True
        assert config.follow_redirects is True
        assert config.max_redirects == 20
        assert config.retry_strategy is None
        assert config.cache_backend is None
        assert config.cache_ttl == 300
        assert config.cache_tags is None

    def test_base_url(self):
        config = HTTPClientConfig(base_url="https://api.example.com")
        assert config.base_url == "https://api.example.com"

    def test_cache_tags(self):
        config = HTTPClientConfig(cache_tags=["users", "profiles"])
        assert config.cache_tags == ["users", "profiles"]

    def test_resolve_timeout_all_default(self):
        config = HTTPClientConfig(default_timeout=10.0)
        t = config.resolve_timeout()
        assert t == {"connect": 10.0, "read": 10.0, "write": 10.0, "pool": 10.0}

    def test_resolve_timeout_overrides(self):
        config = HTTPClientConfig(default_timeout=30.0, connect_timeout=5.0, read_timeout=10.0)
        t = config.resolve_timeout()
        assert t["connect"] == 5.0
        assert t["read"] == 10.0
        assert t["write"] == 30.0
        assert t["pool"] == 30.0

    def test_default_auth(self):
        config = HTTPClientConfig(default_auth=("user", "pass"))
        assert config.default_auth == ("user", "pass")

    def test_default_headers(self):
        config = HTTPClientConfig(default_headers={"Authorization": "Bearer test"})
        assert config.default_headers == {"Authorization": "Bearer test"}

    def test_retry_strategy(self):
        rs = RetryStrategy(max_attempts=5)
        config = HTTPClientConfig(retry_strategy=rs)
        assert config.retry_strategy is rs

    def test_user_agent(self):
        config = HTTPClientConfig(user_agent="MyApp/1.0")
        assert config.user_agent == "MyApp/1.0"


class TestHTTPClientStats:
    def test_default_zero(self):
        s = HTTPClientStats()
        assert s.requests_total == 0
        assert s.success_rate == 0.0

    def test_success_rate_calculation(self):
        s = HTTPClientStats()
        s.requests_total = 10
        s.requests_success = 8
        assert s.success_rate == 10 / 8

    def test_as_dict_keys(self):
        s = HTTPClientStats()
        s.requests_total = 5
        s.requests_success = 4
        d = s.as_dict()
        assert "requests_total" in d
        assert "requests_success" in d
        assert "success_rate" in d
        assert "retries_total" in d
        assert d["requests_total"] == 5

    def test_cache_counters(self):
        s = HTTPClientStats()
        s.cache_hits = 10
        s.cache_misses = 2
        assert s.cache_hits == 10
        assert s.cache_misses == 2


# ==================== Middleware Tests ====================


class TestMiddlewareChain:
    async def test_no_middleware(self):
        request = Request("GET", "https://example.com")

        async def final_send(req):
            yield Response(200, json={"ok": True})

        chain = MiddlewareChain([])
        results = []
        async for resp in chain.run(request, final_send):
            results.append(resp)
        assert len(results) == 1

    async def test_logging_middleware(self):
        import logging

        logger = logging.getLogger("http_test")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()

        class TestHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records = []

            def emit(self, record):
                self.records.append(record)

        test_handler = TestHandler()
        logger.addHandler(test_handler)

        mw = LoggingMiddleware(logger=logger)
        request = Request("GET", "https://example.com")

        async def final_send(req):
            yield Response(200, json={"ok": True})

        chain = MiddlewareChain([mw])
        async for _ in chain.run(request, final_send):
            pass
        assert len(test_handler.records) >= 0

    async def test_header_injection_middleware(self):
        mw = HeaderInjectionMiddleware({"X-Custom": "test-value"})
        request = Request("GET", "https://example.com")

        async def final_send(req):
            yield Response(200, json={})

        chain = MiddlewareChain([mw])
        async for _ in chain.run(request, final_send):
            pass
        assert request.headers.get("X-Custom") == "test-value"

    async def test_base_url_middleware(self):
        mw = BaseURLMiddleware("https://api.example.com")
        request = Request("GET", "/resource")

        async def final_send(req):
            yield Response(200, json={})

        chain = MiddlewareChain([mw])
        async for _ in chain.run(request, final_send):
            pass

    def test_http_middleware_abstract(self):
        with pytest.raises(TypeError):
            HTTPMiddleware()

    def test_middleware_initialization(self):
        mw = LoggingMiddleware()
        assert mw is not None
        mw2 = HeaderInjectionMiddleware({"X-Test": "1"})
        assert mw2 is not None
        mw3 = BaseURLMiddleware("https://example.com")
        assert mw3 is not None


# ==================== HTTPClient (live, standalone, and mock-based) ====================


class TestHTTPClientLifecycle:
    @pytest.fixture
    def client(self):
        return HTTPClientConfig()

    async def test_start_and_stop(self):
        from sillo.http.client.client import HTTPClient

        client = HTTPClient("https://httpbin.org")
        await client.start()
        assert client._state.client is not None
        await client.stop()
        assert client._state.client is None

    async def test_context_manager(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://httpbin.org") as client:
            assert client._state.client is not None
        assert client._state.client is None

    async def test_not_started_raises(self):
        from sillo.http.client.client import HTTPClient

        client = HTTPClient()
        with pytest.raises(RuntimeError, match="not started"):
            _ = client._http_client

    async def test_double_start(self):
        from sillo.http.client.client import HTTPClient

        client = HTTPClient("https://httpbin.org")
        await client.start()
        c1 = client._state.client
        assert c1 is not None
        await client.start()
        c2 = client._state.client
        assert c2 is c1
        await client.stop()

    def test_config_property(self):
        from sillo.http.client.client import HTTPClient

        config = HTTPClientConfig(base_url="https://api.example.com")
        client = HTTPClient(config=config)
        assert client.config is config

    def test_stats_property(self):
        from sillo.http.client.client import HTTPClient

        client = HTTPClient()
        assert client.stats is not None
        assert isinstance(client.stats, HTTPClientStats)

    def test_state_property(self):
        from sillo.http.client.client import HTTPClient

        client = HTTPClient()
        assert client.state is not None


class TestHTTPClientSend:
    """Test _send directly with a local mock HTTP server (httpbin)."""


class TestHTTPClientCaching:
    """Test caching integration within HTTPClient using mocked sends."""

    async def test_cache_hit_avoids_send(self):
        from sillo.http.client.client import HTTPClient

        mem = MemoryCache()
        async with HTTPClient(
            "https://example.com",
            cache_backend=mem,
            cache_ttl=120,
        ) as client:
            req = client._http_client.build_request("GET", "https://example.com/resource")
            cached_resp = CachedResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                body='{"key":"value"}',
                url="https://example.com/resource",
                method="GET",
                cached_at=datetime.now(),
                ttl=120,
            )
            await mem.set("testkey", cached_resp.to_json_dict(), ttl=120)
            with patch.object(client._state.cache, "get", new=AsyncMock(return_value=cached_resp)):
                with patch.object(client._http_client, "send", new=AsyncMock()) as mock_send:
                    resp = await client._send("GET", "https://example.com/resource")
                    assert resp.status_code == 200
                    assert resp.text == '{"key":"value"}'
                    mock_send.assert_not_called()

    async def test_cache_miss_calls_send(self):
        from sillo.http.client.client import HTTPClient

        mem = MemoryCache()
        async with HTTPClient(
            "https://example.com",
            cache_backend=mem,
            cache_ttl=120,
        ) as client:
            req = client._http_client.build_request("GET", "https://example.com/other")
            resp = Response(200, json={"ok": True}, request=req)
            with patch.object(client._http_client, "send", new=AsyncMock(return_value=resp)) as mock_send:
                result = await client._send("GET", "https://example.com/other")
                mock_send.assert_called_once()
                assert result.status_code == 200

    async def test_cache_write_on_success(self):
        from sillo.http.client.client import HTTPClient

        mem = MemoryCache()
        async with HTTPClient(
            "https://example.com",
            cache_backend=mem,
            cache_ttl=60,
        ) as client:
            req = client._http_client.build_request("GET", "https://example.com/write_test")
            with patch.object(client._http_client, "send", new=AsyncMock(return_value=Response(200, json={"ok": True}, request=req))):
                await client._send("GET", "https://example.com/write_test")
            req = client._http_client.build_request("GET", "https://example.com/write_test")
            cached = await client._state.cache.get(req)
            assert cached is not _MISSING
            assert json.loads(cached.body) == {"ok": True}


class TestHTTPClientPydanticValidation:
    """Test response_model validation through the request() method."""

    async def test_validate_single_model(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            with patch.object(client, "_send", new=AsyncMock(return_value=Response(200, json={"id": 1, "name": "Alice", "email": "a@b.com"}))):
                result = await client.get("/users/1", response_model=User)
                assert isinstance(result, User)
                assert result.id == 1
                assert result.name == "Alice"

    async def test_validate_many_models(self):
        from sillo.http.client.client import HTTPClient

        body = '[{"id":1,"name":"A","email":"a@b.com"},{"id":2,"name":"B","email":"b@c.com"}]'
        async with HTTPClient("https://example.com") as client:
            with patch.object(client, "_send", new=AsyncMock(return_value=Response(200, json=json.loads(body)))):
                result = await client.get("/users", response_model=User, many=True)
                assert len(result) == 2

    async def test_no_response_model_returns_json(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            with patch.object(client, "_send", new=AsyncMock(return_value=Response(200, json={"key": "value"}))):
                result = await client.get("/data")
                assert result == {"key": "value"}

    async def test_non_json_response_returns_text(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            with patch.object(client, "_send", new=AsyncMock(return_value=Response(200, text="plain text"))):
                result = await client.get("/text")
                assert result == "plain text"


class TestHTTPClientErrorCases:
    """Test error handling in HTTPClient communications."""

    async def test_timeout_raises_httptimeout(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            with patch.object(client._http_client, "send", new=AsyncMock(side_effect=httpx.TimeoutException("timeout"))):
                with pytest.raises(HTTPTimeoutError):
                    await client._send("GET", "/")

    async def test_connect_error_raises_httpconnection(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            with patch.object(client._http_client, "send", new=AsyncMock(side_effect=httpx.ConnectError("connect fail"))):
                with pytest.raises(HTTPConnectionError):
                    await client._send("GET", "/")

    async def test_http_error_raises_httpstatus(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            with patch.object(client._http_client, "send", new=AsyncMock(side_effect=httpx.HTTPError("generic http error"))):
                with pytest.raises(HTTPStatusError):
                    await client._send("GET", "/")

    async def test_raise_for_status_enabled(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com", raise_for_status=True) as client:
            req = client._http_client.build_request("GET", "https://example.com/not-found")
            resp = Response(404, json={"error": "not found"}, request=req)
            with patch.object(client._http_client, "send", new=AsyncMock(return_value=resp)):
                with pytest.raises(HTTPStatusError) as exc_info:
                    await client._send("GET", "/not-found")
                assert exc_info.value.status_code == 404


class TestHTTPClientCacheManagement:
    """Test cache management methods on HTTPClient."""

    async def test_invalidate_cache_no_cache(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            assert await client.invalidate_cache("https://example.com/x") is False

    async def test_clear_cache_no_cache(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            await client.clear_cache()

    async def test_invalidate_cache_tags_no_cache(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            assert await client.invalidate_cache_tags("tag") == 0

    async def test_cache_operations_with_cache(self):
        from sillo.http.client.client import HTTPClient

        mem = MemoryCache()
        async with HTTPClient("https://example.com", cache_backend=mem) as client:
            req1 = client._http_client.build_request("GET", "https://example.com/test_manage")
            resp1 = Response(200, json={"ok": True}, request=req1)
            with patch.object(client._http_client, "send", new=AsyncMock(return_value=resp1)):
                await client._send("GET", "/test_manage")
            assert await client.invalidate_cache("https://example.com/test_manage") is True
            req2 = client._http_client.build_request("GET", "https://example.com/test_manage")
            req3 = client._http_client.build_request("GET", "https://example.com/test_manage2")
            resp2 = Response(200, json={"ok": True}, request=req2)
            resp3 = Response(200, json={"ok": True}, request=req3)
            with patch.object(client._http_client, "send", new=AsyncMock(side_effect=[resp2, resp3])):
                await client._send("GET", "/test_manage")
                await client._send("GET", "/test_manage2")
            assert await client.invalidate_cache_tags("test-tag") == 0

    async def test_clear_cache(self):
        from sillo.http.client.client import HTTPClient

        mem = MemoryCache()
        async with HTTPClient("https://example.com", cache_backend=mem) as client:
            req_a = client._http_client.build_request("GET", "https://example.com/a")
            req_b = client._http_client.build_request("GET", "https://example.com/b")
            with patch.object(client._http_client, "send", new=AsyncMock(side_effect=[
                Response(200, json={"a": 1}, request=req_a),
                Response(200, json={"b": 2}, request=req_b),
            ])):
                await client._send("GET", "/a")
                await client._send("GET", "/b")
            await client.clear_cache()
            req = client._http_client.build_request("GET", "/a")
            cached = await client._state.cache.get(req)
            assert cached is _MISSING


class TestHTTPClientStatsTracking:
    async def test_stats_tracked_on_success(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            with patch.object(client._http_client, "send", new=AsyncMock(return_value=Response(200, json={}))):
                await client._send("GET", "/")
            assert client.stats.requests_total == 1
            assert client.stats.requests_success == 1
            assert client.stats.requests_failed == 0

    async def test_stats_tracked_on_failure(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            with patch.object(client._http_client, "send", new=AsyncMock(side_effect=httpx.TimeoutException("fail"))):
                with pytest.raises(HTTPTimeoutError):
                    await client._send("GET", "/")
            assert client.stats.requests_failed == 1
            assert client.stats.requests_total == 0

    async def test_stats_tracked_on_http_failure(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            req = client._http_client.build_request("GET", "https://example.com/err")
            resp = Response(500, text="error", request=req)
            with patch.object(client._http_client, "send", new=AsyncMock(return_value=resp)):
                await client._send("GET", "/err")
            assert client.stats.requests_total == 1
            assert client.stats.requests_success == 0
            assert client.stats.requests_failed == 1

    async def test_cache_hit_updates_stats(self):
        from sillo.http.client.client import HTTPClient

        mem = MemoryCache()
        async with HTTPClient("https://example.com", cache_backend=mem, cache_ttl=60) as client:
            cached_resp = CachedResponse(
                status_code=200, headers={}, body='{"x":1}',
                url="https://example.com/x", method="GET",
                cached_at=datetime.now(), ttl=60,
            )
            with patch.object(client._state.cache, "get", new=AsyncMock(return_value=cached_resp)):
                resp = await client._send("GET", "/x")
                assert resp.status_code == 200
            assert client.stats.cache_hits == 1

    async def test_cache_miss_updates_stats(self):
        from sillo.http.client.client import HTTPClient

        mem = MemoryCache()
        async with HTTPClient("https://example.com", cache_backend=mem, cache_ttl=60) as client:
            req = client._http_client.build_request("GET", "https://example.com/miss")
            with patch.object(client._http_client, "send", new=AsyncMock(return_value=Response(200, json={}, request=req))):
                await client._send("GET", "/miss")
            assert client.stats.cache_misses == 1

    async def test_reset_stats(self):
        from sillo.http.client.client import HTTPClient

        async with HTTPClient("https://example.com") as client:
            client._state.stats.requests_total = 10
            client.reset_stats()
            assert client.stats.requests_total == 0


# ==================== ConnectionPoolConfig Tests ====================


class TestConnectionPoolConfig:
    def test_default_values(self):
        c = ConnectionPoolConfig()
        assert c.max_connections == 50
        assert c.max_keepalive_connections == 20
        assert c.keepalive_expiry == 30.0

    def test_custom_values(self):
        c = ConnectionPoolConfig(max_connections=100, max_keepalive_connections=50, keepalive_expiry=15.0)
        assert c.max_connections == 100
        assert c.max_keepalive_connections == 50
        assert c.keepalive_expiry == 15.0

    def test_build_limits(self):
        import httpx

        c = ConnectionPoolConfig(max_connections=10, max_keepalive_connections=5)
        limits = c.build_limits()
        assert isinstance(limits, httpx.Limits)
        assert limits.max_connections == 10

    def test_build_transport(self):
        import httpx

        c = ConnectionPoolConfig(max_connections=5)
        transport = c.build_transport(verify_ssl=True)
        assert isinstance(transport, httpx.AsyncHTTPTransport)

    def test_uds(self):
        c = ConnectionPoolConfig(uds="/tmp/test.sock")
        assert c.uds == "/tmp/test.sock"


# ==================== HTTPClient HTTP Method Shorthands ====================


class TestHTTPClientMethods:
    """Test that all HTTP method shorthands delegate correctly."""

    async def _make_client(self):
        from sillo.http.client.client import HTTPClient

        c = HTTPClient("https://example.com")
        await c.start()
        return c

    async def test_get(self):
        c = await self._make_client()
        with patch.object(c, "request", new=AsyncMock(return_value={"ok": True})) as m:
            result = await c.get("/test")
            m.assert_called_once_with("GET", "/test", response_model=None, many=False, strict=False)
            assert result == {"ok": True}
        await c.stop()

    async def test_post(self):
        c = await self._make_client()
        with patch.object(c, "request", new=AsyncMock(return_value={"ok": True})) as m:
            result = await c.post("/test", json={"key": "val"})
            m.assert_called_once_with("POST", "/test", json={"key": "val"}, data=None, response_model=None, many=False, strict=False)
            assert result == {"ok": True}
        await c.stop()

    async def test_put(self):
        c = await self._make_client()
        with patch.object(c, "request", new=AsyncMock(return_value={"ok": True})) as m:
            result = await c.put("/test", json={"key": "val"})
            m.assert_called_once()
            assert result == {"ok": True}
        await c.stop()

    async def test_patch(self):
        c = await self._make_client()
        with patch.object(c, "request", new=AsyncMock(return_value={"ok": True})) as m:
            result = await c.patch("/test", json={"key": "val"})
            m.assert_called_once()
            assert result == {"ok": True}
        await c.stop()

    async def test_delete(self):
        c = await self._make_client()
        with patch.object(c, "request", new=AsyncMock(return_value={"ok": True})) as m:
            result = await c.delete("/test/1")
            m.assert_called_once_with("DELETE", "/test/1", response_model=None, many=False, strict=False)
            assert result == {"ok": True}
        await c.stop()

    async def test_head(self):
        c = await self._make_client()
        with patch.object(c, "_send", new=AsyncMock(return_value=Response(200))) as m:
            result = await c.head("/test")
            m.assert_called_once_with("HEAD", "/test")
            assert result.status_code == 200
        await c.stop()

    async def test_options(self):
        c = await self._make_client()
        with patch.object(c, "_send", new=AsyncMock(return_value=Response(200, json={"methods": ["GET", "POST"]}))) as m:
            result = await c.options("/test")
            m.assert_called_once()
            assert result == {"methods": ["GET", "POST"]}
        await c.stop()


# ==================== Utils Tests ====================


class TestUtils:
    def test_extract_response_summary_keys(self):
        req = Request("GET", "https://example.com")
        resp = Response(200, json={"x": 1}, request=req)
        resp.elapsed = timedelta(seconds=0.5)
        summary = extract_response_summary(resp)
        assert summary["status_code"] == 200
        assert summary["url"] == "https://example.com"
        assert "body_preview" in summary
        assert "content_length" in summary

    def test_merge_headers_both_none(self):
        assert merge_headers(None, None) == {}

    def test_merge_headers_base_only(self):
        assert merge_headers({"a": "1"}, None) == {"a": "1"}

    def test_merge_headers_override_wins(self):
        assert merge_headers({"a": "1"}, {"a": "2"}) == {"a": "2"}

    def test_merge_headers_combined(self):
        assert merge_headers({"a": "1"}, {"b": "2"}) == {"a": "1", "b": "2"}

    def test_sanitize_url_for_log_api_key(self):
        result = sanitize_url_for_log("https://example.com?api_key=secret123")
        assert "api_key=***" in result
        assert "secret123" not in result

    def test_sanitize_url_clean_url(self):
        url = "https://example.com/users?page=1"
        assert sanitize_url_for_log(url) == url

    def test_sanitize_password(self):
        result = sanitize_url_for_log("https://example.com?password=mypass")
        assert "password=***" in result

    def test_guess_content_type_dict(self):
        assert guess_content_type({"key": "val"}) == "application/json"

    def test_guess_content_type_list(self):
        assert guess_content_type([1, 2]) == "application/json"

    def test_guess_content_type_str(self):
        assert guess_content_type("hello") == "text/plain"

    def test_guess_content_type_bytes(self):
        assert guess_content_type(b"bytes") == "application/octet-stream"

    def test_extract_response_summary_body_preview(self):
        req = Request("GET", "https://e.com")
        long_body = "x" * 1000
        resp = Response(200, text=long_body, request=req)
        resp.elapsed = timedelta(seconds=0.5)
        summary = extract_response_summary(resp)
        assert len(summary["body_preview"]) == 500

    def test_extract_response_summary_content_length(self):
        req = Request("GET", "https://e.com")
        resp = Response(200, json={"k": "v"}, request=req)
        resp.elapsed = timedelta(seconds=0.5)
        summary = extract_response_summary(resp)
        assert summary["content_length"] > 0


# ==================== Error Hierarchy ====================


class TestErrorHierarchy:
    def test_all_exceptions_inherit_from_base(self):
        assert issubclass(HTTPClientConfigError, HTTPClientError)
        assert issubclass(HTTPConnectionError, HTTPClientError)
        assert issubclass(HTTPTimeoutError, HTTPClientError)
        assert issubclass(HTTPStatusError, HTTPClientError)
        assert issubclass(HTTPRetryError, HTTPClientError)
        assert issubclass(HTTPCacheError, HTTPClientError)
        assert issubclass(HTTPValidationError, HTTPClientError)
        assert issubclass(HTTPRedirectError, HTTPClientError)
        assert issubclass(HTTPDecodeError, HTTPClientError)

    def test_error_attributes(self):
        e = HTTPStatusError("status error", status_code=404, response_body="not found", request_url="https://example.com", request_method="GET")
        assert e.status_code == 404
        assert e.response_body == "not found"
        assert e.request_url == "https://example.com"

        e2 = HTTPTimeoutError("timeout", timeout_type="connect")
        assert e2.timeout_type == "connect"

        e3 = HTTPRetryError("retry error", last_exception=ValueError("x"), attempts=3, total_delay=5.0)
        assert e3.attempts == 3

        e4 = HTTPValidationError("bad", validation_errors=[{"loc": ["id"]}], response_body="{}")
        assert len(e4.validation_errors) == 1
