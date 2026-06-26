import json
import logging
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.services.room_service import RoomService
from app.utils import player_to_dict, room_to_dict

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, room_id: str, player_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if room_id not in self.active:
            self.active[room_id] = {}
        self.active[room_id][player_id] = websocket

    def disconnect(self, room_id: str, player_id: str) -> None:
        if room_id in self.active:
            self.active[room_id].pop(player_id, None)
            if not self.active[room_id]:
                del self.active[room_id]

    async def broadcast(self, room_id: str, message: dict, exclude: str | None = None) -> None:
        if room_id not in self.active:
            return
        dead: list[str] = []
        for pid, ws in self.active[room_id].items():
            if exclude and pid == exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(pid)
        for pid in dead:
            self.disconnect(room_id, pid)


manager = ConnectionManager()


async def broadcast_room_state(room, events: list[dict] | None = None) -> None:
    room_id = str(room.id)
    async with async_session() as db:
        service = RoomService(db)
        room = await service._load_room(room.id)
        if not room:
            return
        for player in room.players:
            viewer_state = service.get_viewer_state(room, player)
            payload: dict[str, Any] = {
                "type": "state_updated",
                "room": room_to_dict(room),
                "game_state": viewer_state,
            }
            if events:
                payload["events"] = events
            if room_id in manager.active and str(player.id) in manager.active[room_id]:
                try:
                    await manager.active[room_id][str(player.id)].send_json(payload)
                except Exception:
                    pass

        lobby_payload = {
            "type": "room_updated",
            "room": room_to_dict(room),
        }
        if events:
            lobby_payload["events"] = events
        await manager.broadcast(room_id, lobby_payload)


async def handle_websocket(websocket: WebSocket, room_id: uuid.UUID, token: str) -> None:
    player_id: str | None = None
    room_id_str = str(room_id)

    try:
        async with async_session() as db:
            service = RoomService(db)
            player = await service.authenticate_player(room_id, token)
            if not player:
                await websocket.close(code=4001, reason="Invalid session")
                return
            player_id = str(player.id)
            await service.set_connected(player.id, True)

        await manager.connect(room_id_str, player_id, websocket)

        async with async_session() as db:
            service = RoomService(db)
            room = await service._load_room(room_id)
            if room:
                viewer_state = service.get_viewer_state(room, player)
                await websocket.send_json({
                    "type": "connected",
                    "room": room_to_dict(room),
                    "game_state": viewer_state,
                    "player_id": player_id,
                })

        while True:
            data = await websocket.receive_json()
            await process_message(room_id, player_id, data)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
    finally:
        if player_id:
            manager.disconnect(room_id_str, player_id)
            async with async_session() as db:
                service = RoomService(db)
                await service.set_connected(uuid.UUID(player_id), False)
                room = await service._load_room(room_id)
                if room:
                    await manager.broadcast(room_id_str, {
                        "type": "room_updated",
                        "room": room_to_dict(room),
                    })


async def process_message(room_id: uuid.UUID, player_id: str, data: dict) -> None:
    action_type = data.get("type")
    async with async_session() as db:
        service = RoomService(db)
        pid = uuid.UUID(player_id)
        events: list[dict] = []

        try:
            if action_type == "update_settings":
                room = await service.update_settings(room_id, pid, data.get("settings", {}))
                await manager.broadcast(str(room_id), {
                    "type": "room_updated",
                    "room": room_to_dict(room),
                })

            elif action_type == "add_ai_player":
                room = await service.add_ai_player(
                    room_id, pid, data["team"], data["role"]
                )
                await manager.broadcast(str(room_id), {
                    "type": "room_updated",
                    "room": room_to_dict(room),
                })

            elif action_type == "remove_player":
                room = await service.remove_player(room_id, pid, uuid.UUID(data["player_id"]))
                await manager.broadcast(str(room_id), {
                    "type": "room_updated",
                    "room": room_to_dict(room),
                })

            elif action_type == "start_game":
                room, state = await service.start_game(room_id, pid)
                await manager.broadcast(str(room_id), {
                    "type": "game_started",
                    "room": room_to_dict(room),
                })
                await broadcast_room_state(room, [{"type": "game_started"}])
                await service.run_ai_turn_if_needed(room_id, broadcast_room_state)

            elif action_type in ("submit_clue", "guess_word", "end_turn"):
                room, state, events = await service.apply_game_action(room_id, pid, data)
                await broadcast_room_state(room, events)
                await service.run_ai_turn_if_needed(room_id, broadcast_room_state)

            else:
                await manager.active.get(str(room_id), {}).get(player_id, None)
                if str(room_id) in manager.active and player_id in manager.active[str(room_id)]:
                    await manager.active[str(room_id)][player_id].send_json({
                        "type": "error",
                        "message": f"Unknown action: {action_type}",
                    })

        except ValueError as e:
            if str(room_id) in manager.active and player_id in manager.active[str(room_id)]:
                await manager.active[str(room_id)][player_id].send_json({
                    "type": "error",
                    "message": str(e),
                })
