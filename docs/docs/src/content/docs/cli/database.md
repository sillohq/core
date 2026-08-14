---
title: Database Commands
description: "The db:* command family — init, make, migrate, plan, rollback, sql and status — and the migration workflow they form."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Database Commands
  - tag: meta
    attrs:
      property: og:description
      content: db:init, db:make, db:migrate, db:plan, db:rollback, db:sql and db:status.
---

The `db:*` commands appear when the application has a database manager on
`app.state` — which is what [`setup_record`](/orm/setup/) puts there. There is
nothing else to configure.

## The everyday loop

```bash
sillo db:make add_posts     # you changed a model; write it down
sillo db:plan               # what would run?
sillo db:migrate            # run it
```

And once, when the project is new:

```bash
sillo db:init
```

## `db:init`

Creates the migration package — an empty directory where migrations are
recorded. Safe to re-run: it does nothing when the package already exists.

`db:make` fills it. You run `db:init` once per project and then forget it.

## `db:make`

```bash
sillo db:make
sillo db:make add_published_at
sillo db:make add_published_at --apply
```

Compares your models against the last migration and writes a migration
describing the difference.

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `name` | argument | none | Suffix for the migration filename |
| `--apply` | flag | off | Apply it straight away |

The name is a suffix, not the whole filename — migrations are numbered, so
`add_published_at` becomes something like `0004_add_published_at`. Name them:
the number tells you the order and the suffix tells you what happened.

### Nothing to record is not a success

When the models already match the last migration, nothing is written and the
command says so:

```
No model changes to record.
```

It knows because it counts the pending migrations before and after. That
detail matters more than it looks: the underlying engine reports "no changes"
only on its own stdout, so without the comparison this command would print
*"Migration written"* for a file that does not exist — and you would go looking
for it.

### Review before applying

Without `--apply` the migration is written and you are told what to run next:

```
✓ Migration written.
  Review it, then: sillo db:migrate
```

That is the recommended shape. A generated migration is a guess at your
intent — a renamed column is indistinguishable from a dropped one plus an added
one, and only one of those keeps the data. Read it.

## `db:migrate`

```bash
sillo db:migrate
sillo db:migrate --target 0003_add_posts
sillo db:migrate --fake
```

Applies every pending migration, listing them first:

```
  • 0002_add_users
  • 0003_add_posts

✓ Applied 2 migrations.
```

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `--target` | option | all | Stop at this migration |
| `--fake` | flag | off | Record as applied without running the SQL |

With nothing pending it prints `Nothing pending.` and stops.

### `--fake`

Records migrations as applied without running their SQL. This is for adopting a
schema that already exists — tables created by hand, or before the project had
migrations at all. The migration files describe the tables; the tables are
there; `--fake` writes the bookkeeping so the two agree.

Used anywhere else it will desynchronise your schema from your migration
history, and the next real migration will fail against a table it expected to
have been altered.

## `db:plan`

```bash
sillo db:plan
sillo db:plan --target 0003_add_posts
```

Shows what `db:migrate` would do, and does nothing:

```
2 migrations pending:
  • 0002_add_users
  • 0003_add_posts
```

`--target` plans as far as that migration. Nothing pending prints
`Nothing pending.`

## `db:rollback`

```bash
sillo db:rollback 0002_add_users
sillo db:rollback zero
```

Rolls the database back to a named migration. Everything after it is unapplied.

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `target` | argument | required | Migration to stop at, or `zero` |
| `--fake` | flag | off | Record the rollback without running it |
| `-f`, `--force` | flag | off | Skip the confirmation |

There is deliberately no implicit "one step back". You name where you want to
end up, because a rollback that guesses is a rollback you cannot review.

### `zero` asks properly

Rolling back to `zero` unapplies every migration and drops the tables they
made. That is not a y/n question — a reflexive `y` is exactly how it would
happen by accident — so it asks you to type the word:

```
This unapplies every migration and drops the tables they made.
Type 'zero' to confirm:
```

`--force` skips it, for scripts and CI. Nothing else about the command changes.

## `db:sql`

```bash
sillo db:sql 0003_add_posts
sillo db:sql 0003_add_posts --backward
```

Prints the SQL a migration would execute, without executing it.

| Parameter | Kind | Default | Meaning |
| --- | --- | --- | --- |
| `migration` | argument | required | Migration name, e.g. `0001_initial` |
| `--backward` | flag | off | Show the rollback SQL instead |

This is the review step for anything touching a table with data in it. Read the
`--backward` output too: that is what a rollback would run, and it is where you
find out that a column drop has no way back.

A migration that runs no SQL — a data-only migration, say — reports that rather
than printing nothing.

## `db:status`

```bash
sillo db:status
```

Whether the database is up to date, in a form that is useful in a deploy
script:

```
  app       models
  pending   0

✓ Up to date.
```

Or:

```
  app       models
  pending   2

! 2 migrations not applied:
  • 0002_add_users
  • 0003_add_posts
```

## The app label

Every one of these acts on an app label, `models` by default. That is the label
[`record_commands`](/cli/standalone-consoles/) was bound with; `sillo` binds
the default. Projects with more than one model package register a second set of
commands rather than passing a label per invocation — see
[Building a console](/cli/standalone-consoles/).

## See also

- [Migrations](/orm/migrations/) — what the files contain and how they are
  generated.
- [Applying migrations](/orm/migrations-applying/) — the deployment shape.
