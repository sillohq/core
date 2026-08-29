---
title: Arguments, Options and Flags
description: "Declaring what a command accepts (positional arguments, value options and boolean flags) plus type conversion, choices, repetition, variadics and the parsing rules."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Console Arguments, Options and Flags
  - tag: meta
    attrs:
      property: og:description
      content: The three parameter kinds, type conversion, choices, repetition and the parsing rules.
---

A command lists what it accepts explicitly:

```python
from sillo.console import Argument, Command, Flag, Option


class ListUsers(Command):
    name = "user:list"
    help = "List users, newest first"

    arguments = [
        Argument("email", help="Address to look up"),
        Option("limit", type=int, default=50, short="l", help="How many to show"),
        Flag("staff", help="Only administrators"),
    ]
```

The three kinds map onto the three shapes a command line has. An `Argument` is
positional. An `Option` takes a value. A `Flag` is on or off and never consumes
the token after it.

## `Argument`

```python
Argument(name, help="", default=UNSET, type=None, choices=None, metavar=None, variadic=False)
```

Positional, and **required unless given a default**:

```python
Argument("email")                  # required
Argument("email", default=None)    # optional
```

That distinction is why the absence of a default is its own sentinel rather
than `None`. `None` is a perfectly good default for an optional argument, so it
cannot also mean "no default was given".

### Variadic

```python
Argument("paths", variadic=True, help="Files to process")
```

Collects every remaining positional token into a list. A variadic argument is
never required (absent, it is an empty list) and must be declared last.
Declaring one before another argument raises at registration, naming both.

```bash
sillo files:check a.py b.py c.py     # ["a.py", "b.py", "c.py"]
```

## `Option`

```python
Option(name, help="", default=UNSET, type=None, choices=None,
       metavar=None, short=None, multiple=False, required=False)
```

Named, and takes a value:

```bash
--limit 50
--limit=50
-l 50
-l50
```

| Parameter | Effect |
| --- | --- |
| `short` | A one-character alias, `-l`. More than one character raises. |
| `multiple` | Repeatable; values collect into a list. Defaults to `[]`. |
| `required` | Fail when absent, even though it is an option. |

```python
Option("queue", short="q", multiple=True, help="Queue to consume. Repeatable")
```

```bash
sillo queue:work -q mail -q default    # ["mail", "default"]
```

Each parse gets a fresh list, so a repeated option's default never accumulates
values across two invocations of the same declaration.

## `Flag`

```python
Flag(name, help="", default=False, short=None)
```

On or off, and never consumes the next token:

```python
Flag("staff", help="Only administrators")
```

```bash
--staff          # True
                 # False
```

### Flags that default to on

Give a flag `default=True` and it is turned **off** by the `--no-` form:

```python
Flag("git", default=True, help="Initialise a git repository")
```

```bash
--no-git         # False
                 # True
```

Both spellings are always registered, so `--staff` and `--no-staff` both parse
whichever way the default points. The help prints the one that changes the
default, because that is the only one worth typing.

Passing a value to a flag is an error rather than being ignored:

```
--staff is a flag and takes no value
```

## Conversion and validation

```python
Option("port", type=int, default=8000)
Option("root", type=Path)
Option("rate", type=float, default=1.0)
```

`type` is any callable taking a string. Anything raising `ValueError` or
`TypeError` on bad input works, which covers `int`, `float`, `pathlib.Path` and
most enum constructors. Failures become usage errors naming the value and the
type:

```
port: 'eight' is not a valid int
```

`choices` is checked **after** conversion, so it compares converted values:

```python
Option("format", default="table", choices=["table", "json", "csv"])
```

```
format: 'yaml' is not one of table, json, csv
```

## What the parser accepts

- `--name value` and `--name=value`
- `-n value` and `-nvalue`
- bundled short flags: `-abc` is `-a -b -c`
- `--` stops option parsing; everything after it is `self.extra`

Bundling and inline values interact the way you would expect: in a cluster,
everything after the first option that takes a value is that value. `-c8` is
`--concurrency 8`, and `-fc8` is `--force --concurrency 8`.

### Errors

| Input | Message |
| --- | --- |
| `--unknown` | `unknown option --unknown` |
| `-z` | `unknown option -z` |
| `--limit` with nothing after | `--limit needs a value` |
| a missing required argument | `missing argument <EMAIL>` |
| a missing required option | `missing required option --queue` |
| a surplus positional | `unexpected argument 'extra'` |

All of them exit `2`, and print the usage line for the command plus how to see
its help.

## Naming

Dashes are permitted and are what appears on the command line; lookups accept
either spelling:

```python
Flag("dry-run")           # --dry-run
self.flag("dry_run")      # reads it
self.flag("dry-run")      # also reads it
```

`metavar` renames the placeholder in the help without renaming the parameter:

```python
Argument("identifier", metavar="EMAIL_OR_USERNAME")
```

## Why not argparse

Two reasons, both about control. The console renders its own help and phrases
its own errors, which argparse would have to be fought for. And argparse calls
`sys.exit` on a bad argument. A test cannot catch that cleanly, and an
embedding application should not have it happen underneath it. Here a parse
failure is a `UsageError`, which the console turns into an exit code it
*returns*.

## See also

- [Writing commands](/v0.x/cli/custom-commands/)
- [Output](/v0.x/cli/output/)
