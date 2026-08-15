---
title: Project Structure
description: How an Inertia project is laid out (views, js, root.html) and the three paths that must agree across Vite, the adapter and TypeScript.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Inertia Project Structure
  - tag: meta
    attrs:
      property: og:description
      content: views/, js/ and root.html, and the paths that have to agree across vite.config.ts, app/inertia.py and tsconfig.json.
---

#  Project Structure

```
myapp/
  app/                  the application: assembly, config, the adapter
    bootstrap.py        middleware order, database, static, routes
    config.py           typed settings, loaded from .env
    inertia.py          the adapter, shared props, flash helpers
  database/             connection, models, migrations
  routes/               what paths exist and what they render
  views/                everything React renders
    Layout.tsx          the persistent layout
    pages/              one component per page
  js/                   front-end plumbing
    main.tsx            the client entry
    app.css             Tailwind and the design tokens
    types.ts            SharedProps and friends
  root.html             the HTML shell, at the project root
  vite.config.ts
```

`app/`, `database/` and `routes/` mean what they mean in any Sillo project. See
[Project Structure](/guides/start/structure/) for that boundary and why it
points one way. Three directories are new here, and one is gone.

##  `views/`

Everything React renders. Pages live in `views/pages/`, one component each, and
are resolved by name: `render("Dashboard", …)` finds
`views/pages/Dashboard.tsx`. Nested names work. `render("iam/Users", …)` finds
`views/pages/iam/Users.tsx`.

The resolution happens in `js/main.tsx`, against a Vite glob:

```ts
const pages = import.meta.glob<PageModule>('../views/pages/**/*.tsx', { eager: true })
const page = pages[`../views/pages/${name}.tsx`]
```

The glob is literal on purpose. Vite resolves globs at build time by scanning
source text, so a path built from a variable matches nothing and every page
404s in production while working in development.

Naming a component that does not exist raises with the path it looked for,
rather than rendering an empty page.

**`Layout.tsx`** wraps pages and persists across navigations. That persistence
is what makes an Inertia application feel like a single-page application
without being written as one: the layout's state (an open menu, a scroll
position, a running timer) survives a page change.

##  `js/`

The plumbing, not the pages. The client entry, the stylesheet, shared types.
It stays small.

**`main.tsx`** creates the Inertia app and resolves components. **`app.css`**
holds Tailwind and the design tokens. Tailwind v4 is a Vite plugin rather than
a PostCSS step, so there is no `postcss.config.js` and no
`tailwind.config.js`; content scanning is automatic and the tokens live under
`@theme` in this file.

**`types.ts`** describes what every page receives. `SharedProps` types the
props registered in `app/inertia.py`, so a component reading `auth.user` is
checked against what the server actually sends.

##  `root.html`

The HTML shell, at the project root rather than buried in a template directory.
It is served once, on the first visit, and never again, every navigation after
that swaps props into the page already in the browser.

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <title>{{ app_name }}</title>
    {{ inertia_head }}
  </head>
  <body>
    <div id="{{ root_id }}"></div>
    {{ inertia }}
  </body>
</html>
```

`{{ inertia_head }}` expands to the script and stylesheet tags. The Vite dev
server's client and entry in development, the hashed files from the build
manifest in production. `{{ inertia }}` renders the page object.

`{{ app_name }}` is *view data*, not a prop. The two are different channels:
props reach React, view data only ever reaches the shell. The document title
belongs in the shell so that a page has a title before any JavaScript runs.

:::caution
**Do not move the page object onto the root `<div>` as `data-page`.** That was
the Inertia 1.x convention. Current clients read a
`script[data-page][type="application/json"]` element and nothing else, so the
older placement boots with a null page and throws
`Cannot read properties of null (reading 'component')` from inside
`createInertiaApp`.
:::

##  No `templates/`

Server-side templating is still available and still works. It is just not how
an Inertia project renders pages. `root.html` is the only template, and it is
rendered once per session rather than once per request.

##  Three paths that must agree

Each of these is stated in two files that do not know about each other.

| | Where |
| --- | --- |
| Entry `js/main.tsx` | `build.rollupOptions.input` in `vite.config.ts`, and `ENTRY` in `app/inertia.py` |
| Output `static/build` | `build.outDir` in `vite.config.ts`, and `BUILD_DIR` in `app/inertia.py` |
| Alias `@/` | `resolve.alias` in `vite.config.ts`, and `paths` in `tsconfig.json` |

The alias needs both because Vite resolves imports at build time and `tsc`
only type-checks; neither reads the other's config. The entry and output need
both because Vite writes the manifest and the adapter reads it.

Drift in the entry is the dangerous one. Development keeps working (the dev
server serves whatever path it is asked for) and production ships a page with
no script tag and no error.

##  Next

- [Pages and Props](/guides/inertia/pages/): writing a page
- [Assets and Deployment](/guides/inertia/assets/): what the manifest is for
