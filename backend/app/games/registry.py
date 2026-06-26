from app.games.base import GamePlugin
from app.games.codenames.engine import CodenamesEngine

_REGISTRY: dict[str, GamePlugin] = {
    "codenames": CodenamesEngine(),
}


def get_game(game_type: str) -> GamePlugin:
    plugin = _REGISTRY.get(game_type)
    if not plugin:
        raise ValueError(f"Unknown game type: {game_type}")
    return plugin


def list_games() -> list[dict]:
    return [
        {"id": "codenames", "name": "Codenames", "description": "Team word guessing game"},
    ]
