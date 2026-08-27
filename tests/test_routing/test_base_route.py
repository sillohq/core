"""Direct tests for BaseRoute's constructor.

No shipped route type (Route, WebsocketRoute, Group) calls
``super().__init__()`` — each sets its own attributes directly — so this
exercises the base constructor through a minimal concrete subclass instead.
"""

from __future__ import annotations

from sillo.core.routing.base import BaseRoute


class _ConcreteRoute(BaseRoute):
    def match(self, *args, **kwargs):
        return None

    async def handle(self, scope, receive, send):
        pass

    def url_path_for(self, name, **path_params):
        return name


def test_base_route_init_sets_core_attributes():
    route = _ConcreteRoute("/items/{id}", methods=["GET"], name="items")
    assert route.path == "/items/{id}"
    assert route.methods == ["GET"]
    assert route.name == "items"


def test_base_route_init_defaults():
    route = _ConcreteRoute("/")
    assert route.methods == []
    assert route.name is None
