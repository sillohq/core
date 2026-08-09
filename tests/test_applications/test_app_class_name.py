"""The application class is `SilloApp`, and the old name still resolves.

`silloApp` was the spelling up to 0.0.1a15. It violated every naming
convention Python has for classes, so 0.0.2a1 renamed it — but an alpha with
fifteen releases behind it has real applications importing the old name, and
a rename with no bridge breaks all of them at import time, before any of
their code runs.

These tests pin both halves of that bargain: the new name is the real one and
the only one advertised, and the old name keeps working while saying it is on
the way out.
"""

from __future__ import annotations

import warnings

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

    def test_an_instance_stringifies_under_the_new_name(self):
        """`__str__` reaches logs and dev-server output; it must not still
        say `silloApp`."""
        assert str(SilloApp(title="Projects")) == "<SilloApp: Projects>"


class TestTheOldNameStillWorks:
    def test_the_package_still_resolves_it(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            assert sillo.silloApp is SilloApp

    def test_the_module_still_resolves_it(self):
        """`from sillo.application import ...` is a path the framework itself
        uses, so the alias cannot live on the package alone."""
        import sillo.application

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            assert sillo.application.silloApp is SilloApp

    @pytest.mark.parametrize("module", ["sillo", "sillo.application"])
    def test_using_it_warns(self, module):
        import importlib

        mod = importlib.import_module(module)

        with pytest.warns(DeprecationWarning, match="renamed to SilloApp"):
            getattr(mod, "silloApp")  # noqa: B009

    def test_the_warning_names_the_removal_version(self):
        """A deprecation with no deadline is a deprecation nobody acts on."""
        with pytest.warns(DeprecationWarning) as caught:
            sillo.silloApp

        assert "0.1.0" in str(caught[0].message)


class TestTheOldNameIsNotAdvertised:
    def test_it_is_absent_from_all(self):
        """A star-import must not hand back the deprecated spelling."""
        assert "silloApp" not in sillo.__all__

    def test_a_star_import_does_not_bring_it_in(self):
        namespace: dict = {}
        exec("from sillo import *", namespace)  # noqa: S102

        assert "SilloApp" in namespace
        assert "silloApp" not in namespace

    @pytest.mark.parametrize("module", ["sillo", "sillo.application"])
    def test_an_unrelated_attribute_still_raises(self, module):
        """The `__getattr__` hook must not swallow genuine typos."""
        import importlib

        mod = importlib.import_module(module)

        with pytest.raises(AttributeError, match="no attribute 'sillLoApp'"):
            mod.sillLoApp
