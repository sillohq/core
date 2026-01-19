export const sidebarV2 = [
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
]
