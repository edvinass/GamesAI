from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.games.registry import get_game, list_games
from app.services.room_service import RoomService
from app.utils import room_to_dict

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


@router.get("/{room_ref}")
async def get_room(room_ref: str, db: AsyncSession = Depends(get_db)):
    service = RoomService(db)
    room = await service.resolve_room_ref(room_ref)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room_to_dict(room)
