import copy
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session, get_db
from app.games.codenames.suggest import (
    codenames_position_key,
    model_for_state,
    run_suggestion,
)
from app.games.registry import get_game, list_games
from app.models import RoomStatus
from app.services.room_service import RoomService
from app.utils import hash_session_token, room_to_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rooms", tags=["rooms"])


class CreateRoomRequest(BaseModel):
    game_type: str = "codenames"
    nickname: str = Field(min_length=1, max_length=50)


class JoinRoomRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=50)


class RoomResponse(BaseModel):
    room_id: str
    code: str
    session_token: str
    player_id: str


@router.get("/games")
async def get_games():
    return list_games()


@router.post("", response_model=RoomResponse)
async def create_room(body: CreateRoomRequest, db: AsyncSession = Depends(get_db)):
    try:
        get_game(body.game_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown game type")

    service = RoomService(db)
    room, player, token = await service.create_room(body.game_type, body.nickname)
    return RoomResponse(
        room_id=str(room.id),
        code=room.code,
        session_token=token,
        player_id=str(player.id),
    )


@router.post("/{room_ref}/join", response_model=RoomResponse)
async def join_room(room_ref: str, body: JoinRoomRequest, db: AsyncSession = Depends(get_db)):
    service = RoomService(db)
    try:
        room, player, token = await service.join_room(room_ref, body.nickname)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RoomResponse(
        room_id=str(room.id),
        code=room.code,
        session_token=token,
        player_id=str(player.id),
    )


@router.post("/{room_ref}/codenames/suggest")
async def suggest_codenames(room_ref: str, request: Request):
    """Suggest a clue or guess for the signed-in player.

    The database session is closed before the model runs, and this path never
    takes the room AI lock, so a hint cannot stall the live game.
    """
    token = request.headers.get("x-session-token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Invalid session")

    async with async_session() as db:
        service = RoomService(db)
        room = await service.resolve_room_ref(room_ref)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if room.game_type != "codenames" or room.status != RoomStatus.PLAYING or not room.game_state:
            raise HTTPException(status_code=409, detail="Codenames is not in progress")

        token_hash = hash_session_token(token)
        player = next((p for p in room.players if p.session_token_hash == token_hash), None)
        if not player:
            raise HTTPException(status_code=401, detail="Invalid session")

        raw_state = room.game_state.state
        if not isinstance(raw_state, dict):
            raise HTTPException(status_code=409, detail="Codenames is not in progress")
        snapshot = copy.deepcopy(raw_state)
        team = player.team.value if player.team else None
        role = player.role.value if player.role else None
        player_key = f"{room.id}:{player.id}"

    position_key = codenames_position_key(snapshot)
    model, model_label = model_for_state(snapshot)
    try:
        suggestion = await run_suggestion(
            player_key,
            snapshot,
            team,
            role,
            disconnected=request.is_disconnected,
        )
    except Exception as exc:
        logger.exception("Codenames suggestion failed")
        raise HTTPException(status_code=502, detail="Suggestion failed") from exc

    return {
        "position_key": position_key,
        "model": model,
        "model_label": model_label,
        "suggestion": suggestion,
    }


@router.get("/{room_ref}")
async def get_room(room_ref: str, db: AsyncSession = Depends(get_db)):
    service = RoomService(db)
    room = await service.resolve_room_ref(room_ref)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room_to_dict(room)
