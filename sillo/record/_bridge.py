"""Hands a configuration to the migration engine's command layer.

Two migration operations — creating the migration package, and writing a
migration from model changes — exist only behind the engine's own command line,
which reads its configuration by *importing a dotted path* rather than by taking
a value. That is an implementation detail of the engine. Left exposed it would
become a rule every sillo project has to follow: export a module-level config
mapping, under a particular name, at an import path you then repeat in your
tooling.

So sillo supplies the module. :func:`published` puts the configuration here and
yields the path to it; the command layer imports this module — already in
``sys.modules``, so it sees the value just set — and finds the config waiting.

Nothing outside :mod:`sillo.record.helpers` should touch this.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator

#: The configuration currently published. Set only through :func:`published`.
CONFIG: Dict[str, Any] = {}

#: Where to tell the command layer to look.
PATH = f"{__name__}.CONFIG"


@contextmanager
def published(config: Dict[str, Any]) -> Iterator[str]:
    """Publish *config* for the duration of the block.

    Args:
        config: The configuration to make importable.

    Yields:
        The dotted path the command layer should read it from.
    """
    global CONFIG

    previous = CONFIG
    CONFIG = config
    try:
        yield PATH
    finally:
        # Restored rather than cleared: a migration command that runs inside
        # another one leaves the outer config in place.
        CONFIG = previous
