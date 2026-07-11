import type { StarlightExpressiveCodeOptions } from '@astrojs/starlight/expressive-code';
import type { StarlightUserConfig } from '@astrojs/starlight/types';

const createInlineSvgUrl = (svgContents: string): string => {
    const inlineSvg = svgContents.replace(
        /^(\s*<svg)\s+([^>]+)\s*(\/?>)/,
        (_match, tagStart: string, attributes: string, tagEnd: string) => {
            const sanitizedAttributes = attributes.replaceAll(
                /(?:width|height)\s*=\s*(?:(["'])[^"']*\1|\d+)\s*/g,
                ''
            );

            return `${tagStart} ${sanitizedAttributes.trim()}${tagEnd}`;
        }
    );

    return `url("data:image/svg+xml,${encodeURIComponent(inlineSvg)}")`;
};

export const expressiveCode = (
    config: StarlightUserConfig
): boolean | StarlightExpressiveCodeOptions => {
    const userExpressiveCodeConfig =
        config.expressiveCode === false || config.expressiveCode === true
            ? {}
            : config.expressiveCode;

    return config.expressiveCode === false
        ? false
        : {
              themes: ['github-dark-default', 'github-light-default'],
              ...userExpressiveCodeConfig,
              styleOverrides: {
                  codeBackground: 'var(--code-background)',
                  borderWidth: '0px',
                  borderRadius: 'calc(var(--radius) + 4px)',
                  gutterBorderWidth: '0px',
                  ...userExpressiveCodeConfig?.styleOverrides,
                  frames: {
                      editorBackground: 'var(--code-background)',
                      editorActiveTabBackground: 'var(--gray-5)',
                      editorActiveTabForeground: 'var(--foreground)',
                      editorTabBarBackground: 'var(--gray-6)',
                      editorTabBarBorderColor: 'var(--border)',
                      editorTabBarBorderBottomColor: 'var(--border)',
                      terminalBackground: 'var(--code-background)',
                      terminalTitlebarBackground: 'var(--gray-6)',
                      terminalTitlebarBorderBottomColor: 'var(--border)',
                      terminalTitlebarForeground: 'var(--muted-foreground)',
                      shadowColor: 'transparent',
                      copyIcon: createInlineSvgUrl(
                          `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-clipboard"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"></rect><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path></svg>`
                      ),
                      ...userExpressiveCodeConfig?.styleOverrides?.frames,
                  },
                  textMarkers: {
                      markBackground: 'var(--mark-background)',
                      markBorderColor: 'var(--border)',
                      ...userExpressiveCodeConfig?.styleOverrides?.textMarkers,
                  },
              },
          };
};
