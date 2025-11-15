import { defineConfig } from 'vitepress'

// Function to generate dynamic OG image URL
function generateDynamicOGImage(pageData) {
  const baseUrl = 'https://dynamicog.com/og/docs/img'
  const logo = 'https://nexios-labs.github.io/nexios/logo.png'
  const website = 'nexios-labs.github.io'
  const name = 'Nexios Labs'

  // Extract title and description from page data
  let title = pageData?.title || pageData?.frontmatter?.title || 'Nexios'
  let sub = pageData?.description || pageData?.frontmatter?.description || 'Python Web Framework'

  // Handle different page types and improve titles
  const relativePath = pageData?.relativePath || ''

  // Extract title from first heading if no frontmatter title
  if (title === 'Nexios' && pageData?.content) {
    const headingMatch = pageData.content.match(/^#\s+(.+)$/m)
    if (headingMatch) {
      title = headingMatch[1].replace(/[🚀🤔⚡🔄🎯🌐🛣️📖🔐🐍📡🔌🏭]/g, '').trim()
    }
  }

  // Customize subtitle based on page location
  if (relativePath.includes('/guide/')) {
    if (sub === 'Python Web Framework') {
      sub = 'Guide - Learn Nexios'
    } else {
      sub = 'Guide - ' + sub
    }
  } else if (relativePath.includes('/intro/')) {
    if (sub === 'Python Web Framework') {
      sub = 'Introduction - Getting Started'
    } else {
      sub = 'Introduction - ' + sub
    }
  } else if (relativePath.includes('/community/')) {
    if (sub === 'Python Web Framework') {
      sub = 'Community - Extensions & Middleware'
    } else {
      sub = 'Community - ' + sub
    }
  } else if (relativePath.includes('/v2/')) {
    if (sub === 'Python Web Framework') {
      sub = 'v2 Documentation'
    } else {
      sub = 'v2 - ' + sub
    }
    if (!title.includes('v2')) {
      title = title + ' (v2)'
    }
  } else if (relativePath.includes('/howtos/')) {
    if (sub === 'Python Web Framework') {
      sub = 'How-to Guides'
    } else {
      sub = 'How-to - ' + sub
    }
  }

  // Fallback for pages without proper titles
  if (title === 'Nexios' && relativePath) {
    const pathParts = relativePath.replace('.md', '').split('/')
    const lastPart = pathParts[pathParts.length - 1]
    if (lastPart && lastPart !== 'index') {
      title = lastPart.split('-').map(word =>
        word.charAt(0).toUpperCase() + word.slice(1)
      ).join(' ')
    } else if (pathParts.length > 1) {
      // Use parent directory name
      const parentDir = pathParts[pathParts.length - 2]
      title = parentDir.charAt(0).toUpperCase() + parentDir.slice(1)
    }
  }

  // Ensure title and sub are not too long for the image
  if (title.length > 50) {
    title = title.substring(0, 47) + '...'
  }
  if (sub.length > 80) {
    sub = sub.substring(0, 77) + '...'
  }

  // Clean up for URL encoding
  title = encodeURIComponent(title)
  sub = encodeURIComponent(sub)

  const params = new URLSearchParams({
    logo: logo,
    title: title,
    sub: sub,
    name: name,
    website: website,
    dark: 'false'
  })

  return `${baseUrl}?${params.toString()}`
}

export default defineConfig({

  transformHead: ({ pageData }) => {
    const ogImageUrl = generateDynamicOGImage(pageData)
    const pageTitle = pageData?.title ? `${pageData.title} | Nexios` : 'Nexios - Python Web Framework'
    const pageDescription = pageData?.description || 'Nexios is a modern, fast, and secure web framework for Python. It is designed to be easy to use and understand, while also being powerful and flexible.'

    return [
      // Open Graph tags
      ['meta', { property: 'og:title', content: pageTitle }],
      ['meta', { property: 'og:description', content: pageDescription }],
      ['meta', { property: 'og:image', content: ogImageUrl }],
      ['meta', { property: 'og:image:width', content: '1200' }],
      ['meta', { property: 'og:image:height', content: '630' }],
      ['meta', { property: 'og:image:alt', content: `${pageData?.title || 'Nexios'} - Python Web Framework` }],

      // Twitter Card tags
      ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
      ['meta', { name: 'twitter:title', content: pageTitle }],
      ['meta', { name: 'twitter:description', content: pageDescription }],
      ['meta', { name: 'twitter:image', content: ogImageUrl }],
      ['meta', { name: 'twitter:image:alt', content: `${pageData?.title || 'Nexios'} - Python Web Framework` }],
    ]
  },

  head: [

    ['link', { rel: 'icon', href: '/favicon.ico' }],
    ['meta', { name: 'theme-color', content: '#ff7e17' }],
    ['meta', { property: 'og:title', content: "Nexios - Python Web Framework" }],
    ['meta', { property: 'og:description', content: "Nexios is a modern, fast, and secure web framework for Python. It is designed to be easy to use and understand, while also being powerful and flexible." }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'twitter:site', content: '@nexioslabs' }],
  ],


  title: 'Nexios',
  // base: "/nexios/",
  description: 'Nexios is a modern, fast, and secure web framework for Python. It is designed to be easy to use and understand, while also being powerful and flexible.',

  themeConfig: {
    siteTitle: 'Nexios',
    logo: '/logo.png',
    favicon: '/logo.png',
    themeSwitcher: true,

    socialLinks: [
      { icon: "github", link: "https://github.com/nexios-labs/nexios" },
      { icon: "twitter", link: "https://twitter.com/nexioslabs" },
    ],

    search: {
      provider: 'local'
    },

    nav: [
      { text: 'Intro', link: '/intro' },
      { text: 'Guide', link: '/guide/getting-started' },
      { text: "API Reference", link: "/api-reference" },
      { text: "Community", link: "/community" },
      { text: "Discussions", link: "https://github.com/orgs/nexios-labs/discussions" },
      { text: 'Team', link: 'team' },
      { text: 'Blog', link: 'https://blog.nexioslabs.com' },
      {
        text: 'v3  (Latest)',
        items: [
          { text: 'v3', link: '/guide/getting-started' },
          { text: 'v2.11.1', link: '/v2/guide/getting-started' },
          { text: 'Changelog', link: '/changelog' },
          { text: 'Contributing', link: '/community/contribution-guide' },
        ]
      }
    ],

    sidebar: {
      '/intro/': [
        { text: 'What is Nexios?', link: '/intro' },
        { text: "What is Asgi?", link: '/intro/asgi' },
        { text: 'Nexios And FastAPI', link: '/intro/nexios-and-fastapi' },
        { text: "Quick Start", link: '/intro/quick-start' },
        { text: "Core Concepts", link: '/intro/concepts' },
        { text: "Async Python", link: '/intro/async-python' },
        { text: 'Migrating To Nexios', link: '/intro/migrating-to-nexios' },
      ],
      '/community/': [
        { text: 'Overview', link: '/community' },
        { text: 'Installation', link: '/community/installation' },
        {
          text: 'Middleware',
          collapsed: false,
          items: [
            { text: 'ETag', link: '/community/middleware/etag' },
            { text: 'Trusted Host', link: '/community/middleware/trusted-host' },
            { text: 'URL Normalization', link: '/community/middleware/slashes' },
            { text: 'Proxy', link: '/community/middleware/proxy' },
            { text: 'Request ID', link: '/community/middleware/request-id' },
            { text: 'Timeout', link: '/community/middleware/timeout' },
            { text: 'Accepts', link: '/community/middleware/accepts' },
          ]
        },
        {
          text: 'Integrations',
          collapsed: false,
          items: [
            { text: 'Redis', link: '/community/integrations/redis' },
            { text: 'JSON-RPC', link: '/community/integrations/jrpc' },
            { text: 'Background Tasks', link: '/community/integrations/tasks' },
          ]
        },
        { text: "Contribution Guide", link: "/community/contribution-guide" },
        { text: 'Discussions', link: 'https://github.com/orgs/nexios-labs/discussions' },
        { text: 'Team', link: '/team' },
      ],
      "/api-reference/": [
        { text: 'Overview', link: '/api-reference' },
        { text: 'Nexios App', link: '/api-reference/nexios-app' },
        { text: 'Request', link: '/api-reference/request' },
        { text: 'Response', link: '/api-reference/response' },
        { text: 'Route', link: '/api-reference/route' },
        { text: 'Router', link: '/api-reference/router' },
        { text: 'Group', link: '/api-reference/group' },
        { text: 'Class Based Middleware', link: '/api-reference/middleware' },
        { text: 'Depend', link: '/api-reference/dependencies/depend' },
        { text: 'Builder', link: '/api-reference/openapi-builder' },
        { text: 'TestClient', link: '/api-reference/testclient' },
        { text: 'WebSocket', link: '/api-reference/websocket' },
        { text: 'Channel', link: '/api-reference/channel' },
        { text: 'ChannelBox', link: '/api-reference/channelbox' },



      ],
      '/v2/guide/': [

        { text: 'Getting Started', link: '/guide/getting-started' },
        { text: 'CLI', link: '/guide/cli' },
        { text: "Why Nexios?", link: '/guide/why-nexios' },
        {
          text: 'Core Concepts',
          collapsed: false,
          items: [
            { text: 'Routing', link: '/v2/guide/routing' },
            { text: 'Handlers', link: '/v2/guide/handlers' },
            { text: 'Startups and Shutdowns', link: '/v2/guide/startups-and-shutdowns' },
            { text: 'Request Inputs', link: '/v2/guide/request-inputs' },
            { text: 'Configuration', link: '/v2/guide/configuration' },
            { text: 'Sending Responses', link: '/v2/guide/sending-responses' },
            { text: 'Routers and Subapps', link: '/v2/guide/routers-and-subapps' },
            { text: 'Middleware', link: '/v2/guide/middleware' },
          ]
        },
        {
          text: 'Request Lifecycle',
          collapsed: false,
          items: [
            { text: 'Cookies', link: '/v2/guide/cookies' },
            { text: 'Headers', link: '/v2/guide/headers' },
            { text: 'Sessions', link: '/v2/guide/sessions' },
            { text: 'Request Info', link: '/v2/guide/request-info' },
          ]
        },
        {
          text: 'Advanced Topics',
          collapsed: false,
          items: [
            { text: 'Error Handling', link: '/v2/guide/error-handling' },
            { text: 'Pagination', link: '/v2/guide/pagination' },
            { text: 'Authentication', link: '/v2/guide/authentication' },
            { text: "Handler Hooks", link: '/v2/guide/handler-hooks' },
            { text: 'Class Based Handlers', link: '/v2/guide/class-based-handlers' },
            { text: 'Events', link: '/v2/guide/events' },
            { text: 'Streaming Response', link: '/v2/guide/streaming-response' },
            { text: 'Dependency Injection', link: '/v2/guide/dependency-injection' },
            { text: "Templating", link: "/v2/guide/templating/index" },
            { text: 'Static Files', link: '/v2/guide/static-files' },
            { text: 'File Upload', link: '/v2/guide/file-upload' },
            { text: 'Cors', link: '/v2/guide/cors' },
            { text: 'CSRF', link: '/v2/guide/csrf' },
            { text: 'File Router', link: '/v2/guide/file-router' },
            { text: 'Concurrency Utilities', link: '/v2/guide/concurrency' },
            { text: 'Security', link: '/v2/guide/security' },
            { text: 'Pydantic Integration', link: '/v2/guide/pydantic-integration' },
          ]
        },
        {
          text: 'Websockets',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/v2/guide/websockets/index' },
            { text: 'Channels', link: '/v2/guide/websockets/channels' },
            { text: 'Groups', link: '/v2/guide/websockets/groups' },
            { text: 'Events', link: '/v2/guide/websockets/events' },
            { text: 'Consumer', link: '/v2/guide/websockets/consumer' },
          ]
        },
        {
          text: 'OpenAPI',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/v2/guide/openapi/index' },
            { text: 'Response Models with Pydantic', link: '/v2/guide/openapi/response-models' },
            { text: 'Request Schemas', link: '/v2/guide/openapi/request-schemas' },
            { text: 'Request Parameters', link: '/v2/guide/openapi/request-parameters' },
            { text: 'Customizing OpenAPI Config', link: '/v2/guide/openapi/customizing-openapi-configuration' },
            { text: 'Authentication Docs', link: '/v2/guide/openapi/authentication-documentation' },
          ]
        }
      ],
      '/guide/': [

        { text: 'Getting Started', link: '/guide/getting-started' },
        { text: 'CLI', link: '/guide/cli' },
        { text: "Why Nexios?", link: '/guide/why-nexios' },
        {
          text: 'Core Concepts',
          collapsed: false,
          items: [
            { text: 'Routing', link: '/guide/routing' },
            { text: 'Handlers', link: '/guide/handlers' },
            { text: 'Startups and Shutdowns', link: '/guide/startups-and-shutdowns' },
            { text: 'Request Inputs', link: '/guide/request-inputs' },
            { text: 'Configuration', link: '/guide/configuration' },
            { text: 'Sending Responses', link: '/guide/sending-responses' },
            { text: 'Routers and Subapps', link: '/guide/routers-and-subapps' },
            { text: 'Middleware', link: '/guide/middleware' },
          ]
        },
        {
          text: 'Request Lifecycle',
          collapsed: false,
          items: [
            { text: 'Cookies', link: '/guide/cookies' },
            { text: 'Headers', link: '/guide/headers' },
            { text: 'Sessions', link: '/guide/sessions' },
            { text: 'Request Info', link: '/guide/request-info' },
          ]
        },
        {
          text: 'Advanced Topics',
          collapsed: false,
          items: [
            { text: 'Error Handling', link: '/guide/error-handling' },
            { text: 'Pagination', link: '/guide/pagination' },
            { text: 'Authentication', link: '/guide/authentication' },
            { text: "Handler Hooks", link: '/guide/handler-hooks' },
            { text: 'Class Based Handlers', link: '/guide/class-based-handlers' },
            { text: 'Events', link: '/guide/events' },
            { text: 'Streaming Response', link: '/guide/streaming-response' },
            { text: 'Dependency Injection', link: '/guide/dependency-injection' },
            { text: "Templating", link: "/guide/templating/index" },
            { text: 'Static Files', link: '/guide/static-files' },
            { text: 'File Upload', link: '/guide/file-upload' },
            { text: 'Cors', link: '/guide/cors' },
            { text: 'CSRF', link: '/guide/csrf' },
            { text: 'Concurrency Utilities', link: '/guide/concurrency' },
            { text: 'Security', link: '/guide/security' },
            { text: 'Pydantic Integration', link: '/guide/pydantic-integration' },
          ]
        },
        {
          text: 'Websockets',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/guide/websockets/index' },
            { text: 'Channels', link: '/guide/websockets/channels' },
            { text: 'Groups', link: '/guide/websockets/groups' },
            { text: 'Events', link: '/guide/websockets/events' },
            { text: 'Consumer', link: '/guide/websockets/consumer' },
          ]
        },
        {
          text: 'OpenAPI',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/guide/openapi/index' },
            { text: 'Response Models with Pydantic', link: '/guide/openapi/response-models' },
            { text: 'Request Schemas', link: '/guide/openapi/request-schemas' },
            { text: 'Request Parameters', link: '/guide/openapi/request-parameters' },
            { text: 'Customizing OpenAPI Config', link: '/guide/openapi/customizing-openapi-configuration' },
            { text: 'Authentication Docs', link: '/guide/openapi/authentication-documentation' },
          ]
        }
      ]

    }
  },

  markdown: {
    // lineNumbers: true
  },

  ignoreDeadLinks: true,
})