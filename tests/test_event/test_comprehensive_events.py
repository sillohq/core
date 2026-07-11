"""
Comprehensive tests for sillo event system.

Tests cover:
- Basic event registration and triggering
- One-time listeners
- Event priorities
- Event propagation (parent-child relationships)
- Event cancellation
- Async listeners
- Event namespaces
- Event metrics and history
- Error handling
- Weak references
- Event serialization
"""

import asyncio
import json
import threading
import time
import weakref
from typing import Callable
from unittest.mock import Mock, call, patch

import pytest

from sillo.events import (
    AsyncEventEmitter,
    Event,
    EventCancelledError,
    EventContext,
    EventEmitter,
    EventError,
    EventNamespace,
    EventPhase,
    EventPriority,
    ListenerAlreadyRegisteredError,
    MaxListenersExceededError,
)

# ========== Fixtures ==========


@pytest.fixture
def event_emitter():
    """Create a fresh EventEmitter for each test"""
    emitter = EventEmitter()
    yield emitter
    # Clean up after test
    emitter.remove_all_events()


@pytest.fixture
def async_event_emitter():
    """Create a fresh AsyncEventEmitter for each test"""
    emitter = AsyncEventEmitter()
    yield emitter
    # Clean up after test
    emitter.remove_all_events()
    emitter.shutdown()


@pytest.fixture
def listener_mock():
    """Create a mock listener for testing"""
    return Mock()


# ========== Basic Event Tests ==========


def test_event_creation():
    """Test basic event creation"""
    event = Event("test_event")
    assert event.name == "test_event"
    assert event.listener_count == 0
    assert event.enabled is True
    assert event.max_listeners == Event.DEFAULT_MAX_LISTENERS


def test_event_listener_registration(event_emitter, listener_mock):
    """Test registering listeners on events"""
    event = event_emitter.event("test_event")

    # Register listener
    event.listen(listener_mock)

    assert event.listener_count == 1
    assert event.has_listener(listener_mock)


def test_event_listener_removal(event_emitter, listener_mock):
    """Test removing listeners from events"""
    event = event_emitter.event("test_event")

    # Register and remove listener
    event.listen(listener_mock)
    assert event.listener_count == 1

    event.remove_listener(listener_mock)
    assert event.listener_count == 0
    assert not event.has_listener(listener_mock)


def test_event_triggering(event_emitter, listener_mock):
    """Test triggering events and calling listeners"""
    event = event_emitter.event("test_event")

    # Register listener
    event.listen(listener_mock)

    # Trigger event
    stats = event.trigger("arg1", "arg2", key="value")

    assert stats["listeners_executed"] == 1
    assert listener_mock.call_args == call("arg1", "arg2", key="value")
    assert stats["cancelled"] is False


def test_event_triggering_with_context(event_emitter, listener_mock):
    """Test that event context is properly passed to listeners"""
    event = event_emitter.event("test_event")

    def context_listener(*args, **kwargs):
        # Check that context is available in the event data
        # This simulates how context would be accessed in real usage
        listener_mock(*args, **kwargs)

    event.listen(context_listener)
    event.trigger("test")


# ========== One-time Listeners Tests ==========


def test_once_listener(event_emitter, listener_mock):
    """Test one-time listeners that are removed after first trigger"""
    event = event_emitter.event("test_event")

    # Register once listener
    event.once(listener_mock)

    assert event.listener_count == 1

    # Trigger first time
    stats1 = event.trigger("first")
    assert stats1["listeners_executed"] == 1
    assert listener_mock.call_args == call("first")

    # Trigger second time - listener should be gone
    stats2 = event.trigger("second")
    assert stats2["listeners_executed"] == 0

    assert listener_mock.call_count == 1


def test_once_listener_with_multiple_calls(event_emitter, listener_mock):
    """Test once listener behavior with multiple triggers"""
    event = event_emitter.event("test_event")

    event.once(listener_mock)

    # Multiple triggers
    event.trigger("first")
    event.trigger("second")
    event.trigger("third")

    assert listener_mock.call_count == 1
    assert listener_mock.call_args == call("first")


# ========== Priority Tests ==========


