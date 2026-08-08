from typing import Any

from sillo.core.routing import Route, Router
from sillo.core.routing.grouping import Group


def get_openapi(route: Route | Router | Group | Any) -> list[Route]:
    """Recursively extract all Route objects from a nested route structure.

    Walks through Route, Router, Group, and generic route containers to
    flatten the hierarchy into a single list of Route instances. Handles
    Groups that may wrap a Router internally.

    Args:
        route: A Route, Router, Group, or any object with a ``routes`` attribute.

    Returns:
        A flat list of Route instances extracted from the structure.

    Raises:
        None explicitly. If ``route`` has no viable structure an empty list
        is returned rather than raising.
    """
    routes_list: list[Route] = []

    if isinstance(route, Route):
        return [route]

    if isinstance(route, Router):
        for sub_route in route.routes:
            routes_list.extend(get_openapi(sub_route))

        return routes_list

    if isinstance(route, Group):
        if hasattr(route, "_base_app") and isinstance(route._base_app, Router):
            routes_list.extend(get_openapi(route._base_app))
        elif hasattr(route, "routes"):
            for sub_route in route.routes:
                routes_list.extend(get_openapi(sub_route))
        return routes_list

    if hasattr(route, "routes"):
        for sub_route in route.routes:
            routes_list.extend(get_openapi(sub_route))

    return routes_list
