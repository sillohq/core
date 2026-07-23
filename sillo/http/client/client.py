from __future__ import annotations

import typing

import httpx
from httpx._types import RequestContent
from pydantic import BaseModel

from sillo.cache.base import _MISSING
from sillo.http.client.config import HTTPClientConfig, HTTPClientStats
from sillo.http.client.errors import (
    HTTPConnectionError,
    HTTPRetryError,
    HTTPStatusError,
    HTTPTimeoutError,
)
from sillo.http.client.middleware import MiddlewareChain
from sillo.http.client.models import ResponseValidator
from sillo.http.client.transport import ConnectionPoolConfig

if typing.TYPE_CHECKING:
    from typing import Any, Optional, Union

    from httpx._types import (
        AuthTypes,
        CookieTypes,
        HeaderTypes,
        QueryParamTypes,
        RequestFiles,
        URLTypes,
    )

    RequestData = Union[dict[str, Any], list[Any], str, bytes, None]


class _HTTPClientState:
    """Holds the mutable runtime state of an HTTPClient.

    Wrapped in a helper object so the retry decorator (which wraps the
    public method, not the internal one) can still update stats without
    circular reference issues.
    """

    def __init__(self) -> None:
        self.client: Optional[httpx.AsyncClient] = None
        self.cache: Optional[Any] = None
        self.middleware_chain: Optional[MiddlewareChain] = None
        self.stats = HTTPClientStats()


