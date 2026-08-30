"""
Unit-level coverage of the marker classes themselves.

These exercise branches that route-level tests cannot reach: the legacy
``_convert`` coercion paths, type inference from container defaults, the
public ``solve_params``/``resolve_param`` helpers, and the base class
contract.
"""

from enum import Enum

import pytest

from sillo import Cookie, File, Form, Header, Path, Query, UploadFile
from sillo.parameters import (
    ParameterExtractor,
    ParameterLocation,
    SolvedParamDependency,
    resolve_param,
    solve_params,
)


class Color(Enum):
    RED = "r"
    BLUE = "b"


# ── type resolution ──────────────────────────────────────────────────────


def test_explicit_type_wins_over_default():
    assert Query("5", type=int).resolve_type() is int


def test_type_inferred_from_scalar_default():
    assert Query(1).resolve_type() is int
    assert Query(1.5).resolve_type() is float
    assert Query(True).resolve_type() is bool
    assert Query("x").resolve_type() is str


def test_type_inferred_from_empty_list_default():
    """An empty list cannot reveal its element type, so it falls back to str."""
    assert Query([]).resolve_type() == list[str]


def test_type_inferred_from_populated_list_default():
    assert Query([1]).resolve_type() == list[int]
    assert Query(["a"]).resolve_type() == list[str]


def test_type_falls_back_to_str():
    assert Query().resolve_type() is str
    assert Query(None).resolve_type() is str


def test_enum_default_infers_enum_type():
    assert Query(Color.RED).resolve_type() is Color


def test_file_resolves_to_uploadfile():
    assert File(...).resolve_type() is UploadFile


def test_file_honours_explicit_type():
    assert File(..., type=bytes).resolve_type() is bytes


# ── field info ───────────────────────────────────────────────────────────


def test_example_becomes_schema_examples():
    info = Query(1, type=int, example=7).to_field_info()
    assert info.examples == [7]


def test_documentation_metadata_reaches_field_info():
    info = Query(1, type=int, title="Page", description="A page", deprecated=True)
    field = info.to_field_info()
    assert field.title == "Page"
    assert field.description == "A page"
    assert field.deprecated is True


def test_required_flag_forces_required_field():
    assert Query(1, type=int, required=True).to_field_info().is_required()


def test_path_field_is_always_required_despite_a_default():
    """A path segment cannot be absent, so its default must not make it optional."""
    marker = Path(99, type=int)
    marker.param_name = "item_id"
    assert marker.to_field_info().is_required()


# ── legacy coercion ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "default,raw,expected",
    [
        (1, "42", 42),
        (1.5, "2.5", 2.5),
        (False, "true", True),
        (False, "1", True),
        (False, "yes", True),
        (False, "anything-else", False),
        ("x", "hello", "hello"),
    ],
)
def test_convert_scalars_from_default_type(default, raw, expected):
    assert Query(default)._convert(raw, default) == expected


def test_convert_returns_raw_string_without_a_default():
    marker = Query()
    assert marker._convert("123", ...) == "123"
    assert marker._convert("123", None) == "123"


def test_convert_splits_string_lists_on_commas():
    assert Query([])._convert("a,b,c", []) == ["a", "b", "c"]


def test_convert_splits_and_coerces_numeric_lists():
    assert Query([0])._convert("1,2,3", [0]) == [1, 2, 3]
    assert Query([0.0])._convert("1.5,2.5", [0.0]) == [1.5, 2.5]


def test_convert_looks_enums_up_by_member_name():
    assert Query(Color.RED)._convert("BLUE", Color.RED) is Color.BLUE


def test_convert_returns_raw_value_for_unknown_enum_member():
    assert Query(Color.RED)._convert("PURPLE", Color.RED) == "PURPLE"


# ── extraction without a request ─────────────────────────────────────────


def test_extract_returns_default_when_there_is_no_request():
    """Extractors are usable outside a request context, e.g. in tests."""
    assert Query(7, type=int).extract(None) == 7
    assert Header("h").extract(None) == "h"
    assert Cookie("c").extract(None) == "c"
    assert Path(3).extract(None) == 3


def test_extract_returns_default_when_unbound():
    """An unbound marker has no name to look up, so it yields its default."""
    marker = Query(5)

    class FakeContext:
        query_params = {"anything": "1"}

    assert marker.extract(FakeContext()) == 5


def test_base_class_extract_is_abstract():
    with pytest.raises(NotImplementedError):
        ParameterExtractor().extract(None)


# ── naming ───────────────────────────────────────────────────────────────


def test_header_name_conversion():
    assert Header()._convert_param_to_header_name("x_api_key") == "X-Api-Key"
    assert Header()._convert_param_to_header_name("authorization") == "Authorization"


def test_alias_overrides_the_parameter_name():
    marker = Query(1, alias="p")
    marker.param_name = "page"
    assert marker._get_param_name() == "p"


def test_parameter_name_is_used_without_an_alias():
    marker = Query(1)
    marker.param_name = "page"
    assert marker._get_param_name() == "page"


# ── locations ────────────────────────────────────────────────────────────


def test_each_marker_declares_its_location():
    assert Query.location is ParameterLocation.QUERY
    assert Header.location is ParameterLocation.HEADER
    assert Cookie.location is ParameterLocation.COOKIE
    assert Path.location is ParameterLocation.PATH
    assert Form.location is ParameterLocation.FORM
    assert File.location is ParameterLocation.FORM


def test_form_and_file_are_never_legacy():
    """Form binding postdates the Pydantic engine, so it has no legacy path."""
    assert Form().is_legacy is False
    assert File(...).is_legacy is False


def test_legacy_detection():
    assert Query(1).is_legacy is True
    assert Query(1, alias="p", required=True).is_legacy is True
    assert Query(1, description="doc").is_legacy is True, "docs must not flip the path"
    assert Query(1, type=int).is_legacy is False
    assert Query(1, ge=1).is_legacy is False


# ── public helpers ───────────────────────────────────────────────────────


def test_solve_params_collects_and_binds_markers():
    def handler(ctx, page=Query(1), x_key=Header(), other=5):
        ...

    solved = solve_params(handler)
    assert [s.param_name for s in solved] == ["page", "x_key"]
    assert solved[0].extractor.alias == "page"
    assert solved[1].extractor.alias == "X-Key"


def test_solve_params_on_a_handler_with_no_markers():
    def handler(ctx):
        ...

    assert solve_params(handler) == []


async def test_resolve_param_delegates_to_the_extractor():
    marker = Query(11, type=int)
    dep = SolvedParamDependency(marker, "page")
    assert await resolve_param(dep, None) == 11
