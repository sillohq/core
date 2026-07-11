declare module 'virtual:lucode-starlight-config' {
    const LucodeStarlightConfig: import('./core/config/schemas').LucodeStarlightConfig;
    export default LucodeStarlightConfig;
}

declare module 'virtual:starlight/user-config' {
    const Config: import('@astrojs/starlight/types').StarlightConfig;
    export default Config;
}

declare module 'virtual:starlight/user-images' {
    type ImageMetadata = import('astro').ImageMetadata;
    export const logos: {
        dark?: ImageMetadata;
        light?: ImageMetadata;
    };
}

declare module 'virtual:starlight/pagefind-config' {
    export const pagefindUserConfig: Partial<
        Extract<import('@astrojs/starlight/types').StarlightConfig['pagefind'], object>
    >;
}

declare module 'virtual:starlight/project-context' {
    const ProjectContext: {
        root: string;
        srcDir: string;
        trailingSlash: import('astro').AstroConfig['trailingSlash'];
        build: {
            format: import('astro').AstroConfig['build']['format'];
        };
        legacyCollections: boolean;
    };
    export default ProjectContext;
}

declare module 'virtual:starlight/components/LastUpdated' {
    const LastUpdated: typeof import('@astrojs/starlight/components/LastUpdated.astro').default;
    export default LastUpdated;
}

declare module 'virtual:starlight/components/Pagination' {
    const Pagination: typeof import('@astrojs/starlight/components/Pagination.astro').default;
    export default Pagination;
}

declare module 'virtual:starlight/components/EditLink' {
    const EditLink: typeof import('@astrojs/starlight/components/EditLink.astro').default;
    export default EditLink;
}
