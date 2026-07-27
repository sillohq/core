"""
Model lifecycle events: the dispatcher, observers, and the ``HasEvents`` mixin.

A callback that throws must not take the save down with it, so the
swallow-and-log behaviour is covered as deliberately as the happy path.
"""

import asyncio

import pytest

from sillo.record.events import EventDispatcher, HasEvents, ModelObserver


def _run(coro):
    return asyncio.run(coro)


class Instance:
    """Stand-in for a model row — the dispatcher only passes it through."""

    def __init__(self, name="row"):
        self.name = name
        self.touched_by = []


@pytest.fixture
def dispatcher():
    return EventDispatcher()


# ── callbacks ────────────────────────────────────────────────────────────


def test_a_registered_callback_fires(dispatcher):
    seen = []

    async def callback(instance):
        seen.append(instance)

    dispatcher.on("after_create", callback)
    row = Instance()
    _run(dispatcher.fire("after_create", row))
    assert seen == [row]


def test_a_callback_only_fires_for_its_own_event(dispatcher):
    seen = []

    async def callback(instance):
        seen.append("fired")

    dispatcher.on("after_create", callback)
    _run(dispatcher.fire("after_delete", Instance()))
    assert seen == []


def test_callbacks_fire_in_registration_order(dispatcher):
    order = []

    async def first(instance):
        order.append("first")

    async def second(instance):
        order.append("second")

    dispatcher.on("before_save", first)
    dispatcher.on("before_save", second)
    _run(dispatcher.fire("before_save", Instance()))
    assert order == ["first", "second"]


def test_a_callback_can_mutate_the_instance(dispatcher):
    """``before_create`` normalising a field is the point of the hook."""

    async def normalise(instance):
        instance.name = instance.name.lower()

    dispatcher.on("before_create", normalise)
    row = Instance("MiXeD")
    _run(dispatcher.fire("before_create", row))
    assert row.name == "mixed"


def test_an_unknown_event_name_is_ignored(dispatcher):
    async def callback(instance):
        raise AssertionError("should never run")

    dispatcher.on("not_a_real_event", callback)
    _run(dispatcher.fire("not_a_real_event", Instance()))


def test_firing_an_event_with_no_listeners_is_a_no_op(dispatcher):
    _run(dispatcher.fire("after_save", Instance()))


@pytest.mark.parametrize(
    "event",
    [
        "before_create",
        "after_create",
        "before_save",
        "after_save",
        "before_update",
        "after_update",
        "before_delete",
        "after_delete",
        "before_restore",
        "after_restore",
    ],
)
def test_every_documented_event_can_be_registered(dispatcher, event):
    seen = []

    async def callback(instance):
        seen.append(event)

    dispatcher.on(event, callback)
    _run(dispatcher.fire(event, Instance()))
    assert seen == [event]


def test_a_failing_callback_does_not_stop_the_others(dispatcher):
    """A broken audit hook must not prevent the row from being saved."""
    seen = []

    async def broken(instance):
        raise RuntimeError("hook exploded")

    async def healthy(instance):
        seen.append("ran")

    dispatcher.on("after_create", broken)
    dispatcher.on("after_create", healthy)
    _run(dispatcher.fire("after_create", Instance()))
    assert seen == ["ran"]


def test_a_callback_failure_is_logged(dispatcher, caplog):
    async def broken(instance):
        raise RuntimeError("hook exploded")

    dispatcher.on("after_create", broken)
    with caplog.at_level("ERROR"):
        _run(dispatcher.fire("after_create", Instance()))
    assert "after_create" in caplog.text


# ── observers ────────────────────────────────────────────────────────────


def test_an_observer_receives_the_matching_event(dispatcher):
    class Recorder(ModelObserver):
        def __init__(self):
            self.seen = []

        async def after_create(self, instance):
            self.seen.append(instance)

    observer = Recorder()
    dispatcher.observe(observer)
    row = Instance()
    _run(dispatcher.fire("after_create", row))
    assert observer.seen == [row]


