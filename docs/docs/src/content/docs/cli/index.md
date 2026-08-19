---
title: The Sillo CLI
description: "The sillo command: how it finds your application, which commands appear when, and how the framework, database, user, queue and scheduler command sets fit together."
head:
  - tag: meta
    attrs:
      property: og:title
      content: The Sillo CLI
  - tag: meta
    attrs:
      property: og:description
      content: One command that reads your application and offers exactly the commands it implies.
---

Installing `sillo-framework` puts a `sillo` command on your path. It is the
only command-line tool the framework ships, and a project writes no file to
get it.

```bash
sillo --help
```

## One command, two halves

`sillo` is really two command sets stitched together at startup.

The first half is the framework's own, and needs no project: `version`
and `routes`. Run `sillo` anywhere and those two are what you get.

The second half is everything your application implies. When `sillo` can find
and import your `SilloApp`, it reads what that application set up and registers
the matching commands:

| What the application has | What appears |
| --- | --- |
| A database manager on `app.state` | `db:*` migrations and `user:*` accounts |
| A scheduler on `app.state` | `schedule:*` |
| Always, inside a project | `queue:*` |
| `app.add_command(...)` | Your own commands |

Nothing is configured twice. The database manager
[`setup_record`](/guides/record/) put on `app.state` is the one migrations run
against; the user model the application authenticates against is the one
`user:create` writes to; the scheduler
[`setup_scheduler`](/guides/work/scheduler/) registered is the one
`schedule:list` reads.

## What that looks like

Inside a project with a database and a scheduler:

```bash
$ sillo --help

  sillo  0.1.0b1
  The sillo command line.

  USAGE
    sillo <command> [options]

  COMMANDS
    routes         List the application's routes
    version        Show the installed version and available features

  DB
    db:init        Create the migration package
    db:make        Write a migration from the current model changes
    db:migrate     Apply every pending migration
    db:plan        Show which migrations would run
    db:rollback    Roll the database back to a migration
    db:sql         Show the SQL a migration would run
    db:status      Show whether the database is up to date

  QUEUE
    queue:failed   List jobs that exhausted their retries
    queue:flush    Drop every failed job from the record
    queue:forget   Drop one failed job from the record
    queue:list     Show how much work is waiting on each queue
    queue:work     Run the queue worker until stopped

  SCHEDULE
    schedule:list      List the registered scheduled tasks
    schedule:pause     Stop a scheduled task from running
    schedule:resume    Let a paused task run again
    schedule:run       Run scheduled tasks until stopped

  USER
    user:active    Activate or deactivate an account
    user:admin     Create an administrator
    user:create    Create a user
    user:list      List users, newest first
    user:password  Change a password
    user:show      Show one account
    user:staff     Grant or revoke admin access

  OPTIONS
    -h, --help     Show this help
    -V, --version  Show the version
```

The headings are not configured anywhere. A command name containing a colon is
grouped under the part before it, so `db:migrate` lands under `DB` because of
what it is called.

## Creating a project is not here

There is no `sillo new`. Creating a project is
[`sillo-start`](/start/), a separate tool, so the framework does not have to
carry a copy of a starter it would then have to keep in step with.

## Where to go next

- [Finding your application](/cli/discovery/): the three places `sillo` looks,
  and what to do when it looks in the wrong one.
- [Framework commands](/cli/framework-commands/): `version` and `routes`.
- [Database commands](/cli/database/): the migration workflow end to end.
- [User commands](/cli/users/): creating and managing accounts.
- [Queue](/cli/queues/) and [scheduler](/cli/scheduler/) commands.
- [Writing your own commands](/cli/custom-commands/): the part most projects
  reach within a week.
