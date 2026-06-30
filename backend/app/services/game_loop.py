import asyncio
import logging
import uuid

from app.db.session import async_session
from app.games.registry import get_game
from app.models import RoomStatus
from app.services.room_service import RoomService

logger = logging.getLogger(__name__)

_active_loops: dict[str, asyncio.Task] = {}


async def _run_game_loop(room_id: uuid.UUID, broadcast_fn) -> None:
    room_id_str = str(room_id)

    while True:
        async with async_session() as db:
            service = RoomService(db)
            room = await service._load_room(room_id)
            if not room or room.status != RoomStatus.PLAYING or not room.game_state:
                _active_loops.pop(room_id_str, None)
                return

            game = get_game(room.game_type)
            interval = game.tick_interval_ms()
            if not interval or interval <= 0:
                _active_loops.pop(room_id_str, None)
                return

            settings = room.game_state.state.get("settings") or room.settings or {}
            tick_ms = int(settings.get("tick_ms", interval))

        try:
            async with async_session() as db:
                service = RoomService(db)
                room, state, events = await service.apply_game_tick(room_id)
        except Exception:
            logger.exception("Game tick failed for room %s", room_id_str)
            _active_loops.pop(room_id_str, None)
            return

        await broadcast_fn(room, events)

        if room.status.value != "playing" or state.get("winner"):
            _active_loops.pop(room_id_str, None)
            return

        await asyncio.sleep(tick_ms / 1000)


async def _maybe_start_game_loop(room_id: uuid.UUID, broadcast_fn) -> None:
    room_id_str = str(room_id)
    existing = _active_loops.get(room_id_str)
    if existing and not existing.done():
        return

    async with async_session() as db:
        service = RoomService(db)
        room = await service._load_room(room_id)
        if not room or room.status != RoomStatus.PLAYING:
            return
        game = get_game(room.game_type)
        if not game.tick_interval_ms():
            return

    task = asyncio.create_task(_run_game_loop(room_id, broadcast_fn))
    _active_loops[room_id_str] = task


def start_game_loop(room_id: uuid.UUID, broadcast_fn) -> None:
    asyncio.create_task(_maybe_start_game_loop(room_id, broadcast_fn))


def stop_game_loop(room_id: uuid.UUID) -> None:
    room_id_str = str(room_id)
    task = _active_loops.pop(room_id_str, None)
    if task and not task.done():
        task.cancel()
