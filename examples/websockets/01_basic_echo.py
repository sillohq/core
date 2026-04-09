from nexios import NexiosApp
from nexios.websockets import WebSocket

app = NexiosApp()


@app.ws_route("/ws")
async def websocket_handler(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(f"Echo: {message}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()
