import uuid

from fastapi import APIRouter, WebSocket

from app.websocket.handlers import handle_websocket

router = APIRouter()


@router.websocket("/ws/rooms/{room_id}")
async def websocket_room(websocket: WebSocket, room_id: uuid.UUID, token: str = ""):
    if not token:
        token = websocket.query_params.get("token", "")
    await handle_websocket(websocket, room_id, token)
