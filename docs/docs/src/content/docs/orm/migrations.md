---
title: How Migrations Work
description: "What a Sillo migration is: the generated file, how model changes are detected, what the generator cannot know, and the rules that keep a migration history usable."
head:
  - tag: meta
    attrs:
      property: og:title
      content: How Sillo Migrations Work
  - tag: meta
    attrs:
      property: og:description
      content: The migration file, change detection, and what the generator cannot infer.
---

A migration is a Python file describing one change to the schema. They are
numbered, applied in order, and committed to your repository.

```bash
sillo db:init                     # once, per project
sillo db:make add_published_at    # after changing a model
sillo db:migrate                  # apply it
```

## Where they live

```
database/
  migrations/
    0001_initial.py
    0002_add_posts.py
    0003_add_published_at.py
```

The package is named by [`set_migrations`](/orm/setup/#migrations), and
`db:init` creates it.

The number is the order. The suffix is what you passed to `db:make`, and is
purely for humans, name them, because `0004_add_published_at` tells you
something and `0004_auto` does not.

## What a migration looks like

```python
from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields


class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name="Post",
            fields=[
                ("id", fields.IntField(generated=True, primary_key=True)),
                ("title", fields.CharField(max_length=200)),
                ("body", fields.TextField()),
            ],
            options={"table": "posts", "app": "models"},
            bases=["Model"],
        ),
    ]
```

Plain Python: a list of operations. You can read it, edit it, and write one
from scratch.

## How changes are detected

`db:make` compares your **models as they are now** against the state implied by
the migrations already written, and describes the difference.

Which means the migration history is the source of truth for what the database
should look like. It is not read *from* the database, a schema someone altered
by hand is invisible to the generator, and the next migration will be written
as if that change never happened.

## What the generator cannot know

**A rename looks like a drop plus an add.**

```python
# before
headline = fields.CharField(max_length=200)

# after
title = fields.CharField(max_length=200)
```

The generator sees one column gone and one column new. It writes exactly that,
and applying it deletes every headline in the table.

Edit the generated file to a rename before applying it. This is the single best
reason to run `db:make` without `--apply` and read what came out.

**A type change may not be reversible.** Narrowing a column truncates. The
migration will happily do it.

**Data is not migrated.** A new non-nullable column with no default fails on a
table with rows in it. The usual shape is three migrations: add it nullable,
backfill, then make it non-nullable.

**A docstring is a schema change.** A model's docstring becomes its
`table_description`, so editing one produces a migration. That is also why
[`sillo-start` does not rewrite model files](/start/personalisation/#model-files).

## Review before applying

```bash
sillo db:make add_published_at
# read database/migrations/0004_add_published_at.py
sillo db:sql 0004_add_published_at
sillo db:migrate
```

[`db:sql`](/cli/database/#dbsql) prints the statements without running them,
and `--backward` prints what a rollback would run, which is where you find out
that a column drop has no way back.

`db:make --apply` writes and applies in one step. Use it for a new model on a
local database; not for anything touching a column with data in it.

## Nothing to record

```
No model changes to record.
```

The models already match the last migration. No file is written, and the
command knows the difference, rather than reporting success for a file that
does not exist.

## Rules that keep a history usable

**Commit them.** A migration that only exists on one machine is a schema only
that machine has.

**Never edit an applied migration.** Environments that already ran it will not
run it again, so the edit reaches only the environments that had not. Write a
new one.

**One change per migration**, where practical. A rollback is per migration, and
a file doing four things cannot be partly undone.

**Resolve conflicts by renumbering.** Two branches both adding `0004_` is a
merge conflict in the numbering, not in the files. Renumber the later one and
re-read it. The state it was generated against has changed.

**Keep `DB_GENERATE_SCHEMAS=false`** anywhere you run migrations. Schema
generation creates missing tables and ignores changed ones, which is exactly
the divergence migrations exist to prevent. See
[Setup](/orm/setup/#schema-generation).

## The app label

Every migration belongs to an app label, `models` by default. It is what
appears in `options={"app": "models"}` and what the `db:*` commands are bound
to.

Most projects have one. A project with two model packages registers
[a second set of commands](/cli/standalone-consoles/#record_commands) rather
than passing a label per invocation.

## See also

- [Applying migrations](/orm/migrations-applying/): the deployment shape.
- [Programmatically](/orm/migrations-programmatic/): without the CLI.
- [Database commands](/cli/database/): every flag.
