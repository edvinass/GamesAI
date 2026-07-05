import hashlib
import secrets
import uuid
from typing import Any


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def player_to_dict(player: Any, room_settings: dict | None = None) -> dict:
    data = {
        "id": str(player.id),
        "nickname": player.nickname,
        "team": player.team.value if player.team else None,
        "role": player.role.value if player.role else None,
        "is_ai": player.is_ai,
        "is_connected": player.is_connected,
    }
    if player.is_ai and room_settings:
        difficulties = room_settings.get("ai_difficulties") or {}
        data["ai_difficulty"] = difficulties.get(str(player.id), "normal")
    return data


def room_to_dict(room: Any, players: list[Any] | None = None) -> dict:
    player_list = players if players is not None else room.players
    settings = room.settings or {}
    return {
        "id": str(room.id),
        "game_type": room.game_type,
        "status": room.status.value,
        "settings": settings,
        "host_player_id": str(room.host_player_id) if room.host_player_id else None,
        "players": [player_to_dict(p, settings) for p in player_list],
    }
