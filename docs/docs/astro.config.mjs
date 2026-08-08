// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import lucode from 'lucode-starlight';

// https://astro.build/config
const docsBaseUrl = process.env.DOCS_BASE_URL ?? '/';

export default defineConfig({
    base: docsBaseUrl,
    // The domain the docs are actually served from. This feeds every canonical
    // link, og:url and sitemap entry — pointing it at the marketing site made
    // all of them resolve to paths that only exist here, so anything following
    // a canonical URL (search engines included) landed on a 404.
    site: 'https://docs.sillo.build',
    // On Vercel these are handled at the edge as real HTTP redirects; see
    // vercel.json. Astro's own redirects are static meta-refresh pages, which
    // are kept so `astro dev` and `astro preview` behave the same way locally.
    redirects: {
        '/': {
            status: 302,
            destination: '/guides/introduction/',
        },
        '/guides/getting-started/': {
            status: 302,
            destination: '/guides/introduction/',
        },
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
                baseUrl: 'https://github.com/sillohq/core/edit/main/docs',
            },
            lastUpdated: true,
            plugins: [
                lucode({
                    docs: {
                        includeAiUtilities: true,
                    },
                    navLinks: [
                        { label: 'Docs', link: '/guides/introduction/' },
                    ],
                }),
            ],
            social: [
                {
                    icon: 'github',
                    label: 'GitHub',
                    href: 'https://github.com/sillohq/core',
                },
            ],
            sidebar: [
                {
                    label: 'Start Here',
                    items: [
                        { label: 'Introduction', link: '/guides/introduction/' },
                        { label: 'Installation', link: '/guides/installation/' },
                        { label: 'Configuration', link: '/guides/configuration/' },
                        { label: 'Request Lifecycle', link: '/guides/request-lifecycle/' },
                    ],
                },
                {
                    label: 'Building an Application',
                    items: [
                        { label: 'Creating a Project', link: '/guides/start/' },
                        { label: 'Project Structure', link: '/guides/start/structure/' },
                        { label: 'The Console', link: '/guides/start/console/' },
                        { label: 'Database & Migrations', link: '/guides/start/database/' },
                        { label: 'Users & Authentication', link: '/guides/start/authentication/' },
                        { label: 'The Admin Panel', link: '/guides/start/admin/' },
                        { label: 'Background Work', link: '/guides/start/background-work/' },
                        { label: 'Testing', link: '/guides/start/testing/' },
                        { label: 'Deployment', link: '/guides/start/deployment/' },
                    ],
                },
                {
                    label: 'Core Concepts',
                    items: [
                        { label: 'Routing', link: '/guides/routing/' },
                        { label: 'Routers & Sub-Apps', link: '/guides/routers-and-subapps/' },
                        { label: 'Handlers', link: '/guides/handlers/' },
                        { label: 'Middleware', link: '/guides/middleware/' },
                        { label: 'Dependency Injection', link: '/guides/dependency-injection/' },
                        { label: 'URL Normalization', link: '/guides/url-normalization/' },
                        { label: 'Request Information', link: '/guides/request-info/' },
                        { label: 'Handling Inputs', link: '/guides/request-inputs/' },
                        { label: 'Request Parameters', link: '/guides/request-parameters/' },
                        { label: 'Headers', link: '/guides/headers/' },
                        { label: 'Cookies', link: '/guides/cookies/' },
                        { label: 'File Uploads', link: '/guides/file-upload/' },
                        { label: 'Content Negotiation', link: '/guides/content-negotiation/' },
                        { label: 'Sending Responses', link: '/guides/sending-responses/' },
                        { label: 'JSON Serialization', link: '/guides/serialization/' },
                        { label: 'Streaming Responses', link: '/guides/streaming-response/' },
                        { label: 'Pagination', link: '/guides/pagination/' },
                        { label: 'Error Handling', link: '/guides/error-handling/' },
                    ],
                },
                {
                    label: 'Validation',
                    collapsed: true,
                    items: [
                        { label: 'Overview', link: '/guides/validation/' },
                        { label: 'Parameters', link: '/guides/validation/parameters/' },
                        { label: 'Request Bodies', link: '/guides/validation/request-bodies/' },
                        { label: 'Forms & File Uploads', link: '/guides/validation/forms-and-files/' },
                        { label: 'Response Models', link: '/guides/validation/response-models/' },
                        { label: 'Validation Errors', link: '/guides/validation/errors/' },
                        { label: 'Generated Docs', link: '/guides/validation/openapi/' },
                    ],
                },
                {
                    label: 'ORM (Record)',
                    collapsed: true,
                    items: [
                        { label: 'Overview', link: '/guides/record/' },
                        { label: 'Models & Mixins', link: '/guides/record/models/' },
                        { label: 'Scopes & Events', link: '/guides/record/scopes-events/' },
                        { label: 'Casting & Collections', link: '/guides/record/casting-collections/' },
                        { label: 'Query Pagination', link: '/guides/record/pagination/' },
                        { label: 'Transactions & Factories', link: '/guides/record/transactions-factories/' },
                        { label: 'Exceptions & Pydantic', link: '/guides/record/exceptions-pydantic/' },
                        { label: 'Migrations & Seeding', link: '/guides/record/migrations/' },
                    ],
                },
                {
                    label: 'Deep Dive',
                    collapsed: true,
                    items: [
                        { label: 'Startup & Shutdown', link: '/guides/startups-and-shutdowns/' },
                        { label: 'Concurrency & Thread Pool', link: '/guides/concurrency/' },
                        { label: 'Caching', link: '/guides/cache/' },
                        { label: 'Event System', link: '/guides/events/' },
                        { label: 'OpenAPI Overview', link: '/guides/openapi/' },
                        { label: 'Documentation UI', link: '/guides/openapi/documentation-ui/' },
                        { label: 'OpenAPI Parameters', link: '/guides/openapi/request-parameters/' },
                        { label: 'OpenAPI Request Schemas', link: '/guides/openapi/request-schemas/' },
                        { label: 'OpenAPI Response Models', link: '/guides/openapi/response-models/' },
                        { label: 'OpenAPI Auth Docs', link: '/guides/openapi/authentication-documentation/' },
                        { label: 'OpenAPI Customization', link: '/guides/openapi/customizing-openapi-configuration/' },
                        { label: 'Background Work Overview', link: '/guides/work/' },
                        { label: 'Background Tasks', link: '/guides/work/background/' },
                        { label: 'Queues', link: '/guides/work/queue/' },
                        { label: 'Jobs', link: '/guides/work/jobs/' },
                        { label: 'Scheduler', link: '/guides/work/scheduler/' },
                        { label: 'Event Dispatcher', link: '/guides/work/events/' },
                        { label: 'WebSockets Overview', link: '/guides/websockets/' },
                        { label: 'WebSocket Consumers', link: '/guides/websockets/consumer/' },
                        { label: 'WebSocket Channels', link: '/guides/websockets/channels/' },
                        { label: 'WebSocket Groups', link: '/guides/websockets/groups/' },
                        { label: 'WebSocket Events', link: '/guides/websockets/events/' },
                        { label: 'Templating', link: '/guides/templating/' },
                        { label: 'Advanced Templating', link: '/guides/templating/advanced/' },
                        { label: 'Static Files', link: '/guides/static-files/' },
                        { label: 'Frontend (SPA)', link: '/guides/frontend/' },
                        { label: 'Inertia', link: '/guides/inertia/' },
                        { label: 'HTTP Client', link: '/guides/http/client/' },
                        { label: 'Mail Service', link: '/guides/services/mail/' },
                        { label: 'Console Commands', link: '/guides/console/' },
                        { label: 'GraphQL', link: '/guides/graphql/' },
                    ],
                },
                {
                    label: 'Helpers',
                    collapsed: true,
                    items: [
                        { label: 'Overview', link: '/guides/helpers/' },
                        { label: 'Async', link: '/guides/helpers/async/' },
                        { label: 'Crypto', link: '/guides/helpers/crypto/' },
                        { label: 'Deprecation', link: '/guides/helpers/deprecation/' },
                        { label: 'Files', link: '/guides/helpers/files/' },
                        { label: 'Hashing', link: '/guides/helpers/hashing/' },
                        { label: 'HTML', link: '/guides/helpers/html/' },
                        { label: 'JWT', link: '/guides/helpers/jwt/' },
                        { label: 'Network', link: '/guides/helpers/network/' },
                        { label: 'Retry', link: '/guides/helpers/retry/' },
                        { label: 'Strings', link: '/guides/helpers/strings/' },
                        { label: 'Text', link: '/guides/helpers/text/' },
                    ],
                },
                {
                    label: 'Authentication & Authorization',
                    collapsed: true,
                    items: [
                        { label: 'Overview', link: '/guides/authentication/' },
                        { label: 'Users & User Models', link: '/guides/users/' },
                        { label: 'Password Hashing', link: '/guides/hashing/' },
                        { label: 'Protecting Routes', link: '/guides/protecting-routes/' },
                        { label: 'Permissions', link: '/guides/permissions/' },
                        { label: 'JWT Authentication', link: '/guides/jwt-auth/' },
                        { label: 'Session Authentication', link: '/guides/session-auth/' },
                        { label: 'API Keys', link: '/guides/api-keys/' },
                    ],
                },
                {
                    label: 'Security',
                    collapsed: true,
                    items: [
                        { label: 'Security Headers', link: '/guides/security/' },
                        { label: 'CORS', link: '/guides/cors/' },
                        { label: 'CSRF Protection', link: '/guides/csrf/' },
                        { label: 'Rate Limiting', link: '/guides/rate-limiting/' },
                        { label: 'Session Management', link: '/guides/sessions/' },
                    ],
                },
            ],
        }),
    ],

    vite: {
        plugins: [],
    },
});
