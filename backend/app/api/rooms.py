import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.games.registry import get_game, list_games
from app.models import Room, RoomPlayer, RoomStatus
from app.services.room_service import RoomService
from app.utils import generate_session_token, hash_session_token, room_to_dict

router = APIRouter(prefix="/rooms", tags=["rooms"])


class CreateRoomRequest(BaseModel):
    game_type: str = "codenames"
    nickname: str = Field(min_length=1, max_length=50)


class JoinRoomRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=50)


class RoomResponse(BaseModel):
    room_id: str
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
    return RoomResponse(room_id=str(room.id), session_token=token, player_id=str(player.id))


@router.post("/{room_id}/join", response_model=RoomResponse)
async def join_room(room_id: uuid.UUID, body: JoinRoomRequest, db: AsyncSession = Depends(get_db)):
    service = RoomService(db)
    try:
        room, player, token = await service.join_room(room_id, body.nickname)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RoomResponse(room_id=str(room.id), session_token=token, player_id=str(player.id))


@router.get("/{room_id}")
async def get_room(room_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Room).options(selectinload(Room.players)).where(Room.id == room_id)
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room_to_dict(room)