class HTTPClient:
    """A robust async HTTP client built on top of httpx.

    Features:
    - Base URL support for relative request URLs
    - Response caching via the sillo.cache subsystem (HTTPCache wrapping
      MemoryCache / RedisCache)
    - Pydantic response validation and deserialization
    - Retry via the sillo.helpers.retry decorator
    - Middleware pipeline for cross-cutting concerns
    - Connection pooling and timeout management
    - Request statistics tracking

    Usage:
        ```python
        from pydantic import BaseModel
        from sillo.http.client import HTTPClient

        class User(BaseModel):
            id: int
            name: str

        async with HTTPClient("https://api.example.com") as client:
            user = await client.get("/users/1", response_model=User)
        ```

    With caching and retry:
        ```python
        from sillo.cache import MemoryCache
        from sillo.http.client import HTTPClient
        from sillo.http.client.retry import RetryStrategy

        cache = MemoryCache(namespace="api", default_ttl=60)
        client = HTTPClient(
            "https://api.example.com",
            cache_backend=cache,
            cache_ttl=300,
            cache_tags=["users"],
            retry_strategy=RetryStrategy(max_attempts=3),
        )
        ```
    """

    def __init__(
        self,
        base_url: str = "",
        *,
        config: Optional[HTTPClientConfig] = None,
        **kwargs: Any,
    ) -> None:
        if config is None:
            config = HTTPClientConfig(base_url=base_url, **kwargs)
        else:
            if base_url:
                config.base_url = base_url

        self._config = config
        self._state = _HTTPClientState()

    @property
    def config(self) -> HTTPClientConfig:
        return self._config

    @property
    def state(self) -> _HTTPClientState:
        return self._state

    @property
    def stats(self) -> HTTPClientStats:
        return self._state.stats

    async def __aenter__(self) -> HTTPClient:
        await self.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.stop()

    # ---- lifecycle ---------------------------------------------------

    async def start(self) -> None:
        """Initialise the underlying httpx client, cache, and middleware."""
        if self._state.client is not None:
            return

        timeout_values = self._config.resolve_timeout()
        timeout = httpx.Timeout(
            connect=timeout_values["connect"],
            read=timeout_values["read"],
            write=timeout_values["write"],
            pool=timeout_values["pool"],
        )

        pool_config = ConnectionPoolConfig(
            max_connections=self._config.max_connections,
            max_keepalive_connections=self._config.max_keepalive_connections,
        )

        auth: Optional[AuthTypes] = None
        if self._config.default_auth:
            auth = httpx.BasicAuth(*self._config.default_auth)

        headers: dict[str, str] = {}
        if self._config.default_headers:
            headers.update(self._config.default_headers)
        if self._config.user_agent:
            headers["user-agent"] = self._config.user_agent

        self._state.client = httpx.AsyncClient(
            base_url=self._config.base_url or None,
            timeout=timeout,
            limits=pool_config.build_limits(),
            verify=self._config.verify_ssl,
            trust_env=self._config.trust_env,
            follow_redirects=self._config.follow_redirects,
            max_redirects=self._config.max_redirects,
            auth=auth,
            headers=headers or None,
        )

        if self._config.cache_backend is not None:
            from sillo.http.client.caching import CacheConfig, CachePolicy, HTTPCache

            cache_config = CacheConfig(
                policy=CachePolicy.ENABLED,
                ttl=self._config.cache_ttl,
                key_prefix=self._config.cache_key_prefix,
                tags=self._config.cache_tags,
            )
            self._state.cache = HTTPCache(
                self._config.cache_backend, config=cache_config
            )

        middlewares = list(self._config.middlewares)
        self._state.middleware_chain = MiddlewareChain(middlewares)

    async def stop(self) -> None:
        """Close the underlying httpx client and release resources."""
        state = self._state
        if state.client is not None:
            await state.client.aclose()
            state.client = None

    @property
    def _http_client(self) -> httpx.AsyncClient:
        if self._state.client is None:
            raise RuntimeError(
                "HTTPClient not started. Use 'async with HTTPClient(...)' "
                "or call await client.start() before making requests."
            )
        return self._state.client

    # ---- low-level send ----------------------------------------------

    async def _send(
        self,
        method: str,
        url: URLTypes,
        *,
        content: Optional[RequestContent] = None,
        data: Optional[RequestData] = None,
        json: Optional[RequestData] = None,
        files: Optional[RequestFiles] = None,
        params: Optional[QueryParamTypes] = None,
        headers: Optional[HeaderTypes] = None,
        cookies: Optional[CookieTypes] = None,
        auth: Optional[AuthTypes] = None,
        follow_redirects: Optional[bool] = None,
        timeout: Optional[float] = None,
        extensions: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        """Execute a single HTTP request (one attempt, no retry logic)."""
        effective_timeout: Union[float, httpx.Timeout, None] = None
        if timeout is not None:
            effective_timeout = timeout
        elif self._config.default_timeout != 30.0:
            effective_timeout = self._config.default_timeout

        request = self._http_client.build_request(
            method=method,
            url=url,
            content=content,
            data=data,
            json=json,
            files=files,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=effective_timeout,
            extensions=extensions,
        )

        # Cache check (read-through)
        state = self._state
        if state.cache is not None and state.cache.config.should_read_from_cache(
            request
        ):
            cached = await state.cache.get(request)
            if cached is not _MISSING:
                state.stats.cache_hits += 1
                state.stats.requests_total += 1
                state.stats.requests_success += 1
                return httpx.Response(
                    status_code=cached.status_code,
                    headers=cached.headers,
                    text=cached.body,
                    request=request,
                )
            state.stats.cache_misses += 1

        # Middleware chain (only when middlewares are registered)
        mw_chain = state.middleware_chain

        try:
            if mw_chain and mw_chain._middlewares:
                response = None
                async for r in mw_chain.run(request, self._http_client.send):
                    response = r
                if response is None:
                    raise HTTPStatusError(
                        "Middleware chain produced no response",
                        status_code=0,
                        request_url=str(url),
                        request_method=method,
                    )
            else:
                response = await self._http_client.send(
                    request,
                    auth=auth,
                    follow_redirects=(
                        follow_redirects
                        if follow_redirects is not None
                        else self._config.follow_redirects
                    ),
                )
        except httpx.TimeoutException as exc:
            state.stats.requests_failed += 1
            raise HTTPTimeoutError(
                f"Request timed out: {exc}",
                timeout_type=type(exc).__name__,
            ) from exc
        except httpx.ConnectError as exc:
            state.stats.requests_failed += 1
            raise HTTPConnectionError(f"Connection failed: {exc}") from exc
        except httpx.HTTPError as exc:
            state.stats.requests_failed += 1
            raise HTTPStatusError(
                f"HTTP request failed: {exc}",
                status_code=0,
                request_url=str(url),
                request_method=method,
            ) from exc

        state.stats.requests_total += 1
        if response.is_success:
            state.stats.requests_success += 1
        else:
            state.stats.requests_failed += 1

        if self._config.raise_for_status and not response.is_success:
            raise HTTPStatusError(
                f"HTTP {response.status_code} for {method} {url}",
                status_code=response.status_code,
                response_body=response.text,
                request_url=str(response.url),
                request_method=method,
            )

        # Cache write-through
        if state.cache is not None and state.cache.config.should_cache_response(
            response
        ):
            await state.cache.set(request, response)

        return response

    # ---- retry-aware request (uses sillo.helpers.retry) --------------

    async def request(
        self,
        method: str,
        url: URLTypes,
        *,
        response_model: Optional[type[BaseModel]] = None,
        many: bool = False,
        strict: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Send an HTTP request with optional response validation.

        Retry behaviour is controlled by the ``retry_strategy`` on the
        client config.  When a RetryStrategy is provided the underlying
        :func:`_send` call is wrapped by the sillo ``helpers.retry``
        decorator, giving exponential backoff with jitter.

        Args:
            method: The HTTP method (GET, POST, PUT, DELETE, etc.).
            url: The request URL (relative or absolute).
            response_model: Optional Pydantic model for response validation.
            many: When True, validates a JSON array against ``response_model``.
            strict: When True, enables Pydantic strict mode.
            **kwargs: Additional arguments forwarded to the httpx request.

        Returns:
            The validated Pydantic model instance, a list of model instances,
            the raw parsed JSON, or the raw httpx.Response depending on input.
        """
        retry_strategy = self._config.retry_strategy
        _send = self._send

        if retry_strategy is not None:
            from sillo.helpers.retry import retry as sillo_retry

            retry_kwargs: dict[str, Any] = {
                "max_attempts": retry_strategy.max_attempts,
                "base_delay": retry_strategy.base_delay,
                "max_delay": retry_strategy.max_delay,
                "backoff_factor": retry_strategy.backoff_factor,
                "jitter": retry_strategy.jitter,
            }
            if retry_strategy.retryable_exceptions:
                retry_kwargs["retryable_exceptions"] = (
                    retry_strategy.retryable_exceptions
                )

            @sillo_retry(**retry_kwargs)
            async def _send_with_retry(*a: Any, **kw: Any) -> httpx.Response:
                resp = await _send(*a, **kw)
                if not resp.is_success and retry_strategy.should_retry_for_status(
                    resp.status_code
                ):
                    raise HTTPStatusError(
                        f"Retryable status {resp.status_code} for {method} {url}",
                        status_code=resp.status_code,
                        response_body=resp.text,
                        request_url=str(resp.url),
                        request_method=method,
                    )
                return resp

            try:
                response = await _send_with_retry(method, url, **kwargs)
            except Exception as exc:
                self._state.stats.retries_total += 1
                raise HTTPRetryError(
                    f"Request failed after retries: {exc}",
                    last_exception=exc if isinstance(exc, Exception) else None,
                ) from exc
        else:
            response = await _send(method, url, **kwargs)

        if response_model is None:
            try:
                return response.json()
            except Exception:
                return response.text

        raw_body = await response.aread()
        body_text = (
            raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body
        )

        return ResponseValidator.validate(
            body_text,
            response_model=response_model,
            many=many,
            strict=strict,
        )

    # ---- HTTP method shorthands --------------------------------------

    async def get(
        self,
        url: URLTypes,
        *,
        response_model: Optional[type[BaseModel]] = None,
        many: bool = False,
        strict: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Send a GET request."""
        return await self.request(
            "GET",
            url,
            response_model=response_model,
            many=many,
            strict=strict,
            **kwargs,
        )

    async def post(
        self,
        url: URLTypes,
        *,
        json: Optional[RequestData] = None,
        data: Optional[RequestData] = None,
        response_model: Optional[type[BaseModel]] = None,
        many: bool = False,
        strict: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Send a POST request."""
        return await self.request(
            "POST",
            url,
            json=json,
            data=data,
            response_model=response_model,
            many=many,
            strict=strict,
            **kwargs,
        )

    async def put(
        self,
        url: URLTypes,
        *,
        json: Optional[RequestData] = None,
        data: Optional[RequestData] = None,
        response_model: Optional[type[BaseModel]] = None,
        many: bool = False,
        strict: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Send a PUT request."""
        return await self.request(
            "PUT",
            url,
            json=json,
            data=data,
            response_model=response_model,
            many=many,
            strict=strict,
            **kwargs,
        )

    async def patch(
        self,
        url: URLTypes,
        *,
        json: Optional[RequestData] = None,
        data: Optional[RequestData] = None,
        response_model: Optional[type[BaseModel]] = None,
        many: bool = False,
        strict: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Send a PATCH request."""
        return await self.request(
            "PATCH",
            url,
            json=json,
            data=data,
            response_model=response_model,
            many=many,
            strict=strict,
            **kwargs,
        )

    async def delete(
        self,
        url: URLTypes,
        *,
        response_model: Optional[type[BaseModel]] = None,
        many: bool = False,
        strict: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Send a DELETE request."""
        return await self.request(
            "DELETE",
            url,
            response_model=response_model,
            many=many,
            strict=strict,
            **kwargs,
        )

    async def head(
        self,
        url: URLTypes,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a HEAD request."""
        return await self._send("HEAD", url, **kwargs)

    async def options(
        self,
        url: URLTypes,
        **kwargs: Any,
    ) -> Any:
        """Send an OPTIONS request."""
        response = await self._send("OPTIONS", url, **kwargs)
        try:
            return response.json()
        except Exception:
            return response.text

    # ---- Cache management --------------------------------------------

    async def invalidate_cache(self, url: URLTypes) -> bool:
        """Invalidate a cached response for the given URL."""
        if self._state.cache is None:
            return False
        request = self._http_client.build_request("GET", url)
        return await self._state.cache.invalidate(request)

    async def invalidate_cache_tags(self, *tags: str) -> int:
        """Invalidate all cached responses associated with the given tags."""
        if self._state.cache is None:
            return 0
        return await self._state.cache.invalidate_tags(*tags)

    async def clear_cache(self) -> None:
        """Clear the entire response cache."""
        if self._state.cache is not None:
            await self._state.cache.clear()

    # ---- Stats --------------------------------------------------------

    def reset_stats(self) -> None:
        """Reset all request statistics counters to zero."""
        self._state.stats = HTTPClientStats()


__all__ = [
    "HTTPClient",
]
