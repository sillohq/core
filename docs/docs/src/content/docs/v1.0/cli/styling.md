---
title: Styling and the Terminal
description: "The Style and Palette primitives, the built-in styles, colour and unicode capability detection, terminal width, raw-mode key reading and stripping ANSI for tests."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Console Styling
  - tag: meta
    attrs:
      property: og:description
      content: Style, Palette, capability detection and the terminal primitives.
---

## `Style`

A style is a description, not an escape sequence:

```python
from sillo.console import Style

HEADER = Style(fg="white", bg="blue", bold=True)
```

| Field | Type |
| --- | --- |
| `fg`, `bg` | colour name or hex |
| `bold`, `dim`, `italic`, `underline`, `strike` | `bool` |

Derive rather than rebuild:

```python
LOUD = HEADER.with_(underline=True)
```

`with_` returns a new style with those fields changed. Styles are values, so
sharing one between two outputs is safe.

## The built-in styles

```python
from sillo.console import (
    PRIMARY, SUCCESS, WARNING, DANGER, INFO, MUTED, HEADING,
)
```

These are what the framework's own commands use, and what `self.success()`,
`self.warn()` and the rest resolve to. Using them keeps a project's commands
looking like the bundled ones, worth more than a bespoke palette, since they
appear in the same help listing.

## `Palette`

A palette renders styles for one stream, and decides once whether to render
anything at all:

```python
from sillo.console import Palette

palette = Palette(sys.stdout)              # inspect the stream
palette = Palette(sys.stdout, enabled=False)   # never colour
palette = Palette(sys.stdout, truecolor=True)  # 24-bit
```

`palette.render(text, style)` returns the text with escapes, or the text
unchanged when colour is off.

The capability checks read the environment and call `isatty` on every
construction rather than caching globally, so a test can build a palette with
`enabled=False` and get plain output regardless of what the real terminal
supports.

## Capability detection

```python
from sillo.console import supports_color, supports_unicode, is_interactive, terminal_width
```

### `supports_color(stream=None)`

In order: `NO_COLOR` (presence, not value) disables; `FORCE_COLOR` (presence)
enables; `TERM=dumb` disables; otherwise, whether the stream is a TTY.

A stream is allowed to raise from `isatty` (`io.IOBase` only promises the
method exists) so that call is guarded and a raising stream is treated as not a
terminal.

### `supports_unicode(stream=None)`

Tests whether the stream's encoding round-trips the characters the output
helpers actually use: `─│┌╭●✓✗▏`. If it cannot, tables draw with ASCII and
bullets fall back to `*`.

This is an encode test rather than a platform check, because the same Windows
terminal answers differently depending on the code page it was started with.

### `is_interactive(input_stream=None, output_stream=None)`

Both streams have to be terminals. Prompting requires reading *and* drawing, so
a command whose output is piped is not interactive even though its stdin is a
terminal.

### `terminal_width(default=80)`

The usable width, falling back to 80 when it cannot be determined, a pipe, a CI
log.

## Reading keys

The list prompts take over the terminal, which needs raw mode:

```python
from sillo.console import Key
from sillo.console.terminal import raw_mode, read_key

with raw_mode():
    while True:
        key = read_key()
        if key == Key.ENTER:
            break
```

`Key` names the keys a prompt reacts to: `UP`, `DOWN`, `LEFT`, `RIGHT`, `HOME`,
`END`, `ENTER`, `SPACE`, `TAB`, `ESCAPE`, `BACKSPACE`, `DELETE` and
`INTERRUPT`. Anything else comes back as the character itself.

`raw_mode` restores the terminal on the way out, including when the body
raised. Leaving a terminal in raw mode is the failure that makes a user's shell
stop echoing and requires a `reset`, so it is worth never reaching for the
underlying `termios` calls directly.

You will not normally need any of this. [The prompts](/v1.0/cli/prompts/) are built
on it. It is here for a project drawing something the prompts do not cover.

## Testing coloured output

```python
from sillo.console import strip_ansi

assert strip_ansi(captured) == "Applied 2 migrations."
```

Better still, build the console with colour off and compare directly:

```python
console = Console(prog="tools.py", color=False, interactive=False)
```

`strip_ansi` is for the case where you do not own the console that produced the
text.
