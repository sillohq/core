import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Nexios - Async Python Web Framework',
  description: 'Build high-performance async APIs with Nexios, a modern Python web framework featuring clean architecture, zero boilerplate, and excellent developer experience.',
  
  theme: {
    sidebar: [
      {
        text: 'Getting Started',
        items: [
          { text: 'Installation', link: '/guide/getting-started' },
          { text: 'Quick Start', link: '/guide/quick-start' },
          { text: 'Why Nexios?', link: '/guide/why-nexios' }
        ]
      },
      {
        text: 'Essential Guides',
        items: [
          { text: 'Configuration', link: '/guide/configuration' },
          { text: 'Routing', link: '/guide/routing' },
          { text: 'Middleware', link: '/guide/middleware' },
          { text: 'Request & Response', link: '/guide/request-response' }
        ]
      },
      {
        text: 'Features',
        items: [
          { text: '📚 Summary', link: '/summary' },
          { text: 'Sessions', link: '/guide/sessions' },
          { text: 'CORS', link: '/guide/cors' },
          { text: 'CSRF', link: '/guide/csrf' },
          { text: 'Authentication', link: '/v2/guide/authentication' },
          { text: 'WebSockets', link: '/guide/websockets' },
          { text: 'Templates', link: '/guide/templating' },
          { text: 'OpenAPI', link: '/guide/openapi' }
        ]
      },
      {
        text: 'Advanced',
        items: [
          { text: 'Dependency Injection', link: '/guide/dependency-injection' },
          { text: 'Testing', link: '/guide/testing' },
          { text: 'Database', link: '/guide/database' },
          { text: 'Deployment', link: '/guide/deployment' }
        ]
      },
      {
        text: 'API Reference',
        items: [
          { text: 'Nexios API', link: '/api-reference/' },
          { text: 'CLI Reference', link: '/guide/cli' }
        ]
      }
    ]
  },
  
  head: [
    ['meta', { property: 'og:title', content: 'Nexios - Async Python Web Framework' }],
    ['meta', { property: 'og:description', content: 'Build high-performance async APIs with Nexios, a modern Python web framework featuring clean architecture, zero boilerplate, and excellent developer experience.' }],
    ['meta', { name: 'description', content: 'Build high-performance async APIs with Nexios, a modern Python web framework featuring clean architecture, zero boilerplate, and excellent developer experience.' }],
    ['meta', { name: 'keywords', content: 'python, async, web framework, api, asgi, fast, performance' }],
    ['meta', { name: 'author', content: 'Nexios Labs' }],
    ['meta', { name: 'viewport', content: 'width=device-width, initial-scale=1.0' }],
    ['link', { rel: 'icon', href: '/favicon.ico' }],
    ['meta', { name: 'theme-color', content: '#4CAF50' }]
  ],
  
  vite: {
    optimizeDeps: {
      include: ['vitepress']
    }
  }
})
