<p align="center">
    <br />
    <img src="https://raw.githubusercontent.com/lucas-labs/lucode-starlight-theme/refs/heads/master/docs/src/assets/logo.svg" alt="Lucode Starlight Theme" width="64" />
    <br />
    <strong>Lucode Starlight Theme</strong>
    <br />
    An Astro Starlight theme inspired by <code>shadcn/ui</code>.
    <br />
    <a href="https://lucas-labs.github.io/lucode-starlight-theme">Preview/docs</a> · <a href="https://www.npmjs.com/package/lucode-starlight">Npm</a>
</p>

<br />

# lucode-starlight

Lucode Starlight is a theme plugin for Astro Starlight inspired by [shadcn/ui](https://ui.shadcn.com/).

## Features

- Starlight plugin API integration.
- Custom overrides for header, sidebar, page frame, hero, footer, search, table of contents, pagination, and Markdown content.
- Token-based, layered CSS theme with light and dark mode values.
- Styled built-in Starlight components including hero splashes, cards, link cards, asides, badges, tabs, steps, file trees, and link buttons.

## Installation

```bash
npm install lucode-starlight
```

With Bun:

```bash
bun add lucode-starlight
```

## Usage

Add the plugin inside the Starlight integration:

```js
// astro.config.mjs
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import lucode from 'lucode-starlight';

export default defineConfig({
  integrations: [
    starlight({
      title: 'My Docs',
      plugins: [lucode()],
    }),
  ],
});
```

The plugin automatically registers Lucode component overrides, appends the theme CSS files, and configures Expressive Code.

## Attribution

This theme recreates the design of the documentation site for [shadcn/ui](https://ui.shadcn.com/).

I used [adrian-ub/starlight-theme-black](https://github.com/adrian-ub/starlight-theme-black) as a base, which brought an earlier shadcn/ui-inspired design to Astro Starlight.

## Docs Schema

To use Lucode's splash-page frontmatter fields with type checking, extend the Starlight docs schema:

```ts
// src/content.config.ts
import { defineCollection } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';
import { ExtendDocsSchema } from 'lucode-starlight/schema';

export const collections = {
  docs: defineCollection({
    loader: docsLoader(),
    schema: docsSchema({ extend: ExtendDocsSchema }),
  }),
};
```

## Plugin Options

```ts
type LucodeStarlightUserConfig = {
  navLinks?: Link[];
  footerText?: string;
};

type Link = {
  label: string | Record<string, string>;
  link: string;
  badge?: string;
  attrs?: Record<string, string | number | boolean | undefined>;
};
```

Example:

```js
lucode({
  navLinks: [
    { label: 'Docs', link: '/guides/getting-started/' },
    { label: 'GitHub', link: 'https://github.com/lucas-labs/lucode-starlight-theme' },
  ],
  footerText:
    'Built with [Lucode Starlight](https://github.com/lucas-labs/lucode-starlight-theme).',
});
```

## Splash Pages

Use Starlight's `template: splash` and set `hero.layout`:

```md
---
title: Developer Portal
description: API docs, examples, and integration guides.
template: splash
hero:
  layout: split-left
  announcement:
    text: Version 2.0 is ready
    link: /guides/getting-started/
  actions:
    - text: Get started
      link: /guides/getting-started/
      icon: right-arrow
---
```

Available layouts:

- `centered`
- `centered-top`
- `split-left`
- `split-right`
- `banner`

## Components

Import user-facing components from `lucode-starlight/components`:

```astro
---
import { ContainerSection, Dropdown, LinkButton } from 'lucode-starlight/components';
---

<ContainerSection width="lg">
  <h2>Build better docs</h2>
  <p>Use Lucode sections on splash pages and custom MDX content.</p>
  <LinkButton href="/lucode-starlight-theme/guides/getting-started/">Get started</LinkButton>
</ContainerSection>

<Dropdown.Root>
  <Dropdown.Trigger variant="secondary">Theme actions</Dropdown.Trigger>
  <Dropdown.Content align="start">
    <Dropdown.Label>Documentation</Dropdown.Label>
    <Dropdown.Item as="a" href="/guides/getting-started/">
      Getting Started
    </Dropdown.Item>
    <Dropdown.Item as="a" href="/guides/theming/">
      Customize Theme
      <Dropdown.Shortcut>CSS</Dropdown.Shortcut>
    </Dropdown.Item>
  </Dropdown.Content>
</Dropdown.Root>
```

### `LinkButton`

Props:

- `href`: anchor destination.
- `variant`: `primary`, `secondary`, or `minimal`.
- `size`: `2xs`, `xs`, `sm`, `md`, or `lg`.
- Other anchor attributes are forwarded.

### `ContainerSection`

Props:

- `width`: `sm`, `md`, `lg`, or `xl`.

### `Dropdown`

Compound menu component exported as `Dropdown.Root`, `Dropdown.Trigger`, `Dropdown.Content`, `Dropdown.Item`, `Dropdown.Label`, `Dropdown.Separator`, and `Dropdown.Shortcut`.

Useful props:

- `Dropdown.Root`: `openOnHover`, `closeDelay`.
- `Dropdown.Trigger`: `asChild`, `variant`, `size`.
- `Dropdown.Content`: `side`, `align`, `sideOffset`, `animationDuration`.
- `Dropdown.Item`: `as`, `inset`, `disabled`.
- `Dropdown.Label`: `inset`.

## Styling

Override theme tokens from your app CSS:

```css
:root {
  --radius: 0.5rem;
  --sidebar-width: 17rem;
  --container-max-width: 1440px;
}
```

## License

MIT
