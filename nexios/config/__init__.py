from typing import Any, Optional

from .base import MakeConfig


__all__ = [
    "MakeConfig",
    "get_config",
    "set_config",
]

_global_config: Optional[MakeConfig] = None


def set_config(config: Optional[MakeConfig] = None, **kwargs: Any) -> None:
    global _global_config
    if config is not None:
        _global_config = config
    if kwargs and _global_config:
        for key, value in kwargs.items():
            _global_config._set_config(key, value)  # type: ignore


def get_config() -> MakeConfig:
    global _global_config
    if _global_config is None:
        raise RuntimeError("Nexios config is not initialized")
    return _global_config
