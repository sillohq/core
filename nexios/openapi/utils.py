from typing import Any, List, Union

from nexios.routing import Route, Router
from nexios.routing.grouping import Group


def get_openapi(route: Union[Route, Router, Group, Any]) -> List[Route]:
    """
    Recursively extract all Route from a route structure, handling nested Groups and Routers.
    """
    routes_list: List[Route] = []

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
