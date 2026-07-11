import type { ViteUserConfig } from 'astro';
import type { LucodeStarlightConfig } from './schemas';

export function vitePlugin(config: LucodeStarlightConfig): VitePlugin {
    const moduleId = 'virtual:lucode-starlight-config';
    const resolvedModuleId = `\0${moduleId}`;
    const moduleContent = `export default ${JSON.stringify(config)}`;

    return {
        name: 'vite-plugin-lucode-starlight',
        load(id) {
            return id === resolvedModuleId ? moduleContent : undefined;
        },
        resolveId(id) {
            return id === moduleId ? resolvedModuleId : undefined;
        },
    };
}

type VitePlugin = NonNullable<ViteUserConfig['plugins']>[number];
