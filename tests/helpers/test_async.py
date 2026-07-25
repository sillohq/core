import functools
import sys

import pytest

from sillo.core.helpers.async_helpers import (
    AwaitableOrContextManagerWrapper,
    SupportsAsyncClose,
    collapse_excgroups,
    is_async_callable,
)

if sys.version_info < (3, 11):
    try:
        from exceptiongroup import BaseExceptionGroup
    except ImportError:
        pass


async def _async_fn():
    return "async"


def _sync_fn():
    return "sync"


class _AsyncCallable:
    async def __call__(self):
        return "async-call"


class _SyncCallable:
    def __call__(self):
        return "sync-call"


class _Conn:
    closed = False

    async def close(self):
        _Conn.closed = True


async def _open_conn():
    return _Conn()


def test_is_async_callable_async_function():
    assert is_async_callable(_async_fn) is True


def test_is_async_callable_sync_function():
    assert is_async_callable(_sync_fn) is False


def test_is_async_callable_async_callable_object():
    assert is_async_callable(_AsyncCallable()) is True


def test_is_async_callable_sync_callable_object():
    assert is_async_callable(_SyncCallable()) is False


def test_is_async_callable_partial_async():
    bound = functools.partial(_async_fn)
    assert is_async_callable(bound) is True


def test_is_async_callable_partial_sync():
    bound = functools.partial(_sync_fn)
    assert is_async_callable(bound) is False


def test_is_async_callable_partial_async_callable_object():
    bound = functools.partial(_AsyncCallable())
    assert is_async_callable(bound) is True


def test_is_async_callable_non_callable():
    assert is_async_callable(123) is False
    assert is_async_callable("str") is False


def test_is_async_callable_lambda_sync():
    assert is_async_callable(lambda: 1) is False


async def test_awaitable_wrapper_await():
    wrapper = AwaitableOrContextManagerWrapper(_open_conn())
    conn = await wrapper
    assert isinstance(conn, _Conn)


async def test_awaitable_wrapper_async_with_closes():
    _Conn.closed = False
    async with AwaitableOrContextManagerWrapper(_open_conn()) as conn:
        assert isinstance(conn, _Conn)
        assert _Conn.closed is False
    assert _Conn.closed is True


async def test_awaitable_wrapper_supports_protocol_type():
    wrapper = AwaitableOrContextManagerWrapper(_open_conn())
    # The wrapper satisfies the awaitable + async-context-manager contract.
    assert hasattr(wrapper, "__await__")
    assert hasattr(wrapper, "__aenter__")
    assert hasattr(wrapper, "__aexit__")


def test_collapse_excgroups_unwraps_single():
    with pytest.raises(ValueError):
        with collapse_excgroups():
            try:
                raise ValueError("boom")
            except ValueError as exc:
                try:
                    raise BaseExceptionGroup("g", [exc])
                except BaseExceptionGroup as grp:
                    raise grp


def test_collapse_excgroups_passes_through_multi():
    # A group with more than one exception is re-raised as-is.
    with pytest.raises(BaseExceptionGroup):
        with collapse_excgroups():
            raise BaseExceptionGroup("g", [ValueError("a"), TypeError("b")])


def test_collapse_excgroups_plain_exception():
    with pytest.raises(KeyError):
        with collapse_excgroups():
            raise KeyError("missing")
