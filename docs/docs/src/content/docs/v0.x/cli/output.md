---
title: Output
description: "Writing readable console output: lines, levels, bullets, key/value pairs, tables, panels, rules, progress bars and spinners, with colour that degrades cleanly."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Console Output
  - tag: meta
    attrs:
      property: og:description
      content: Lines, levels, tables, pairs, panels, progress bars and spinners.
---

Every output helper is available on the command itself. There is nothing to
import and nothing to construct.

```python
async def handle(self):
    self.line("Working through the backlog")
    self.success("Done.")
```

## Lines and levels

```python
self.line("plain text")
self.line("styled", style=PRIMARY)
self.blank()          # one empty line
self.blank(2)         # two

self.info("Waiting for jobs.")
self.success("Applied 2 migrations.")
self.warn("This queue is in-process.")
self.error("Could not reach the broker.")
self.muted("  Nothing done.")
```

The five levels each carry their own colour and marker. `muted` is the one to
reach for when a line is a *continuation* of the one above it (a hint under a
warning, a count under a table) which is why it appears indented throughout the
framework's own commands.

Errors written with `self.error` still go to stdout. It is the console's
top-level failure reporting that uses stderr, so that a command's own narration
and its final failure are not interleaved on the same stream.

## Bullets

```python
for line in pending:
    self.bullet(line)
```

```
  • 0002_add_users
  • 0003_add_posts
```

`indent` takes a different number of spaces if you need one.

## Key/value pairs

```python
self.pairs([
    ("app", "models"),
    ("pending", 2),
])
```

```
  app       models
  pending   2
```

The keys are padded to a common width. This is the shape to use for a small
fixed set of facts. A header before the work starts, a summary after.

## Tables

```python
self.table(
    ["queue", "waiting"],
    [["mail", 3], ["default", 0]],
    align=["left", "right"],
)
```

```
  queue     waiting
  ─────────────────
  mail            3
  default         0
```

`align` takes `"left"`, `"right"` or `"center"` per column, and defaults to
left. Right-align numbers. A column of counts that is left-aligned is
noticeably harder to compare at a glance.

Values are stringified as they are, so format them before they arrive if you
care how they look. Column widths come from the content.

## Panels and rules

```python
self.panel("The migration was written but not applied.", title="Next step")
self.rule("Results")
```

A panel boxes a short passage; a rule draws a labelled horizontal line. Both
are for separating phases of a long-running command. Neither is worth using in
a command that prints five lines.

## Progress bars

```python
with self.progress(len(items), label="Importing") as bar:
    for item in items:
        await process(item)
        bar.advance()
```

```
  Importing  ███████████████░░░░░░░░░░░░░░░  52%  (312/600)
```

The bar redraws in place on one line. `advance(step)` moves by more than one;
`set(current)` jumps to an absolute position, which is what you want when the
work reports its own position rather than counting iterations.

Leaving the `with` block finishes the bar and moves to a new line, including
when the body raised, so a failure does not leave a half-drawn bar as the last
thing on screen.

## Spinners

```python
with self.spinner("Resolving dependencies"):
    await resolve()
```

For work whose size is not known in advance. A progress bar that cannot show
progress is worse than a spinner, because it implies a total it does not have.

Both the bar and the spinner detect a non-interactive stream and stop
animating. A build log should not contain several thousand redraw frames.

## Colour

Colour is decided per stream, once, by four checks in order:

1. `NO_COLOR` set to anything at all: a presence check, per the convention, so
   `NO_COLOR=0` still disables colour.
2. `FORCE_COLOR` set to anything: for build systems that pipe output but do
   render escapes.
3. `TERM=dumb`.
4. Whether the stream is a terminal.

Redirect a command to a file and the output is plain text with no escape
sequences to strip.

To force it either way for a whole console:

```python
Console(prog="tools.py", color=False)
```

Styles are values, not strings:

```python
from sillo.console import PRIMARY, SUCCESS, Style

self.line("Custom", style=Style(fg="cyan", bold=True))
self.line("Derived", style=SUCCESS.with_(underline=True))
```

See [Styling](/v0.x/cli/styling/) for the palette and the terminal checks.

## Unicode

Box-drawing characters, bullets and the spinner frames all have ASCII
fallbacks, chosen by inspecting the stream's encoding. A Windows console that
cannot render `─` gets `-`, rather than a `UnicodeEncodeError` in the middle of
a table.

## Using `Output` directly

Outside a command (in a script, or your own tooling) the same object is
available on its own:

```python
import sys
from sillo.console import Output, Palette

out = Output(sys.stdout, Palette(sys.stdout))
out.heading("Report")
out.table(["name", "count"], rows)
```

`Console` builds two of these: `console.output` on stdout and
`console.error_output` on stderr.
