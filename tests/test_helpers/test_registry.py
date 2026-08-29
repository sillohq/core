"""
InstanceRegistry — the primitive mail and storage share for "the instance
setup_x built, reachable from anywhere".

Deliberately no request, no task, no ASGI app anywhere in this file: the
property under test is that a plain register/current pair works the same way
regardless of what is calling it.
"""

from __future__ import annotations

import pytest

from sillo.helpers.registry import InstanceRegistry, NotConfiguredError


@pytest.fixture
def registry() -> InstanceRegistry[str]:
    return InstanceRegistry("thing")


def _current(registry: InstanceRegistry[str]) -> str:
    return registry.current(setup="setup_thing", example="setup_thing(app)")


def test_current_raises_before_anything_is_registered(
    registry: InstanceRegistry[str],
) -> None:
    with pytest.raises(NotConfiguredError):
        _current(registry)


def test_error_names_the_thing_and_the_setup_call(
    registry: InstanceRegistry[str],
) -> None:
    with pytest.raises(NotConfiguredError) as excinfo:
        _current(registry)

    message = str(excinfo.value)
    assert "thing" in message
    assert "setup_thing" in message
    assert "setup_thing(app)" in message


def test_register_makes_current_available(registry: InstanceRegistry[str]) -> None:
    registry.register("instance-a")
    assert _current(registry) == "instance-a"


def test_registering_again_replaces_the_previous_instance(
    registry: InstanceRegistry[str],
) -> None:
    registry.register("instance-a")
    registry.register("instance-b")
    assert _current(registry) == "instance-b"


def test_current_is_reachable_with_no_request_or_task_in_play(
    registry: InstanceRegistry[str],
) -> None:
    """The whole point: register once, read back from a plain function call.

    No fixture here builds an app, a request, or a task — reading the
    instance back is exactly as available as calling any other function.
    """
    registry.register("instance-a")

    def deep_in_a_queue_job() -> str:
        return _current(registry)

    assert deep_in_a_queue_job() == "instance-a"


def test_two_registries_with_the_same_label_do_not_share_state() -> None:
    first = InstanceRegistry("duplicate-label")
    second = InstanceRegistry("duplicate-label")

    first.register("only-on-first")

    with pytest.raises(NotConfiguredError):
        _current(second)
