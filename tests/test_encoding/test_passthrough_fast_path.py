"""Guards on the JSON-native fast path in ``jsonable_encoder``.

The encoder returns ``str``, ``int``, ``float``, ``bool``, ``None``, ``dict``
and ``list`` without walking the full dispatch chain. That shortcut is only
correct while it matches on the *exact* type: loosening any of these checks to
``isinstance`` would hand back an Enum member instead of its value, or a
``defaultdict`` instead of a plain dict. Each test below fails on that change.
"""

from __future__ import annotations

import enum
from collections import Counter, OrderedDict, defaultdict, deque

from sillo.core.encoding import CUSTOM_ENCODERS, jsonable_encoder, register_encoder


class Colour(str, enum.Enum):
    RED = "red"


class Count(int, enum.Enum):
    ONE = 1


class TestSubclassesDoNotTakeTheFastPath:
    def test_str_enum_encodes_to_its_value(self):
        assert jsonable_encoder(Colour.RED) == "red"
        assert type(jsonable_encoder(Colour.RED)) is str

    def test_int_enum_encodes_to_its_value(self):
        assert jsonable_encoder(Count.ONE) == 1
        assert type(jsonable_encoder(Count.ONE)) is int

    def test_enum_nested_in_a_dict_and_list(self):
        assert jsonable_encoder({"a": [Colour.RED]}) == {"a": ["red"]}

    def test_enum_used_as_a_dict_key(self):
        assert jsonable_encoder({Colour.RED: 1}) == {"red": 1}

    def test_dict_subclasses_become_plain_dicts(self):
        for value in (
            defaultdict(int, {"k": 1}),
            OrderedDict(k=1),
            Counter(k=1),
        ):
            encoded = jsonable_encoder(value)
            assert encoded == {"k": 1}
            assert type(encoded) is dict

    def test_sequence_types_become_plain_lists(self):
        for value in ((1, 2), deque([1, 2])):
            encoded = jsonable_encoder(value)
            assert encoded == [1, 2]
            assert type(encoded) is list

    def test_bool_stays_a_bool(self):
        assert jsonable_encoder(True) is True
        assert jsonable_encoder({"a": False}) == {"a": False}


class TestOptionsDisableTheFastPath:
    def test_exclude_none_still_drops_keys(self):
        assert jsonable_encoder({"a": 1, "b": None}, exclude_none=True) == {"a": 1}

    def test_include_still_narrows(self):
        assert jsonable_encoder({"a": 1, "b": 2}, include={"a"}) == {"a": 1}

    def test_exclude_still_removes(self):
        assert jsonable_encoder({"a": 1, "b": 2}, exclude={"b"}) == {"a": 1}


class TestCustomEncodersDisableTheFastPath:
    def test_encoder_registered_on_a_native_type_is_applied(self):
        register_encoder(str, lambda s: s.upper())
        try:
            assert jsonable_encoder({"k": "v"}) == {"K": "V"}
        finally:
            CUSTOM_ENCODERS.pop(str, None)

    def test_per_call_encoder_on_a_native_type_is_applied(self):
        encoded = jsonable_encoder([1, 2], custom_encoder={int: lambda i: i * 10})
        assert encoded == [10, 20]


class TestEncodingIsIdempotent:
    """The router encodes once and hands the result straight to ``JSONResponse``.

    That is only safe while a second pass would have been a no-op.
    """

    def test_re_encoding_an_encoded_payload_changes_nothing(self):
        payload = {
            "a": [1, "b", True, None, 2.5],
            "c": {"d": Colour.RED, "e": (1, 2)},
        }
        once = jsonable_encoder(payload)
        assert jsonable_encoder(once) == once
