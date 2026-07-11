import type { StarlightPlugin } from '@astrojs/starlight/types';
import { override, COMPONENT_OVERRIDES } from './config/override';
import { expressiveCode } from './config/expresive-code';
import { vitePlugin } from './config/vite';
import {
    LucodeStarlightConfigSchema,
    type LucodeStarlightConfig,
    type LucodeStarlightUserConfig,
} from './config/schemas';

const parseConfig = (userConfig?: LucodeStarlightUserConfig): LucodeStarlightConfig => {
    const parsedConfig = LucodeStarlightConfigSchema.safeParse(userConfig ?? {});

    if (!parsedConfig.success) {
        throw new Error(
            `The provided plugin configuration for lucode-starlight is invalid.\n${parsedConfig.error.issues.map((issue) => issue.message).join('\n')}`
        );
    }

    return parsedConfig.data;
};

const plugin = (userConfig?: LucodeStarlightUserConfig): StarlightPlugin =>
    ({
        name: 'lucode-starlight',
        hooks: {
            'config:setup': ({ config, logger, updateConfig, addIntegration }) => {
                updateConfig({
                    components: override(config, COMPONENT_OVERRIDES, logger),
                    customCss: [
                        ...(config.customCss ?? []),
                        'lucode-starlight/styles/layers',
                        'lucode-starlight/styles/theme',
                        'lucode-starlight/styles/base',
                    ],
                    expressiveCode: expressiveCode(config),
                });

                addIntegration({
                    name: 'lucode-starlight-integration',
                    hooks: {
                        'astro:config:setup': ({ updateConfig }) => {
                            updateConfig({
                                vite: { plugins: [vitePlugin(parseConfig(userConfig))] },
                            });
                        },
                    },
                });
            },
            // 'i18n:setup': function ({ injectTranslations }) {
            //     injectTranslations(translations);
            // },
        },
    }) satisfies StarlightPlugin;

export { plugin };
