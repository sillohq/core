"""Tests for normalize_middleware, the one reading of "what is a middleware"."""

import pytest

from sillo.middleware.base import BaseMiddleware
from sillo.middleware.bridge import ASGIRequestResponseBridge
from sillo.middleware.define import DefineMiddleware, normalize_middleware


class RawFactory:
    def __init__(self, app, tag="x"):
        self.app = app
        self.tag = tag

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


class RawInstance:
    def __init__(self, tag="x"):
        self.app = None
        self.tag = tag

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


async def dispatch_fn(ctx, call_next):
    return await call_next()


class DispatchClass(BaseMiddleware):
    pass


def test_define_middleware_passes_through():
    spec = DefineMiddleware(RawFactory, tag="a")
    assert normalize_middleware(spec) is spec


def test_define_middleware_refuses_extra_arguments():
    with pytest.raises(TypeError, match="already carries"):
        normalize_middleware(DefineMiddleware(RawFactory), tag="a")


@pytest.mark.parametrize(
    "spec, args, kwargs",
    [
        ((RawFactory,), (), {}),
        ((RawFactory, ("a",)), ("a",), {}),
        ((RawFactory, ("a",), {"k": 1}), ("a",), {"k": 1}),
        ([RawFactory, (), {"tag": "z"}], (), {"tag": "z"}),
    ],
)
def test_tuple_forms(spec, args, kwargs):
    result = normalize_middleware(spec)
    assert result.cls is RawFactory
    assert result.args == args
    assert result.kwargs == kwargs


def test_tuple_refuses_extra_arguments():
    with pytest.raises(TypeError, match="already carries its own arguments"):
        normalize_middleware((RawFactory, (), {}), tag="a")


@pytest.mark.parametrize("bad", [(), (1,), (RawFactory, (), {}, "extra")])
def test_bad_tuples_are_refused(bad):
    with pytest.raises(TypeError, match="middleware tuple"):
        normalize_middleware(bad)


def test_dispatch_function_is_bridged():
    result = normalize_middleware(dispatch_fn)
    assert result.cls is ASGIRequestResponseBridge
    assert result.kwargs == {"dispatch": dispatch_fn}


def test_dispatch_instance_is_bridged():
    instance = DispatchClass()
    assert normalize_middleware(instance).cls is ASGIRequestResponseBridge


def test_raw_class_is_a_factory_with_its_arguments():
    result = normalize_middleware(RawFactory, tag="q")
    assert result.cls is RawFactory
    assert result.kwargs == {"tag": "q"}


def test_raw_instance_is_rebound_in_place_by_default():
    instance = RawInstance()
    result = normalize_middleware(instance)

    async def inner(scope, receive, send): ...

    built = result.cls(inner)
    assert built is instance
    assert instance.app is inner


def test_raw_instance_copy_keeps_instances_independent_but_shares_state():
    instance = RawInstance()
    instance.shared = {"hits": 0}
    result = normalize_middleware(instance, copy_instance=True)

    async def one(scope, receive, send): ...

    async def two(scope, receive, send): ...

    a, b = result.cls(one), result.cls(two)
    assert a is not instance and b is not instance and a is not b
    assert (a.app, b.app) == (one, two)
    assert instance.app is None
    assert a.shared is b.shared is instance.shared


def test_arguments_for_dispatch_are_refused():
    with pytest.raises(TypeError, match="dispatch form"):
        normalize_middleware(dispatch_fn, tag="a")


def test_arguments_for_a_built_instance_are_refused():
    with pytest.raises(TypeError, match="already constructed"):
        normalize_middleware(RawInstance(), tag="a")


def test_raw_flag_overrides_inference():
    class Odd:
        def __init__(self, app, **kw):
            self.app = app

        async def __call__(self, *args): ...

    result = normalize_middleware(Odd, raw=True, tag="z")
    assert result.cls is Odd and result.kwargs == {"tag": "z"}
