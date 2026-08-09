"""The application class is `SilloApp`, and `silloApp` no longer exists.

`silloApp` was the spelling up to 0.0.1a15. It violated every naming
convention Python has for classes — a lowercase-initial name reads as a
function at every call site, which is exactly how `app = silloApp()` looked.

0.0.2a1 renamed it and kept the old name resolvable behind a deprecation
warning. 0.0.2a2 removes it outright: an alias that still works is an alias
people keep writing, and the framework is early enough that a clean break
costs less than a name nobody trusts.

These tests pin both directions. The new name is the real one, and the old
one raises rather than silently resolving to anything.
"""

from __future__ import annotations

import pytest

import sillo
from sillo import SilloApp


class TestTheNewName:
    def test_the_class_is_exported(self):
        assert sillo.SilloApp is SilloApp

    def test_it_is_the_class_actually_defined(self):
        """Not an alias pointing somewhere else."""
        assert SilloApp.__name__ == "SilloApp"
        assert SilloApp.__qualname__ == "SilloApp"

    def test_it_is_importable_from_the_module_too(self):
        from sillo.application import SilloApp as FromModule

        assert FromModule is SilloApp

    def test_it_is_the_advertised_name(self):
        assert "SilloApp" in sillo.__all__

    def test_a_star_import_brings_it_in(self):
        namespace: dict = {}
        exec("from sillo import *", namespace)  # noqa: S102

        assert namespace["SilloApp"] is SilloApp

    def test_an_instance_stringifies_under_the_new_name(self):
        """`__str__` reaches logs and dev-server output; it must not still
        say `silloApp`."""
        assert str(SilloApp(title="Projects")) == "<SilloApp: Projects>"


class TestTheOldNameIsGone:
    """Removed, not merely undocumented.

    The failure has to be loud and immediate. A name that resolves to
    something plausible — a shim, a subclass, `None` — fails later and
    somewhere else, which is worse than not existing.
    """

    @pytest.mark.parametrize("module", ["sillo", "sillo.application"])
    def test_the_attribute_does_not_exist(self, module):
        import importlib

        mod = importlib.import_module(module)

        with pytest.raises(AttributeError):
            mod.silloApp

    @pytest.mark.parametrize("module", ["sillo", "sillo.application"])
    def test_importing_it_fails(self, module):
        """The form real code uses: `from sillo import silloApp`."""
        with pytest.raises(ImportError):
            exec(f"from {module} import silloApp")  # noqa: S102

    def test_it_is_absent_from_all(self):
        assert "silloApp" not in sillo.__all__

    def test_a_star_import_does_not_bring_it_in(self):
        namespace: dict = {}
        exec("from sillo import *", namespace)  # noqa: S102

        assert "silloApp" not in namespace

    def test_it_is_absent_from_dir(self):
        """`dir()` drives editor completion; the old name must not appear."""
        assert "silloApp" not in dir(sillo)

    def test_no_deprecation_shim_survives(self):
        """A module `__getattr__` is how the 0.0.2a1 alias worked.

        Asserting the hook itself is gone catches a partial revert that
        reinstates the shim while leaving these tests otherwise passing.
        """
        import sillo.application

        assert not hasattr(sillo, "__getattr__")
        assert not hasattr(sillo.application, "__getattr__")
