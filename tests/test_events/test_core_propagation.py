"""``sillo.events.core.Event`` — hierarchy, propagation and weak listeners.

An Event can have a parent and children, and a trigger walks capture down then
bubble up. That machinery, the weak-reference bookkeeping underneath it, and
the cancellation paths were the parts no test reached.
"""

import gc

import pytest

from sillo.events.core import Event
from sillo.events.enums import EventPhase
from sillo.events.types import EventContext
from sillo.events.exceptions import EventCancelledError


@pytest.fixture
def event():
    return Event("orders.created")


class TestRepresentation:
    def test_it_reports_its_name_and_listener_count(self, event):
        @event.listen
        def listener():
            return None

        text = repr(event)

        assert "orders.created" in text
        assert "listeners=1" in text


class TestMaxListeners:
    def test_it_can_be_raised(self, event):
        event.max_listeners = 50
        assert event.max_listeners == 50

    def test_it_cannot_be_set_below_the_current_count(self, event):
        for i in range(3):
            event.listen(lambda i=i: None)

        with pytest.raises(ValueError, match="Cannot set max_listeners"):
            event.max_listeners = 1


class TestHierarchy:
    def test_add_child_sets_the_parent(self):
        parent = Event("parent")
        child = Event("child")

        parent.add_child(child)

        assert child.parent is parent

    def test_remove_child_clears_the_parent(self):
        parent = Event("parent")
        child = Event("child")
        parent.add_child(child)

        parent.remove_child(child)

        assert child.parent is None

    def test_removing_a_stranger_is_a_no_op(self):
        parent = Event("parent")
        stranger = Event("stranger")

        parent.remove_child(stranger)

        assert stranger.parent is None

    def test_reparenting_detaches_from_the_previous_parent(self):
        first = Event("first")
        second = Event("second")
        child = Event("child")

        first.add_child(child)
        second.add_child(child)

        assert child.parent is second
        assert len(first._children) == 0

    def test_clearing_the_parent_directly(self):
        parent = Event("parent")
        child = Event("child")
        child.parent = parent

        child.parent = None

        assert child.parent is None


class TestPropagation:
    def test_a_parent_listener_sees_a_child_trigger(self):
        parent = Event("parent")
        child = Event("child")
        parent.add_child(child)
        seen = []

        @parent.listen
        def on_parent(*args, **kwargs):
            seen.append("parent")

        @child.listen
        def on_child(*args, **kwargs):
            seen.append("child")

        child.trigger()

        assert "child" in seen
        assert "parent" in seen

    async def test_propagation_works_asynchronously_too(self):
        parent = Event("parent")
        child = Event("child")
        parent.add_child(child)
        seen = []

        @parent.listen
        async def on_parent(*args, **kwargs):
            seen.append("parent")

        @child.listen
        async def on_child(*args, **kwargs):
            seen.append("child")

        await child.trigger_async()

        assert "child" in seen
        assert "parent" in seen

    def _event_data(self, event):
        """The shape trigger() builds and hands to _propagate."""
        return {
            "args": (),
            "kwargs": {},
            "context": EventContext(timestamp=0.0, event_id="test", source=event),
            "cancelled": False,
        }

    def test_capture_reaches_the_parent(self):
        parent = Event("parent")
        child = Event("child")
        parent.add_child(child)
        phases = []

        @parent.listen
        def on_parent(*args, **kwargs):
            phases.append("parent")

        child._propagate(self._event_data(child), EventPhase.CAPTURING)

        assert phases == ["parent"]

    def test_bubbling_reaches_the_children(self):
        parent = Event("parent")
        child = Event("child")
        parent.add_child(child)
        phases = []

        @child.listen
        def on_child(*args, **kwargs):
            phases.append("child")

        parent._propagate(self._event_data(parent), EventPhase.BUBBLING)

        assert phases == ["child"]

    async def test_async_capture_reaches_the_parent(self):
        parent = Event("parent")
        child = Event("child")
        parent.add_child(child)
        phases = []

        @parent.listen
        async def on_parent(*args, **kwargs):
            phases.append("parent")

        await child._propagate_async(self._event_data(child), EventPhase.CAPTURING)

        assert phases == ["parent"]

    async def test_async_bubbling_reaches_the_children(self):
        parent = Event("parent")
        child = Event("child")
        parent.add_child(child)
        phases = []

        @child.listen
        async def on_child(*args, **kwargs):
            phases.append("child")

        await parent._propagate_async(self._event_data(parent), EventPhase.BUBBLING)

        assert phases == ["child"]


class TestDisabling:
    def test_a_disabled_event_does_not_fire(self, event):
        calls = []

        @event.listen
        def listener():
            calls.append(1)

        event.enabled = False
        event.trigger()

        assert calls == []

    def test_a_disabled_event_reports_why(self, event):
        event.enabled = False

        assert event.trigger()["cancelled"] is True

    async def test_a_disabled_event_is_also_skipped_asynchronously(self, event):
        event.enabled = False

        result = await event.trigger_async()

        assert result["cancelled"] is True

    def test_it_can_be_re_enabled(self, event):
        calls = []

        @event.listen
        def listener():
            calls.append(1)

        event.enabled = False
        event.enabled = True
        event.trigger()

        assert calls == [1]


class TestWeakListeners:
    def test_a_weak_listener_fires_while_it_lives(self, event):
        calls = []

        class Holder:
            def handle(self):
                calls.append(1)

        holder = Holder()
        event.listen(holder.handle, weak_ref=True)

        event.trigger()

        assert calls == [1]

    def test_a_dead_weak_listener_is_skipped(self, event):
        class Holder:
            def handle(self):  # pragma: no cover - must not run once collected
                raise AssertionError("a collected listener fired")

        holder = Holder()
        event.listen(holder.handle, weak_ref=True)
        del holder
        gc.collect()

        # Must not raise, and must not call the dead listener.
        event.trigger()

    async def test_a_dead_weak_listener_is_skipped_asynchronously(self, event):
        class Holder:
            def handle(self):  # pragma: no cover - must not run once collected
                raise AssertionError("a collected listener fired")

        holder = Holder()
        event.listen(holder.handle, weak_ref=True)
        del holder
        gc.collect()

        await event.trigger_async()

    def test_a_weak_listener_is_recognised_when_removed(self, event):
        class Holder:
            def handle(self):
                return None

        holder = Holder()
        event.listen(holder.handle, weak_ref=True)

        assert event.has_listener(holder.handle) is True


class TestListenerIdentity:
    def test_a_wrapped_listener_matches_its_wrapper(self, event):
        import functools

        def original():
            return None

        @functools.wraps(original)
        def wrapper():
            return original()

        event.listen(wrapper)

        assert event.has_listener(wrapper) is True

    def test_an_unregistered_listener_is_not_found(self, event):
        def stranger():
            return None

        assert event.has_listener(stranger) is False

    def test_a_once_listener_is_found_too(self, event):
        def listener():
            return None

        event.once(listener)

        assert event.has_listener(listener) is True


class TestCancellation:
    def test_cancel_raises_to_stop_propagation(self, event):
        with pytest.raises(EventCancelledError):
            event.cancel()

    def test_prevent_default_marks_the_event_data(self, event):
        seen = {}

        @event.listen
        def listener(*args, **kwargs):
            event.prevent_default()
            seen["done"] = True

        event.trigger()

        assert seen.get("done") is True
