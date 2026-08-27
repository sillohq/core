"""Direct coverage for sillo.route_builder: replace_params() and duplicated
path-parameter detection in compile_path(), neither reached by the routing
integration tests (which exercise route matching, not this module directly).
"""

from __future__ import annotations

import pytest

from sillo.core.converters import CONVERTOR_TYPES
from sillo.route_builder import RouteBuilder, compile_path, replace_params


def test_replace_params_substitutes_matching_placeholders():
    convertors = {"user_id": CONVERTOR_TYPES["int"]}
    params = {"user_id": 42, "extra": "value"}

    path, remaining = replace_params("/users/{user_id}", convertors, params)

    assert path == "/users/42"
    assert remaining == {"extra": "value"}


def test_replace_params_leaves_unmatched_params_untouched():
    path, remaining = replace_params("/static", {}, {"unrelated": "x"})
    assert path == "/static"
    assert remaining == {"unrelated": "x"}


def test_compile_path_rejects_duplicate_param_names():
    with pytest.raises(ValueError, match="Duplicated param name"):
        compile_path("/users/{id}/friends/{id}")


def test_compile_path_rejects_multiple_duplicate_param_names():
    with pytest.raises(ValueError, match="Duplicated param names"):
        compile_path("/a/{x}/{y}/{x}/{y}")


def test_route_builder_create_pattern():
    pattern = RouteBuilder.create_pattern("/users/{user_id:int}")
    match = pattern.pattern.match("/users/42")
    assert match is not None
    assert match.group("user_id") == "42"
    assert pattern.param_names == ["user_id"]
