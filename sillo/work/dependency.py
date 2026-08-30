"""
sillo.work.dependency — DI providers for injecting work components into handlers.

Each provider is a function usable with ``Depend()`` that pulls the
corresponding work component from the application state.  This lets you
access schedulers, queue connections, event dispatchers, and background
task managers directly in your handler signatures without manually
reaching into ``ctx.app.state``.

Usage::

    from sillo.core.dependencies import Depend
    from sillo.work.dependency import scheduler, queue_connection, events

    @app.get("/admin/scheduler")
    async def scheduler_status(ctx, sched = Depend(scheduler)):
        return json(sched.stats.to_dict())

    @app.get("/admin/queues")
    async def queue_status(ctx, conn = Depend(queue_connection)):
        return json({"size": await conn.size("default")})

    @app.post("/signup")
    async def signup(ctx, dispatcher = Depend(events)):
        user = await create_user(...)
        await dispatcher.dispatch(UserSignedUp(user_id=user.id))
        return json(ok=True)
"""

from __future__ import annotations

from sillo.core.dependencies import Depend


def _make_provider(key: str):
    """Create a DI provider function that pulls *key* from app.state."""

    async def provider(ctx=Depend(get_request=True)):
        """Provider"""
        app = ctx.base_app  # ty: ignore[unresolved-attribute]
        return app.state.get(key) if hasattr(app, "state") else None

    return provider


scheduler = _make_provider("scheduler")
queue_connection = _make_provider("queue_connection")
events = _make_provider("events")
default_queue = _make_provider("default_queue")