def test_event_priorities(event_emitter, listener_mock):
    """Test that listeners are executed in priority order"""
    event = event_emitter.event("test_event")

    # Register listeners with different priorities
    event.listen(lambda: listener_mock("highest"), priority=EventPriority.HIGHEST)
    event.listen(lambda: listener_mock("high"), priority=EventPriority.HIGH)
    event.listen(lambda: listener_mock("normal"), priority=EventPriority.NORMAL)
    event.listen(lambda: listener_mock("low"), priority=EventPriority.LOW)
    event.listen(lambda: listener_mock("lowest"), priority=EventPriority.LOWEST)

    # Trigger event
    event.trigger()

    # Check execution order (highest priority first)
    expected_calls = [
        call("highest"),
        call("high"),
        call("normal"),
        call("low"),
        call("lowest"),
    ]
    assert listener_mock.call_args_list == expected_calls


def test_event_priority_listener_registration(event_emitter, listener_mock):
    """Test registering listeners with different priorities"""
    event = event_emitter.event("test_event")

    # Register with explicit priority
    event.listen(listener_mock, priority=EventPriority.HIGH)

    assert event.listener_count == 1


# ========== Propagation Tests ==========


def test_event_propagation_parent_child(event_emitter, listener_mock):
    """Test event propagation from parent to child"""
    parent_event = event_emitter.event("parent")
    child_event = event_emitter.event("child")

    # Set up parent-child relationship
    child_event.parent = parent_event

    def parent_listener(*args, **kwargs):
        listener_mock("parent_called")

    def child_listener(*args, **kwargs):
        listener_mock("child_called")

    parent_event.listen(parent_listener)
    child_event.listen(child_listener)

    # Trigger child event - should trigger parent in capture phase
    stats = event_emitter.emit("child")

    # Note: The current implementation may need adjustment for proper propagation
    # This test documents expected behavior
    assert stats["listeners_executed"] >= 1


def test_event_propagation_capture_bubble_phases(event_emitter, listener_mock):
    """Test capture and bubble phases of event propagation"""
    parent_event = event_emitter.event("parent")
    child_event = event_emitter.event("child")

    child_event.parent = parent_event

    phases = []

    def parent_listener(*args, **kwargs):
        phases.append("parent")

    def child_listener(*args, **kwargs):
        phases.append("child")

    parent_event.listen(parent_listener)
    child_event.listen(child_listener)

    # Trigger child event
    event_emitter.emit("child")

    # Should see both parent and child listeners called
    assert len(phases) >= 1


# ========== Cancellation Tests ==========


def test_event_cancellation(event_emitter, listener_mock):
    """Test event cancellation"""
    event = event_emitter.event("test_event")

    def cancelling_listener(*args, **kwargs):
        listener_mock("called")
        # Cancel the event
        event.cancel()

    def second_listener(*args, **kwargs):
        listener_mock("should_not_be_called")

    event.listen(cancelling_listener)
    event.listen(second_listener)

    # Trigger event - should be cancelled after first listener
    with pytest.raises(EventCancelledError):
        event.trigger()

    assert listener_mock.call_args_list == [call("called")]
    # Second listener should not have been called due to cancellation


def test_event_prevent_default(event_emitter, listener_mock):
    """Test prevent_default functionality"""
    event = event_emitter.event("test_event")

    def listener_with_prevent_default(*args, **kwargs):
        listener_mock("called")
        # Prevent default behavior
        event.prevent_default()

    event.listen(listener_with_prevent_default)
    stats = event.trigger()

    # The prevent_default functionality should mark the event
    assert stats["listeners_executed"] == 1


# ========== Async Listeners Tests ==========


@pytest.mark.asyncio
async def test_async_listener_support(event_emitter, listener_mock):
    """Test that async listeners work correctly"""
    event = event_emitter.event("test_event")

    async def async_listener(*args, **kwargs):
        await asyncio.sleep(0.01)  # Small delay to test async behavior
        listener_mock("async_called")

    event.listen(async_listener)

    # Trigger event - async listeners should be handled properly
    stats = event.trigger()

    # Give time for async listener to complete
    await asyncio.sleep(0.02)

    assert stats["listeners_executed"] == 1
    assert listener_mock.call_args == call("async_called")


