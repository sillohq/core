# Dependency Injection System

Nexios provides a powerful dependency injection system that allows you to manage shared resources, services, and state across your application in a clean and testable way.

## 📋 Depend Class

The `Depend` class is the core component for dependency injection in Nexios.

### Class Definition

```python
class Depend:
    def __init__(self, dependency: Optional[Callable[..., Any]] = None)
```

### Basic Usage

```python
from nexios import Depend

async def get_database():
    return Database(url="postgresql://...")

@app.get("/users")
async def list_users(request: Request, response: Response, db=Depend(get_database)):
    users = await db.query("SELECT * FROM users")
    return response.json(users)
```

## 🔧 Dependency Types

### Simple Dependencies
Functions that return a value.

```python
async def get_settings():
    return {
        "api_key": "secret",
        "debug": True,
        "max_connections": 100
    }

@app.get("/config")
async def get_config(request: Request, response: Response, settings=Depend(get_settings)):
    return response.json(settings)
```

### Class-based Dependencies
Using classes as dependency providers.

```python
class DatabaseService:
    def __init__(self):
        self.connection = None
    
    async def connect(self):
        self.connection = await create_connection()
        return self
    
    async def query(self, sql):
        return await self.connection.execute(sql)

async def get_db_service():
    service = DatabaseService()
    await service.connect()
    return service

@app.get("/data")
async def get_data(request: Request, response: Response, db=Depend(get_db_service)):
    result = await db.query("SELECT * FROM items")
    return response.json(result)
```

### Context-aware Dependencies
Dependencies that access request context.

```python
async def get_current_user(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(401, "Authentication required")
    
    user = await verify_token(token)
    if not user:
        raise HTTPException(401, "Invalid token")
    
    return user

@app.get("/profile")
async def get_profile(request: Request, response: Response, user=Depend(get_current_user)):
    return response.json({
        "id": user.id,
        "name": user.name,
        "email": user.email
    })
```

## 🔗 Nested Dependencies

Dependencies can depend on other dependencies, creating a dependency tree.

```python
async def get_database():
    return Database()

async def get_user_service(db=Depend(get_database)):
    return UserService(db)

async def get_current_user(request: Request, user_service=Depend(get_user_service)):
    token = request.headers.get("Authorization")
    return await user_service.get_user_by_token(token)

@app.get("/dashboard")
async def dashboard(
    request: Request, 
    response: Response, 
    user=Depend(get_current_user),
    user_service=Depend(get_user_service)
):
    # Both user and user_service are available
    # user_service reuses the same database instance
    stats = await user_service.get_user_stats(user.id)
    return response.json(stats)
```

## 🧹 Generator Dependencies (Cleanup)

Use generator functions for dependencies that need cleanup.

```python
async def get_database_connection():
    connection = await create_connection()
    try:
        yield connection
    finally:
        await connection.close()

@app.get("/users")
async def list_users(request: Request, response: Response, db=Depend(get_database_connection)):
    # Connection is automatically closed after the request
    users = await db.query("SELECT * FROM users")
    return response.json(users)
```

### Synchronous Generator Dependencies

```python
def get_file_handle():
    file = open("data.txt", "r")
    try:
        yield file
    finally:
        file.close()

@app.get("/file-content")
async def read_file(request: Request, response: Response, file=Depend(get_file_handle)):
    content = file.read()
    return response.text(content)
```

## 🏗️ Application-level Dependencies

Dependencies can be registered at the application level to apply to all routes.

```python
async def get_database():
    return Database()

async def get_logger():
    return Logger()

app = NexiosApp(
    dependencies=[
        Depend(get_database),
        Depend(get_logger)
    ]
)

@app.get("/users")
async def list_users(
    request: Request, 
    response: Response, 
    db=Depend(get_database),  # Available automatically
    logger=Depend(get_logger)  # Available automatically
):
    logger.info("Listing users")
    users = await db.query("SELECT * FROM users")
    return response.json(users)
```

## 🛣️ Router-level Dependencies

Dependencies can be applied to specific routers.

```python
async def get_admin_user(request: Request):
    user = await get_current_user(request)
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user

admin_router = Router(
    prefix="/admin",
    dependencies=[Depend(get_admin_user)]
)

@admin_router.get("/users")
async def admin_list_users(
    request: Request, 
    response: Response, 
    admin=Depend(get_admin_user)  # Automatically injected
):
    users = await get_all_users_admin()
    return response.json(users)

app.mount_router(admin_router)
```

## 📋 Context Class

The `Context` class provides access to request-scoped information within dependencies.

### Context Definition

