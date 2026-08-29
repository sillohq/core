---
title: Scheduler Commands
description: "Running and inspecting scheduled tasks from the terminal: schedule:run, schedule:list, schedule:pause and schedule:resume."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Scheduler Commands
  - tag: meta
    attrs:
      property: og:description
      content: schedule:run, schedule:list, schedule:pause and schedule:resume.
---

The `schedule:*` commands appear when the application has a scheduler on
`app.state`, what [`setup_scheduler`](/v1.0/guides/work/scheduler/) puts there.

Without one, the commands are still registered but say what is missing rather
than failing obscurely:

```
No scheduler was bound to this console. Pass work_commands(scheduler=...)
with the manager your project registers tasks on.
```

## `schedule:run`

```bash
sillo schedule:run
```

Aliased to `sillo scheduler`. Runs the registered tasks until stopped, printing
what it is about to run:

```
  tasks   3
  • cleanup:sessions — 0 3 * * *
  • reports:daily — 0 9 * * 1-5
  • heartbeat — every 30s

Running. Ctrl-C to stop.
```

This is a long-running process, and it is a *separate* one from your web
server. Run exactly one of it. Two schedulers against the same task set will
each fire every task, and a nightly report will go out twice.

## `schedule:list`

```bash
sillo schedule:list
```

The registered tasks and their state, without running anything:

```
  name               trigger        status   runs   last run
  ─────────────────────────────────────────────────────────────────────
  cleanup:sessions   0 3 * * *      active     12   2026-08-14 03:00:01
  reports:daily      0 9 * * 1-5    paused      8   2026-08-13 09:00:00
  heartbeat          every 30s      active   4021   2026-08-14 09:14:30
```

### How the trigger column is derived

The trigger is described by whichever shape it has:

- a **cron expression**, printed as written;
- an **interval**, as `every 30s`;
- a **one-shot time**, as `once at …`;
- anything else, as the trigger's class name.

That last fallback is deliberate. A trigger type this command has not been
taught still tells you something true about itself, which beats a generic word
that tells you nothing.

Tasks are read out of the scheduler in the process you ran the command in, so
`runs` and `last run` reflect that manager's own counters.

## `schedule:pause`

```bash
sillo schedule:pause reports:daily
```

Stops a task from running. Takes the task's id, the `name` column of
`schedule:list`. An unknown id is an error.

## `schedule:resume`

```bash
sillo schedule:resume reports:daily
```

Lets a paused task run again.

:::caution[Pausing is in-process]
`pause` and `resume` act on the scheduler manager in the process you ran the
command in. Unless your project has given the scheduler durable state, pausing
from a shell does not reach the long-running `schedule:run` process, and a
restart forgets it.

For an operational off switch that survives both, put the condition in the task
itself. A feature flag it reads before doing any work.
:::

## Running it in production

The scheduler is a process, like the worker. A typical deployment runs three:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000   # or uvicorn/granian directly
sillo queue:work -q default
sillo schedule:run
```

The scheduler *dispatches*; it does not execute. A scheduled task that queues a
job needs a worker running or the job simply accumulates. See
[Deployment](/v1.0/guides/start/deployment/).

## See also

- [Scheduler](/v1.0/guides/work/scheduler/): defining tasks and triggers.
- [Queue commands](/v1.0/cli/queues/): the worker the scheduler feeds.
