import { describe, expect, it } from 'vitest';
import { PAGE_TITLE_ID } from '../../packages/lucode-starlight/core/config/constants';
import { expressiveCode } from '../../packages/lucode-starlight/core/config/expresive-code';
import { override } from '../../packages/lucode-starlight/core/config/override';
import { LucodeStarlightConfigSchema } from '../../packages/lucode-starlight/core/config/schemas';
import { vitePlugin } from '../../packages/lucode-starlight/core/config/vite';
import { ExtendDocsSchema, heroLayoutSchema } from 'lucode-starlight/schema';

type VitePluginLike = {
    resolveId: ((id: string) => string | undefined) | undefined;
    load: ((id: string) => string | undefined) | undefined;
};

function asPlugin(value: ReturnType<typeof vitePlugin>): VitePluginLike {
    if (!value || Array.isArray(value) || typeof value !== 'object' || 'then' in value) {
        throw new Error('Expected vitePlugin() to return a single Vite plugin object.');
    }

    return value as unknown as VitePluginLike;
}

describe('LucodeStarlightConfigSchema', () => {
    it('applies defaults to optional fields', () => {
        const result = LucodeStarlightConfigSchema.parse({});

        expect(result.docs.includeAiUtilities).toBe(false);
        expect(result.footerText).toContain('Inspired by');
        expect(result.navLinks).toBeUndefined();
    });

    it('accepts nav links with HTML attributes', () => {
        const result = LucodeStarlightConfigSchema.parse({
            navLinks: [
                {
                    label: 'GitHub',
                    link: 'https://github.com/lucas-labs',
                    attrs: {
                        target: '_blank',
                        tabindex: 0,
                        hidden: false,
                    },
                },
            ],
        });

        expect(result.navLinks).toEqual([
            {
                label: 'GitHub',
                link: 'https://github.com/lucas-labs',
                attrs: {
                    target: '_blank',
                    tabindex: 0,
                    hidden: false,
                },
            },
        ]);
    });
});

describe('vitePlugin', () => {
    it('exposes the virtual config module', () => {
        const config = LucodeStarlightConfigSchema.parse({
            docs: { includeAiUtilities: true },
            footerText: 'Custom footer',
        });
        const plugin = asPlugin(vitePlugin(config));

        expect(plugin.resolveId?.('virtual:lucode-starlight-config')).toBe(
            '\0virtual:lucode-starlight-config'
        );
        expect(plugin.resolveId?.('virtual:another-module')).toBeUndefined();
        expect(plugin.load?.('\0virtual:lucode-starlight-config')).toBe(
            `export default ${JSON.stringify(config)}`
        );
        expect(plugin.load?.('virtual:another-module')).toBeUndefined();
    });
});

describe('override', () => {
    it('adds package overrides without replacing existing ones', () => {
        const warnings: string[] = [];
        const logger = {
            warn(message: string) {
                warnings.push(message);
            },
        };

        const components = override(
            {
                components: {
                    Header: './src/components/Header.astro',
                },
            } as never,
            ['Header', 'Footer'] as never,
            logger as never
        );

        expect(components).toEqual({
            Header: './src/components/Header.astro',
            Footer: 'lucode-starlight/components/overrides/Footer.astro',
        });
        expect(warnings).toHaveLength(2);
        expect(warnings[0]).toContain('Header');
        expect(warnings[1]).toContain('lucode-starlight/components/overrides/Header.astro');
    });
});

describe('expressiveCode', () => {
    it('returns false when expressive code is disabled', () => {
        expect(expressiveCode({ expressiveCode: false } as never)).toBe(false);
    });

    it('merges Lucode defaults with user expressive-code settings', () => {
        const result = expressiveCode({
            expressiveCode: {
                themes: ['custom-theme'],
                styleOverrides: {
                    frames: {
                        copyIcon: 'custom-copy-icon',
                    },
                    textMarkers: {
                        markBackground: 'var(--custom-mark)',
                    },
                },
            },
        } as never);

        expect(result).not.toBe(false);
        if (result === false) return;

        expect(result).toMatchObject({
            themes: ['custom-theme'],
            styleOverrides: {
                codeBackground: 'var(--code-background)',
                textMarkers: {
                    markBackground: 'var(--custom-mark)',
                    markBorderColor: 'var(--border)',
                },
                frames: {
                    editorBackground: 'var(--code-background)',
                    copyIcon: 'custom-copy-icon',
                },
            },
        });
    });
});

describe('schema exports', () => {
    it('defaults the hero layout to centered', () => {
        const result = ExtendDocsSchema.parse({
            hero: {
                announcement: {
                    text: 'New release',
                    link: '/guides/getting-started',
                },
            },
        });

        expect(result.hero?.layout).toBe('centered');
    });

    it('rejects unsupported hero layouts', () => {
        expect(() => heroLayoutSchema.parse('stacked')).toThrow();
    });
});

describe('constants', () => {
    it('exports the page title anchor id', () => {
        expect(PAGE_TITLE_ID).toBe('_top');
    });
});