```python
class Context:
    def __init__(
        self,
        request: Optional[Request] = None,
        user: Optional[BaseUser] = None,
        base_app: Optional[NexiosApp] = None,
        app: Optional[Router] = None,
        **kwargs: Dict[str, Any],
    )
```

### Using Context in Dependencies

```python
from nexios.dependencies import Context, current_context

async def get_request_info(ctx: Context = Depend(lambda: current_context.get())):
    return {
        "method": ctx.request.method,
        "path": ctx.request.path,
        "user_agent": ctx.request.user_agent
    }

@app.get("/request-info")
async def request_info(request: Request, response: Response, info=Depend(get_request_info)):
    return response.json(info)
```

## 🚀 Advanced Dependency Patterns

### Conditional Dependencies

```python
async def get_cache(request: Request):
    if request.app.config.get("cache_enabled", False):
        return RedisCache()
    else:
        return MemoryCache()

@app.get("/data")
async def get_data(request: Request, response: Response, cache=Depend(get_cache)):
    cached_data = await cache.get("data")
    if cached_data:
        return response.json(cached_data)
    
    # Fetch and cache data
    data = await fetch_data()
    await cache.set("data", data, ttl=300)
    return response.json(data)
```

### Factory Dependencies

```python
def create_service_factory(service_type: str):
    async def get_service():
        if service_type == "database":
            return DatabaseService()
        elif service_type == "cache":
            return CacheService()
        else:
            raise ValueError(f"Unknown service type: {service_type}")
    return get_service

# Create specific service dependencies
get_db_service = create_service_factory("database")
get_cache_service = create_service_factory("cache")

@app.get("/data")
async def get_data(
    request: Request, 
    response: Response, 
    db=Depend(get_db_service),
    cache=Depend(get_cache_service)
):
    # Use both services
    pass
```

### Scoped Dependencies

```python
class RequestScopedService:
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.data = {}
    
    def set_data(self, key, value):
        self.data[key] = value
    
    def get_data(self, key):
        return self.data.get(key)

async def get_request_scoped_service(request: Request):
    request_id = request.headers.get("X-Request-ID", "unknown")
    return RequestScopedService(request_id)

@app.get("/scoped-data")
async def scoped_data(
    request: Request, 
    response: Response, 
    service=Depend(get_request_scoped_service)
):
    service.set_data("timestamp", time.time())
    return response.json({
        "request_id": service.request_id,
        "data": service.data
    })
```

## 💾 Dependency Caching and Lifecycle

### Per-request Caching
Dependencies are cached per request by default.

```python
call_count = 0

async def expensive_dependency():
    global call_count
    call_count += 1
    print(f"Expensive operation called {call_count} times")
    await asyncio.sleep(1)  # Simulate expensive operation
    return {"result": "expensive_data"}

@app.get("/test1")
async def test1(request: Request, response: Response, data=Depend(expensive_dependency)):
    return response.json(data)

@app.get("/test2")
async def test2(request: Request, response: Response, data=Depend(expensive_dependency)):
    # Same dependency, but called in different request - will execute again
    return response.json(data)

@app.get("/test-both")
async def test_both(
    request: Request, 
    response: Response, 
    data1=Depend(expensive_dependency),
    data2=Depend(expensive_dependency)  # Same request - cached, won't execute again
):
    return response.json({"data1": data1, "data2": data2})
```

### Cleanup Handling

```python
async def get_database_with_cleanup():
    print("Opening database connection")
    db = await Database.connect()
    
    try:
        yield db
    finally:
        print("Closing database connection")
        await db.close()

@app.get("/users")
async def list_users(request: Request, response: Response, db=Depend(get_database_with_cleanup)):
    # Database connection is automatically closed after response
    users = await db.query("SELECT * FROM users")
    return response.json(users)
```

## 🧪 Testing with Dependencies

### Dependency Overrides for Testing

```python
# Production dependency
async def get_real_database():
    return RealDatabase()

# Test dependency
async def get_test_database():
    return MockDatabase()

# In tests
def test_users_endpoint():
    app = create_app()
    
    # Override dependency for testing
    app.dependency_overrides[get_real_database] = get_test_database
    
    client = TestClient(app)
    response = client.get("/users")
    
    assert response.status_code == 200
```

### Mock Dependencies

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_user_service():
    service = AsyncMock()
    service.get_all_users.return_value = [
        {"id": 1, "name": "Test User"}
    ]
    return service

async def test_list_users(mock_user_service):
    async def get_mock_service():
        return mock_user_service
    
    # Create app with mock dependency
    app = NexiosApp()
    
    @app.get("/users")
    async def list_users(request, response, service=Depend(get_mock_service)):
        users = await service.get_all_users()
        return response.json(users)
    
    async with TestClient(app) as client:
        response = await client.get("/users")
        assert response.status_code == 200
        assert len(response.json()) == 1
