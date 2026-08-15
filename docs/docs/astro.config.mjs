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
                // Site-wide social defaults. Starlight already emits og:title
                // and og:description per page from the frontmatter; these are
                // the tags it does not set, so a shared docs link renders as a
                // Sillo card instead of a bare URL. A page can still override
                // any of them through its own `head` frontmatter.
                {
                    tag: 'meta',
                    attrs: { property: 'og:site_name', content: 'Sillo Documentation' },
                },
                {
                    tag: 'meta',
                    attrs: { property: 'og:type', content: 'article' },
                },
                {
                    tag: 'meta',
                    attrs: { property: 'og:locale', content: 'en_US' },
                },
                {
                    tag: 'meta',
                    attrs: { name: 'twitter:card', content: 'summary_large_image' },
                },
                {
                    tag: 'meta',
                    attrs: { name: 'twitter:site', content: '@sillohq' },
                },
                {
                    tag: 'meta',
                    attrs: {
                        name: 'keywords',
                        content:
                            'Python web framework, async Python framework, Python backend framework, ASGI framework, Python ORM, Python authentication, Python job queue, Python scheduler, Python WebSockets, full-stack Python',
                    },
                },
            ],
            favicon: '/favicon.svg',
            customCss: ['./src/styles/global.css'],
            // Wraps lucode-starlight's own PageFrame and appends the site
            // footer beneath it. The theme plugin logs a warning that this
            // override already exists and steps aside, which is the documented
            // way to take one of its components over; src/components/PageFrame
            // re-renders the theme version so the layout is unchanged.
            components: {
                PageFrame: './src/components/PageFrame.astro',
                Header: './src/components/Header.astro',
            },
            plugins: [
                lucode({
                    docs: {
                        includeAiUtilities: true,
                    },
                }),
            ],
            social: [
                {
                    icon: 'github',
                    label: 'GitHub',
                    href: 'https://github.com/sillohq/core',
                },
            ],
            /*
             * One sidebar per section of the top bar.
             *
             * lucode-starlight's Sidebar keeps only the groups whose links
             * start with the current URL's first path segment, so a group
             * under `/orm/` is invisible everywhere except `/orm/**`. That is
             * what makes these five manuals independent without five configs:
             * the segment is the divider, and src/components/SectionNav reads
             * the same one to decide which tab is current.
             */
            sidebar: [
                // -- Sillo Start ------------------------------------------
                {
                    label: 'Sillo Start',
                    items: [
                        { label: 'Overview', link: '/start/' },
                        { label: 'Installing', link: '/start/install/' },
                        { label: 'create-app', link: '/start/create-app/' },
                        { label: 'The Official Starters', link: '/start/starters/' },
                    ],
                },
                {
                    label: 'What It Does',
                    items: [
                        { label: 'Project Names', link: '/start/naming/' },
                        { label: 'Personalisation', link: '/start/personalisation/' },
                        { label: 'Secrets & .env', link: '/start/secrets/' },
                        { label: 'After Creating', link: '/start/after-creating/' },
                    ],
                },
                {
                    label: 'Going Further',
                    items: [
                        { label: 'Custom Starters', link: '/start/custom-starters/' },
                        { label: 'Package Managers', link: '/start/package-managers/' },
                        { label: 'Errors & Exit Codes', link: '/start/errors/' },
                        { label: 'Internals', link: '/start/internals/' },
                    ],
                },

                // -- CLI ---------------------------------------------------
                {
                    label: 'The CLI',
                    items: [
                        { label: 'Overview', link: '/cli/' },
                        { label: 'Finding Your Application', link: '/cli/discovery/' },
                        { label: 'Framework Commands', link: '/cli/framework-commands/' },
                    ],
                },
                {
                    label: 'Bundled Commands',
                    items: [
                        { label: 'Database', link: '/cli/database/' },
                        { label: 'Users', link: '/cli/users/' },
                        { label: 'Queues', link: '/cli/queues/' },
                        { label: 'Scheduler', link: '/cli/scheduler/' },
                    ],
                },
                {
                    label: 'Building Your Own',
                    items: [
                        { label: 'Writing Commands', link: '/cli/custom-commands/' },
                        { label: 'Arguments & Options', link: '/cli/arguments/' },
                        { label: 'Output', link: '/cli/output/' },
                        { label: 'Prompts', link: '/cli/prompts/' },
                        { label: 'Styling & Terminal', link: '/cli/styling/' },
                        { label: 'Building a Console', link: '/cli/standalone-consoles/' },
                    ],
                },

                // -- ORM & Admin -------------------------------------------
                {
                    label: 'ORM & Admin',
                    items: [
                        { label: 'Overview', link: '/orm/' },
                        { label: 'Setup', link: '/orm/setup/' },
                        { label: 'Configuration', link: '/orm/configuration/' },
                    ],
                },
                {
                    label: 'Models',
                    items: [
                        { label: 'Models', link: '/orm/models/' },
                        { label: 'Field Reference', link: '/orm/field-reference/' },
                        { label: "Record's Own Fields", link: '/orm/fields/' },
                        { label: 'Relationships', link: '/orm/relationships/' },
                        { label: 'Meta, Indexes & Constraints', link: '/orm/meta/' },
                        { label: 'Mass Assignment', link: '/orm/mass-assignment/' },
                        { label: 'Mixins', link: '/orm/mixins/' },
                        { label: 'Attribute Casting', link: '/orm/casting/' },
                        { label: 'Query Scopes', link: '/orm/scopes/' },
                        { label: 'Model Events', link: '/orm/events/' },
                    ],
                },
                {
                    label: 'Querying',
                    items: [
                        { label: 'The QuerySet API', link: '/orm/queryset/' },
                        { label: 'Field Lookups', link: '/orm/lookups/' },
                        { label: 'Filtering with Q and F', link: '/orm/filtering/' },
                        { label: 'Aggregation', link: '/orm/aggregation/' },
                        { label: 'Eager Loading', link: '/orm/eager-loading/' },
                        { label: 'Values & Projections', link: '/orm/values/' },
                        { label: 'Raw SQL', link: '/orm/raw-sql/' },
                    ],
                },
                {
                    label: 'Reading & Writing',
                    items: [
                        { label: 'Query Helpers', link: '/orm/queries/' },
                        { label: 'Collections', link: '/orm/collections/' },
                        { label: 'Pagination', link: '/orm/pagination/' },
                        { label: 'Bulk Operations', link: '/orm/bulk/' },
                        { label: 'Transactions', link: '/orm/transactions/' },
                        { label: 'Connections', link: '/orm/connections/' },
                    ],
                },
                {
                    label: 'Testing & Schemas',
                    items: [
                        { label: 'Factories', link: '/orm/factories/' },
                        { label: 'Seeding & Fixtures', link: '/orm/seeding/' },
                        { label: 'Pydantic Schemas', link: '/orm/pydantic/' },
                        { label: 'Exception Handlers', link: '/orm/exceptions/' },
                    ],
                },
                {
                    label: 'Migrations',
                    items: [
                        { label: 'How Migrations Work', link: '/orm/migrations/' },
                        { label: 'Applying Them', link: '/orm/migrations-applying/' },
                        { label: 'Programmatically', link: '/orm/migrations-programmatic/' },
                    ],
                },
                {
                    label: 'The Admin Panel',
                    items: [
                        { label: 'Overview', link: '/orm/admin/' },
                        { label: 'Registering Models', link: '/orm/admin-registering/' },
                        { label: 'Customising', link: '/orm/admin-customising/' },
                        { label: 'Permissions & Auth', link: '/orm/admin-permissions/' },
                    ],
                },

                // -- Pydantic ----------------------------------------------
                {
                    label: 'Pydantic',
                    items: [{ label: 'Overview', link: '/pydantic/' }],
                },
                {
                    label: 'The Library',
                    items: [
                        { label: 'Models', link: '/pydantic/models/' },
                        { label: 'Types', link: '/pydantic/types/' },
                        { label: 'Fields', link: '/pydantic/fields/' },
                        { label: 'Validators', link: '/pydantic/validators/' },
                        { label: 'Nested Models', link: '/pydantic/nested/' },
                        { label: 'Serialisation', link: '/pydantic/serialization/' },
                        { label: 'Configuration', link: '/pydantic/config/' },
                        { label: 'Validation Errors', link: '/pydantic/errors/' },
                    ],
                },
                {
                    label: 'In a Sillo App',
                    items: [
                        { label: 'Request Models', link: '/pydantic/request-models/' },
                        { label: 'Parameters', link: '/pydantic/parameters/' },
                        { label: 'Response Models', link: '/pydantic/response-models/' },
                        { label: 'OpenAPI', link: '/pydantic/openapi/' },
                        { label: 'The ORM Bridge', link: '/pydantic/orm-bridge/' },
                        { label: 'Patterns', link: '/pydantic/patterns/' },
                    ],
                },

                // -- Advanced (the internal engineering reference) ---------
                //
                // Grouped exactly as docs-internal/00-TABLE-OF-CONTENTS.md
                // groups them, so the numbered ordering of those files is
                // preserved here rather than in the page titles.
                {
                    label: 'Internal Reference',
                    items: [{ label: 'Contents', link: '/advanced/' }],
                },
                {
                    label: 'Architecture & Foundations',
                    collapsed: true,
                    items: [
                        { label: 'Architecture Overview', link: '/advanced/architecture-overview/' },
                        { label: 'Application Lifecycle', link: '/advanced/application-lifecycle/' },
                        { label: 'Configuration System', link: '/advanced/configuration/' },
                        { label: 'Type System & Encoding', link: '/advanced/types-and-encoding/' },
                    ],
                },
                {
                    label: 'HTTP Layer',
                    collapsed: true,
                    items: [
                        { label: 'Routing System', link: '/advanced/routing/' },
                        { label: 'Middleware Pipeline', link: '/advanced/middleware/' },
                        { label: 'HTTP Request', link: '/advanced/http-request/' },
                        { label: 'HTTP Response', link: '/advanced/http-response/' },
                        { label: 'HTTP Correctness', link: '/advanced/http-correctness/' },
                        { label: 'Exception Handling', link: '/advanced/exception-handling/' },
                    ],
                },
                {
                    label: 'Dependency Injection & Validation',
                    collapsed: true,
                    items: [
                        { label: 'Dependency Injection', link: '/advanced/dependency-injection/' },
                        { label: 'Parameter Extraction', link: '/advanced/parameters/' },
                        { label: 'Validation System', link: '/advanced/validation/' },
                        { label: 'OpenAPI Generation', link: '/advanced/openapi/' },
                    ],
                },
                {
                    label: 'Authentication & Authorization',
                    collapsed: true,
                    items: [
                        { label: 'Authentication Architecture', link: '/advanced/authentication/' },
                        { label: 'Auth Backends', link: '/advanced/auth-backends/' },
                        { label: 'User System', link: '/advanced/users/' },
                        { label: 'Permissions & Groups', link: '/advanced/permissions/' },
                        { label: 'Password Hashing', link: '/advanced/hashing/' },
                    ],
                },
                {
                    label: 'Security',
                    collapsed: true,
                    items: [
                        { label: 'Security Middleware', link: '/advanced/security/' },
                    ],
                },
                {
                    label: 'Database & ORM',
                    collapsed: true,
                    items: [
                        { label: 'Record ORM - Models', link: '/advanced/record-models/' },
                        { label: 'Record ORM - Queries', link: '/advanced/record-queries/' },
                        { label: 'Record ORM - Transactions', link: '/advanced/record-transactions/' },
                        { label: 'Record ORM - Migrations', link: '/advanced/record-migrations/' },
                        { label: 'Record ORM - Factories & Seeders', link: '/advanced/record-factories/' },
                    ],
                },
                {
                    label: 'Background Work',
                    collapsed: true,
                    items: [
                        { label: 'Work - Task System', link: '/advanced/work-tasks/' },
                        { label: 'Work - Queue System', link: '/advanced/work-queues/' },
                        { label: 'Work - Scheduler', link: '/advanced/work-scheduler/' },
                        { label: 'Work - Background Tasks', link: '/advanced/work-background/' },
                    ],
                },
                {
                    label: 'Real-Time',
                    collapsed: true,
                    items: [
                        { label: 'Events System', link: '/advanced/events/' },
                        { label: 'WebSockets', link: '/advanced/websockets/' },
                    ],
                },
                {
                    label: 'Application Features',
                    collapsed: true,
                    items: [
                        { label: 'Session Management', link: '/advanced/sessions/' },
                        { label: 'Cache System', link: '/advanced/cache/' },
                        { label: 'Templating', link: '/advanced/templating/' },
                        { label: 'Mail Service', link: '/advanced/mail/' },
                        { label: 'Console Framework', link: '/advanced/console/' },
                        { label: 'Admin Panel', link: '/advanced/admin/' },
                        { label: 'Pagination', link: '/advanced/pagination/' },
                    ],
                },
                {
                    label: 'Testing & Tools',
                    collapsed: true,
                    items: [
                        { label: 'Test Client', link: '/advanced/test-client/' },
                        { label: 'Helpers & Utilities', link: '/advanced/helpers/' },
                    ],
                },
                {
                    label: 'Ecosystem Packages',
                    collapsed: true,
                    items: [
                        { label: 'sillo-oauth', link: '/advanced/oauth/' },
                        { label: 'sillo-inertia', link: '/advanced/inertia/' },
                        { label: 'sillo-start', link: '/advanced/start/' },
                        { label: '@sillo/atlas', link: '/advanced/atlas/' },
                        { label: 'records-orm', link: '/advanced/records-orm/' },
                    ],
                },
                {
                    label: 'Cross-Cutting Concerns',
                    collapsed: true,
                    items: [
                        { label: 'Architectural Decisions', link: '/advanced/decisions/' },
                        { label: 'Debugging Guide', link: '/advanced/debugging/' },
                        { label: 'Extending Sillo', link: '/advanced/extending/' },
                        { label: 'Change Impact Analysis', link: '/advanced/change-impact/' },
                        { label: 'Glossary', link: '/advanced/glossary/' },
                    ],
                },

                // -- Guides ------------------------------------------------
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
                    label: 'Inertia',
                    collapsed: true,
                    items: [
                        { label: 'Overview', link: '/guides/inertia/' },
                        { label: 'Creating a Project', link: '/guides/inertia/start/' },
                        { label: 'Project Structure', link: '/guides/inertia/structure/' },
                        { label: 'Pages & Props', link: '/guides/inertia/pages/' },
                        { label: 'Forms & Validation', link: '/guides/inertia/forms/' },
                        { label: 'Assets & Deployment', link: '/guides/inertia/assets/' },
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
                    label: 'OAuth2 & Social Login',
                    collapsed: true,
                    items: [
                        { label: 'OAuth2 Overview', link: '/guides/oauth/' },
                        { label: 'OAuth Providers', link: '/guides/oauth/providers/' },
                        { label: 'Persisting the Login', link: '/guides/oauth/persisting-logins/' },
                        { label: 'OAuth in OpenAPI', link: '/guides/oauth/openapi/' },
                        { label: 'The Security Model', link: '/guides/oauth/security/' },
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
