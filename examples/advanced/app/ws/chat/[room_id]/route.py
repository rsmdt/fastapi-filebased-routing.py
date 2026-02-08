"""WebSocket handler demonstration.

Directory structure: app/ws/chat/[room_id]/route.py

WebSocket handlers:
  - Must be named 'websocket'
  - Must be async (required by FastAPI)
  - Receive a WebSocket object as first parameter
  - Can have path parameters like HTTP handlers
"""

from fastapi import WebSocket, WebSocketDisconnect

TAGS = ["websocket", "chat"]


async def websocket(websocket: WebSocket, room_id: str):
    """WebSocket endpoint for chat rooms.

    This demonstrates:
    - WebSocket support in file-based routing
    - Path parameters in WebSocket routes
    - Real-time bidirectional communication

    Connect via: ws://localhost:8000/ws/chat/{room_id}
    """
    await websocket.accept()

    # Send welcome message
    await websocket.send_json({
        "type": "system",
        "message": f"Welcome to chat room: {room_id}",
    })

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            # Echo back with room context
            await websocket.send_json({
                "type": "message",
                "room": room_id,
                "content": data,
                "echo": True,
            })

    except WebSocketDisconnect:
        print(f"Client disconnected from room: {room_id}")
