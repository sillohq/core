---
title: Assets and Deployment
description: How Vite serves the front end in development and production, what the manifest is for, why asset versions force a reload, and what to change before shipping.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Inertia Assets and Deployment
  - tag: meta
    attrs:
      property: og:description
      content: Vite in development and production, the build manifest, asset versions, and what to change before shipping.
---

#  Assets and Deployment

##  One flag decides everything

**`VITE_DEV=true`**. The shell points at the Vite dev server, and you get hot
module replacement. Nothing is built.

**`VITE_DEV=false`**. The shell reads the build manifest and emits the hashed
filenames from it. `npm run build` must have run.

```bash
npm run build                     # writes static/build
VITE_DEV=false uvicorn app:app
```

That is the whole difference. `{{ inertia_head }}` in `root.html` expands to
one thing or the other.

##  The manifest

Vite writes a manifest naming every hashed output file, and the adapter reads
it to build the script tags. Without it a production render has no way to find
the filenames. The page comes back with no script tag and no error.

```ts
// vite.config.ts
build: {
  outDir: 'static/build',
  manifest: true,          // without this there is no manifest
  rollupOptions: { input: 'js/main.tsx' },
}
```

```python
# app/inertia.py
BUILD_DIR = BASE_DIR / "static" / "build"
MANIFEST = BUILD_DIR / ".vite" / "manifest.json"
```

The adapter is given the **full path** to the manifest rather than a directory.
Vite moved it into `.vite/` inside the output directory as of Vite 5 (it used
to sit at the root) so naming the file means a future move fails loudly here
instead of rendering a page with no script tag.

##  Serving the built files

`app/bootstrap.py` mounts `static/build/assets` at `/assets`, because that is
what the adapter builds URLs against: it takes each file named in the
manifest, strips the leading `assets/`, and prefixes `asset_prefix`.

The directory served must be the `assets` folder **inside** the build output,
not the output itself. Mount one level up and every script 404s against a
manifest that is perfectly correct.

The mount is skipped when nothing is built, so `pytest` and `uvicorn app:app --reload` do
not require `npm run build` first.

In production, put nginx or Caddy in front and let it serve
`static/build/assets` directly. This mount never sees traffic.

##  Asset versions

When the client's `X-Inertia-Version` does not match the current one, the
middleware answers with a **409** and `X-Inertia-Location` before the handler
runs. The client does a full visit and comes back on the current build.

That is what stops a browser running yesterday's JavaScript from rendering a
new page object against components that no longer match it.

```python
Inertia(app, root_view=..., version="1.0.0")             # a fixed string
Inertia(app, root_view=..., version=read_manifest_hash)  # re-read per request
```

A `version` of `None` disables the check.

Set `ASSET_VERSION` to something that changes per release. A commit SHA does.
Leave it fixed across deploys and clients keep the stale bundle until they
happen to hard-reload.

##  Before you ship

Everything on [Deployment](/guides/start/deployment/) applies. Three things
are specific here:

1. **Build the front end** as part of the release, before the application
   starts. `npm run build`.
2. **Set `VITE_DEV=false`.** Left true, production serves script tags pointing
   at a dev server that is not running.
3. **Set `ASSET_VERSION`** per release, so clients pick up the new bundle.

A release looks like:

```bash
uv sync --no-dev
npm ci && npm run build
uv run sillo db:migrate
VITE_DEV=false ASSET_VERSION=$(git rev-parse --short HEAD) uvicorn app:app
```

##  Things that will bite you

**A page renders with no JavaScript and no error.** The entry in
`vite.config.ts` and `ENTRY` in `app/inertia.py` have drifted. Development
still works, because the dev server serves whatever path it is asked for;
production silently ships a page with no script tag.

**Every script 404s but the manifest looks right.** The static mount is one
level too high. It must be `static/build/assets`, not `static/build`.

**Styles missing in production only.** Tailwind is a Vite plugin here, so the
stylesheet is an output of the build like any other. If `npm run build` did not
run, there is no CSS to name.

**A client stuck on an old bundle.** `ASSET_VERSION` did not change between
releases, so the version check never fires.

##  Related

- [Deployment](/guides/start/deployment/): everything both starters share
- [Static Files](/guides/static-files/): the file server itself
