from typing import Any, List, Union

from nexios.routing.grouping import Group
from nexios.routing.http import Router, Routes


def get_openapi(route: Union[Routes, Router, Group, Any]) -> List[Routes]:
    """
    Recursively extract all Routes from a route structure, handling nested Groups and Routers.
    """
    routes_list: List[Routes] = []

    if isinstance(route, Routes):
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
