---
title: Plugin API
description: Type-level reference for lucode-starlight plugin options and frontmatter extensions.
---

## Import

```ts
import lucode from 'lucode-starlight';
```

Use the default export inside Starlight's `plugins` array:

```js
starlight({
  plugins: [lucode()],
});
```

## `LucodeStarlightUserConfig`

```ts
type LucodeStarlightUserConfig = {
  navLinks?: Link[];
  footerText?: string;
};
```

### `navLinks`

Header navigation links rendered by the theme.

```ts
type Link = {
  label: string | Record<string, string>;
  link: string;
  badge?: string;
  attrs?: Record<string, string | number | boolean | undefined>;
};
```

```js
lucode({
  navLinks: [
    { label: 'Docs', link: '/guides/getting-started/' },
    { label: 'API', link: '/reference/plugin-api/' },
    {
      label: 'GitHub',
      link: 'https://github.com/lucas-labs/lucode-starlight-theme',
      attrs: { target: '_blank', rel: 'noreferrer' },
    },
  ],
});
```

### `footerText`

Markdown rendered in the footer text slot.

```js
lucode({
  footerText:
    'Built with [Lucode Starlight](https://github.com/lucas-labs/lucode-starlight-theme).',
});
```

If omitted, the theme uses its built-in credit line.

## Frontmatter Extension

Import `ExtendDocsSchema` from `lucode-starlight/schema` and pass it to Starlight's `docsSchema()`.

```ts
import { ExtendDocsSchema } from 'lucode-starlight/schema';

schema: docsSchema({ extend: ExtendDocsSchema });
```

The extension adds:

```ts
type LucodeDocsFrontmatter = {
  links?: {
    doc?: string;
    api?: string;
  };
  hero?: {
    layout?: 'centered' | 'centered-top' | 'split-left' | 'split-right' | 'banner';
    announcement?: {
      text: string;
      link: string;
    };
  };
};
```

`hero.layout` defaults to `centered`.

## Package Exports

```ts
import lucode from 'lucode-starlight';
import { ExtendDocsSchema } from 'lucode-starlight/schema';
import { ContainerSection, LinkButton } from 'lucode-starlight/components';
```

The package also exports the internal Starlight override components and CSS files for advanced composition:

- `lucode-starlight/styles/layers`
- `lucode-starlight/styles/theme`
- `lucode-starlight/styles/base`
- `lucode-starlight/components/overrides/Header.astro`
- `lucode-starlight/components/overrides/Hero.astro`
- `lucode-starlight/components/overrides/Footer.astro`

Prefer the plugin for normal sites. Reach for direct exports only when you are building a custom integration or intentionally composing with one of the theme overrides.
