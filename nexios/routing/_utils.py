from enum import Enum

from nexios.types import Scope


class MatchStatus(Enum):
    """Enumeration for route matching status.

    Attributes:
        NONE: Path does not match this route.
        PARTIAL: Path partially matches, more segments expected.
        FULL: Path fully matches this route.
    """

    NONE = 0
    PARTIAL = 1
    FULL = 2


def get_route_path(scope: Scope) -> str:
    """Extract the relative route path from ASGI scope.

    Strips the root_path prefix from the full path to get the portion
    that should be used for route matching.

    Args:
        scope: ASGI scope containing path and root_path.

    Returns:
        The path relative to the mounted application root.
    """
    path: str = scope["path"]
    root_path = scope.get("root_path", "")
    if not root_path:
        return path

    if not path.startswith(root_path):
        return path

    if path == root_path:
        return ""

    return path[len(root_path) :] if path.startswith(root_path) else path