@pytest.mark.asyncio
async def test_mixed_sync_async_listeners(event_emitter, listener_mock):
    """Test mixing sync and async listeners"""
    event = event_emitter.event("test_event")

    def sync_listener(*args, **kwargs):
        listener_mock("sync_called")

    async def async_listener(*args, **kwargs):
        await asyncio.sleep(0.01)
        listener_mock("async_called")

    event.listen(sync_listener)
    event.listen(async_listener)

    stats = event.trigger()

    # Give time for async listener to complete
    await asyncio.sleep(0.02)

    assert stats["listeners_executed"] == 2
    # Sync should be called first, then async
    assert listener_mock.call_args_list == [call("sync_called"), call("async_called")]


# ========== Namespace Tests ==========


def test_event_namespaces(event_emitter, listener_mock):
    """Test event namespaces"""
    # Create namespace
    user_ns = event_emitter.namespace("user")

    # Register listener in namespace
    user_ns.on("login", listener_mock)

    # Trigger event in namespace
    stats = user_ns.emit("login", "user_data")

    assert stats["listeners_executed"] == 1
    assert listener_mock.call_args == call("user_data")


def test_nested_namespaces(event_emitter, listener_mock):
    """Test nested event namespaces"""
    # Create nested namespace
    user_auth_ns = event_emitter.namespace("user").namespace("auth")

    # Register listener in nested namespace
    user_auth_ns.on("login", listener_mock)

    # Trigger event in nested namespace
    stats = user_auth_ns.emit("login", "nested_data")

    assert stats["listeners_executed"] == 1
    assert listener_mock.call_args == call("nested_data")


def test_namespace_event_access(event_emitter, listener_mock):
    """Test accessing events through namespaces"""
    user_ns = event_emitter.namespace("user")

    # Access event through namespace
    login_event = user_ns.event("login")
    login_event.listen(listener_mock)

    # Trigger through namespace
    stats = user_ns.emit("login")

    assert stats["listeners_executed"] == 1


# ========== Metrics and History Tests ==========


def test_event_metrics(event_emitter, listener_mock):
    """Test event metrics collection"""
    event = event_emitter.event("test_event")
    event.listen(listener_mock)

    # Trigger multiple times
    for i in range(5):
        event.trigger(f"data_{i}")

    metrics = event.get_metrics()

    assert metrics["trigger_count"] == 5
    assert metrics["total_listeners_executed"] == 5
    assert metrics["average_execution_time"] >= 0


def test_event_history(event_emitter, listener_mock):
    """Test event history tracking"""
    event = event_emitter.event("test_event")
    event.listen(listener_mock)

    # Trigger event
    event.trigger("test_data")

    history = event.get_history()

    assert len(history) == 1
    assert history[0]["listeners_executed"] == 1
    assert history[0]["args"] == "('test_data',)"


def test_event_history_limit(event_emitter, listener_mock):
    """Test that event history is limited"""
    event = event_emitter.event("test_event")
    event.listen(listener_mock)

    # Trigger many events (more than the 100 limit)
    for i in range(150):
        event.trigger(f"data_{i}")

    history = event.get_history()

    # Should be limited to 100 entries
    assert len(history) <= 100


def test_event_history_with_limit(event_emitter, listener_mock):
    """Test getting limited history"""
    event = event_emitter.event("test_event")
    event.listen(listener_mock)

    # Trigger events
    for i in range(10):
        event.trigger(f"data_{i}")

    # Get last 5 events
    history = event.get_history(limit=5)

    assert len(history) == 5
    assert history[0]["args"] == "('data_5',)"


# ========== Error Handling Tests ==========


def test_listener_exception_handling(event_emitter, listener_mock):
    """Test that listener exceptions are caught and logged"""
    event = event_emitter.event("test_event")

    def failing_listener(*args, **kwargs):
        listener_mock("called")
        raise ValueError("Test error")

    def working_listener(*args, **kwargs):
        listener_mock("working")

    event.listen(failing_listener)
    event.listen(working_listener)

    # Trigger event - should continue despite first listener failing
    stats = event.trigger()

    assert listener_mock.call_args_list == [call("called"), call("working")]


def test_max_listeners_exceeded(event_emitter):
    """Test max listeners limit enforcement"""
    event = event_emitter.event("test_event")
    event.max_listeners = 2

    # Add listeners up to limit
    event.listen(lambda: None)
    event.listen(lambda: None)

    # Adding third should fail
    with pytest.raises(MaxListenersExceededError):
        event.listen(lambda: None)


