// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import lucode from 'lucode-starlight';

// https://astro.build/config
const docsBasePath = process.env.DOCS_BASE_PATH ?? '/lucode-starlight-theme';

export default defineConfig({
    site: 'https://sillo.build',
    redirects: {
        '/': '/guides/getting-started/',
    },

    integrations: [
        starlight({
            title: 'sillo',
            logo: {
                light: './src/assets/logo-black.svg',
                dark: './src/assets/logo-white.svg',
                alt: 'sillo logo',
                replacesTitle: true,
            },
            head: [
                {
                    tag: 'link',
                    attrs: {
                        rel: 'icon',
                        href: '/favicon.svg',
                        type: 'image/svg+xml',
                    },
                },
            ],
            favicon: '/favicon.svg',
            customCss: ['./src/styles/global.css'],
            editLink: {
                baseUrl: 'https://github.com/sillo-labs/sillo/edit/main/docs',
            },
            lastUpdated: true,
            plugins: [
                lucode({
                    docs: {
                        includeAiUtilities: true,
                    },
                    navLinks: [
                        { label: 'Docs', link: '/guides/getting-started/' },
                        { label: 'Community', link: '/community/' },
                        { label: 'Showcase', link: '/showcase/starlight-components/' },
                        { label: 'API', link: '/reference/plugin-api/' },
                    ],
                }),
            ],
            social: [
                {
                    icon: 'github',
                    label: 'GitHub',
                    href: 'https://github.com/sillo-labs/sillo',
                },
            ],
            sidebar: [
                {
                    label: 'Getting Started',
                    items: [
                        { label: 'Why sillo?', link: '/guides/why-nexios/' },
                        { label: 'Getting Started', link: '/guides/getting-started/' },
                        { label: 'Configuration', link: '/guides/configuration/' },
                        { label: 'sillo CLI Guide', link: '/guides/cli/' },
                        { label: 'Customize the Theme', link: '/guides/theming/' },
                    ],
                },
                {
                    label: 'Core Concepts',
                    items: [
                        { label: 'Routing', link: '/guides/routing/' },
                        { label: 'Routers & Sub-Apps', link: '/guides/routers-and-subapps/' },
                        { label: 'Handlers', link: '/guides/handlers/' },
                        { label: 'Class-Based Views', link: '/guides/class-based-handlers/' },
                        { label: 'Middleware', link: '/guides/middleware/' },
                        { label: 'Dependency Injection', link: '/guides/dependency-injection/' },
                    ],
                },
                {
                    label: 'Request & Response',
                    items: [
                        { label: 'Request Information', link: '/guides/request-info/' },
                        { label: 'Handling Inputs', link: '/guides/request-inputs/' },
                        { label: 'Request Parameters', link: '/guides/request-parameters/' },
                        { label: 'Headers', link: '/guides/headers/' },
                        { label: 'Sending Responses', link: '/guides/sending-responses/' },
                        { label: 'Streaming Responses', link: '/guides/streaming-response/' },
                        { label: 'Error Handling', link: '/guides/error-handling/' },
                    ],
                },
                {
                    label: 'Security',
                    items: [
                        { label: 'Authentication', link: '/guides/authentication/' },
                        { label: 'CORS', link: '/guides/cors/' },
                        { label: 'CSRF', link: '/guides/csrf/' },
                        { label: 'Cookies', link: '/guides/cookies/' },
                        { label: 'Session Management', link: '/guides/sessions/' },
                        { label: 'Security Middleware', link: '/guides/security/' },
                    ],
                },
                {
                    label: 'Features',
                    items: [
                        { label: 'Concurrency', link: '/guides/concurrency/' },
                        { label: 'Pagination', link: '/guides/pagination/' },
                        { label: 'Event System', link: '/guides/events/' },
                        { label: 'Pydantic Integration', link: '/guides/pydantic-integration/' },
                        { label: 'Static Files', link: '/guides/static-files/' },
                        { label: 'File Upload', link: '/guides/file-upload/' },
                        { label: 'Frontend (SPA)', link: '/guides/frontend/' },
                        { label: 'Startup & Shutdown', link: '/guides/startups-and-shutdowns/' },
                    ],
            },
            {
                label: 'Work',
                collapsed: false,
                items: [
                    { label: 'Overview', link: '/guides/work/' },
                    { label: 'Background Tasks', link: '/guides/work/background/' },
                    { label: 'Queue', link: '/guides/work/queue/' },
                    { label: 'Scheduler', link: '/guides/work/scheduler/' },
                    { label: 'Events', link: '/guides/work/events/' },
                    { label: 'Jobs', link: '/guides/work/jobs/' },
                ],
            },
            {
                label: 'Services',
                items: [
                    { label: 'Mail', link: '/guides/services/mail/' },
                ],
            },
            {
                label: 'Helpers',
                items: [
                    { label: 'Overview', link: '/guides/helpers/' },
                    { label: 'JWT', link: '/guides/helpers/jwt/' },
                    { label: 'Network', link: '/guides/helpers/network/' },
                    { label: 'Retry', link: '/guides/helpers/retry/' },
                    { label: 'Strings', link: '/guides/helpers/strings/' },
                    { label: 'Text', link: '/guides/helpers/text/' },
                    { label: 'HTML', link: '/guides/helpers/html/' },
                    { label: 'Files', link: '/guides/helpers/files/' },
                    { label: 'Hashing', link: '/guides/helpers/hashing/' },
                    { label: 'Crypto', link: '/guides/helpers/crypto/' },
                    { label: 'Deprecation', link: '/guides/helpers/deprecation/' },
                ],
            },
            {
                label: 'OpenAPI',
                    items: [
                        { label: 'Overview', link: '/guides/openapi/' },
                        { label: 'Request Parameters', link: '/guides/openapi/request-parameters/' },
                        { label: 'Request Schemas', link: '/guides/openapi/request-schemas/' },
                        { label: 'Response Models', link: '/guides/openapi/response-models/' },
                        { label: 'Authentication Docs', link: '/guides/openapi/authentication-documentation/' },
                        { label: 'Custom Config', link: '/guides/openapi/customizing-openapi-configuration/' },
                    ],
                },
                {
                    label: 'WebSockets',
                    items: [
                        { label: 'Overview', link: '/guides/websockets/' },
                        { label: 'Channels', link: '/guides/websockets/channels/' },
                        { label: 'Consumers', link: '/guides/websockets/consumer/' },
                        { label: 'Groups', link: '/guides/websockets/groups/' },
                        { label: 'Events Integration', link: '/guides/websockets/events/' },
                    ],
                },
                {
                    label: 'Templating',
                    items: [
                        { label: 'Overview', link: '/guides/templating/' },
                        { label: 'Advanced', link: '/guides/templating/advanced/' },
                    ],
                },
                {
                    label: 'Community',
                    items: [
                        { label: 'Overview', link: '/community/' },
                        { label: 'Installation', link: '/community/installation/' },
                        { label: 'Contribution Guide', link: '/community/contribution-guide/' },
                    ],
                },
                {
                    label: 'Community Integrations',
                    items: [
                        { label: 'GraphQL', link: '/community/integrations/graphql/' },
                        { label: 'JSON-RPC', link: '/community/integrations/jrpc/' },
                        { label: 'Mail', link: '/community/integrations/mail/' },
                        { label: 'Redis', link: '/community/integrations/redis/' },
                        { label: 'Scheduler', link: '/community/integrations/scheduler/' },
                        { label: 'Background Tasks', link: '/community/integrations/tasks/' },
                        { label: 'Tortoise ORM', link: '/community/integrations/tortoise/' },
                    ],
                },
                {
                    label: 'Community Middleware',
                    items: [
                        { label: 'Accepts', link: '/community/middleware/accepts/' },
                        { label: 'ETag', link: '/community/middleware/etag/' },
                        { label: 'Proxy', link: '/community/middleware/proxy/' },
                        { label: 'Request ID', link: '/community/middleware/request-id/' },
                        { label: 'Slashes', link: '/community/middleware/slashes/' },
                        { label: 'Timeout', link: '/community/middleware/timeout/' },
                        { label: 'Trusted Host', link: '/community/middleware/trusted-host/' },
                    ],
                },
                {
                    label: 'Showcase',
                    items: [
                        { label: 'Starlight Components', link: '/showcase/starlight-components/' },
                        { label: 'Splash Pages', link: '/showcase/splash-pages/' },
                        { label: 'Typography', link: '/showcase/typography/' },
                    ],
                },
                {
                    label: 'Splash Examples',
                    items: [
                        { label: 'Centered', link: '/showcase/splash/centered/' },
                        { label: 'Centered Top', link: '/showcase/splash/centered-top/' },
                        { label: 'Split Left', link: '/showcase/splash/split-left/' },
                        { label: 'Split Right', link: '/showcase/splash/split-right/' },
                        { label: 'Banner', link: '/showcase/splash/banner/' },
                    ],
                },
                {
                    label: 'Reference',
                    items: [
                        { label: 'Theme Components', link: '/reference/components/' },
                        { label: 'Plugin API', link: '/reference/plugin-api/' },
                    ],
                },
            ],
        }),
    ],

    vite: {
        plugins: [],
    },
});
