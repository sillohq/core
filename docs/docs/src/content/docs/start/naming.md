---
title: Project Names
description: "What makes a valid Sillo project name, why it is checked before anything is fetched, and the name shapes derived from yours — package, distribution, table and class names."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Project Names
  - tag: meta
    attrs:
      property: og:description
      content: The naming rules, and the identifier shapes derived from a project name.
---

The name you give a project becomes a directory, a Python package, and a
distribution name. Those three have different rules, and the strictest wins.

## The rules

A valid project name:

- starts with a **letter**;
- contains only letters, digits, `.`, `-` and `_`;
- is **100 characters or fewer**;
- converts to a valid, non-keyword Python identifier.

```bash
sillo-start create-app myapp          # ✓
sillo-start create-app my-cool-app    # ✓
sillo-start create-app my_app         # ✓
sillo-start create-app blog2          # ✓

sillo-start create-app 2blog          # ✗ does not start with a letter
sillo-start create-app "my app"       # ✗ contains a space
sillo-start create-app class          # ✗ a Python keyword
```

A rejection names the rule rather than just refusing:

```
✗ '2blog' is not a valid project name.
  Use a letter followed by letters, digits, hyphens or underscores.
```

This is checked **before anything is fetched**. A name that cannot work should
cost you nothing.

## Dashes are fine

Dashes are permitted because that is the convention for distribution names on
PyPI. They are converted where a dash is not legal:

| | |
| --- | --- |
| Project name | `my-cool-app` |
| Package name | `my_cool_app` |
| Distribution name | `my-cool-app` |

So `my-cool-app` is what you type, `my_cool_app` is what you import, and both
are what you would have chosen by hand.

The identifier check is applied to the **converted** form. That is what makes
the rule precise rather than approximate: a name is valid when the package name
it produces is a legal, non-keyword identifier.

## The shapes derived from a name

Generators and templates need the same name in several forms at once. Sillo
Start derives them all from one input, so they cannot drift apart:

| Function | `BlogPost` becomes | `blog_post` becomes |
| --- | --- | --- |
| `to_snake` | `blog_post` | `blog_post` |
| `to_pascal` | `BlogPost` | `BlogPost` |
| `to_camel` | `blogPost` | `blogPost` |
| `to_kebab` | `blog-post` | `blog-post` |
| `to_title` | `Blog Post` | `Blog Post` |
| `to_human` | `Blog post` | `Blog post` |
| `table_name` | `blog_posts` | `blog_posts` |

The splitter handles camelCase, PascalCase, snake_case, kebab-case and
space-separated text, including acronym runs — `APIKey` splits to
`["api", "key"]` rather than `["a", "p", "i", "key"]`.

## Pluralisation

`table_name` pluralises the last word only, so `BlogPost` becomes `blog_posts`
rather than `blogs_posts`.

The rules are deliberately a small set rather than a dependency:

- irregulars: `person`/`people`, `child`/`children`, `man`/`men`,
  `woman`/`women`, `tooth`/`teeth`, `foot`/`feet`, `mouse`/`mice`,
  `goose`/`geese`;
- uncountables left alone: `equipment`, `information`, `money`, `series`,
  `species`, `data`;
- ending `s`, `x`, `z`, `ch` or `sh` takes `es`;
- consonant followed by `y` becomes `ies`;
- `f` and `fe` become `ves`;
- otherwise `s`.

That covers the shapes model names actually take. Anything it gets wrong you
can override on the model:

```python
class Meta:
    table = "people_records"
```

Which is the right escape hatch — an inflection library would be a dependency
carried by every project to be right about a handful of nouns.

## Using them yourself

They are importable, and they are plain functions:

```python
from sillo_start.utils.naming import (
    to_snake, to_pascal, to_camel, to_kebab, to_title, to_human,
    pluralize, table_name,
    is_valid_project_name, is_valid_python_identifier,
    package_name_for, distribution_name_for, ensure_suffix,
)
```

`ensure_suffix` is the one worth knowing about — it appends a suffix unless it
is already there, case-insensitively:

```python
ensure_suffix("User", "Controller")            # UserController
ensure_suffix("UserController", "Controller")  # UserController
```

So a generator can accept `User` or `UserController` and produce the same thing
either way.
