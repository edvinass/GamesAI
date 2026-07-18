"""Add short room invite codes

Revision ID: 002
Revises: 001
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import secrets

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Crockford base32 (no I, L, O, U)
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def upgrade() -> None:
    op.add_column("rooms", sa.Column("code", sa.String(length=6), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM rooms WHERE code IS NULL")).fetchall()
    used: set[str] = set()
    for (room_id,) in rows:
        code = _generate_code()
        while code in used:
            code = _generate_code()
        used.add(code)
        conn.execute(
            sa.text("UPDATE rooms SET code = :code WHERE id = :id"),
            {"code": code, "id": room_id},
        )

    op.alter_column("rooms", "code", nullable=False)
    op.create_index("ix_rooms_code", "rooms", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_rooms_code", table_name="rooms")
    op.drop_column("rooms", "code")
