"""
sillo.work.dependency — DI providers for injecting work components into handlers.

Each provider is a function usable with ``Depend()`` that pulls the
corresponding work component from the application state.  This lets you
access schedulers, queue connections, event dispatchers, and background
task managers directly in your handler signatures without manually
reaching into ``request.app.state``.

Usage::

    from sillo.core.dependencies import Depend
    from sillo.work.dependency import scheduler, queue_connection, events

    @app.get("/admin/scheduler")
    async def scheduler_status(request, response, sched = Depend(scheduler)):
        return response.json(sched.stats.to_dict())

    @app.get("/admin/queues")
    async def queue_status(request, response, conn = Depend(queue_connection)):
        return response.json({"size": await conn.size("default")})

    @app.post("/signup")
    async def signup(request, response, dispatcher = Depend(events)):
        user = await create_user(...)
        await dispatcher.dispatch(UserSignedUp(user_id=user.id))
        return response.json(ok=True)
"""

from __future__ import annotations

from sillo.core.dependencies import Depend


def _make_provider(key: str):
    """Create a DI provider function that pulls *key* from app.state."""

    async def provider(req=Depend(get_request=True)):
        """Provider

        Args:
            req: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        app = req.base_app
        return app.state.get(key) if hasattr(app, "state") else None

    return provider


scheduler = _make_provider("scheduler")
queue_connection = _make_provider("queue_connection")
events = _make_provider("events")
default_queue = _make_provider("default_queue")
