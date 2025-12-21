# WebSocket

The WebSocket system in Nexios provides real-time, bidirectional communication between clients and servers with full async/await support and comprehensive error handling.

## 📋 WebSocket Class

### Class Definition

```python
class WebSocket:
    def __init__(self, scope: Scope, receive: Receive, send: Send)
```

The WebSocket class handles individual WebSocket connections and provides methods for sending and receiving messages.

## 🔌 Connection Management

### accept()
Accept the WebSocket connection.

```python
@app.ws_route("/ws")
async def websocket_handler(websocket):
    await websocket.accept()
    
    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(f"Echo: {message}")
    except WebSocketDisconnect:
        print("Client disconnected")
```

**Parameters**:
- `subprotocol` (Optional[str]): WebSocket subprotocol to use
- `headers` (Optional[Dict[str, str]]): Additional headers to send

```python
@app.ws_route("/ws")
async def websocket_handler(websocket):
    await websocket.accept(
        subprotocol="chat",
        headers={"X-Server": "Nexios"}
    )
```

### close()
Close the WebSocket connection.

```python
@app.ws_route("/ws")
async def websocket_handler(websocket):
    await websocket.accept()
    
    try:
        message = await websocket.receive_text()
        if message == "quit":
            await websocket.close(code=1000, reason="User requested disconnect")
    except WebSocketDisconnect:
        pass
```

**Parameters**:
- `code` (int): WebSocket close code (default: 1000)
- `reason` (Optional[str]): Reason for closing

## 💬 Message Handling

### Receiving Messages

#### receive_text()
Receive text message from client.

```python
@app.ws_route("/chat")
async def chat_handler(websocket):
    await websocket.accept()
    
    try:
        while True:
            message = await websocket.receive_text()
            print(f"Received: {message}")
            
            # Echo back to client
            await websocket.send_text(f"Server received: {message}")
    except WebSocketDisconnect:
        print("Client disconnected")
```

#### receive_bytes()
Receive binary message from client.

```python
@app.ws_route("/binary")
async def binary_handler(websocket):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_bytes()
            print(f"Received {len(data)} bytes")
            
            # Process binary data
            processed_data = process_binary(data)
            await websocket.send_bytes(processed_data)
    except WebSocketDisconnect:
        print("Client disconnected")
```

#### receive_json()
Receive and parse JSON message from client.

```python
@app.ws_route("/api")
async def api_handler(websocket):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Handle different message types
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "message":
                await handle_message(data["content"])
    except WebSocketDisconnect:
        print("Client disconnected")
    except json.JSONDecodeError:
        await websocket.send_json({"error": "Invalid JSON"})
```

### Sending Messages

#### send_text()
Send text message to client.

```python
@app.ws_route("/notifications")
async def notification_handler(websocket):
    await websocket.accept()
    
    # Send welcome message
    await websocket.send_text("Welcome to notifications!")
    
    # Send periodic updates
    while True:
        await asyncio.sleep(30)
        timestamp = datetime.now().isoformat()
        await websocket.send_text(f"Update at {timestamp}")
```

#### send_bytes()
Send binary message to client.

```python
@app.ws_route("/file-stream")
async def file_stream_handler(websocket):
    await websocket.accept()
    
    # Stream file in chunks
    with open("large_file.bin", "rb") as f:
        while True:
            chunk = f.read(8192)  # 8KB chunks
            if not chunk:
                break
            await websocket.send_bytes(chunk)
    
    await websocket.close()
```

#### send_json()
Send JSON message to client.

```python
@app.ws_route("/data")
async def data_handler(websocket):
    await websocket.accept()
    
    # Send structured data
    await websocket.send_json({
        "type": "user_data",
        "user": {
            "id": 123,
            "name": "John Doe",
            "status": "online"
        },
        "timestamp": datetime.now().isoformat()
    })
```

## 📊 WebSocket Properties

### client: Optional[Address]
Client connection information.

```python
@app.ws_route("/ws")
async def websocket_handler(websocket):
    await websocket.accept()
    
    if websocket.client:
        client_ip = websocket.client.host
        client_port = websocket.client.port
        print(f"Connection from {client_ip}:{client_port}")
```

### headers: Headers
Request headers from the WebSocket handshake.

```python
@app.ws_route("/ws")
async def websocket_handler(websocket):
    # Check authentication header
    auth_header = websocket.headers.get("Authorization")
    if not auth_header:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    await websocket.accept()
```

### query_params: QueryParams
Query parameters from the WebSocket URL.

