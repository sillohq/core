---
title: Widgets
description: How a value is edited — twenty-nine controls, and the inference that means you rarely name one.
---

`Widget` is the write half of the display pair;
[`Format`](/packages/warder/columns/) is the read half.

```python
Field("body", widget=Widget.markdown(height=400))
Field("tags", widget=Widget.relation(display="name", multiple=True))
```

## Inference first

You rarely name one. The resolver reads the model's column and picks:

| Column | Widget |
|---|---|
| `CharField` | `text` — or `textarea` past 255 characters |
| `TextField` | `textarea` |
| `SlugField` | `slug`, tracking its source field |
| `PasswordField` | `password` |
| `BooleanField` | `switch` |
| `IntField` | `number` |
| `DecimalField` / `FloatField` | `number(step=0.01, precision=2)` |
| `JSONField` | `json` |
| `DatetimeField` / `DateField` / `TimeField` | the matching picker |
| a field with `choices` or an enum | `select`, clearable when nullable |
| `ForeignKeyField` | `relation`, searching over the wire |
| `ManyToManyField` | `relation(multiple=True)` |
| `UUIDField` / `BinaryField` | `text(mono=True)` |

That is read off the **schema**, which states these things, and never off an
annotation.

## The catalogue

**Text** — `text`, `textarea`, `markdown`, `rich`, `code`, `password`, `slug`,
`email`, `url`, `phone`

**Numbers** — `number`, `money`, `range`

**Choices** — `select`, `radio`, `checkbox`, `switch`, `tags`

**Time** — `date`, `datetime`, `time`, `duration`

**Data** — `file`, `image`, `json`, `keyvalue`, `color`

**Relations** — `relation`, `hidden`

Each has a `Field` shorthand: `Field.markdown("body")` is
`Field("body", widget=Widget.markdown())`.

## The ones worth knowing about

**`select`** becomes searchable past ten options on its own, because a ten-item
list is faster to read than to type into and a forty-item one is the reverse.

**`password`** is never populated from the stored value and never sent back. An
empty box on an edit form means "leave the existing hash alone", which is the
only behaviour that makes an edit form usable. Writing goes through
`sillo.hashing`.

**`keyvalue`** edits a JSON object as rows, which is what most `JSONField`s
actually hold.

**`relation`** searches over the wire rather than loading every row into a
`<select>` — the difference between a foreign key to `Country` and one to
`Customer`. See [Relations](/packages/warder/relations/).

**`slug`** follows its source field until somebody types in it.

```python
Field.slug("slug", source="title")
```

## Options reach the browser as props

A widget is a kind and its options, and the React side is a generic renderer for
that shape. Adding an option is a prop the front end already reads:

```python
>>> Widget.select(["draft", "live"])
Widget('select', choices=(('draft', 'Draft'), ('live', 'Live')), clearable=True)
```

Choices are accepted in all three ways people write them — a flat list, pairs, or
a mapping — and stored one way.
