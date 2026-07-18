import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RoomStatus(str, enum.Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    FINISHED = "finished"


class Team(str, enum.Enum):
    RED = "red"
    BLUE = "blue"


class Role(str, enum.Enum):
    SPYMASTER = "spymaster"
    OPERATIVE = "operative"


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(6), unique=True, nullable=False, index=True)
    game_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[RoomStatus] = mapped_column(
        Enum(RoomStatus, name="room_status", values_callable=lambda x: [e.value for e in x]),
        default=RoomStatus.LOBBY,
        nullable=False,
    )
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    host_player_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    players: Mapped[list["RoomPlayer"]] = relationship(
        "RoomPlayer", back_populates="room", cascade="all, delete-orphan"
    )
    game_state: Mapped["GameState | None"] = relationship(
        "GameState", back_populates="room", uselist=False, cascade="all, delete-orphan"
    )


class RoomPlayer(Base):
    __tablename__ = "room_players"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    session_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    team: Mapped[Team | None] = mapped_column(
        Enum(Team, name="team", values_callable=lambda x: [e.value for e in x]), nullable=True
    )
    role: Mapped[Role | None] = mapped_column(
        Enum(Role, name="role", values_callable=lambda x: [e.value for e in x]), nullable=True
    )
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped["Room"] = relationship("Room", back_populates="players")


class GameState(Base):
    __tablename__ = "game_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    room: Mapped["Room"] = relationship("Room", back_populates="game_state")