def test_an_observer_ignores_events_it_does_not_override(dispatcher):
    """The base class defines every hook as a no-op, so unhandled events are
    silently fine."""

    class Recorder(ModelObserver):
        def __init__(self):
            self.seen = []

        async def after_create(self, instance):
            self.seen.append("create")

    observer = Recorder()
    dispatcher.observe(observer)
    _run(dispatcher.fire("after_delete", Instance()))
    assert observer.seen == []


def test_several_observers_all_fire(dispatcher):
    class Recorder(ModelObserver):
        def __init__(self, tag):
            self.tag = tag
            self.seen = []

        async def before_save(self, instance):
            instance.touched_by.append(self.tag)

    dispatcher.observe(Recorder("a"))
    dispatcher.observe(Recorder("b"))
    row = Instance()
    _run(dispatcher.fire("before_save", row))
    assert row.touched_by == ["a", "b"]


def test_a_failing_observer_does_not_stop_the_others(dispatcher):
    class Broken(ModelObserver):
        async def after_save(self, instance):
            raise RuntimeError("observer exploded")

    class Healthy(ModelObserver):
        async def after_save(self, instance):
            instance.touched_by.append("healthy")

    dispatcher.observe(Broken())
    dispatcher.observe(Healthy())
    row = Instance()
    _run(dispatcher.fire("after_save", row))
    assert row.touched_by == ["healthy"]


def test_an_observer_failure_is_logged(dispatcher, caplog):
    class Broken(ModelObserver):
        async def after_save(self, instance):
            raise RuntimeError("observer exploded")

    dispatcher.observe(Broken())
    with caplog.at_level("ERROR"):
        _run(dispatcher.fire("after_save", Instance()))
    assert "Broken" in caplog.text


def test_callbacks_run_before_observers(dispatcher):
    order = []

    class Watcher(ModelObserver):
        async def after_create(self, instance):
            order.append("observer")

    async def callback(instance):
        order.append("callback")

    dispatcher.on("after_create", callback)
    dispatcher.observe(Watcher())
    _run(dispatcher.fire("after_create", Instance()))
    assert order == ["callback", "observer"]


def test_the_base_observer_hooks_are_all_awaitable():
    observer = ModelObserver()
    row = Instance()
    for name in (
        "before_create",
        "after_create",
        "before_save",
        "after_save",
        "before_update",
        "after_update",
        "before_delete",
        "after_delete",
    ):
        assert _run(getattr(observer, name)(row)) is None


# ── the HasEvents mixin ──────────────────────────────────────────────────


def test_the_decorator_registers_a_callback():
    class Widget(HasEvents):
        _events = None

    seen = []

    @Widget.on("after_create")
    async def record(instance):
        seen.append(instance)

    row = Instance()
    _run(Widget.fire_event("after_create", row))
    assert seen == [row]


def test_the_decorator_returns_the_original_function():
    class Widget(HasEvents):
        _events = None

    @Widget.on("after_create")
    async def record(instance):
        return "value"

    assert _run(record(Instance())) == "value"


def test_a_model_can_register_an_observer():
    class Widget(HasEvents):
        _events = None

    class Watcher(ModelObserver):
        async def before_delete(self, instance):
            instance.touched_by.append("watched")

    Widget.observe(Watcher())
    row = Instance()
    _run(Widget.fire_event("before_delete", row))
    assert row.touched_by == ["watched"]


def test_firing_on_a_model_with_no_events_is_a_no_op():
    class Widget(HasEvents):
        _events = None

    _run(Widget.fire_event("after_create", Instance()))


def test_the_dispatcher_is_created_once():
    class Widget(HasEvents):
        _events = None

    Widget._ensure_events()
    first = Widget._events
    Widget._ensure_events()
    assert Widget._events is first


def test_several_callbacks_on_one_model():
    class Widget(HasEvents):
        _events = None

    order = []

    @Widget.on("before_save")
    async def first(instance):
        order.append("first")

    @Widget.on("before_save")
    async def second(instance):
        order.append("second")

    _run(Widget.fire_event("before_save", Instance()))
    assert order == ["first", "second"]