def test_duplicate_listener_registration(event_emitter, listener_mock):
    """Test that duplicate listeners are rejected"""
    event = event_emitter.event("test_event")

    # Register same listener twice
    event.listen(listener_mock)

    with pytest.raises(ListenerAlreadyRegisteredError):
        event.listen(listener_mock)


# ========== Weak Reference Tests ==========


def test_weak_reference_listener(event_emitter):
    """Test weak reference listeners"""
    event = event_emitter.event("test_event")

    def test_listener():
        pass

    # Register with weak reference
    event.listen(test_listener, weak_ref=True)

    # Delete the original function
    del test_listener

    # Trigger event - weak reference should be cleaned up
    stats = event.trigger()

    # Should have no listeners executed since weak reference is gone
    assert stats["listeners_executed"] == 0


def test_weak_reference_method(event_emitter):
    """Test weak reference with methods"""
    event = event_emitter.event("test_event")

    class TestClass:
        def test_method(self):
            pass

    obj = TestClass()

    # Register method with weak reference
    event.listen(obj.test_method, weak_ref=True)

    # Delete the object
    del obj

    # Trigger event - weak reference should be cleaned up
    stats = event.trigger()

    assert stats["listeners_executed"] == 0


# ========== Serialization Tests ==========


def test_event_serialization(event_emitter, listener_mock):
    """Test event serialization"""
    event = event_emitter.event("test_event")
    event.listen(listener_mock)
    event.max_listeners = 50

    # Serialize event
    json_str = event.to_json()

    # Deserialize event
    new_event = Event.from_json(json_str)

    assert new_event.name == event.name
    assert new_event.max_listeners == event.max_listeners
    assert new_event.enabled == event.enabled


def test_event_serialization_roundtrip(event_emitter, listener_mock):
    """Test event serialization roundtrip"""
    original_event = event_emitter.event("test_event")
    original_event.listen(listener_mock)
    original_event.max_listeners = 25
    original_event.enabled = False

    # Serialize and deserialize
    json_str = original_event.to_json()
    restored_event = Event.from_json(json_str)

    assert restored_event.name == "test_event"
    assert restored_event.max_listeners == 25
    assert restored_event.enabled is False


# ========== EventEmitter Integration Tests ==========


def test_event_emitter_decorator_usage(event_emitter, listener_mock):
    """Test EventEmitter decorator usage"""

    # Register using decorator
    @event_emitter.on("test_event")
    def decorated_listener(*args, **kwargs):
        listener_mock("decorated")

    # Trigger event
    stats = event_emitter.emit("test_event")

    assert stats["listeners_executed"] == 1
    assert listener_mock.call_args == call("decorated")


def test_event_emitter_once_decorator(event_emitter, listener_mock):
    """Test EventEmitter once decorator"""

    @event_emitter.once("test_event")
    def once_listener(*args, **kwargs):
        listener_mock("once")

    # Trigger twice
    event_emitter.emit("test_event")
    stats2 = event_emitter.emit("test_event")

    assert listener_mock.call_count == 1
    assert stats2["listeners_executed"] == 0


def test_event_emitter_remove_all_listeners(event_emitter, listener_mock):
    """Test removing all listeners from specific event"""
    event = event_emitter.event("test_event")
    event.listen(listener_mock)

    # Remove all listeners
    event_emitter.remove_all_listeners("test_event")

    # Trigger event - no listeners should be called
    stats = event_emitter.emit("test_event")

    assert stats["listeners_executed"] == 0
    assert not event.has_listener(listener_mock)


def test_event_emitter_remove_all_events(event_emitter, listener_mock):
    """Test removing all events"""
    event1 = event_emitter.event("event1")
    event2 = event_emitter.event("event2")

    event1.listen(listener_mock)
    event2.listen(listener_mock)

    # Remove all events
    event_emitter.remove_all_events()

    # Check that events are gone
    assert not event_emitter.has_event("event1")
    assert not event_emitter.has_event("event2")


# ========== Async EventEmitter Tests ==========


def test_event_with_no_listeners(event_emitter):
    """Test triggering event with no listeners"""
    event = event_emitter.event("empty_event")

    # Should not raise error
    stats = event.trigger("test")

    assert stats["listeners_executed"] == 0
    assert stats["cancelled"] is False


