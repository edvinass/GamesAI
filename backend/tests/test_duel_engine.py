import copy
from datetime import datetime, timedelta, timezone

import pytest

from app.games.duel.engine import DuelEngine


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
def engine() -> DuelEngine:
    return DuelEngine()


@pytest.fixture
def state(engine: DuelEngine) -> dict:
    players = make_players(2)
    s = engine.create_initial_state(players, {"countdown_sec": 0})
    s["phase"] = "playing"
    s["countdown_ends_at"] = None
    return s


def test_lobby_validation(engine: DuelEngine) -> None:
    assert engine.validate_lobby(make_players(1), {}) is not None
    assert engine.validate_lobby(make_players(2), {}) is None
    assert engine.validate_lobby(make_players(3), {}) is not None
    assert engine.validate_lobby(make_players(1), {"solo_practice": True}) is None
    assert engine.validate_lobby(make_players(2), {"solo_practice": True}) is not None


def test_initial_state_spawns_on_sides(engine: DuelEngine) -> None:
    players = make_players(2)
    game_state = engine.create_initial_state(players, {})
    fighters = game_state["fighters"]
    assert len(fighters) == 2
    left = fighters["p0"]
    right = fighters["p1"]
    assert left["side"] == "left"
    assert right["side"] == "right"
    assert left["x"] < right["x"]
    assert game_state["phase"] == "countdown"


def test_move_and_shoot_actions(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]

    state, _ = engine.apply_action(state, {"type": "set_move", "direction": "up"}, player)
    assert state["fighters"][pid]["move_direction"] == "up"

    state, _ = engine.apply_action(state, {"type": "shoot"}, player)
    assert state["fighters"][pid]["pending_shoot"] is True


def test_shoot_spawns_bullet(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    left["pending_shoot"] = True
    left["cooldown_until_tick"] = 0

    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 1
    assert state["bullets"][0]["vx"] == 1
    assert state["bullets"][0]["owner_id"] == "p0"


def test_fighter_is_three_bars_tall(engine: DuelEngine) -> None:
    players = make_players(2)
    game_state = engine.create_initial_state(players, {})
    assert game_state["settings"]["fighter_height"] == 3
    left = game_state["fighters"]["p0"]
    assert left["y"] == (game_state["grid_height"] - 3) // 2


def test_bullet_hits_any_fighter_bar(engine: DuelEngine, state: dict) -> None:
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 10
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 1, "owner_id": "p0"}]

    state, events = engine.tick(state)
    assert state["phase"] == "finished"
    assert state["winner"] == "p0"
    assert any(e["type"] == "player_hit" for e in events)


def test_cooldown_blocks_rapid_fire(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    left["pending_shoot"] = True
    left["cooldown_until_tick"] = 0

    state, _ = engine.tick(state)
    first_count = len(state["bullets"])

    left["pending_shoot"] = True
    state, _ = engine.tick(state)
    assert len(state["bullets"]) == first_count