```python
@app.ws_route("/ws")
async def websocket_handler(websocket):
    # Get room ID from query parameters
    room_id = websocket.query_params.get("room")
    user_id = websocket.query_params.get("user")
    
    if not room_id or not user_id:
        await websocket.close(code=1008, reason="Missing parameters")
        return
    
    await websocket.accept()
    await join_room(room_id, user_id, websocket)
```

### path_params: Dict[str, Any]
Path parameters from the WebSocket route.

```python
@app.ws_route("/chat/{room_id}")
async def chat_room_handler(websocket):
    room_id = websocket.path_params["room_id"]
    
    # Validate room exists
    if not await room_exists(room_id):
        await websocket.close(code=1008, reason="Room not found")
        return
    
    await websocket.accept()
```

### state: State
WebSocket-scoped state for storing connection-specific data.

```python
@app.ws_route("/ws")
async def websocket_handler(websocket):
    await websocket.accept()
    
    # Store connection metadata
    websocket.state.user_id = await authenticate_user(websocket)
    websocket.state.connected_at = datetime.now()
    websocket.state.message_count = 0
    
    try:
        while True:
            message = await websocket.receive_text()
            websocket.state.message_count += 1
            await process_message(message, websocket.state.user_id)
    except WebSocketDisconnect:
        print(f"User {websocket.state.user_id} disconnected after {websocket.state.message_count} messages")
```

## 🚀 Advanced WebSocket Patterns

### Authentication and Authorization

```python
async def authenticate_websocket(websocket):
    """Authenticate WebSocket connection"""
    token = websocket.query_params.get("token")
    if not token:
        # Try header authentication
        auth_header = websocket.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return None
    
    try:
        user = await verify_jwt_token(token)
        return user
    except InvalidTokenError:
        await websocket.close(code=1008, reason="Invalid token")
        return None

@app.ws_route("/secure")
async def secure_websocket(websocket):
    user = await authenticate_websocket(websocket)
    if not user:
        return
    
    await websocket.accept()
    websocket.state.user = user
    
    try:
        while True:
            message = await websocket.receive_text()
            # Process authenticated message
            await handle_authenticated_message(message, user)
    except WebSocketDisconnect:
        print(f"User {user.id} disconnected")
```

### Room-based Chat System

```python
class ChatRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.connections: Set[WebSocket] = set()
        self.message_history: List[Dict] = []
    
    async def add_connection(self, websocket: WebSocket, user: dict):
        self.connections.add(websocket)
        
        # Send message history
        for message in self.message_history[-50:]:  # Last 50 messages
            await websocket.send_json(message)
        
        # Notify others
        await self.broadcast({
            "type": "user_joined",
            "user": user["name"],
            "timestamp": datetime.now().isoformat()
        }, exclude=websocket)
    
    async def remove_connection(self, websocket: WebSocket, user: dict):
        self.connections.discard(websocket)
        
        # Notify others
        await self.broadcast({
            "type": "user_left",
            "user": user["name"],
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast(self, message: dict, exclude: WebSocket = None):
        """Send message to all connections in the room"""
        disconnected = set()
        
        for connection in self.connections:
            if connection == exclude:
                continue
            
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                disconnected.add(connection)
        
        # Clean up disconnected connections
        self.connections -= disconnected
    
    async def add_message(self, message: dict):
        self.message_history.append(message)
        # Keep only last 1000 messages
        if len(self.message_history) > 1000:
            self.message_history = self.message_history[-1000:]
        
        await self.broadcast(message)

# Global room manager
rooms: Dict[str, ChatRoom] = {}

@app.ws_route("/chat/{room_id}")
async def chat_room_handler(websocket):
    room_id = websocket.path_params["room_id"]
    
    # Authenticate user
    user = await authenticate_websocket(websocket)
    if not user:
        return
    
    await websocket.accept()
    
    # Get or create room
    if room_id not in rooms:
        rooms[room_id] = ChatRoom(room_id)
    
    room = rooms[room_id]
    await room.add_connection(websocket, user)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "message":
                message = {
                    "type": "message",
                    "user": user["name"],
                    "content": data["content"],
                    "timestamp": datetime.now().isoformat()
                }
                await room.add_message(message)
    
    except WebSocketDisconnect:
        await room.remove_connection(websocket, user)
```

### Real-time Data Streaming

