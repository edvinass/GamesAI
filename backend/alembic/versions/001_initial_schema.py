"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    room_status = postgresql.ENUM("lobby", "playing", "finished", name="room_status")
    team = postgresql.ENUM("red", "blue", name="team")
    role = postgresql.ENUM("spymaster", "operative", name="role")
    room_status.create(op.get_bind(), checkfirst=True)
    team.create(op.get_bind(), checkfirst=True)
    role.create(op.get_bind(), checkfirst=True)

    room_status_no_create = postgresql.ENUM(
        "lobby", "playing", "finished", name="room_status", create_type=False
    )
    team_no_create = postgresql.ENUM("red", "blue", name="team", create_type=False)
    role_no_create = postgresql.ENUM("spymaster", "operative", name="role", create_type=False)

    op.create_table(
        "rooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("game_type", sa.String(length=50), nullable=False),
        sa.Column("status", room_status_no_create, nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("host_player_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "room_players",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nickname", sa.String(length=50), nullable=False),
        sa.Column("session_token_hash", sa.String(length=128), nullable=False),
        sa.Column("team", team_no_create, nullable=True),
        sa.Column("role", role_no_create, nullable=True),
        sa.Column("is_ai", sa.Boolean(), nullable=False),
        sa.Column("is_connected", sa.Boolean(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "game_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id"),
    )


def downgrade() -> None:
    op.drop_table("game_states")
    op.drop_table("room_players")
    op.drop_table("rooms")
    sa.Enum(name="role").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="team").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="room_status").drop(op.get_bind(), checkfirst=True)