---
title: Theming
description: Four directions over one token set, and every measurement a person can feel.
---

```python
Admin(theme=Theme.console(accent="#4f46e5", density="compact"))
```

Everything here writes CSS custom properties into the shell. No rebuild, no
Node, no second stylesheet — which is what keeps theming a keyword rather than
an ejection.

## Four directions

All four ship light and dark, all four are the same custom properties with
different values. This is a choice about defaults, not about architecture.

| | |
|---|---|
| **Console** *(default)* | Quiet, roomy, keyboard-first. 52px rows, 20px cells, hairline borders, tabular numerals, monospace for ids. The one that does not fight a dense table |
| **Paper** | Light, generous, editorial. 64px rows, warm neutrals, soft shadows. Right when the admin is a content tool used occasionally |
| **Grid** | Spreadsheet-first. 38px rows, 4px radius, almost no chrome. Right for reconciliation, imports, moderation queues |
| **Native** | No opinion. Emits structure and no colour, so your design system's tokens win by not being overridden |

```python
Theme.console()   Theme.paper()   Theme.grid()   Theme.native()
```

## Every measurement is a token

Including the ones interfaces usually hard-code:

```
bg surface raised sunken ink dim faint line edge accent on-accent
radius radius-sm row cell-x pad sidebar header text small heading
shadow font mono
```

That is what makes `density` a real setting rather than a smaller font:

```python
>>> Theme(density="compact").css_variables()["--wd-row"]
'45px'
>>> Theme(density="relaxed").css_variables()["--wd-row"]
'62px'
```

`compact`, `normal` and `relaxed` scale row height, cell padding and page padding
— what a person can feel — and never the type size.

## Overriding

```python
Theme(accent="#059669")                       # one value for both modes
Theme(accent=("#111827", "#e5e7eb"))          # light, dark
Theme(radius="0px", font="Inter, sans-serif")
Theme(tokens={"ink": ("#000", "#fff"), "row": "60px"})
```

## Light and dark

```python
Theme(dark=True)        # or "system" — follows the viewer. The default
Theme(dark="dark")      # dark for everybody; [data-theme="light"] is the way back
Theme(dark=False)       # or "light" — one palette, no toggle
```

The default emits light on bare `:root` so somebody with no preference gets a
complete palette, and dark under both `prefers-color-scheme` and
`[data-theme="dark"]` so an explicit choice wins in either direction. The header
toggle sets that attribute and remembers it per browser — the same person wants
a different answer on a laptop at night and a projector in a meeting.

`dark="dark"` is the organisation's answer rather than the viewer's, for an admin
that sits beside a dark product.

Every block sets `color-scheme`, which is not decoration: it is what makes a
native `<select>`, a date picker, a scrollbar and the canvas behind the page
match. Without it a dark admin has white dropdowns and a white flash on load.

## Branding

```python
Admin(
    title="Ridgeway College",
    brand="Ridgeway",
    logo="/static/crest.svg",
    favicon="/static/favicon.png",
    footer="Ridgeway College · internal only",
    theme=Theme.console(wide=True),
)
```

`wide=True` removes the maximum content width, for tables that want the whole
screen.

## Nothing is fetched

The bundle names Inter first and never downloads it: anyone who has it gets it,
everybody else gets their system's own. No stylesheet, script, font or image
comes from a CDN, because an admin has to work on an air-gapped network and under
a Content-Security-Policy that forbids third-party anything — which are the
normal conditions for the people who most want an admin panel.
