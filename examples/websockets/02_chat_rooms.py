from typing import Dict, Set

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.websockets import WebSocket

app = NexiosApp()

# Store chat rooms and their connected clients
chat_rooms: Dict[str, Set[WebSocket]] = {}


@app.ws_route("/ws/chat/{room_id}")
async def chat_room(websocket: WebSocket):
    room_id = websocket.path_params["room_id"]
    await websocket.accept()

    # Create room if it doesn't exist
    if room_id not in chat_rooms:
        chat_rooms[room_id] = set()

    # Add client to room
    chat_rooms[room_id].add(websocket)

    try:
        # Announce new user
        for client in chat_rooms[room_id]:
            if client != websocket:
                await client.send_json(
                    {"type": "system", "message": "New user joined the chat"}
                )

        # Handle messages
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")

            # Broadcast message to room
            for client in chat_rooms[room_id]:
                if client != websocket:  # Don't send back to sender
                    await client.send_json({"type": "message", "message": message})
    except Exception as e:
        print(f"WebSocket error in room {room_id}: {e}")
    finally:
        # Remove client from room
        chat_rooms[room_id].remove(websocket)
        if not chat_rooms[room_id]:
            del chat_rooms[room_id]
        await websocket.close()


@app.get("/")
async def index(request, response):
    html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Nexios Chat Rooms</title>
        </head>
        <body>
            <h1>Chat Room Example</h1>
            <div>
                <label>Room ID: <input type="text" id="roomId" value="room1"></label>
                <button onclick="joinRoom()">Join Room</button>
            </div>
            <div id="chat" style="display:none">
                <div id="messages" style="height:300px;overflow-y:scroll;border:1px solid #ccc;margin:10px 0;"></div>
                <input type="text" id="messageInput" placeholder="Type a message...">
                <button onclick="sendMessage()">Send</button>
            </div>
            
            <script>
                let ws;
                
                function joinRoom() {
                    const roomId = document.getElementById('roomId').value;
                    ws = new WebSocket(`ws://${window.location.host}/ws/chat/${roomId}`);
                    
                    ws.onmessage = function(event) {
                        const data = JSON.parse(event.data);
                        const messages = document.getElementById('messages');
                        const messageDiv = document.createElement('div');
                        messageDiv.textContent = data.type === 'system' 
                            ? `System: ${data.message}`
                            : `Message: ${data.message}`;
                        messages.appendChild(messageDiv);
                        messages.scrollTop = messages.scrollHeight;
                    };
                    
                    document.getElementById('chat').style.display = 'block';
                }
                
                function sendMessage() {
                    const input = document.getElementById('messageInput');
                    ws.send(JSON.stringify({message: input.value}));
                    input.value = '';
                }
            </script>
        </body>
    </html>
    """
    return response.html(html)
