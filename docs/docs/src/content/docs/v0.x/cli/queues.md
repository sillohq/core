---
title: Queue Commands
description: "Running the worker and managing failed jobs, queue:work, queue:list, queue:failed, queue:forget and queue:flush, and the in-process queue warning that matters most."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Queue Commands
  - tag: meta
    attrs:
      property: og:description
      content: queue:work, queue:list, queue:failed, queue:forget and queue:flush.
---

The `queue:*` commands are registered inside any project. They do not need a
database. What they connect to comes from `QUEUE_URL` in the environment.

## Read this first

Without a `redis://` URL the queue is **in-process**. It lives inside whichever
process created it, so a job dispatched by your web process lands in *that*
process's queue and a separate `queue:work` will never see it.

This is the single most common confusion with a job queue, so the commands say
so rather than sitting at zero and looking healthy:

```
! This queue is in-process.
  Jobs dispatched by a web process land in that process, not here.
  Set a redis:// URL to share one.
```

In-process is a perfectly good default for tests and for a single-process
development server. It is not a background worker.

```bash
export QUEUE_URL=redis://localhost:6379/0
```

## `queue:work`

```bash
sillo queue:work
sillo queue:work -q mail -q default
sillo queue:work --concurrency 8 --timeout 120
```

Aliased to `sillo worker`. Runs until stopped with Ctrl-C.

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `-q`, `--queue` | option, repeatable | bound set | Queue to consume |
| `-c`, `--concurrency` | option | `4` | Jobs at once |
| `--timeout` | option | `60.0` | Seconds one job may run |
| `--max-jobs` | option | `0` | Restart after this many jobs; 0 is unlimited |

```
  queues        mail, default
  concurrency   4
  broker        redis://localhost:6379/0

Waiting for jobs. Ctrl-C to stop.
```

### Queue order is priority

`--queue` is repeatable, and the order is the priority order: the first is
drained before the second is looked at. `-q mail -q default` means mail always
goes first, and `default` is only touched when `mail` is empty.

That is a strict priority, not a weighting. A permanently busy `mail` queue
will starve `default` entirely.

### `--max-jobs`

Restarts the worker after that many jobs. This is a blunt but effective answer
to a slow memory leak in a job (the process is replaced before it grows) and it
is why the option exists rather than a memory limit, which would need
platform-specific measurement to enforce.

Set it with a process manager that restarts the worker; on its own the process
just exits.

### `--timeout`

The seconds a single job may run before it is abandoned. A job that hangs on a
network call it never gave a timeout to would otherwise hold one of your
`--concurrency` slots forever.

## `queue:list`

```bash
sillo queue:list
sillo queue:list -q mail -q default
```

How much work is waiting on each queue:

```
  queue     waiting
  ─────────────────
  mail            3
  default         0

  broker   redis://localhost:6379/0
```

A broker that cannot be reached is reported as itself:

```
Could not reach the queue backend: Error 61 connecting to localhost:6379.
```

, rather than as a traceback from inside the table builder, which is what you
would otherwise be reading at 3am.

## `queue:failed`

```bash
sillo queue:failed
sillo queue:failed --limit 100 --offset 100
```

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `-l`, `--limit` | option | `50` | Maximum rows |
| `--offset` | option | `0` | Rows to skip |

Jobs that exhausted their retries:

```
  id                                    job              queue    failed at            error
  ──────────────────────────────────────────────────────────────────────────────────────────────
  0f0c1e2a-...                          SendWelcomeMail  mail     2026-08-14 09:12:04  SMTPConnectE…
```

The error column is truncated to 60 characters. It is there to tell you which
failure this is, not to be the whole traceback.

### An empty list is not always good news

The failed-job repository defaults to an in-memory one, which is empty in every
fresh process, including this one. So "no failures" from a console that was
never given a durable repository means nothing at all, and the command says so:

```
No failed jobs recorded.

! Failures are only kept in memory.
  This process has its own empty record. Bind a durable repository with
  work_commands(failed=...) to see the worker's.
```

If you see that warning, the answer is a durable repository. See [Building a
console](/v0.x/cli/standalone-consoles/).

## `queue:forget`

```bash
sillo queue:forget 0f0c1e2a-6b3d-4a1e-9c77-2b5a8e4d1f30
```

Drops one failed job from the record, by the id `queue:failed` printed. An
unknown id is an error rather than a silent success.

## `queue:flush`

```bash
sillo queue:flush
sillo queue:flush --force
```

Drops every failed job from the record. Asks first; `-f`/`--force` skips the
question for scripts.

Note what this does and does not do: it clears the *record of* the failures. It
does not retry them, and it does not undo anything a partially completed job
already did.

## See also

- [Queues](/v0.x/guides/work/queue/): dispatching, retries and backoff.
- [Jobs](/v0.x/guides/work/jobs/): writing one.
- [Background work overview](/v0.x/guides/work/).
