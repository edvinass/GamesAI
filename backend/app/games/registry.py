from app.games.base import GamePlugin
from app.games.codenames.engine import CodenamesEngine
from app.games.duel.engine import DuelEngine
from app.games.snake.engine import SnakeEngine
from app.games.spyfall.engine import SpyfallEngine

_REGISTRY: dict[str, GamePlugin] = {
    "codenames": CodenamesEngine(),
    "spyfall": SpyfallEngine(),
    "snake": SnakeEngine(),
    "duel": DuelEngine(),
}


def get_game(game_type: str) -> GamePlugin:
    plugin = _REGISTRY.get(game_type)
    if not plugin:
        raise ValueError(f"Unknown game type: {game_type}")
    return plugin


def list_games() -> list[dict]:
    return [
        {"id": "codenames", "name": "Codenames", "description": "Team word guessing game"},
        {"id": "spyfall", "name": "Spyfall", "description": "Social deduction at a secret location"},
        {"id": "snake", "name": "Multiplayer Snake", "description": "Battle on a shared grid — last snake standing"},
        {"id": "duel", "name": "Side Duel", "description": "Two players shoot from opposite sides — dodge and fire"},
    ]
