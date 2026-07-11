import { describe, expect, it, vi } from 'vitest';
import lucodeStarlight from 'lucode-starlight';
import { plugin } from '../../packages/lucode-starlight/core/plugin.js';

function firstCallArg<T>(mock: ReturnType<typeof vi.fn>): T {
    const firstCall = mock.mock.calls[0];

    if (!firstCall) {
        throw new Error('Expected mock to be called at least once.');
    }

    return firstCall[0] as T;
}

function firstPlugin<T>(plugins: T[]): T {
    const plugin = plugins[0];

    if (!plugin) {
        throw new Error('Expected at least one plugin to be registered.');
    }

    return plugin;
}

describe('plugin entrypoint', () => {
    it('re-exports the plugin as the package default', () => {
        expect(lucodeStarlight).toBe(plugin);
    });
});

describe('plugin', () => {
    it('falls back to default config when no user config or custom CSS is provided', () => {
        const updateConfig = vi.fn();
        const addIntegration = vi.fn();

        plugin().hooks['config:setup']?.({
            config: {
                components: {},
                expressiveCode: true,
            },
            logger: {
                warn: vi.fn(),
            },
            updateConfig,
            addIntegration,
        } as never);

        const setupConfig = firstCallArg<{ customCss: string[] }>(updateConfig);
        expect(setupConfig.customCss).toEqual([
            'lucode-starlight/styles/layers',
            'lucode-starlight/styles/theme',
            'lucode-starlight/styles/base',
        ]);

        const integration = firstCallArg<{
            hooks: {
                'astro:config:setup'?: (context: {
                    updateConfig: ReturnType<typeof vi.fn>;
                }) => void;
            };
        }>(addIntegration);
        const integrationUpdateConfig = vi.fn();
        integration.hooks['astro:config:setup']?.({
            updateConfig: integrationUpdateConfig,
        } as never);

        const viteConfig = firstCallArg<{
            vite: { plugins: Array<{ load(id: string): string | undefined }> };
        }>(integrationUpdateConfig);
        const vitePlugin = firstPlugin(viteConfig.vite.plugins);
        expect(vitePlugin.load('\0virtual:lucode-starlight-config')).toContain(
            '"includeAiUtilities":false'
        );
    });

    it('registers config and Vite integration hooks', () => {
        const updateConfig = vi.fn();
        const addIntegration = vi.fn();

        plugin({ docs: { includeAiUtilities: true } }).hooks['config:setup']?.({
            config: {
                components: {},
                customCss: ['./existing.css'],
                expressiveCode: false,
            },
            logger: {
                warn: vi.fn(),
            },
            updateConfig,
            addIntegration,
        } as never);

        expect(updateConfig).toHaveBeenCalledTimes(1);

        const setupConfig = firstCallArg<{
            customCss: string[];
            expressiveCode: boolean;
            components: Record<string, string>;
        }>(updateConfig);
        expect(setupConfig.customCss).toEqual([
            './existing.css',
            'lucode-starlight/styles/layers',
            'lucode-starlight/styles/theme',
            'lucode-starlight/styles/base',
        ]);
        expect(setupConfig.expressiveCode).toBe(false);
        expect(setupConfig.components.Header).toBe(
            'lucode-starlight/components/overrides/Header.astro'
        );
        expect(setupConfig.components.Footer).toBe(
            'lucode-starlight/components/overrides/Footer.astro'
        );

        expect(addIntegration).toHaveBeenCalledTimes(1);

        const integration = firstCallArg<{
            hooks: {
                'astro:config:setup'?: (context: {
                    updateConfig: ReturnType<typeof vi.fn>;
                }) => void;
            };
        }>(addIntegration);
        const integrationUpdateConfig = vi.fn();
        integration.hooks['astro:config:setup']?.({
            updateConfig: integrationUpdateConfig,
        } as never);

        expect(integrationUpdateConfig).toHaveBeenCalledTimes(1);

        const viteConfig = firstCallArg<{
            vite: {
                plugins: Array<{
                    resolveId(id: string): string | undefined;
                    load(id: string): string | undefined;
                }>;
            };
        }>(integrationUpdateConfig);
        const vitePlugin = firstPlugin(viteConfig.vite.plugins);

        expect(vitePlugin.resolveId('virtual:lucode-starlight-config')).toBe(
            '\0virtual:lucode-starlight-config'
        );
        expect(vitePlugin.load('\0virtual:lucode-starlight-config')).toContain(
            '"includeAiUtilities":true'
        );
    });

    it('throws when the user config is invalid', () => {
        const addIntegration = vi.fn();

        plugin({ docs: { includeAiUtilities: 'yes' } as never }).hooks['config:setup']?.({
            config: {
                components: {},
                expressiveCode: true,
            },
            logger: {
                warn: vi.fn(),
            },
            updateConfig: vi.fn(),
            addIntegration,
        } as never);

        const integration = firstCallArg<{
            hooks: {
                'astro:config:setup'?: (context: {
                    updateConfig: ReturnType<typeof vi.fn>;
                }) => void;
            };
        }>(addIntegration);

        expect(() =>
            integration.hooks['astro:config:setup']?.({ updateConfig: vi.fn() } as never)
        ).toThrow(/invalid/);
    });
});
