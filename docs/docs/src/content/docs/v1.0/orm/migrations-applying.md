---
title: Applying Migrations
description: "Running migrations safely: the local loop, the deployment shape, rolling back, adopting an existing schema with --fake, and the expand/contract pattern for zero downtime."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Applying Sillo Migrations
  - tag: meta
    attrs:
      property: og:description
      content: The deployment shape, rollbacks, --fake, and zero-downtime schema changes.
---

## Locally

```bash
sillo db:plan        # what would run
sillo db:migrate     # run it
sillo db:status      # confirm
```

## In a deployment

```bash
sillo db:status      # fail the deploy if this is not what you expect
sillo db:migrate
```

Three things make this reliable:

**Run it once.** Not from every application process on boot. That is *n*
processes racing to apply the same migration. A release step, a job, or a
single-instance init container.

**Run it before the new code.** The new code assumes the new schema.

**Fail the deploy if it fails.** `db:migrate` exits non-zero. A deployment that
continues past a failed migration puts new code on an old schema.

```yaml
# a release step, whatever your platform calls it
- sillo db:migrate
```

`db:migrate` with nothing pending prints `Nothing pending.` and exits `0`, so
it is safe to run on every deploy.

## Rolling back

```bash
sillo db:rollback 0003_add_posts
```

Everything after `0003_add_posts` is unapplied. There is deliberately no
implicit "one step back". You name where you want to end up, because a rollback
that guesses is one you cannot review.

```bash
sillo db:rollback zero        # unapply everything, drop the tables
```

`zero` asks you to type the word rather than answering a y/n, because a
reflexive `y` is exactly how it would happen by accident. `--force` skips it
for scripts.

:::caution[A rollback is not an undo]
Reversing `ADD COLUMN` is `DROP COLUMN`, and the data in it is gone. Reversing
a type change reverses the type and not the truncation.

Read `sillo db:sql <migration> --backward` **before** you need it: ideally
before applying the forward migration at all. If the answer is "this loses
data", the plan is a restore from backup, not a rollback.
:::

In practice, rolling forward is usually safer: write a new migration that
corrects the problem, and deploy that.

## Adopting an existing schema

```bash
sillo db:migrate --fake
```

Records migrations as applied without running their SQL. For a database whose
tables already exist, created by hand, or before the project had migrations.

The workflow:

1. Write models matching the tables you have.
2. `sillo db:make initial` and read the generated file carefully: it must
   describe the schema **as it is**, not as you wish it were.
3. `sillo db:migrate --fake`.
4. `sillo db:status`: up to date, with no SQL run.

From there everything is normal.

Used anywhere else, `--fake` desynchronises the history from the schema, and
the next real migration fails against a table it expected to have been altered.

## Zero downtime

During a rolling deploy, old and new code run at once. A migration that breaks
the old code takes the site down for the length of the rollout.

The pattern is **expand, migrate, contract**, three deploys:

**1. Expand.** Add the new thing, keep the old.

```python
# migration: add `full_name`, nullable
```

Old code ignores it; new code can read it.

**2. Migrate.** Backfill, and write to both.

```python
# code writes name and full_name
# a job backfills full_name for existing rows
```

**3. Contract.** Once nothing reads the old column, drop it.

```python
# migration: drop `name`
```

Slower than one migration, and it is the difference between a schema change and
an outage.

The operations that need this treatment: dropping or renaming a column, making
a column non-nullable, narrowing a type, and adding a unique constraint to a
column that might already have duplicates.

## Locking

On a large table, some operations rewrite it and hold a lock for the duration.

- **PostgreSQL:** `ADD COLUMN` with no default is instant. `ADD COLUMN` with a
  volatile default rewrites. `CREATE INDEX` locks writes. Use `CREATE INDEX
  CONCURRENTLY`, which cannot run inside a transaction and so needs a
  hand-written migration.
- **MySQL:** varies by version and engine; check `ALGORITHM=INPLACE` support
  for the operation.
- **SQLite:** rewrites the table for most `ALTER`s, and locks the whole
  database.

`sillo db:sql` shows you the statement. Whether it locks is your database's
documentation, and worth reading before running it against a table with
millions of rows.

## Testing them

Apply migrations in CI against a fresh database, then run the suite:

```bash
sillo db:migrate
pytest
```

This catches the migration that works on your machine because your database
already had the column.

Test the rollback too, at least for recent migrations:

```bash
sillo db:migrate
sillo db:rollback 0003_add_posts --force
sillo db:migrate
```

## See also

- [How migrations work](/v1.0/orm/migrations/)
- [Database commands](/v1.0/cli/database/): every flag
- [Deployment](/v1.0/guides/start/deployment/)
