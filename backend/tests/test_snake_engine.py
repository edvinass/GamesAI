import copy
from datetime import datetime, timedelta, timezone

import pytest

from app.games.snake.engine import SnakeEngine


def make_players(count: int = 2) -> list[dict]:
    return [
        {
            "id": f"p{i}",
            "nickname": f"Player {i}",
            "team": None,
            "role": None,
            "is_ai": False,
            "is_connected": True,
        }
        for i in range(count)
    ]


@pytest.fixture
def engine() -> SnakeEngine:
    return SnakeEngine()


@pytest.fixture
def state(engine: SnakeEngine) -> dict:
    players = make_players(2)
    s = engine.create_initial_state(players, {"countdown_sec": 0})
    s["phase"] = "playing"
    s["countdown_ends_at"] = None
    return s


def test_lobby_validation(engine: SnakeEngine) -> None:
    assert engine.validate_lobby(make_players(1), {}) is not None
    assert engine.validate_lobby(make_players(2), {}) is None
    assert engine.validate_lobby(make_players(9), {}) is not None
    assert engine.validate_lobby(make_players(1), {"solo_practice": True}) is None
    assert engine.validate_lobby(make_players(2), {"solo_practice": True}) is not None


def test_initial_state_spawns(engine: SnakeEngine) -> None:
    players = make_players(3)
    state = engine.create_initial_state(players, {})
    assert len(state["snakes"]) == 3
    assert state["phase"] == "countdown"
    assert state["food"] is not None

    occupied: set[tuple[int, int]] = set()
    for snake in state["snakes"].values():
        for seg in snake["body"]:
            key = (seg[0], seg[1])
            assert key not in occupied
            occupied.add(key)


def test_direction_queuing(engine: SnakeEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    snake = state["snakes"][pid]
    snake["direction"] = "right"
    snake["next_direction"] = "right"

    state, _ = engine.apply_action(state, {"type": "set_direction", "direction": "left"}, player)
    assert state["snakes"][pid]["next_direction"] == "right"

    state, _ = engine.apply_action(state, {"type": "set_direction", "direction": "up"}, player)
    assert state["snakes"][pid]["next_direction"] == "up"


def test_direction_ignored_when_dead(engine: SnakeEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["snakes"][pid]["alive"] = False

    state, _ = engine.apply_action(state, {"type": "set_direction", "direction": "up"}, player)
    assert state["snakes"][pid]["next_direction"] == state["snakes"][pid]["direction"]


def test_wall_collision(engine: SnakeEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    other_pid = state["players"][1]["id"]
    snake = state["snakes"][pid]
    snake["body"] = [[0, 0], [1, 0], [2, 0]]
    snake["direction"] = "left"
    snake["next_direction"] = "left"
    assert state["snakes"][other_pid]["alive"]

    state, events = engine.tick(state)
    assert not state["snakes"][pid]["alive"]
    assert state["snakes"][other_pid]["alive"]
    assert any(e["type"] == "player_died" for e in events)
    assert state["winner"] == other_pid


def test_food_eaten_grows_score(engine: SnakeEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    snake = state["snakes"][pid]
    snake["body"] = [[5, 5], [4, 5], [3, 5]]
    snake["direction"] = "right"
    snake["next_direction"] = "right"
    state["food"] = [6, 5]
    state["snakes"][state["players"][1]["id"]]["alive"] = False

    initial_len = len(snake["body"])
    state, events = engine.tick(state)
    assert state["snakes"][pid]["score"] == 1
    assert len(state["snakes"][pid]["body"]) == initial_len + 1
    assert any(e["type"] == "food_eaten" for e in events)


def test_countdown_to_playing(engine: SnakeEngine) -> None:
    players = make_players(2)
    state = engine.create_initial_state(players, {"countdown_sec": 3})
    assert state["phase"] == "countdown"

    state["countdown_ends_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    state, events = engine.tick(state)
    assert state["phase"] == "playing"
    assert any(e["type"] == "game_started" for e in events)


def test_winner_last_standing(engine: SnakeEngine, state: dict) -> None:
    p0, p1 = state["players"][0]["id"], state["players"][1]["id"]
    state["snakes"][p0]["alive"] = False
    state["snakes"][p1]["alive"] = True

    engine._resolve_winner(state)
    assert state["winner"] == p1
    assert state["win_reason"] == "last_standing"
    assert state["phase"] == "finished"


def test_winner_highest_score_on_mutual_death(engine: SnakeEngine, state: dict) -> None:
    p0, p1 = state["players"][0]["id"], state["players"][1]["id"]
    state["snakes"][p0]["alive"] = False
    state["snakes"][p0]["score"] = 5
    state["snakes"][p1]["alive"] = False
    state["snakes"][p1]["score"] = 2

    engine._resolve_winner(state)
    assert state["winner"] == p0
    assert state["win_reason"] == "highest_score"


def test_tick_interval(engine: SnakeEngine) -> None:
    assert engine.tick_interval_ms() == 150


def test_check_winner(engine: SnakeEngine, state: dict) -> None:
    assert engine.check_winner(state) is None
    state["phase"] = "finished"
    state["winner"] = state["players"][0]["id"]
    assert engine.check_winner(state) == state["players"][0]["id"]
