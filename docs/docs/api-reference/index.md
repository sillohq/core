# Nexios API Reference

Welcome to the comprehensive Nexios API reference documentation. This section provides detailed information about all classes, methods, and components in the Nexios framework.

## Core Components

### Application
- [NexiosApp](./application/nexios-app.md) - Main application class
- [Configuration](./application/configuration.md) - Application configuration system
- [Lifecycle Management](./application/lifecycle.md) - Startup and shutdown handlers

### HTTP Handling
- [Request](./http/request.md) - HTTP request object and methods
- [Response](./http/response.md) - HTTP response classes and utilities
- [Cookies](./http/cookies.md) - Cookie handling and management

### Routing System
- [Router](./routing/router.md) - Main routing class
- [Route](./routing/route.md) - Individual route definitions
- [Groups](./routing/groups.md) - Route grouping and organization
- [URL Generation](./routing/url-generation.md) - URL building utilities

### Middleware
- [Base Middleware](./middleware/base.md) - Middleware foundation
- [CORS Middleware](./middleware/cors.md) - Cross-origin resource sharing
- [CSRF Middleware](./middleware/csrf.md) - Cross-site request forgery protection
- [Session Middleware](./middleware/session.md) - Session management
- [Security Middleware](./middleware/security.md) - Security headers and protection

### Dependency Injection
- [Depend](./dependencies/depend.md) - Dependency injection system
- [Context](./dependencies/context.md) - Request context management
- [Resolution](./dependencies/resolution.md) - Dependency resolution process

### WebSocket Support
- [WebSocket](./websockets/websocket.md) - WebSocket connection handling
- [WebSocket Router](./websockets/router.md) - WebSocket routing
- [Channels](./websockets/channels.md) - WebSocket channel management

### Authentication & Authorization
- [Auth Base](./auth/base.md) - Authentication foundation
- [User Models](./auth/users.md) - User management
- [Auth Middleware](./auth/middleware.md) - Authentication middleware
- [Backends](./auth/backends.md) - Authentication backends

### OpenAPI Integration
- [OpenAPI Builder](./openapi/builder.md) - OpenAPI documentation generation
- [Models](./openapi/models.md) - OpenAPI model definitions
- [Configuration](./openapi/config.md) - OpenAPI configuration options

### Testing
- [Test Client](./testing/client.md) - Testing utilities
- [Async Client](./testing/async-client.md) - Asynchronous testing
- [Helpers](./testing/helpers.md) - Testing helper functions

### Utilities
- [Async Helpers](./utils/async-helpers.md) - Asynchronous utility functions
- [Concurrency](./utils/concurrency.md) - Concurrency management
- [Pydantic Integration](./utils/pydantic.md) - Pydantic model utilities

## Quick Navigation

- **Getting Started**: [Application Setup](./application/nexios-app.md)
- **Request Handling**: [Request Object](./http/request.md) | [Response Object](./http/response.md)
- **Routing**: [Router](./routing/router.md) | [Route Definitions](./routing/route.md)
- **Middleware**: [Creating Middleware](./middleware/base.md)
- **Dependencies**: [Dependency Injection](./dependencies/depend.md)
- **WebSockets**: [WebSocket Handling](./websockets/websocket.md)
- **Testing**: [Test Client](./testing/client.md)

## API Conventions

### Method Signatures
All async methods are clearly marked and should be awaited when called.

### Type Annotations
Nexios uses comprehensive type annotations. All parameters and return types are documented.

### Error Handling
Exception types and error conditions are documented for each method.

### Examples
Each API component includes practical usage examples and common patterns.