```python
import asyncio
from asyncio import Queue

class DataStreamer:
    def __init__(self):
        self.subscribers: Dict[str, Set[WebSocket]] = {}
        self.data_queue = Queue()
        self.running = False
    
    async def start(self):
        """Start the data streaming service"""
        self.running = True
        asyncio.create_task(self.process_data())
    
    async def stop(self):
        """Stop the data streaming service"""
        self.running = False
    
    async def subscribe(self, websocket: WebSocket, data_type: str):
        """Subscribe a WebSocket to a data stream"""
        if data_type not in self.subscribers:
            self.subscribers[data_type] = set()
        
        self.subscribers[data_type].add(websocket)
    
    async def unsubscribe(self, websocket: WebSocket, data_type: str):
        """Unsubscribe a WebSocket from a data stream"""
        if data_type in self.subscribers:
            self.subscribers[data_type].discard(websocket)
    
    async def publish_data(self, data_type: str, data: dict):
        """Publish data to all subscribers"""
        if data_type not in self.subscribers:
            return
        
        message = {
            "type": data_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        disconnected = set()
        for websocket in self.subscribers[data_type]:
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                disconnected.add(websocket)
        
        # Clean up disconnected WebSockets
        self.subscribers[data_type] -= disconnected
    
    async def process_data(self):
        """Process data from external sources"""
        while self.running:
            try:
                # Simulate real-time data
                stock_data = await fetch_stock_prices()
                await self.publish_data("stocks", stock_data)
                
                weather_data = await fetch_weather_data()
                await self.publish_data("weather", weather_data)
                
                await asyncio.sleep(1)  # Update every second
            except Exception as e:
                print(f"Error processing data: {e}")
                await asyncio.sleep(5)

# Global data streamer
data_streamer = DataStreamer()

@app.on_startup
async def start_data_streamer():
    await data_streamer.start()

@app.on_shutdown
async def stop_data_streamer():
    await data_streamer.stop()

@app.ws_route("/stream/{data_type}")
async def data_stream_handler(websocket):
    data_type = websocket.path_params["data_type"]
    
    # Validate data type
    if data_type not in ["stocks", "weather", "news"]:
        await websocket.close(code=1008, reason="Invalid data type")
        return
    
    await websocket.accept()
    await data_streamer.subscribe(websocket, data_type)
    
    try:
        # Keep connection alive and handle client messages
        while True:
            message = await websocket.receive_text()
            
            if message == "ping":
                await websocket.send_text("pong")
            elif message == "unsubscribe":
                await data_streamer.unsubscribe(websocket, data_type)
                await websocket.close()
                break
    
    except WebSocketDisconnect:
        await data_streamer.unsubscribe(websocket, data_type)
```

### WebSocket Middleware

```python
async def websocket_auth_middleware(websocket, call_next):
    """WebSocket authentication middleware"""
    token = websocket.query_params.get("token")
    
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    try:
        user = await verify_token(token)
        websocket.state.user = user
        await call_next()
    except InvalidTokenError:
        await websocket.close(code=1008, reason="Invalid token")

async def websocket_rate_limit_middleware(websocket, call_next):
    """WebSocket rate limiting middleware"""
    client_ip = websocket.client.host if websocket.client else "unknown"
    
    # Check rate limit (implementation depends on your rate limiting strategy)
    if await is_rate_limited(client_ip):
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return
    
    await call_next()

# Add WebSocket middleware to the application
app.add_ws_middleware(websocket_auth_middleware)
app.add_ws_middleware(websocket_rate_limit_middleware)
```

## ⚠️ Error Handling

### WebSocket Exceptions

```python
from nexios.websockets.errors import WebSocketDisconnect

@app.ws_route("/ws")
async def websocket_handler(websocket):
    try:
        await websocket.accept()
        
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(f"Echo: {message}")
    
    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected: {e.code} - {e.reason}")
    
    except json.JSONDecodeError:
        await websocket.send_json({"error": "Invalid JSON format"})
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        await websocket.close(code=1011, reason="Internal server error")
```

### Connection State Management

```python
@app.ws_route("/ws")
async def websocket_handler(websocket):
    await websocket.accept()
    
    try:
        # Set up heartbeat
        last_ping = time.time()
        
        while True:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(
                    websocket.receive_text(), 
                    timeout=30.0
                )
                
                if message == "ping":
                    await websocket.send_text("pong")
                    last_ping = time.time()
                else:
                    await process_message(message)
            
            except asyncio.TimeoutError:
                # Check if connection is still alive
                if time.time() - last_ping > 60:  # 60 seconds timeout
                    await websocket.close(code=1000, reason="Timeout")
                    break
                
                # Send ping to check connection
                await websocket.send_text("ping")
    
    except WebSocketDisconnect:
        print("Client disconnected")
    
    finally:
        # Cleanup resources
        await cleanup_connection(websocket)
```

