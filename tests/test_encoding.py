from __future__ import annotations

import dataclasses
import datetime
import decimal
import enum
import ipaddress
import re
import typing
import uuid
from collections import deque
from pathlib import Path, PurePath, PurePosixPath
from types import GeneratorType

import pytest
from pydantic import BaseModel, Field
from pydantic.networks import AnyUrl, NameEmail
from pydantic.types import SecretBytes, SecretStr
from pydantic_core import PydanticUndefined, PydanticUndefinedType

from sillo.encoding import (
    ENCODERS_BY_TYPE,
    decimal_encoder,
    encoders_by_class_tuples,
    generate_encoders_by_class_tuples,
    isoformat,
    jsonable_encoder,
)

# ---------------------------------------------------------------------------
# isoformat helper
# ---------------------------------------------------------------------------


def test_isoformat_date():
    assert isoformat(datetime.date(2024, 7, 4)) == "2024-07-04"


def test_isoformat_datetime():
    assert isoformat(datetime.datetime(2024, 7, 4, 15, 30, 0)) == "2024-07-04T15:30:00"


def test_isoformat_time():
    assert isoformat(datetime.time(15, 30, 0)) == "15:30:00"


# ---------------------------------------------------------------------------
# decimal_encoder helper
# ---------------------------------------------------------------------------


def test_decimal_encoder_int():
    # exponent >= 0  -> int
    assert decimal_encoder(decimal.Decimal("42")) == 42
    assert isinstance(decimal_encoder(decimal.Decimal("42")), int)


def test_decimal_encoder_float():
    # exponent < 0  -> float
    assert decimal_encoder(decimal.Decimal("3.14")) == 3.14
    assert isinstance(decimal_encoder(decimal.Decimal("3.14")), float)


# ---------------------------------------------------------------------------
# generate_encoders_by_class_tuples
# ---------------------------------------------------------------------------


def test_generate_encoders_by_class_tuples():
    mapping = {int: str, float: str}
    result = generate_encoders_by_class_tuples(mapping)
    # str encoder should have (int, float) classes_tuple
    assert result[str] == (int, float)


# ---------------------------------------------------------------------------
# ENCODERS_BY_TYPE structure
# ---------------------------------------------------------------------------


def test_encoders_by_type_has_expected_keys():
    expected = {
        bytes,
        datetime.date,
        datetime.datetime,
        datetime.time,
        datetime.timedelta,
        decimal.Decimal,
        enum.Enum,
        frozenset,
        deque,
        GeneratorType,
        ipaddress.IPv4Address,
        ipaddress.IPv4Interface,
        ipaddress.IPv4Network,
        ipaddress.IPv6Address,
        ipaddress.IPv6Interface,
        ipaddress.IPv6Network,
        NameEmail,
        Path,
        type(re.compile("")),
        SecretBytes,
        SecretStr,
        set,
        uuid.UUID,
        AnyUrl,
    }
    assert set(ENCODERS_BY_TYPE) == expected


def test_encoders_by_class_tuples_has_subclass_fallbacks():
    # PurePath is handled via isinstance check before class tuples lookup
    # Path is in ENCODERS_BY_TYPE directly
    assert Path in ENCODERS_BY_TYPE


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def test_none():
    assert jsonable_encoder(None) is None


def test_int():
    assert jsonable_encoder(42) == 42
    assert jsonable_encoder(-1) == -1
    assert jsonable_encoder(0) == 0


def test_float():
    assert jsonable_encoder(3.14) == 3.14
    assert jsonable_encoder(float("inf")) == float("inf")
    assert jsonable_encoder(float("nan")) is not None


def test_str():
    assert jsonable_encoder("hello") == "hello"
    assert jsonable_encoder("") == ""


def test_bool():
    assert jsonable_encoder(True) is True
    assert jsonable_encoder(False) is False


def test_bytes():
    assert jsonable_encoder(b"hello") == "hello"
    assert jsonable_encoder(b"") == ""


# ---------------------------------------------------------------------------
# Date / time
# ---------------------------------------------------------------------------


def test_date():
    d = datetime.date(2024, 1, 15)
    assert jsonable_encoder(d) == "2024-01-15"


def test_datetime():
    dt = datetime.datetime(2024, 1, 15, 10, 30, 0, 123456)
    assert jsonable_encoder(dt) == "2024-01-15T10:30:00.123456"


def test_time():
    t = datetime.time(10, 30, 0)
    assert jsonable_encoder(t) == "10:30:00"


def test_timedelta():
    td = datetime.timedelta(hours=1, minutes=30, seconds=15)
    assert jsonable_encoder(td) == 5415.0


# ---------------------------------------------------------------------------
# UUID / Decimal
# ---------------------------------------------------------------------------


def test_uuid():
    u = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert jsonable_encoder(u) == "12345678-1234-5678-1234-567812345678"


