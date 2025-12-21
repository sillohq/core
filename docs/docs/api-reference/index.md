# Nexios API Reference

Welcome to the comprehensive Nexios API reference documentation. This section provides detailed information about all classes, methods, and components in the Nexios framework.

## Core Components

### Application
- [NexiosApp](./nexios-app.md) - Main application class

### HTTP Handling
- [Request](./request.md) - HTTP request object and methods
- [Response](./response.md) - HTTP response classes and utilities

### Routing System
- [Router](./router.md) - Main routing class
- [Route](./route.md) - Individual route definitions
- [Groups](./group.md) - Route grouping and organization

### Middleware
- [Middleware](./middleware.md) - Middleware system and implementation

### Dependency Injection
- [Depend](./depend.md) - Dependency injection system

### WebSocket Support
- [WebSocket](./websocket.md) - WebSocket connection handling
- [Channel](./channel.md) - WebSocket channel management
- [ChannelBox](./channelbox.md) - Channel boxing utilities

### OpenAPI Integration
- [OpenAPI Builder](./openapi-builder.md) - OpenAPI documentation generation

### Testing
- [Test Client](./testclient.md) - Testing utilities

## Quick Navigation

- **Getting Started**: [Application Setup](./nexios-app.md)
- **Request Handling**: [Request Object](./request.md) | [Response Object](./response.md)
- **Routing**: [Router](./router.md) | [Route Definitions](./route.md) | [Route Groups](./group.md)
- **Middleware**: [Middleware System](./middleware.md)
- **Dependencies**: [Dependency Injection](./depend.md)
- **WebSockets**: [WebSocket Handling](./websocket.md) | [Channels](./channel.md) | [ChannelBox](./channelbox.md)
- **Testing**: [Test Client](./testclient.md)
- **OpenAPI**: [Documentation Builder](./openapi-builder.md)

## API Conventions

### Method Signatures
All async methods are clearly marked and should be awaited when called.

### Type Annotations
Nexios uses comprehensive type annotations. All parameters and return types are documented.

### Error Handling
Exception types and error conditions are documented for each method.

### Examples
Each API component includes practical usage examples and common patterns.