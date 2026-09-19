"""
sillo.work.dependency — DI providers for injecting work components into handlers.

Each provider is a function usable with ``Depend()`` that pulls the
corresponding work component from the application state.  This lets you
access schedulers, queue connections, event dispatchers, and background
task managers directly in your handler signatures without manually
reaching into ``ctx.app.state``.

Each provider takes the active context, so it is declared with
``get_context=True`` — ``Depend``'s default changed to ``False`` in 1.0.0a3,
since most dependencies need no context at all; these do.

Usage::

    from sillo.core.dependencies import Depend
    from sillo.work.dependency import scheduler, queue_connection, events

    @app.get("/admin/scheduler")
    async def scheduler_status(ctx, sched = Depend(scheduler, get_context=True)):
        return json(sched.stats.to_dict())

    @app.get("/admin/queues")
    async def queue_status(ctx, conn = Depend(queue_connection, get_context=True)):
        return json({"size": await conn.size("default")})

    @app.post("/signup")
    async def signup(ctx, dispatcher = Depend(events, get_context=True)):
        user = await create_user(...)
        await dispatcher.dispatch(UserSignedUp(user_id=user.id))
        return json(ok=True)
"""

from __future__ import annotations


def _make_provider(key: str):
    """Create a DI provider function that pulls *key* from app.state."""

    async def provider(ctx):
        """Provider"""
        app = ctx.base_app  # ty: ignore[unresolved-attribute]
        return app.state.get(key) if hasattr(app, "state") else None

    return provider


scheduler = _make_provider("scheduler")
queue_connection = _make_provider("queue_connection")
events = _make_provider("events")
default_queue = _make_provider("default_queue")
