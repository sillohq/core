import type { HookParameters } from '@astrojs/starlight/types';
import type { AstroIntegrationLogger } from 'astro';

type StarlightUserConfig = HookParameters<'config:setup'>['config'];
type ComponentOverride = keyof NonNullable<StarlightUserConfig['components']>;

export const COMPONENT_OVERRIDES: ComponentOverride[] = [
    'ThemeSelect',
    'PageFrame',
    'Header',
    'SiteTitle',
    'Sidebar',
    'TwoColumnContent',
    'ContentPanel',
    'PageTitle',
    'MarkdownContent',
    'Hero',
    'Footer',
    'SocialIcons',
    'Pagination',
    'Search',
    'TableOfContents',
    'PageSidebar',
];

export function override(
    starlightConfig: StarlightUserConfig,
    overrides: ComponentOverride[],
    logger: AstroIntegrationLogger
): StarlightUserConfig['components'] {
    const components = { ...starlightConfig.components };
    for (const override of overrides) {
        if (starlightConfig.components?.[override] != null) {
            const fallback = `lucode-starlight/components/overrides/${override}.astro`;

            logger.warn(
                `A \`<${override}>\` component override is already defined in your Starlight configuration.`
            );
            logger.warn(
                `To use \`lucode-starlight/components\`, either remove this override or manually render the content from \`${fallback}\`.`
            );
            continue;
        }
        components[override] = `lucode-starlight/components/overrides/${override}.astro`;
    }

    return components;
}
