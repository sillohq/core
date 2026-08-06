"""
sillo._internals.lazy — re-export a name without importing it yet.

sillo's optional features are optional at install time but not, historically, at
import time: a package that re-exported ``RecordBackend`` for convenience pulled
Tortoise into ``import sillo``, and a bare install of the framework raised
``ModuleNotFoundError: No module named 'tortoise'`` before reaching any code
that wanted a database.

The fix is a module-level ``__getattr__`` (PEP 562) that imports on first
access. This builds one::

    from sillo._internals.lazy import deferred

    __getattr__ = deferred(__name__, {"RecordBackend": ".backends"})

The name stays in ``__all__`` and the import path stays the same. What changes
is when the dependency is required — at use rather than at import.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

__all__ = ["deferred"]


def deferred(package: str, names: Mapping[str, str]) -> Callable[[str], Any]:
    """Build a module ``__getattr__`` that imports *names* on first use.

    Args:
        package: The importing module's ``__name__``, used to resolve relative
            module paths.
        names: Attribute name to the module it lives in. The module may be
            relative (``".backends"``) or absolute (``"sillo.users.base"``).

    Returns:
        A function to assign to ``__getattr__``.
    """

    def __getattr__(name: str) -> Any:
        """Import and return the object *name* refers to.

        Args:
            name: The attribute being read.

        Returns:
            The requested object.

        Raises:
            AttributeError: If *name* is not one of the deferred names. Raising
                this rather than ImportError is what keeps ``hasattr`` and
                ``dir()`` honest for everything else.
            ImportError: From the dependency itself, when the extra that
                provides it is not installed.
        """
        module = names.get(name)
        if module is None:
            raise AttributeError(f"module {package!r} has no attribute {name!r}")

        from importlib import import_module

        source = (
            import_module(module, package)
            if module.startswith(".")
            else (import_module(module))
        )
        return getattr(source, name)

    return __getattr__