def test_decimal_int():
    assert jsonable_encoder(decimal.Decimal("100")) == 100


def test_decimal_float():
    assert jsonable_encoder(decimal.Decimal("19.99")) == 19.99


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class Color(enum.Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class IntEnum(enum.IntEnum):
    ONE = 1
    TWO = 2


def test_enum():
    assert jsonable_encoder(Color.RED) == "red"
    assert jsonable_encoder(IntEnum.ONE) == 1


# ---------------------------------------------------------------------------
# Path / PurePath
# ---------------------------------------------------------------------------


def test_path():
    assert jsonable_encoder(Path("/a/b/c")) == "/a/b/c"


def test_pure_path_subclass():
    assert jsonable_encoder(PurePosixPath("/x/y")) == "/x/y"


def test_pure_path():
    assert jsonable_encoder(PurePath("foo/bar")) == "foo/bar"


# ---------------------------------------------------------------------------
# Pattern (re.Pattern)
# ---------------------------------------------------------------------------


def test_pattern():
    p = re.compile(r"\d+\.\d+")
    # re.Pattern returns its raw pattern string
    assert jsonable_encoder(p) == r"\d+\.\d+"


def test_pattern_no_slash():
    p = re.compile("hello")
    assert jsonable_encoder(p) == "hello"


# ---------------------------------------------------------------------------
# Pydantic BaseModel
# ---------------------------------------------------------------------------


class SimpleModel(BaseModel):
    name: str
    price: float


class NestedModel(BaseModel):
    item: SimpleModel
    count: int


class ModelWithExclude(BaseModel):
    a: str = "a"
    b: str = "b"
    c: str = "c"


class ModelWithDefaults(BaseModel):
    x: int = 0
    y: int = 42


def test_base_model():
    m = SimpleModel(name="widget", price=9.99)
    assert jsonable_encoder(m) == {"name": "widget", "price": 9.99}


def test_base_model_with_datetime():
    m = SimpleModel(name="test", price=1.0)
    result = jsonable_encoder(m)
    assert result["name"] == "test"


def test_nested_pydantic():
    m = NestedModel(item=SimpleModel(name="inner", price=5.0), count=3)
    assert jsonable_encoder(m) == {"item": {"name": "inner", "price": 5.0}, "count": 3}


def test_model_with_exclude():
    m = ModelWithExclude(a="keep", b="hidden", c="keep")
    result = jsonable_encoder(m, exclude={"b"})
    assert result == {"a": "keep", "c": "keep"}


def test_model_with_include():
    m = ModelWithExclude(a="x", b="y", c="z")
    result = jsonable_encoder(m, include={"a"})
    assert result == {"a": "x"}


def test_model_exclude_none():
    class M(BaseModel):
        a: str | None = "x"
        b: str | None = None

    m = M()
    result = jsonable_encoder(m, exclude_none=True)
    assert "b" not in result
    assert result["a"] == "x"


def test_model_exclude_defaults():
    m = ModelWithDefaults()
    result = jsonable_encoder(m, exclude_defaults=True)
    # both x and y have defaults, so both could be excluded
    assert result == {}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Point:
    x: int
    y: int


@dataclasses.dataclass
class Box:
    top_left: Point
    bottom_right: Point


def test_dataclass():
    assert jsonable_encoder(Point(10, 20)) == {"x": 10, "y": 20}


def test_nested_dataclass():
    b = Box(top_left=Point(0, 0), bottom_right=Point(100, 200))
    assert jsonable_encoder(b) == {
        "top_left": {"x": 0, "y": 0},
        "bottom_right": {"x": 100, "y": 200},
    }


def test_dataclass_with_exclude():
    @dataclasses.dataclass
    class Three:
        a: str = "a"
        b: str = "b"
        c: str = "c"

    result = jsonable_encoder(Three(), exclude={"b"})
    assert result == {"a": "a", "c": "c"}


def test_dataclass_with_include():
    @dataclasses.dataclass
    class Two:
        a: str = "a"
        b: str = "b"

    result = jsonable_encoder(Two(), include={"a"})
    assert result == {"a": "a"}


# ---------------------------------------------------------------------------
# Dict
# ---------------------------------------------------------------------------


def test_dict_flat():
    assert jsonable_encoder({"a": 1, "b": "two"}) == {"a": 1, "b": "two"}


def test_dict_nested():
    assert jsonable_encoder({"outer": {"inner": [1, 2, 3]}}) == {
        "outer": {"inner": [1, 2, 3]}
    }


def test_dict_with_exclude():
    d = {"x": 1, "y": 2, "z": 3}
    assert jsonable_encoder(d, exclude={"y"}) == {"x": 1, "z": 3}


def test_dict_with_include():
    d = {"a": 10, "b": 20, "c": 30}
    assert jsonable_encoder(d, include={"a", "b"}) == {"a": 10, "b": 20}


def test_dict_exclude_none():
    d = {"a": 1, "b": None, "c": 3}
    result = jsonable_encoder(d, exclude_none=True)
    assert result == {"a": 1, "c": 3}


def test_dict_exclude_none_false():
    d = {"a": None}
    result = jsonable_encoder(d, exclude_none=False)
    assert result == {"a": None}


def test_dict_empty():
    assert jsonable_encoder({}) == {}


def test_dict_mixed_keys():
    # int keys get encoded as strings via json.dumps, but our encoder keeps them
    assert jsonable_encoder({1: "one", 2: "two"}) == {1: "one", 2: "two"}


# ---------------------------------------------------------------------------
# Lists / Sets / Tuples / Frozenset / Deque / Generator
# ---------------------------------------------------------------------------


def test_list():
    assert jsonable_encoder([1, "two", 3.0]) == [1, "two", 3.0]


def test_list_nested():
    assert jsonable_encoder([[1, 2], [3, {"a": 4}]]) == [[1, 2], [3, {"a": 4}]]


def test_list_empty():
    assert jsonable_encoder([]) == []


def test_set():
    result = jsonable_encoder({3, 1, 2})
    assert sorted(result) == [1, 2, 3]


def test_frozenset():
    result = jsonable_encoder(frozenset([1, 2, 3]))
    assert sorted(result) == [1, 2, 3]


def test_tuple():
    result = jsonable_encoder((1, "a", 3.14))
    assert result == [1, "a", 3.14]


def test_deque():
    dq = deque([1, 2, 3])
    assert jsonable_encoder(dq) == [1, 2, 3]


def test_generator():
    gen = (x * 2 for x in range(3))
    assert jsonable_encoder(gen) == [0, 2, 4]


def test_nested_collection():
    assert jsonable_encoder({"items": [{"id": 1}, {"id": 2}]}) == {
        "items": [{"id": 1}, {"id": 2}]
    }


# ---------------------------------------------------------------------------
# Custom encoder
# ---------------------------------------------------------------------------


def test_custom_encoder_exact_type():
    class Special:
        def __init__(self, val):
            self.val = val

    result = jsonable_encoder(Special(42), custom_encoder={Special: lambda o: o.val})
    assert result == 42


def test_custom_encoder_subtype():
    class Base:
        pass

    class Derived(Base):
        def __init__(self, val):
            self.val = val

    result = jsonable_encoder(
        Derived("x"), custom_encoder={Base: lambda o: o.val}
    )
    assert result == "x"


def test_custom_encoder_exact_type_overrides_subtype():
    class Shape:
        pass

    class Circle(Shape):
        def __init__(self, r):
            self.r = r

    result = jsonable_encoder(
        Circle(5),
        custom_encoder={Circle: lambda o: f"circle_r{o.r}", Shape: lambda o: "shape"},
    )
    assert result == "circle_r5"


def test_custom_encoder_not_applied():
    assert jsonable_encoder(42, custom_encoder={str: lambda o: "oops"}) == 42


# ---------------------------------------------------------------------------
# Pydantic types: PydanticUndefinedType, SecretStr, SecretBytes, AnyUrl, NameEmail
# ---------------------------------------------------------------------------


def test_pydantic_undefined():
    assert jsonable_encoder(PydanticUndefined) is None


def test_secret_str():
    # SecretStr.__str__ masks the value
    s = SecretStr("my-secret")
    assert jsonable_encoder(s) == "**********"


def test_secret_bytes():
    s = SecretBytes(b"secret-bytes")
    assert jsonable_encoder(s) == "b'**********'"


def test_any_url():
    url = AnyUrl("https://example.com/path")
    assert jsonable_encoder(url) == "https://example.com/path"


def test_name_email():
    ne = NameEmail("John Doe", "john@example.com")
    assert jsonable_encoder(ne) == "John Doe <john@example.com>"


# ---------------------------------------------------------------------------
# IP addresses
# ---------------------------------------------------------------------------


def test_ipv4_address():
    assert jsonable_encoder(ipaddress.IPv4Address("192.168.1.1")) == "192.168.1.1"


def test_ipv4_interface():
    assert (
        jsonable_encoder(ipaddress.IPv4Interface("192.168.1.1/24"))
        == "192.168.1.1/24"
    )


def test_ipv4_network():
    assert (
        jsonable_encoder(ipaddress.IPv4Network("192.168.1.0/24"))
        == "192.168.1.0/24"
    )


def test_ipv6_address():
    assert (
        jsonable_encoder(ipaddress.IPv6Address("::1")) == "::1"
    )


def test_ipv6_interface():
    assert (
        jsonable_encoder(ipaddress.IPv6Interface("::1/64")) == "::1/64"
    )


def test_ipv6_network():
    assert (
        jsonable_encoder(ipaddress.IPv6Network("::1/128")) == "::1/128"
    )


# ---------------------------------------------------------------------------
# Subclass handling via encoders_by_class_tuples
# ---------------------------------------------------------------------------


def test_subclass_of_path():
    class MyPath(type(Path())):
        pass

    p = MyPath("/foo/bar")
    assert jsonable_encoder(p) == "/foo/bar"


def test_enum_via_encoders_by_class_tuples():
    # ENCODERS_BY_TYPE has Enum, so isinstance check via class tuples works for any enum
    class FreshEnum(enum.Enum):
        X = "x"

    assert jsonable_encoder(FreshEnum.X) == "x"


# ---------------------------------------------------------------------------
# dict() / vars() fallback
# ---------------------------------------------------------------------------


class CustomIterable:
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __iter__(self):
        return iter([("a", self.a), ("b", self.b)])


class CustomVars:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def test_dict_iterable():
    obj = CustomIterable(1, 2)
    assert jsonable_encoder(obj) == {"a": 1, "b": 2}


def test_vars_fallback():
    obj = CustomVars(10, 20)
    assert jsonable_encoder(obj) == {"x": 10, "y": 20}


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_function_falls_back_to_vars():
    def f():
        pass

    # Functions have __dict__ so vars(f) succeeds with empty dict
    assert jsonable_encoder(f) == {}


def test_class_raises_value_error():
    class SomeClass:
        pass

    with pytest.raises(ValueError):
        jsonable_encoder(SomeClass)


# ---------------------------------------------------------------------------
# Integration-style: objects that nest multiple types
# ---------------------------------------------------------------------------


def test_mixed_nested_object():
    @dataclasses.dataclass
    class OrderLine:
        sku: str
        qty: int

    class Order(BaseModel):
        order_id: str
        lines: list[OrderLine]
        created: datetime.datetime

    order = Order(
        order_id="ORD-001",
        lines=[OrderLine(sku="WIDGET", qty=2), OrderLine(sku="GADGET", qty=1)],
        created=datetime.datetime(2024, 6, 15, 12, 0, 0),
    )
    result = jsonable_encoder(order)
    assert result == {
        "order_id": "ORD-001",
        "lines": [{"sku": "WIDGET", "qty": 2}, {"sku": "GADGET", "qty": 1}],
        "created": "2024-06-15T12:00:00",
    }


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_string():
    assert jsonable_encoder("") == ""


def test_zero():
    assert jsonable_encoder(0) == 0


def test_negative_zero_float():
    assert jsonable_encoder(-0.0) == 0.0


def test_very_deeply_nested_dict():
    d = {}
    cur = d
    for i in range(100):
        cur["n"] = {}
        cur = cur["n"]
    cur["leaf"] = 1
    # ensure no recursion limit issues
    result = jsonable_encoder(d)
    cur = result
    for _ in range(100):
        cur = cur["n"]
    assert cur["leaf"] == 1


def test_dict_with_encoded_keys():
    # keys that are not strings get encoded
    d = {1: "a", 2: "b"}
    assert jsonable_encoder(d) == {1: "a", 2: "b"}


# ---------------------------------------------------------------------------
# Global custom encoder registry (CUSTOM_ENCODERS / register_encoder)
# ---------------------------------------------------------------------------


from sillo.encoding import CUSTOM_ENCODERS, register_encoder, get_custom_encoders


class _RegType:
    def __init__(self, v):
        self.v = v


def _cleanup_registry():
    CUSTOM_ENCODERS.pop(_RegType, None)


def test_register_encoder_global_application():
    try:
        register_encoder(_RegType, lambda o: o.v)
        assert jsonable_encoder(_RegType(7)) == 7
    finally:
        _cleanup_registry()


def test_get_custom_encoders_returns_copy():
    try:
        register_encoder(_RegType, lambda o: o.v)
        snapshot = get_custom_encoders()
        assert snapshot[_RegType](_RegType(3)) == 3
        # mutating the snapshot must not affect the registry
        snapshot.clear()
        assert _RegType in CUSTOM_ENCODERS
    finally:
        _cleanup_registry()


def test_registered_encoder_nested():
    try:
        register_encoder(_RegType, lambda o: o.v)
        assert jsonable_encoder({"items": [_RegType(1), _RegType(2)]}) == {
            "items": [1, 2]
        }
    finally:
        _cleanup_registry()


def test_per_call_encoder_overrides_registry():
    try:
        register_encoder(_RegType, lambda o: "registry")
        result = jsonable_encoder(
            _RegType(9), custom_encoder={_RegType: lambda o: "per-call"}
        )
        assert result == "per-call"
    finally:
        _cleanup_registry()
