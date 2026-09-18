"""Coverage for sillo.objects.common: Secret and State, neither of which
had direct tests."""

from __future__ import annotations

import pytest

from sillo.objects.common import Address, Secret, State


class TestAddress:
    def test_is_a_host_port_pair(self):
        address = Address(host="127.0.0.1", port=8000)
        assert address.host == "127.0.0.1"
        assert address.port == 8000


class TestSecret:
    def test_str_reveals_the_value(self):
        assert str(Secret("s3cret")) == "s3cret"

    def test_repr_masks_the_value(self):
        assert repr(Secret("s3cret")) == "Secret('**********')"
        assert "s3cret" not in repr(Secret("s3cret"))

    def test_truthy_when_non_empty(self):
        assert bool(Secret("s3cret")) is True

    def test_falsy_when_empty(self):
        assert bool(Secret("")) is False


class TestState:
    def test_defaults_to_an_empty_state(self):
        state = State()
        assert state.anything is None

    def test_can_be_seeded_with_an_initial_dict(self):
        state = State({"user_id": 1})
        assert state.user_id == 1

    def test_attribute_assignment_is_stored(self):
        state = State()
        state.user_id = 42
        assert state.user_id == 42

    def test_missing_attribute_reads_as_none(self):
        state = State()
        assert state.does_not_exist is None

    def test_deleting_an_attribute_removes_it(self):
        state = State()
        state.user_id = 42
        del state.user_id
        assert state.user_id is None

    def test_deleting_a_missing_attribute_raises(self):
        state = State()
        with pytest.raises(KeyError):
            del state.does_not_exist

    def test_str_shows_the_underlying_dict(self):
        state = State({"user_id": 1})
        assert str(state) == "<State data={'user_id': 1}>"

    def test_update_merges_multiple_values(self):
        state = State({"a": 1})
        state.update({"a": 2, "b": 3})
        assert state.a == 2
        assert state.b == 3
