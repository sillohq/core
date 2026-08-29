---
title: Forms and Validation
description: Returning validation errors from an Inertia submission, why they travel through the session, and why the redirect is a 303.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Inertia Forms and Validation
  - tag: meta
    attrs:
      property: og:description
      content: Why validation errors travel through the session, and why the redirect after a failed submission is a 303.
---

#  Forms and Validation

Inertia has no way to return a validation error from a POST directly. A failed
submission **redirects back**, and the errors have to survive that one
redirect. The session is where they wait.

That single constraint explains the shape of everything below.

##  The round trip

1. The form posts.
2. The handler validates. On failure it flashes the errors and redirects back.
3. The next render reads the errors out of the session: which also clears them,
   and passes them to the page as a shared prop.
4. The component renders them beside the fields.

##  Flashing

The starter ships the two helpers this needs in `app/inertia.py`:

```python
from sillo import HttpContext

def flash(ctx: HttpContext, key: str, value: Any) -> None:
    """Store a value for the next ctx only."""
    ctx.session[_flash_key(key)] = value


def take_flash(ctx: HttpContext, key: str) -> Any:
    """Read a flashed value and remove it."""
    ...
```

Reading is destructive on purpose. A validation error that stayed in the
session would reappear on the next page the user visited.

##  Returning the user to the form

```python
from sillo import HttpContext

def back_with_errors(ctx: HttpContext, errors: dict[str, str], fallback: str):
    flash(ctx, "errors", errors)
    return back(fallback=fallback)
```

```python
if problems:
    return back_with_errors(ctx, problems, fallback="/register")
```

Two details make this work, and both are easy to get wrong.

**The status is a 303**, which `back()` picks automatically after a POST. On a
302 the browser repeats the POST against the new URL, so a failed sign-up is
attempted twice.

**The redirect goes to the referring page**, falling back to the form's own
URL. Inertia's client follows it, and the errors are read out of the session by
the shared prop while that next page renders, which is also what clears them.

##  `errors` is always present

```python
inertia.share(
    errors=lambda ctx: take_flash(ctx, "errors") or {},
)
```

Registered as a shared prop with an empty mapping as its default, so every
page has it. That is deliberate: a component doing `errors.email` cannot be
written defensively at every use site, and typing it as possibly-undefined
would push a `?.` into every form field for a case that cannot occur.

```tsx
{errors.email && <em className={field.error}>{errors.email}</em>}
```

##  Flash messages

The same mechanism carries success and failure notices:

```python
from sillo import redirect

flash(ctx, "success", "Your account was created.")
return redirect("/dashboard")
```

```python
inertia.share(
    flash=lambda ctx: {
        "success": take_flash(ctx, "success"),
        "error": take_flash(ctx, "error"),
    },
)
```

Rendered once in `Layout.tsx`, so no page has to remember to show them.

##  Accepting both encodings

Inertia's client posts JSON. A plain HTML form (the no-JavaScript fallback, and
what `curl -d` sends) posts urlencoded fields. Reading both means the routes
work before the front end has booted:

```python
content_type = (ctx.content_type or "").lower()
if "application/json" in content_type:
    return dict(await ctx.json)

form = await ctx.form
return {key: form.get(key) for key in form}
```

:::caution
`json` and `form` are async **properties**, not methods, awaited without
parentheses. `await request.json()` calls the coroutine the property returns,
which raises `TypeError` and leaves a "coroutine was never awaited" warning as
the only clue.
:::

##  CSRF

Inertia's client is axios, which attaches a CSRF header on unsafe methods, but
under its own convention: it reads the `XSRF-TOKEN` cookie and sends
`X-XSRF-TOKEN`. Sillo's defaults are `csrftoken` and `X-CSRFToken`, so left
alone every POST from the front end is rejected with a 403 and nothing on
either side explains why.

The starter renames them in `app/bootstrap.py`:

```python
CSRFMiddleware(config=CSRFConfig(
    cookie_name="XSRF-TOKEN",
    header_name="X-XSRF-TOKEN",
    cookie_httponly=False,
    ...
))
```

`httponly` is off for this cookie only, because axios cannot read a cookie the
browser hides from JavaScript. That is safe precisely because the token is
useless without the session cookie, which stays `httponly`. Someone who can
read the CSRF token still cannot act as the user.

##  Next

- [Assets and Deployment](/v1.0/guides/inertia/assets/): building and shipping it
- [CSRF Protection](/v1.0/guides/csrf/): the middleware itself
