"""
The ``sillo.encoding`` import path.

The serialization guide documents ``from sillo.encoding import register_encoder``
while the implementation lives in ``sillo.core.encoding``. This module verifies
the documented path resolves and shares state with the real one — otherwise an
encoder registered through the documented import would silently never apply.
"""

import sillo.core.encoding as core_encoding
import sillo.encoding as shim


def test_documented_import_path_resolves():
    from sillo.encoding import jsonable_encoder, register_encoder  # noqa: F401


def test_shim_exports_the_same_objects():
    assert shim.jsonable_encoder is core_encoding.jsonable_encoder
    assert shim.register_encoder is core_encoding.register_encoder
    assert shim.get_custom_encoders is core_encoding.get_custom_encoders
    assert shim.CUSTOM_ENCODERS is core_encoding.CUSTOM_ENCODERS
    assert shim.ENCODERS_BY_TYPE is core_encoding.ENCODERS_BY_TYPE


def test_registry_is_shared_across_both_paths():
    """An encoder registered via the shim must be visible to the real module."""

    class Widget:
        def __init__(self, n):
            self.n = n

    try:
        shim.register_encoder(Widget, lambda w: f"widget-{w.n}")
        assert core_encoding.jsonable_encoder(Widget(3)) == "widget-3"
        assert Widget in core_encoding.get_custom_encoders()
    finally:
        core_encoding.CUSTOM_ENCODERS.pop(Widget, None)


def test_all_names_in_dunder_all_exist():
    for name in shim.__all__:
        assert hasattr(shim, name), name