## 🧪 Testing WebSockets

### WebSocket Test Client

```python
import pytest
from nexios.testing import TestClient

@pytest.mark.asyncio
async def test_websocket_echo():
    app = NexiosApp()
    
    @app.ws_route("/ws")
    async def websocket_handler(websocket):
        await websocket.accept()
        try:
            while True:
                message = await websocket.receive_text()
                await websocket.send_text(f"Echo: {message}")
        except WebSocketDisconnect:
            pass
    
    async with TestClient(app) as client:
        async with client.websocket_connect("/ws") as websocket:
            await websocket.send_text("Hello")
            response = await websocket.receive_text()
            assert response == "Echo: Hello"
```

### Testing WebSocket JSON Communication

```python
@pytest.mark.asyncio
async def test_websocket_json():
    app = NexiosApp()
    
    @app.ws_route("/api")
    async def api_handler(websocket):
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
    
    async with TestClient(app) as client:
        async with client.websocket_connect("/api") as websocket:
            await websocket.send_json({"type": "ping"})
            response = await websocket.receive_json()
            assert response == {"type": "pong"}
```

## ⚡ Performance Considerations

### Connection Pooling

```python
class WebSocketPool:
    def __init__(self, max_connections: int = 1000):
        self.max_connections = max_connections
        self.active_connections: Set[WebSocket] = set()
    
    async def add_connection(self, websocket: WebSocket) -> bool:
        if len(self.active_connections) >= self.max_connections:
            await websocket.close(code=1008, reason="Server at capacity")
            return False
        
        self.active_connections.add(websocket)
        return True
    
    def remove_connection(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
    
    async def broadcast_to_all(self, message: dict):
        disconnected = set()
        
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                disconnected.add(websocket)
        
        self.active_connections -= disconnected

# Global connection pool
ws_pool = WebSocketPool(max_connections=500)

@app.ws_route("/ws")
async def websocket_handler(websocket):
    if not await ws_pool.add_connection(websocket):
        return
    
    await websocket.accept()
    
    try:
        while True:
            message = await websocket.receive_text()
            await process_message(message)
    except WebSocketDisconnect:
        pass
    finally:
        ws_pool.remove_connection(websocket)
```

### Message Queuing

```python
from asyncio import Queue

class MessageQueue:
    def __init__(self, maxsize: int = 1000):
        self.queue = Queue(maxsize=maxsize)
    
    async def put_message(self, message: dict):
        try:
            await self.queue.put(message)
        except asyncio.QueueFull:
            # Handle queue overflow
            await self.queue.get()  # Remove oldest message
            await self.queue.put(message)
    
    async def get_message(self):
        return await self.queue.get()

@app.ws_route("/queued")
async def queued_websocket_handler(websocket):
    await websocket.accept()
    
    message_queue = MessageQueue()
    
    # Start message processor
    async def process_messages():
        while True:
            try:
                message = await message_queue.get_message()
                await websocket.send_json(message)
            except WebSocketDisconnect:
                break
    
    processor_task = asyncio.create_task(process_messages())
    
    try:
        while True:
            data = await websocket.receive_json()
            await message_queue.put_message(data)
    
    except WebSocketDisconnect:
        processor_task.cancel()
```

## ✨ Best Practices

1. **Always handle WebSocketDisconnect** - Clients can disconnect at any time
2. **Implement heartbeat/ping-pong** - Keep connections alive and detect dead connections
3. **Use connection limits** - Prevent resource exhaustion
4. **Authenticate connections** - Verify client identity before accepting
5. **Handle JSON parsing errors** - Validate message format
6. **Implement proper cleanup** - Release resources when connections close
7. **Use message queuing** - Handle high-throughput scenarios
8. **Monitor connection health** - Track connection metrics
9. **Implement rate limiting** - Prevent abuse
10. **Test thoroughly** - Use WebSocket test clients for comprehensive testing

## 🔍 See Also

- [Router](./router.md) - WebSocket routing system
- [Channel](./channel.md) - WebSocket channel management
- [Middleware](./middleware.md) - WebSocket middleware
- [Testing](./testclient.md) - WebSocket testing utilities
- [Real-time Examples](../../examples/websockets.md) - WebSocket usage examples