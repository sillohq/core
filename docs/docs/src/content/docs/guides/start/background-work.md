---
title: Background Work
description: "Queue jobs and scheduled tasks: writing a job, running the worker inside the application or beside it, and what each choice costs."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Background Work in a Sillo Project
  - tag: meta
    attrs:
      property: og:description
      content: Queue jobs and scheduled tasks, and where to run the worker.
---

#  Background Work

Work that should not happen inside a request: sending mail, generating a
report, calling an API that takes ten seconds.

Background work is **wired and switched off** in a new project. Turning it
on is one line in `app/bootstrap.py`.

##  Turning it on

```python
_register_work(application, in_process=True)
```

That starts the queue connection, the scheduler, **and a worker inside the
application process**, on the default in-memory queue. Nothing to install,
nothing else to run.

To run the worker separately instead:

```python
_register_work(application)
```

```bash
sillo queue:work
```

Which of those you want is the substance of this page. See [Where to run the
worker](#where-to-run-the-worker).

##  Writing a job

A job is a class with a `handle()`. Whatever the constructor takes is what
you dispatch with.

```python
# app/jobs/welcome_email.py
from __future__ import annotations

import logging

from sillo.work.queue import Job

logger = logging.getLogger("app.jobs")


class SendWelcomeEmail(Job):
    """Greet someone who has just signed up."""

    def __init__(self, user_id: int, template: str = "welcome") -> None:
        self.user_id = user_id
        self.template = template

    async def handle(self) -> None:
        from database.models.user import User

        user = await User.get_or_none(id=self.user_id)
        if user is None:
            # Deleted between dispatch and delivery. Nobody to write to.
            logger.info("welcome email skipped: user %s no longer exists", self.user_id)
            return

        logger.info("welcome email (%s) to %s", self.template, user.email)
```

Import it in the package's `__init__.py`:

```python
# app/jobs/__init__.py
from app.jobs.welcome_email import SendWelcomeEmail

__all__ = ["SendWelcomeEmail"]
```

Dispatch it:

```python
from app.jobs import SendWelcomeEmail

await SendWelcomeEmail.dispatch(user.id)
```

###  Dispatch the id, not the object

The constructor's arguments are **written to the queue and read back**, so
they must be plain data: ids, addresses, strings, numbers. Not a model
instance, not an open connection, not a request.

Beyond serialisation, there is a correctness reason. A user serialised at
dispatch is that user *as they were then*. By the time the job runs the row may
have changed, or been deleted, which is why the example loads it inside
`handle()` and tolerates it being gone.

###  Queue it, do not await it

```python
user = await User.objects.create_user(...)

# Queued, not awaited: the reply should not wait on a mail server, and a
# mail server being down should not fail a sign-up.
await SendWelcomeEmail.dispatch(user.id)

return response.json(_serialize(user), status_code=201)
```

The `await` on `dispatch` is the *push* onto the queue, not the work.

With a job that takes ten seconds, the difference is exactly what you
would hope:

```text
POST /api/auth/register           -> 201 in 0.25s
GET  /api/health during the job   -> 200 in 0.00s
  + 0.25s  welcome email queued for ada@example.com
  +10.25s  welcome email sent to ada <ada@example.com>
```

The request returned in a quarter of a second; the send finished ten
seconds later; the application stayed responsive throughout.

###  Errors

Raising from `handle()` marks the job failed and records the traceback. That is
what you want. A job that swallows its own errors is a job that silently does
nothing.

Conditions that are not errors, like the deleted user above, should return
rather than raise. Retrying will not conjure the row back.

##  Where to run the worker

Three arrangements, and the choice is about how much you are prepared to
lose.

###  In-process, in-memory

```python
_register_work(application, in_process=True)
```

One process. No Redis. Jobs run in the same event loop as request
handling.

**Good for** development, and single-instance deployments where losing a
queued job on restart is acceptable.

**Costs:** a job that blocks blocks responses. With more than one
application process each gets its own worker and its own queue. Nothing
survives a restart, and there is no retry across one.

###  Separate worker, Redis

```python
_register_work(application)
```

```bash
QUEUE_URL=redis://localhost:6379 uv run sillo queue:work
```

**Good for** production. Jobs survive an application restart, several
workers can share the load, and slow jobs cannot touch request latency.

**Costs:** Redis to run, and a second process to deploy and watch.

###  Not a queue at all

```python
result = await Resize.perform_now("avatar.png", width=256)
```

`perform_now` calls `handle()` directly: no connection, no worker, no
serialisation. The request waits for the work, and you get the return value
*and* the exception.

**Good for** work that is fast, work whose failure should fail the
request, and tests where a background worker only adds timing to reason
about.

From synchronous code (a management script, a migration) use `dispatch_sync`,
which runs its own event loop. Inside async code it refuses, by name:

```text
Resize.dispatch_sync() cannot be called while an event loop is running.
Use `await Resize.perform_now(...)` instead.
```

The same class works all three ways. Dispatching it later changes nothing
about it.

:::caution
**With the default in-memory queue, a separate `sillo queue:work` processes
nothing.** `SyncConnection` lives inside one process, so the worker has
its own empty queue while the application dispatches into another. Nothing
errors; nothing happens.

| Setup | |
| --- | --- |
| `in_process=True`, default queue | jobs run |
| `sillo queue:work`, default queue | separate queue. Nothing to do |
| `sillo queue:work` + `QUEUE_URL=redis://…` | jobs run |
:::

##  How the in-process worker is wired

```python
def _run_worker_in_process(application: SilloApp, connection) -> None:
    worker = build_worker(connection=connection, queues=["default"], concurrency=4)
    state: dict = {}

    async def start() -> None:
        state["task"] = asyncio.create_task(worker.run())

    async def stop() -> None:
        worker.stop()
        task = state.get("task")
        if task is not None:
            task.cancel()

    application.on_startup(start)
    application.on_shutdown(stop)
```

Two details are the whole trick, and both are easy to get wrong by hand.

**The worker is built from the application's `connection`, not from a
URL.** Build from a URL and you get a *second* queue: jobs go into one,
the worker drains the other, and nothing appears to happen.

**It runs as a background task.** `worker.run()` does not return until the
worker is stopped, so awaiting it in a startup hook is an application that
never finishes starting.

`_register_work` also binds the connection to every job class:

```python
Job.on_connection(work["connection"])
```

Without it the first dispatch raises `No queue connection configured for
SendWelcomeEmail`, which names the job rather than the wiring.

##  Where jobs must live

The worker resolves a queued payload by **importing the module the payload
names**. A job records where it can be found:

```python
SendWelcomeEmail.job_reference()   # "app.jobs.welcome_email.SendWelcomeEmail"
```

So a job class must be **module-level, in an importable module**.

| | |
| --- | --- |
| `app/jobs/emails.py`, module level | works |
| Any importable package on `sys.path` | works |
| Defined inside a function | not importable |
| Defined in a script run as `__main__` | resolves to the *worker's* `__main__` |

That last one is the trap. It works in-process and fails the moment you
run a separate worker:

```text
__main__.Backfill  ->  AttributeError: module '__main__' has no attribute 'Backfill'
```

Your app's `__main__` is your entry script; the worker's `__main__` is the
worker. Put job classes in `app/jobs/`.

:::caution
**Moving or renaming a job class while payloads are queued** breaks those
payloads: they still name the old path. Drain the queue before moving a
job, or leave an import behind at the old location.
:::

`app/jobs/__init__.py` importing everything is a convention rather than a
requirement. The worker imports the module itself from the reference. It
matters for one case: payloads written by older releases recorded only a class
name, and those resolve by searching **imported** job classes.

##  Scheduled tasks

```python
# app/tasks/__init__.py
def register_tasks(scheduler) -> None:
    from sillo.work.scheduler import CronTrigger
    from app.tasks.cleanup import cleanup

    scheduler.schedule(cleanup, trigger=CronTrigger("0 3 * * *"), name="cleanup")
```

Both the application and a standalone `sillo schedule:run` call this, so
both see the same schedule. Register a task in two places and they drift.

```bash
uv run sillo schedule:run
```

With `_register_work` on, the scheduler runs inside the application and
that separate process is unnecessary.

:::caution
**Several application replicas each run their own scheduler**, so a
nightly task runs once per replica. For anything that must happen exactly
once, run one scheduler process on its own and leave `in_process` off, or
guard the task with a lock.
:::

##  Running the worker in production

```bash
QUEUE_URL=redis://redis:6379 uv run sillo queue:work --concurrency 8
```

`run_worker` installs a SIGTERM handler, so a container stop finishes the
job in flight rather than killing it halfway. That is the difference
between a clean shutdown and a half-sent email.

Queue priority is order:

```bash
uv run sillo queue:work --queue urgent --queue default
```

`urgent` is drained before `default` is looked at.

##  Testing jobs

Call `handle()` directly. It is an ordinary coroutine:

```python
async def test_welcome_email_skips_a_deleted_user(caplog):
    job = SendWelcomeEmail(user_id=999)

    await job.handle()

    assert "no longer exists" in caplog.text
```

For a route that dispatches, assert on the *effect* rather than on the
dispatch, a job queued and never delivered looks exactly like one that worked.
The starter's smoke test does this by capturing what the job logs:

```python
check("welcome email job ran", await _job_ran(jobs_log), True)
```

An assertion that cannot fail is worth nothing; that one was checked by
removing the dispatch and watching it go red.

##  Things that will bite you

1. **Jobs must be module-level classes** in an importable module.

2. **`sillo queue:work` with the in-memory queue does nothing.** Use
   `in_process=True` or point `QUEUE_URL` at Redis.

3. **Dispatch plain data**, never model instances.

4. **The in-memory queue does not survive a restart**, and there is no
   retry across one.

5. **`await Job.dispatch(...)` awaits the push, not the work.** If you
   want the work, you want `perform_now`.

6. **An idle worker sleeps between polls**, so a job may not start the
   instant it is queued. Fine in production, surprising in a test that
   waits 100ms.

##  Related

- [The Console](/guides/start/console/): `worker` and `scheduler`
- [Project Structure](/guides/start/structure/): `app/jobs/` and `app/tasks/`
- [Deployment](/guides/start/deployment/): running workers alongside the app
- [Concurrency](/guides/concurrency/): the framework-level model