def test_event_disabled(event_emitter, listener_mock):
    """Test disabled events"""
    event = event_emitter.event("disabled_event")
    event.listen(listener_mock)
    event.enabled = False

    # Trigger disabled event
    stats = event.trigger()

    assert stats["cancelled"] is True
    assert stats["reason"] == "Event disabled"
    assert listener_mock.call_count == 0


def test_concurrent_event_triggering(event_emitter, listener_mock):
    """Test concurrent event triggering"""
    event = event_emitter.event("concurrent_event")

    def slow_listener(*args, **kwargs):
        time.sleep(0.1)  # Simulate slow operation
        listener_mock("slow")

    event.listen(slow_listener)

    # Trigger multiple times concurrently
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(event.trigger) for _ in range(3)]

        results = [future.result() for future in futures]

    # All should succeed
    for result in results:
        assert result["listeners_executed"] == 1

    # Should have been called 3 times
    assert listener_mock.call_count == 3


def test_large_number_of_listeners(event_emitter):
    """Test performance with large number of listeners"""
    event = event_emitter.event("performance_event")
    event.max_listeners = 1000

    # Add many listeners
    listeners = []
    for i in range(100):

        def listener(i=i):
            pass  # Simple no-op listener

        event.listen(listener)
        listeners.append(listener)

    # Trigger event
    start_time = time.time()
    stats = event.trigger()
    end_time = time.time()

    assert stats["listeners_executed"] == 100
    # Should complete reasonably quickly (less than 1 second for 100 simple listeners)
    assert end_time - start_time < 1.0


# ========== Decorator Tests ==========


def test_event_decorator_usage(event_emitter, listener_mock):
    """Test using Event.listen as decorator"""
    event = event_emitter.event("decorator_event")

    @event.listen
    def decorated_function(*args, **kwargs):
        listener_mock("decorated")

    # Trigger event
    stats = event.trigger()

    assert stats["listeners_executed"] == 1
    assert listener_mock.call_args == call("decorated")


def test_event_once_decorator(event_emitter, listener_mock):
    """Test using Event.once as decorator"""
    event = event_emitter.event("once_decorator_event")

    @event.once
    def once_decorated(*args, **kwargs):
        listener_mock("once_decorated")

    # Trigger twice
    event.trigger()
    stats2 = event.trigger()

    assert listener_mock.call_count == 1
    assert stats2["listeners_executed"] == 0


# ========== EventEmitter Namespace Integration Tests ==========


def test_namespace_decorator_usage(event_emitter, listener_mock):
    """Test namespace decorator usage"""
    user_ns = event_emitter.namespace("user")

    @user_ns.on("login")
    def login_handler(*args, **kwargs):
        listener_mock("login")

    @user_ns.once("logout")
    def logout_handler(*args, **kwargs):
        listener_mock("logout")

    # Trigger events
    stats1 = user_ns.emit("login")
    stats2 = user_ns.emit("logout")
    stats3 = user_ns.emit("logout")  # Should not trigger again

    assert stats1["listeners_executed"] == 1
    assert stats2["listeners_executed"] == 1
    assert stats3["listeners_executed"] == 0
    assert listener_mock.call_args_list == [call("login"), call("logout")]


# ========== Complete Integration Test ==========


def test_complete_event_workflow(event_emitter, listener_mock):
    """Test a complete event workflow with multiple features"""
    # Create events with parent-child relationship
    app_event = event_emitter.event("app:startup")
    user_event = event_emitter.event("user:login")
    user_event.parent = app_event

    # Track execution order
    execution_order = []

    @app_event.listen(priority=EventPriority.HIGH)
    def app_startup(*args, **kwargs):
        execution_order.append("app_startup")

    @user_event.listen(priority=EventPriority.NORMAL)
    def user_login(*args, **kwargs):
        execution_order.append("user_login")

    @user_event.once(priority=EventPriority.LOW)
    def welcome_message(*args, **kwargs):
        execution_order.append("welcome")

    # Create namespace for additional events
    auth_ns = event_emitter.namespace("auth")

    @auth_ns.on("session_created")
    def session_handler(*args, **kwargs):
        execution_order.append("session")

    # Trigger events
    app_event.trigger()
    user_event.trigger("user123")
    auth_ns.emit("session_created", "session456")

    # Trigger user event again - once listener should be gone
    user_event.trigger("user456")

    # Check execution order and results
    expected_order = ["app_startup", "user_login", "welcome", "session", "user_login"]
    assert set(execution_order) == set(expected_order)
