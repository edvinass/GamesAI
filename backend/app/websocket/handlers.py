import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.games.registry import get_game
from app.services.game_loop import start_game_loop, stop_game_loop
from app.services.room_service import RoomService, process_ai_turns
from app.utils import player_to_dict, room_to_dict

logger = logging.getLogger(__name__)

POKER_REACTIONS = frozenset({"👍", "🔥", "😂", "😮", "👏", "🃏", "💰", "😎", "🫡", "💀"})


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


def schedule_ai_turn(room_id: uuid.UUID) -> None:
    asyncio.create_task(process_ai_turns(room_id, broadcast_room_state))


def schedule_game_updates(room_id: uuid.UUID, game_type: str) -> None:
    game = get_game(game_type)
    if game.tick_interval_ms():
        start_game_loop(room_id, broadcast_room_state)
    else:
        schedule_ai_turn(room_id)


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
                if room.status.value == "playing":
                    schedule_game_updates(room_id, room.game_type)

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
                    room_id, pid, data.get("team"), data.get("role")
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

            elif action_type == "update_player":
                room = await service.update_player(
                    room_id,
                    pid,
                    uuid.UUID(data["player_id"]),
                    team=data.get("team"),
                    role=data.get("role"),
                )
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
                schedule_game_updates(room_id, room.game_type)

            elif action_type == "return_to_lobby":
                stop_game_loop(room_id)
                room = await service.return_to_lobby(room_id, pid)
                await manager.broadcast(str(room_id), {
                    "type": "returned_to_lobby",
                    "room": room_to_dict(room),
                })

            elif action_type == "reaction":
                emoji = data.get("emoji", "")
                if emoji not in POKER_REACTIONS:
                    raise ValueError("Invalid reaction")
                room = await service._load_room(room_id)
                if not room or room.status.value != "playing":
                    return
                player = next((p for p in room.players if str(p.id) == player_id), None)
                if not player:
                    return
                await manager.broadcast(str(room_id), {
                    "type": "reaction",
                    "player_id": player_id,
                    "nickname": player.nickname,
                    "emoji": emoji,
                })

            else:
                # Game actions — delegate to the active game plugin
                room, state, events = await service.apply_game_action(room_id, pid, data)
                await broadcast_room_state(room, events)
                if room.game_type not in ("snake", "duel", "tetris"):
                    schedule_ai_turn(room_id)

        except ValueError as e:
            if str(room_id) in manager.active and player_id in manager.active[str(room_id)]:
                await manager.active[str(room_id)][player_id].send_json({
                    "type": "error",
                    "message": str(e),
                })
