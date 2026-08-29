import { defineCollection } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';
import { ExtendDocsSchema } from 'lucode-starlight/schema';
import { VERSIONS } from './versions.mjs';

const VERSION_SLUGS = new Set(VERSIONS.map((version) => version.slug));

/**
 * The page's URL path, with the version segment left exactly as written.
 *
 * The loader's default slugifies every path segment, and slugifying drops the
 * dot: `v1.0/guides/routing.mdx` came out as `v10/guides/routing`, which reads
 * as version ten. Every other segment in this tree is already a slug —
 * lowercase, hyphenated, no dots — so the whole default is replaceable by
 * dropping the extension and folding `index` into its directory, which is what
 * this does.
 *
 * Anything outside a version directory (the theme docs under `showcase/` and
 * `reference/`) still goes through the default.
 */
function versionAwareId({ entry }: { entry: string }): string | undefined {
    const [first] = entry.split('/');
    if (!first || !VERSION_SLUGS.has(first)) return undefined;
    return entry.replace(/\.mdx?$/, '').replace(/(^|\/)index$/, '');
}

export const collections = {
    docs: defineCollection({
        loader: docsLoader({
            generateId: (options) => versionAwareId(options) ?? defaultId(options),
        }),
        schema: docsSchema({ extend: ExtendDocsSchema }),
    }),
};

/** The loader's own rule, for the pages that are not versioned. */
function defaultId({ entry }: { entry: string }): string {
    return entry
        .replace(/\.mdx?$/, '')
        .replace(/(^|\/)index$/, '')
        .split('/')
        .map((segment) => segment.replace(/[^a-zA-Z0-9-_/]/g, '').toLowerCase())
        .join('/');
}
