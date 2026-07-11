---
title: Customize the Theme
description: Override Lucode Starlight tokens and extend the visual system without forking the package.
---

Lucode Starlight keeps most visual decisions in CSS custom properties. Override them from your app-level stylesheet, usually `src/styles/global.css`, and include that file in Starlight's `customCss`.

## Add a Site Stylesheet

```js
// astro.config.mjs
starlight({
  customCss: ['./src/styles/global.css'],
  plugins: [lucode()],
});
```

The theme appends its own CSS after your custom CSS. Use cascade layers and matching selectors when you intentionally want to override Lucode tokens:

```css
/* src/styles/global.css */
@layer lucode {
  :root {
    --radius: 0.5rem;
    --sidebar-width: 17rem;
    --container-max-width: 1440px;
  }
}
```

## Core Tokens

| Token | Purpose |
| --- | --- |
| `--spacing` | Base spacing unit used by the layout and custom components. |
| `--radius` | Shared radius for buttons, asides, tabs, and cards. |
| `--header-height` | Sticky header height. |
| `--sidebar-width` | Desktop sidebar width. |
| `--container-max-width` | Maximum width for the top-level page container. |
| `--foreground` | Primary text and high-contrast UI color. |
| `--background` | Main page background. |
| `--primary` | Primary button background. |
| `--secondary` | Secondary surfaces and quiet controls. |
| `--muted` | Low-emphasis backgrounds. |
| `--muted-foreground` | Secondary text. |
| `--accent` | Hover and active backgrounds. |
| `--border` | Borders and separators. |
| `--code-background` | Code blocks, cards, tabs, and file trees. |

## Color Modes

Define light and dark values separately with Starlight's `data-theme` attribute.

```css
@layer lucode {
  :root[data-theme='light'] {
    --foreground: oklch(18% 0.015 250);
    --background: oklch(99% 0.003 250);
    --primary: oklch(24% 0.03 250);
    --primary-foreground: white;
    --border: oklch(88% 0.01 250);
  }

  :root[data-theme='dark'] {
    --foreground: oklch(97% 0.005 250);
    --background: oklch(14% 0.015 250);
    --primary: oklch(97% 0.005 250);
    --primary-foreground: oklch(14% 0.015 250);
    --border: oklch(28% 0.015 250);
  }
}
```

## Starlight Color Mapping

Lucode maps Starlight's built-in colors to its own tokens:

```css
--sl-color-bg: var(--background);
--sl-color-text: var(--foreground);
--sl-color-text-accent: var(--foreground);
--sl-color-accent: var(--border);
--sl-color-accent-high: var(--foreground);
--sl-color-gray-1: var(--gray-1);
--sl-color-gray-7: var(--gray-7);
```

This means Starlight components, Markdown content, badges, asides, and custom theme chrome stay visually aligned when you update Lucode tokens.

## Typography

The theme refines Starlight's default Markdown typography, but it does not force a font import. Set fonts globally from your app CSS:

```css
@layer lucode {
  :root {
    --sl-font: Inter, ui-sans-serif, system-ui, sans-serif;
    --sl-font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
  }
}
```

Use the [Typography](/lucode-starlight-theme/showcase/typography/) page to review headings, paragraphs, links, tables, lists, images, keyboard shortcuts, and code after changing fonts.

## Adjust Component Surfaces

Cards, tabs, file trees, code blocks, and asides use `--code-background` as their shared surface. For a lighter docs interface, keep it close to the page background:

```css
@layer lucode {
  :root[data-theme='light'] {
    --code-background: oklch(98% 0.006 250);
  }

  :root[data-theme='dark'] {
    --code-background: oklch(18% 0.01 250);
  }
}
```

For a more panelled interface, increase contrast between `--background`, `--secondary`, and `--code-background`.

## Customize Splash Pages

Splash pages are regular Starlight docs pages with `template: splash`. Lucode adds a `hero.layout` field:

```md
---
title: Developer Portal
description: API docs, examples, and integration guides.
template: splash
hero:
  layout: banner
  announcement:
    text: Version 2.0 is ready
    link: /guides/migration/
  actions:
    - text: Get started
      link: /guides/getting-started/
      icon: right-arrow
---
```

Use [Splash Pages](/lucode-starlight-theme/showcase/splash-pages/) to compare each layout in context.
