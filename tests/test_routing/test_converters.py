import uuid

import pytest

from sillo.core.converters import (
    CONVERTOR_TYPES,
    FloatConvertor,
    IntegerConvertor,
    PathConvertor,
    SlugConvertor,
    StringConvertor,
    UUIDConvertor,
    register_url_convertor,
)


def test_string_convertor():
    c = StringConvertor()
    assert c.convert("abc") == "abc"
    assert c.to_string("abc") == "abc"
    with pytest.raises(AssertionError):
        c.to_string("a/b")
    with pytest.raises(AssertionError):
        c.to_string("")


def test_path_convertor():
    c = PathConvertor()
    assert c.convert("/foo/bar") == "/foo/bar"
    assert c.to_string("/foo/bar") == "/foo/bar"


def test_integer_convertor():
    c = IntegerConvertor()
    assert c.convert("123") == 123
    assert c.to_string(42) == "42"
    with pytest.raises(AssertionError):
        c.to_string(-1)


def test_float_convertor():
    c = FloatConvertor()
    assert c.convert("3.14") == 3.14
    assert c.to_string(2.5) == "2.5"
    with pytest.raises(AssertionError):
        c.to_string(-0.1)
    with pytest.raises(AssertionError):
        c.to_string(float("nan"))
    with pytest.raises(AssertionError):
        c.to_string(float("inf"))


def test_uuid_convertor():
    c = UUIDConvertor()
    u = uuid.uuid4()
    assert c.convert(str(u)) == u
    assert c.to_string(u) == str(u)


def test_slug_convertor():
    c = SlugConvertor()
    assert c.convert("foo-bar") == "foo-bar"
    with pytest.raises(ValueError):
        c.convert("foo_bar")
    assert c.to_string("foo-bar") == "foo-bar"
    with pytest.raises(ValueError):
        c.to_string("foo_bar")


def test_register_url_convertor():
    class Dummy:
        pass

    register_url_convertor("dummy", Dummy())
    assert "dummy" in CONVERTOR_TYPES
