"""Deep tests for sillo.work event system: EventDispatcher, listen decorator,
wildcards, priority, stop_propagation, and ListenerRegistry.
"""

import pytest

from sillo.work.queue.events import Event, EventDispatcher, listen
from sillo.work.queue.listener import EventListener, ListenerRegistry, WildcardListener
from dataclasses import dataclass


@dataclass
class OrderShipped(Event):
    order_id: str
    tracking: str


@dataclass
class PaymentReceived(Event):
    amount: int


async def test_dispatch_calls_registered_listener():
    disp = EventDispatcher()
    seen = []

    async def handler(ev: OrderShipped):
        seen.append(ev.order_id)

    disp.register(OrderShipped, handler)
    await disp.dispatch(OrderShipped(order_id="42", tracking="1Z"))
    assert seen == ["42"]


async def test_listen_decorator_marks_function():
    @listen(OrderShipped)
    async def h(ev):
        return ev

    assert hasattr(h, "_listens_to")
    assert OrderShipped in h._listens_to


async def test_priority_ordering():
    disp = EventDispatcher()
    order = []

    async def low(ev):
        order.append("low")

    async def high(ev):
        order.append("high")

    disp.register(OrderShipped, low, priority=1)
    disp.register(OrderShipped, high, priority=10)
    await disp.dispatch(OrderShipped(order_id="1", tracking="t"))
    assert order == ["high", "low"]


async def test_stop_propagation_blocks_later_listeners():
    disp = EventDispatcher()
    order = []

    async def first(ev):
        order.append("first")
        ev.stop_propagation()

    async def second(ev):
        order.append("second")

    disp.register(OrderShipped, first)
    disp.register(OrderShipped, second)
    await disp.dispatch(OrderShipped(order_id="1", tracking="t"))
    assert order == ["first"]


async def test_wildcard_receives_all_events():
    disp = EventDispatcher()
    seen = []

    async def wild(ev):
        seen.append(type(ev).__name__)

    disp.register_wildcard(wild)
    await disp.dispatch(OrderShipped(order_id="1", tracking="t"))
    await disp.dispatch(PaymentReceived(amount=5))
    assert set(seen) == {"OrderShipped", "PaymentReceived"}


async def test_forget_removes_listener():
    disp = EventDispatcher()
    seen = []

    async def h(ev):
        seen.append(1)

    disp.register(OrderShipped, h)
    assert disp.forget(OrderShipped, h) is True
    await disp.dispatch(OrderShipped(order_id="1", tracking="t"))
    assert seen == []


async def test_has_listeners():
    disp = EventDispatcher()
    assert disp.has_listeners(OrderShipped) is False
    disp.register_wildcard(lambda ev: None)
    assert disp.has_listeners(OrderShipped) is True


async def test_listener_registry_wildcard_glob():
    disp = EventDispatcher()
    reg = ListenerRegistry(disp)
    seen = []

    async def h(ev):
        seen.append(type(ev).__name__)

    reg.on("Order*", h)
    ev1 = OrderShipped(order_id="1", tracking="t")
    ev2 = PaymentReceived(amount=1)
    await disp.dispatch(ev1)
    await reg.dispatch_wildcards(ev1)
    await disp.dispatch(ev2)
    await reg.dispatch_wildcards(ev2)
    assert seen == ["OrderShipped"]


async def test_listener_registry_once_autounsubscribes():
    disp = EventDispatcher()
    reg = ListenerRegistry(disp)
    seen = []

    async def h(ev):
        seen.append(1)

    reg.once("OrderShipped", h)
    ev1 = OrderShipped(order_id="1", tracking="t")
    ev2 = OrderShipped(order_id="2", tracking="t")
    await disp.dispatch(ev1)
    await reg.dispatch_wildcards(ev1)
    await disp.dispatch(ev2)
    await reg.dispatch_wildcards(ev2)
    assert len(seen) == 1


async def test_listener_registry_guard():
    disp = EventDispatcher()
    reg = ListenerRegistry(disp)
    seen = []

    async def h(ev):
        seen.append(1)

    reg.on("OrderShipped", h, priority=0)
    wl = reg._wildcards[0]
    assert isinstance(wl, WildcardListener)
    wl.guard = lambda ev: False  # never fire
    ev = OrderShipped(order_id="1", tracking="t")
    await disp.dispatch(ev)
    await reg.dispatch_wildcards(ev)
    assert seen == []


async def test_event_listener_high_level():
    disp = EventDispatcher()
    el = EventListener(disp)
    seen = []

    async def h(ev):
        seen.append(ev.order_id)

    el.listen(OrderShipped, h)
    ev = OrderShipped(order_id="99", tracking="t")
    await disp.dispatch(ev)
    assert seen == ["99"]