```

## ⚠️ Error Handling in Dependencies

### Dependency Validation

```python
async def get_validated_database():
    try:
        db = await Database.connect()
        await db.ping()  # Validate connection
        return db
    except ConnectionError:
        raise HTTPException(503, "Database unavailable")
    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")

@app.get("/users")
async def list_users(request: Request, response: Response, db=Depend(get_validated_database)):
    # Database is guaranteed to be connected
    users = await db.query("SELECT * FROM users")
    return response.json(users)
```

### Graceful Degradation

```python
async def get_cache_with_fallback():
    try:
        cache = await RedisCache.connect()
        return cache
    except ConnectionError:
        # Fallback to memory cache
        return MemoryCache()

@app.get("/data")
async def get_data(request: Request, response: Response, cache=Depend(get_cache_with_fallback)):
    # Will work with either Redis or memory cache
    data = await cache.get("key")
    return response.json(data or {})
```

## ⚡ Performance Considerations

### Lazy Loading

```python
class LazyService:
    def __init__(self):
        self._connection = None
    
    async def get_connection(self):
        if self._connection is None:
            self._connection = await create_expensive_connection()
        return self._connection

async def get_lazy_service():
    return LazyService()

@app.get("/data")
async def get_data(request: Request, response: Response, service=Depend(get_lazy_service)):
    # Connection is only created when needed
    connection = await service.get_connection()
    data = await connection.fetch_data()
    return response.json(data)
```

### Connection Pooling

```python
from asyncio import Queue

class ConnectionPool:
    def __init__(self, max_connections=10):
        self.pool = Queue(maxsize=max_connections)
        self.max_connections = max_connections
        self._initialized = False
    
    async def initialize(self):
        if not self._initialized:
            for _ in range(self.max_connections):
                conn = await create_connection()
                await self.pool.put(conn)
            self._initialized = True
    
    async def get_connection(self):
        await self.initialize()
        return await self.pool.get()
    
    async def return_connection(self, conn):
        await self.pool.put(conn)

# Global connection pool
connection_pool = ConnectionPool()

async def get_pooled_connection():
    conn = await connection_pool.get_connection()
    try:
        yield conn
    finally:
        await connection_pool.return_connection(conn)

@app.get("/users")
async def list_users(request: Request, response: Response, conn=Depend(get_pooled_connection)):
    users = await conn.query("SELECT * FROM users")
    return response.json(users)
```

## ✨ Best Practices

1. **Keep dependencies focused** - Each dependency should have a single responsibility
2. **Use generators for cleanup** - Always clean up resources properly
3. **Handle errors gracefully** - Provide meaningful error messages
4. **Cache expensive operations** - Leverage per-request caching
5. **Test with mocks** - Use dependency overrides for testing
6. **Document dependencies** - Clearly document what each dependency provides
7. **Avoid circular dependencies** - Design dependency graphs carefully
8. **Use type hints** - Provide clear type annotations for better IDE support
9. **Consider lifecycle** - Think about when dependencies are created and destroyed
10. **Monitor performance** - Profile dependency resolution for bottlenecks

## 💡 Common Patterns

### Repository Pattern

```python
class UserRepository:
    def __init__(self, db):
        self.db = db
    
    async def get_all(self):
        return await self.db.query("SELECT * FROM users")
    
    async def get_by_id(self, user_id):
        return await self.db.query("SELECT * FROM users WHERE id = ?", user_id)
    
    async def create(self, user_data):
        return await self.db.execute("INSERT INTO users ...", user_data)

async def get_user_repository(db=Depend(get_database)):
    return UserRepository(db)

@app.get("/users")
async def list_users(request: Request, response: Response, repo=Depend(get_user_repository)):
    users = await repo.get_all()
    return response.json(users)
```

### Service Layer Pattern

```python
class UserService:
    def __init__(self, repository, cache):
        self.repository = repository
        self.cache = cache
    
    async def get_users(self):
        cached = await self.cache.get("users")
        if cached:
            return cached
        
        users = await self.repository.get_all()
        await self.cache.set("users", users, ttl=300)
        return users

async def get_user_service(
    repo=Depend(get_user_repository),
    cache=Depend(get_cache)
):
    return UserService(repo, cache)

@app.get("/users")
async def list_users(request: Request, response: Response, service=Depend(get_user_service)):
    users = await service.get_users()
    return response.json(users)
```

## 🔍 See Also

- [Context](./context.md) - Request context management
- [Resolution](./resolution.md) - Dependency resolution process
- [Middleware](../middleware/base.md) - Middleware system
- [Testing](../testing/client.md) - Testing with dependencies
- [Application](../application/nexios-app.md) - Application-level dependencies