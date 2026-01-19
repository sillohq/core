export const sidebarIntro = [
  { text: 'What is Nexios?', link: '/intro' },
  { text: "What is Asgi?", link: '/intro/asgi' },
  { text: 'Nexios And FastAPI', link: '/intro/nexios-and-fastapi' },
  { text: "Quick Start", link: '/intro/quick-start' },
  { text: "Core Concepts", link: '/intro/concepts' },
  { text: "Async Python", link: '/intro/async-python' },
  { text: 'Migrating To Nexios', link: '/intro/migrating-to-nexios' },
]

export const sidebarCommunity = [
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
      { text: 'GraphQL', link: '/community/integrations/graphql' },
      { text: 'Background Tasks', link: '/community/integrations/tasks' },
      { text: 'Tortoise ORM', link: '/community/integrations/tortoise' },
    ]
  },
  { text: "Contribution Guide", link: "/community/contribution-guide" },
  { text: 'Discussions', link: 'https://github.com/orgs/nexios-labs/discussions' },
  { text: 'Team', link: '/team' },
]

export const sidebarApiReference = [
  { text: 'Overview', link: '/api-reference' },
  { text: 'Nexios App', link: '/api-reference/nexios-app' },
  { text: 'Request', link: '/api-reference/request' },
  { text: 'Response', link: '/api-reference/response' },
  { text: 'Route', link: '/api-reference/route' },
  { text: 'Router', link: '/api-reference/router' },
  { text: 'Group', link: '/api-reference/group' },
  { text: 'Class Based Middleware', link: '/api-reference/middleware' },
  { text: 'Depend', link: '/api-reference/depend' },
  { text: 'Builder', link: '/api-reference/openapi-builder' },
  { text: 'TestClient', link: '/api-reference/testclient' },
  { text: 'WebSocket', link: '/api-reference/websocket' },
  { text: 'Channel', link: '/api-reference/channel' },
  { text: 'ChannelBox', link: '/api-reference/channelbox' },
]

export const sidebarGuide = [
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
