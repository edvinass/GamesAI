import hashlib
import secrets
import uuid
from typing import Any


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def player_to_dict(player: Any) -> dict:
    return {
        "id": str(player.id),
        "nickname": player.nickname,
        "team": player.team.value if player.team else None,
        "role": player.role.value if player.role else None,
        "is_ai": player.is_ai,
        "is_connected": player.is_connected,
    }


def room_to_dict(room: Any, players: list[Any] | None = None) -> dict:
    player_list = players if players is not None else room.players
    return {
        "id": str(room.id),
        "game_type": room.game_type,
        "status": room.status.value,
        "settings": room.settings,
        "host_player_id": str(room.host_player_id) if room.host_player_id else None,
        "players": [player_to_dict(p) for p in player_list],
    }
