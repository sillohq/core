---
title: Typography
description: A sample documentation page that shows how Markdown content renders with Lucode Starlight.
---

This page is intentionally content-heavy. Use it to inspect the reading experience after changing fonts, colors, spacing, or Markdown component styles.

## A Real Documentation Section

Lucode Starlight favors compact headings, generous line height, and restrained link styling. The result should feel like product documentation: calm enough for repeated reading, but still sharp enough for launch pages and component references.

The theme maps Starlight colors to Lucode tokens, so prose, links, sidebars, cards, and code blocks stay coordinated when you customize the palette.

### When to Create a Guide

Create a guide when the reader is trying to complete a workflow. Guides can include explanation, but the page should keep moving toward an outcome.

- Start with the goal and the required context.
- Show the smallest working setup first.
- Add variations after the base path works.
- Link to reference pages for exhaustive option tables.

### When to Create Reference

Create reference when the reader already knows what they are looking for. Tables, property lists, and compact examples work well there.

1. Name the API or component.
2. Show the import or frontmatter field.
3. List options with types and defaults.
4. Add one complete example.

## Inline Elements

This paragraph includes **bold text**, *italic text*, `inline code`, and a [link to the theme configuration guide](/lucode-starlight-theme/guides/configuration/). It also includes a keyboard hint: press <kbd>Ctrl</kbd> + <kbd>K</kbd> to open search.

Use inline code for file names like `astro.config.mjs`, package names like `lucode-starlight`, and token names like `--code-background`.

## Blockquotes

> Good documentation does not need to shout. It needs to make the next step feel obvious.

Longer quotes should still feel aligned with the surrounding prose:

> A theme is more than colors. It is spacing, motion, affordance, density, and the quiet feeling that every page belongs to the same system.

## Code Blocks

```ts
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import lucode from 'lucode-starlight';

export default defineConfig({
  integrations: [
    starlight({
      title: 'Acme Docs',
      plugins: [lucode()],
    }),
  ],
});
```

```css
@layer lucode {
  :root {
    --radius: 0.5rem;
    --container-max-width: 1440px;
  }
}
```

## Tables

| Page type | Primary job | Good fit |
| --- | --- | --- |
| Guide | Teach a workflow | Installation, setup, migration |
| Reference | Describe an API | Options, props, exports |
| Showcase | Expose visual states | Components, typography, splash layouts |
| Concept | Explain a model | Architecture, design principles |

## Images

Images inherit the surrounding Markdown rhythm. Use real product screenshots or focused diagrams when the page needs them.

![Houston, the Astro mascot](../../../assets/houston.webp)

## Horizontal Rule

Content above the rule.

---

Content below the rule should not feel like it jumped to another design system.

## Definition-style Content

**Theme token**
: A CSS custom property that controls a repeated visual decision.

**Component override**
: A Starlight component replacement registered by the plugin during configuration.

**Splash page**
: A Starlight page using `template: splash`, often with a prominent hero and actions.
