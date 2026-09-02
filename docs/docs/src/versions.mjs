/**
 * The versioned docs, in one place.
 *
 * Every manual — Guides, Sillo Start, CLI, ORM & Admin, Pydantic, Advanced —
 * exists once per version, under `src/content/docs/<slug>/`. So a page's URL
 * is `/<version>/<manual>/<page>/` and its first two segments are what decide
 * both the version switcher's current entry and which sidebar groups are
 * visible.
 *
 * This module is imported by `astro.config.mjs` (to generate one sidebar per
 * version) and by the `Sidebar` and `SectionNav` components (to read the
 * version back off the URL). Keeping the list here rather than in the config
 * is what stops the three from disagreeing about which versions exist.
 *
 * The theme docs under `/showcase/` and `/reference/` are deliberately not
 * versioned: they document lucode-starlight, not Sillo, and there is one of
 * them. Neither are the package manuals under `/packages/` — see PACKAGES
 * below for why.
 */

import { existsSync } from 'node:fs';
import { join } from 'node:path';

/**
 * @typedef {object} DocsVersion
 * @property {string} slug   First URL segment, and the content directory name.
 * @property {string} label  What the switcher shows.
 * @property {string} [note] A short qualifier beside the label in the menu.
 * @property {boolean} [preview] Renders the "in development" treatment and
 *   puts a banner at the top of every page in the version.
 */

/** @type {DocsVersion[]} */
export const VERSIONS = [
    { slug: 'v0.x', label: 'v0.x', note: 'current release' },
    { slug: 'v1.0', label: 'v1.0', note: 'in development', preview: true },
];

/**
 * The version an unversioned URL lands on.
 *
 * This is the released one, not the newest one: `/guides/routing/` is what is
 * linked from the marketing site and indexed by search engines, and someone
 * following one of those has `pip install sillo` installed, which is 0.x. The
 * v1.0 manual is reachable from the switcher and says at the top of every page
 * that it describes an unreleased version.
 */
export const DEFAULT_VERSION = 'v0.x';

/**
 * Every manual, in section-bar order. `segment` is the second URL segment.
 *
 * `labels` overrides `label` for one version. The ORM manual needs it: the
 * built-in admin panel was part of that manual in 0.x and is not in the
 * framework at all in 1.0 — it lives in its own package now — so the tab that
 * reads "ORM & Admin" on a 0.x page has to read "ORM" on a 1.0 one.
 */
export const MANUALS = [
    { segment: 'guides', label: 'Guides', home: 'guides/introduction/', icon: 'book' },
    { segment: 'start', label: 'Sillo Start', home: 'start/', icon: 'spark' },
    { segment: 'cli', label: 'CLI', home: 'cli/', icon: 'terminal' },
    {
        segment: 'orm',
        label: 'ORM & Admin',
        labels: { 'v1.0': 'ORM' },
        home: 'orm/',
        icon: 'database',
    },
    { segment: 'pydantic', label: 'Pydantic', home: 'pydantic/', icon: 'shield' },
    { segment: 'advanced', label: 'Advanced', home: 'advanced/', icon: 'layers' },
];

/**
 * The ecosystem packages, each with a manual of its own under `/packages/`.
 *
 * They are not versioned with the core docs. A package releases on its own
 * cadence and declares which framework versions it supports, so filing its
 * pages under `v1.0/` would claim a coupling that does not exist — and would
 * mean copying every page again the next time the framework's version
 * changes.
 *
 * `segment` is the second URL segment, after `packages`.
 */
export const PACKAGES = [
    { segment: 'wire', label: 'Wire', install: 'sillo-wire', module: 'sillo.wire' },
    {
        segment: 'graphql',
        label: 'GraphQL',
        install: 'sillo-graphql',
        module: 'sillo.graphql',
    },
    // Warder is the exception to the naming rule below: it imports under its
    // own name rather than under `sillo.`, because it is not an extension of
    // the framework's surface -- it is an application you mount on yours.
    { segment: 'warder', label: 'Warder', install: 'warder', module: 'warder' },
];

const PACKAGE_BY_SEGMENT = new Map(PACKAGES.map((entry) => [entry.segment, entry]));

/**
 * The package a base-stripped pathname belongs to, if any.
 *
 * `undefined` for `/packages/` itself, which is an index across all of them
 * and so has no single package's sidebar to show.
 *
 * @param {string} pathname A pathname with Astro's `base` already removed.
 * @returns {{ package?: typeof PACKAGES[number] }}
 */
export function packageParts(pathname) {
    const [first, second] = pathname.split('/').filter(Boolean);
    if (first !== 'packages' || !second) return {};
    return { package: PACKAGE_BY_SEGMENT.get(second) };
}

const BY_SLUG = new Map(VERSIONS.map((version) => [version.slug, version]));

/**
 * Split a base-stripped pathname into the version and manual it names.
 *
 * Both come back `undefined` for a path that is not versioned — the theme docs,
 * the 404 page, the root redirect — which is what callers check to decide
 * whether to render the version switcher at all.
 *
 * @param {string} pathname A pathname with Astro's `base` already removed.
 * @returns {{ version?: DocsVersion, manual?: string, rest: string }}
 */
export function routeParts(pathname) {
    const [first, second, ...tail] = pathname.split('/').filter(Boolean);
    const version = first ? BY_SLUG.get(first) : undefined;
    if (!version) return { rest: pathname };
    return {
        version,
        manual: second,
        // Trailing slash included, so callers can concatenate without one.
        rest: [second, ...tail].filter(Boolean).join('/') + (second ? '/' : ''),
    };
}

/**
 * Whether a page exists in a given version.
 *
 * Versions do not hold the same set of pages — the WebSocket rooms guides are
 * under v0.x and not under v1.0, having moved to `sillo-wire`. Checking the
 * content tree rather than maintaining a list means nothing can drift: delete
 * the page and every link to it adjusts.
 *
 * Build-time only, which is why reading the filesystem here is safe: this
 * module is imported by `astro.config.mjs` and by component frontmatter, both
 * of which run in Node and neither of which reaches the browser.
 *
 * The content root is resolved from the working directory rather than from
 * `import.meta.url`. Astro loads the config in Node, where the two agree, but
 * serves component frontmatter through Vite, which rewrites the module's own
 * URL — so the same call answered correctly in one caller and always `false`
 * in the other.
 *
 * @param {string} slug An unversioned page path, e.g. `'guides/routing/'`.
 * @param {string} version A version slug, e.g. `'v1.0'`.
 */
export function pageExistsIn(slug, version) {
    const trimmed = String(slug).replace(/^\/|\/$/g, '');
    if (!trimmed) return false;

    const dir = join(process.cwd(), 'src', 'content', 'docs', version);
    return ['.md', '.mdx', '/index.md', '/index.mdx'].some((suffix) =>
        existsSync(join(dir, trimmed + suffix))
    );
}
