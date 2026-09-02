---
title: Actions
description: Something a person can do to rows — given a queryset, not a list of ids.
---

```python
Action("Publish", publish, icon="upload", confirm="Publish {count} posts?")
Action("Promote", promote, fields=[Field.relation("classroom", label="Into")])
Action.delete()
Action.export("Export roll")
```

## The handler is given a queryset

Not a list of ids. `rows` is already scoped, already filtered, and not yet
evaluated, so an action over forty thousand selected rows is one statement:

```python
async def publish(ctx, rows):
    count = await rows.filter(status="draft").update(status="live")
    return notice(f"Published {count} posts")
```

## How it is called is decided by the declaration

With no `fields=` it is `(ctx, rows)`. With `fields=` it is `(ctx, rows, values)`,
where *values* is the little form the confirmation dialog collected. Nothing is
inferred from the handler's signature — the difference is a keyword you wrote.

```python
async def promote(ctx, rows, values):
    room = values.get("classroom")
    return notice(f"Promoted {await rows.update(classroom_id=room)} students")

Action("Promote", promote, fields=[Field.relation("classroom", label="Into")])
```

## Selection is part of the declaration

```python
Action("Publish", publish, selection="many")      # the default
Action("Open", ..., selection="one")              # only one row makes sense
Action.export(selection="none")                   # acts on the filtered set
```

`"none"` is what export uses: exporting means "everything I am looking at", and
making somebody select forty thousand rows first is a way of not having the
feature.

## Outcomes

Free builders, the way `json()` and `text()` are elsewhere in Sillo. Returning
`None` means "it worked, reload", which is what most actions want and what
happens if you write no return at all.

| | |
|---|---|
| `notice(text)` | it worked. Say so, and reload |
| `warning(text)` | it worked, partly |
| `problem(text)` | it did not work, and this is why |
| `go(url)` | send them somewhere |
| `download(content, filename=)` | hand back a file |
| `modal(component, props=)` | open one of your own components over the list |
| `refresh()` / `nothing()` | reload, or stay exactly where you are |

`problem` is distinct from raising: an action that raises is a bug and becomes a
500; one that returns `problem` has decided something, and says it.

`ActionFailed` and `Denied` may also be raised, and reach the person who pressed
the button rather than the error log.

## Confirmations

```python
Action("Publish", publish, confirm="Publish {count} posts?")
```

`{count}` and `{n}` are both substituted. A placeholder that is not one of those
is left as written rather than raising — an admin should not fail to render over
a brace.

## Built-in actions

`Action.delete()` and `Action.export()` carry **no handler**. They are the two
things the resource already knows how to do, declared so their label, icon,
placement and confirmation are yours to set — and so that deleting cannot be
granted by adding an action.

## An action cannot widen what the resource allows

Its own `gate=` and `access=` narrow and never widen. An action's `change`
permission is checked *and* the resource's, so `Access(change=False)` is not
advisory.

```python
Action("Publish", publish, gate=Gate.role("editor"))
Action("Refund", refund, access=Access(change="payment.refund"))
```

The interface hides the buttons too. That is a courtesy, not a control: every
one of these holds against a request that skips the browser entirely.
