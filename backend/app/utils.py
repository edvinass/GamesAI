import hashlib
import secrets
import uuid
from typing import Any

# Crockford base32 — unambiguous for voice / typing (no I, L, O, U)
_ROOM_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ROOM_CODE_LENGTH = 6


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_room_code(length: int = _ROOM_CODE_LENGTH) -> str:
    return "".join(secrets.choice(_ROOM_CODE_ALPHABET) for _ in range(length))


def normalize_room_code(value: str) -> str:
    return value.strip().upper().replace(" ", "").replace("-", "")


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
        default = str(room_settings.get("ai_difficulty") or "normal")
        data["ai_difficulty"] = difficulties.get(str(player.id), default)
    return data


def room_to_dict(room: Any, players: list[Any] | None = None) -> dict:
    player_list = players if players is not None else room.players
    settings = room.settings or {}
    return {
        "id": str(room.id),
        "code": getattr(room, "code", None),
        "game_type": room.game_type,
        "status": room.status.value,
        "settings": settings,
        "host_player_id": str(room.host_player_id) if room.host_player_id else None,
        "players": [player_to_dict(p, settings) for p in player_list],
    }
