from enum import Enum

from sillo.types import Scope


class MatchStatus(Enum):
    """Enumeration for route matching status.

    This enum is used throughout the routing system to indicate the result
    of attempting to match an incoming request path against a route pattern.
    It provides three distinct states that allow the router to make informed
    decisions about how to dispatch requests.

    Attributes:
        NONE: Path does not match this route at all. The router should
            continue searching for other matching routes.
        PARTIAL: Path partially matches, more segments expected. The router
            may use this as a fallback if no full match is found.
        FULL: Path fully matches this route. The router should dispatch
            the request to this route's handler immediately.
    """

    NONE = 0
    PARTIAL = 1
    FULL = 2


def get_route_path(scope: Scope) -> str:
    """Extract the relative route path from an ASGI scope dictionary.

    Strips the root_path prefix from the full path to get the portion
    that should be used for route matching. This is essential for correctly
    routing requests when the application is mounted under a sub-path
    behind a reverse proxy or within another ASGI application.

    The function handles several edge cases including empty root paths,
    paths that exactly equal the root path, and paths that do not begin
    with the root path prefix.

    Args:
        scope: ASGI scope containing path and root_path keys. The path
            key holds the full request path while root_path holds the
            mount point of the application.

    Returns:
        The path relative to the mounted application root. If no root
        path is set or the path does not start with root_path, the
        original path is returned unchanged.

    Examples:
        >>> scope = {"path": "/api/users", "root_path": "/api"}
        >>> get_route_path(scope)
        '/users'
    """
    path: str = scope["path"]
    root_path = scope.get("root_path", "")
    if not root_path:
        return path

    if not path.startswith(root_path):
        return path

    if path == root_path:
        return ""

    return path.removeprefix(root_path)
