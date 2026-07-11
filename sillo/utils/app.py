import importlib
import os
import sys


def get_app_instance(target: str):
    """
    Load and return the app instance from a string like 'main:app',
    ensuring the current working directory is on sys.path.
    """
    if not target:
        return None

    if ":" not in target:
        raise ValueError("Target must be in the format 'module:attribute'")

    module_name, attr_name = target.split(":", 1)

    # Add current working directory to sys.path if not already present
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        raise ImportError(f"Cannot import module '{module_name}'") from e
    try:
        app = getattr(module, attr_name)
    except AttributeError as e:
        raise AttributeError(
            f"Module '{module_name}' has no attribute '{attr_name}'"
        ) from e

    return app
