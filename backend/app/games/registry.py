from app.games.base import GamePlugin
from app.games.codenames.engine import CodenamesEngine
from app.games.duel.engine import DuelEngine
from app.games.gravity_master.engine import GravityMasterEngine
from app.games.snake.engine import SnakeEngine
from app.games.spyfall.engine import SpyfallEngine
from app.games.tetris.engine import TetrisEngine

_REGISTRY: dict[str, GamePlugin] = {
    "codenames": CodenamesEngine(),
    "spyfall": SpyfallEngine(),
    "snake": SnakeEngine(),
    "duel": DuelEngine(),
    "tetris": TetrisEngine(),
    "gravity_master": GravityMasterEngine(),
}


def get_game(game_type: str) -> GamePlugin:
    plugin = _REGISTRY.get(game_type)
    if not plugin:
        raise ValueError(f"Unknown game type: {game_type}")
    return plugin


_GAME_LIST_META: dict[str, dict[str, str]] = {
    "codenames": {"name": "Codenames", "description": "Team word guessing game"},
    "spyfall": {"name": "Spyfall", "description": "Social deduction at a secret location"},
    "snake": {"name": "Multiplayer Snake", "description": "Battle on a shared grid — last snake standing"},
    "duel": {"name": "Side Duel", "description": "Two players shoot from opposite sides — dodge and fire"},
    "tetris": {"name": "Multiplier Tetris", "description": "Each player stacks alone — speed rises, last board standing wins"},
    "gravity_master": {"name": "Gravity Master", "description": "Draw shapes that fall and become walls — guide the ball to the target"},
}


def list_games() -> list[dict]:
    return [
        {"id": game_id, **_GAME_LIST_META[game_id]}
        for game_id in _REGISTRY
        if game_id in _GAME_LIST_META
    ]
