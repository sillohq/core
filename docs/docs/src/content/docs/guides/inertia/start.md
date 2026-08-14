---
title: Creating a Project
description: Start an Inertia application from sillohq/starter-inertia — the two development processes, and every task the project ships with.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Creating an Inertia Project with Sillo
  - tag: meta
    attrs:
      property: og:description
      content: A React front end served by Sillo, running in two processes, with the full task reference.
---

#  Creating a Project

[`sillohq/starter-inertia`](https://github.com/sillohq/starter-inertia) is a
working application: session authentication, a persistent layout, server-side
validation whose errors render on the form, Record, a queue, and a production
asset pipeline. You copy it and make it yours.

```bash
uvx sillo-start create-app sillohq/starter-inertia myapp
cd myapp
make setup
```

`sillo-start` takes the repository as an argument — there is no `--inertia`
flag, because it fetches a real starter rather than rendering a template. It
renames the project to yours and gives it its own secrets.

`make setup` installs the Python **and** Node dependencies, writes a `.env`
with a freshly generated `SECRET_KEY`, and creates the database.

Everything on [Creating a Project](/guides/start/) applies here too — the
requirements, what `sillo-start` does to the files, using your own starter.
This page covers what is different.

##  Two processes in development

This is the part that catches everyone once.

```bash
make dev        # the application, on :8000
npm run dev     # the Vite dev server, on :5173 — in a second terminal
```

Then open <http://127.0.0.1:8000>.

Both are required. The page is served by Sillo, but it loads its JavaScript
from Vite, so with only `make dev` running you get a blank page and a console
full of failed module requests. With only `npm run dev` you get nothing at all
— Vite serves modules, not your application.

`make dev` prints a reminder for exactly this reason. Vite is deliberately
*not* started from the Makefile: running both under one target hides which
process printed an error, and the HMR output is worth having where you can
see it.

:::note
Open the application's origin, `127.0.0.1:8000` — not Vite's `:5173`. Vite
serves modules to the page; it does not serve the page.
:::

##  Tasks

`make` on its own prints this list.

| Task | |
| --- | --- |
| `make setup` | Install everything, write `.env`, create the database |
| `make dev` | The application, with reload. Needs `npm run dev` alongside |
| `npm run dev` | The Vite dev server |
| `make migrate` | Apply every pending migration |
| `make migration m="add_posts"` | Write a migration and apply it |
| `make plan` | Show which migrations would run |
| `make rollback to=0001_initial` | Roll back to a migration |
| `make admin e=ada@example.com u=ada` | Create an administrator |
| `make users` | List users |
| `make build` | Compile the front end into `static/build` |
| `make serve` | Run as production would. Needs `make build` and `VITE_DEV=false` |
| `make test` | The Python suite |
| `make typecheck` | Type-check the front end |
| `make lint` / `make format` | Ruff, checking or fixing |
| `make check` | Everything CI runs |
| `make clean` | Remove caches and build artefacts |

The database and user tasks wrap `uv run sillo db:*` and `user:*` — see
[The Console](/guides/start/console/) for what those do and how to add your
own. The Makefile is shorthand, not a layer: every target is one readable
command you can run by hand when you need to vary it.

:::caution
`make migration` needs the name quoted as `m="…"`, and `make rollback` needs
`to=…`. Both refuse with a hint rather than doing something surprising when
the argument is missing.
:::

##  Testing

`make test` runs the Python suite. The tests drive real requests through the
application and assert on the page object, so they cover the handler, the
props, and the adapter together.

`make check` runs `lint`, `typecheck`, `build`, then `test` — in that order,
and the `build` is not incidental. The production-asset tests skip themselves
when there is nothing built, and a check that silently skips its most fragile
assertions is not a check.

##  Things that will bite you

**A blank page with failed module requests.** `npm run dev` is not running, or
`VITE_DEV=false` is set with nothing built.

**Every module blocked by CORS.** The browser is on the Sillo origin and pulls
modules from Vite's, which is cross-origin. `server.cors` in `vite.config.ts`
is set for this reason — removing it renders the page blank with only a
console error to say so.

**A full page refresh on every save instead of HMR.** Vite guesses the HMR
host from the page, which is the Sillo origin rather than its own.
`server.hmr.host` states it.

##  Next

- [Project Structure](/guides/inertia/structure/) — what is in the box and
  where it lives
- [Pages and Props](/guides/inertia/pages/) — adding a page of your own
