from datetime import datetime, timedelta, timezone

import pytest

from app.games.bomberman.engine import (
    TILE_EMPTY,
    TILE_HARD,
    TILE_SOFT,
    BombermanEngine,
)


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
def engine() -> BombermanEngine:
    return BombermanEngine()


@pytest.fixture
def state(engine: BombermanEngine) -> dict:
    players = make_players(2)
    s = engine.create_initial_state(players, {"countdown_sec": 0})
    s["phase"] = "playing"
    s["countdown_ends_at"] = None
    return s


def test_lobby_validation(engine: BombermanEngine) -> None:
    assert engine.validate_lobby(make_players(1), {}) is not None
    assert engine.validate_lobby(make_players(2), {}) is None
    assert engine.validate_lobby(make_players(9), {}) is not None
    assert engine.validate_lobby(make_players(1), {"solo_practice": True}) is None
    assert engine.validate_lobby(make_players(2), {"solo_practice": True}) is not None


def test_initial_state_spawns(engine: BombermanEngine) -> None:
    players = make_players(4)
    state = engine.create_initial_state(players, {})
    assert len(state["bombers"]) == 4
    assert state["phase"] == "countdown"
    assert state["grid_width"] == 15
    assert state["grid_height"] == 13

    occupied: set[tuple[int, int]] = set()
    for bomber in state["bombers"].values():
        key = (bomber["x"], bomber["y"])
        assert key not in occupied
        occupied.add(key)
        assert state["grid"][bomber["y"]][bomber["x"]] == TILE_EMPTY


def test_direction_and_bomb_actions(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]

    state, _ = engine.apply_action(
        state, {"type": "set_direction", "direction": "right"}, player
    )
    assert state["bombers"][pid]["next_direction"] == "right"

    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert any(e["type"] == "bomb_placed" for e in events)
    assert len(state["bombs"]) == 1
    assert state["bombs"][0]["x"] == bomber["x"]
    assert state["bombs"][0]["y"] == bomber["y"]

    # Second bomb blocked until first explodes / max_bombs increased
    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert not any(e["type"] == "bomb_placed" for e in events)


def test_movement_blocked_by_hard_wall(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]
    # Corner spawn (1,1) — moving up hits the border hard wall
    bomber["x"] = 1
    bomber["y"] = 1
    bomber["next_direction"] = "up"
    bomber["direction"] = "up"
    bomber["move_credit"] = 0.0
    state["bombers"][state["players"][1]["id"]]["alive"] = False

    ox, oy = bomber["x"], bomber["y"]
    state, _ = engine.tick(state)
    assert state["bombers"][pid]["x"] == ox
    assert state["bombers"][pid]["y"] == oy
    # Blocked steps must not burn credit into a sticky delay
    assert state["bombers"][pid]["move_credit"] >= 0.99


def test_slide_along_wall_when_turn_blocked(engine: BombermanEngine, state: dict) -> None:
    """Holding up into a wall while moving right should keep sliding right."""
    player = state["players"][0]
    pid = player["id"]
    other = state["players"][1]["id"]
    state["bombers"][other]["alive"] = False
    bomber = state["bombers"][pid]

    for x in range(1, 6):
        state["grid"][1][x] = TILE_EMPTY
    # Hard wall directly above the path
    state["grid"][0][3] = TILE_HARD

    bomber["x"], bomber["y"] = 2, 1
    bomber["direction"] = "right"
    bomber["next_direction"] = "up"  # blocked — should slide right
    bomber["move_credit"] = 0.0
    state["bombs"] = []
    state["explosions"] = []

    state, _ = engine.tick(state)
    assert state["bombers"][pid]["x"] == 3
    assert state["bombers"][pid]["y"] == 1
    assert state["bombers"][pid]["direction"] == "right"


def test_blocked_then_open_moves_immediately(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    other = state["players"][1]["id"]
    bomber = state["bombers"][pid]
    # Keep the opponent alive far away so the match doesn't end mid-test.
    state["bombers"][other]["x"] = state["grid_width"] - 2
    state["bombers"][other]["y"] = state["grid_height"] - 2
    state["bombers"][other]["next_direction"] = "stop"

    for x in range(1, 5):
        state["grid"][1][x] = TILE_EMPTY
    bomber["x"], bomber["y"] = 1, 1
    bomber["next_direction"] = "left"  # into border
    bomber["direction"] = "left"
    bomber["move_credit"] = 0.0
    state["bombs"] = []
    state["explosions"] = []

    state, _ = engine.tick(state)
    assert state["phase"] == "playing"
    assert state["bombers"][pid]["x"] == 1
    assert state["bombers"][pid]["move_credit"] >= 0.99

    bomber["next_direction"] = "right"
    state, _ = engine.tick(state)
    assert state["bombers"][pid]["x"] == 2


def test_bomb_destroys_soft_and_kills(engine: BombermanEngine, state: dict) -> None:
    p0 = state["players"][0]
    p1 = state["players"][1]
    b0 = state["bombers"][p0["id"]]
    b1 = state["bombers"][p1["id"]]

    # Build a clear corridor on row y=1 (odd — no pillars)
    for x in range(1, 8):
        state["grid"][1][x] = TILE_EMPTY
    state["grid"][1][2] = TILE_SOFT
    b0["x"], b0["y"] = 3, 1
    b0["bomb_range"] = 3
    b0["max_bombs"] = 1
    b1["x"], b1["y"] = 6, 1
    b0["next_direction"] = "stop"
    b1["next_direction"] = "stop"
    state["bombs"] = []
    state["explosions"] = []
    state["powerups"] = []

    state, events = engine.apply_action(state, {"type": "place_bomb"}, p0)
    assert any(e["type"] == "bomb_placed" for e in events)
    # Move placer off the blast row entirely
    b0["x"], b0["y"] = 3, 5
    if state["grid"][5][3] == TILE_HARD:
        b0["x"], b0["y"] = 1, 5
        state["grid"][5][1] = TILE_EMPTY
    else:
        state["grid"][5][3] = TILE_EMPTY
    b0["passable_bomb_ids"] = []
    bomb = state["bombs"][0]
    bomb["fuse"] = 1

    state, events = engine.tick(state)
    assert any(e["type"] == "bomb_exploded" for e in events)
    assert state["grid"][1][2] == TILE_EMPTY
    assert state["bombers"][p0["id"]]["alive"]
    assert not state["bombers"][p1["id"]]["alive"]
    assert state["bombers"][p0["id"]]["kills"] == 1


def test_last_standing_wins(engine: BombermanEngine, state: dict) -> None:
    p0 = state["players"][0]["id"]
    p1 = state["players"][1]["id"]
    state["bombers"][p1]["alive"] = False
    state["bombs"] = []
    state["explosions"] = []

    state, events = engine.tick(state)
    assert state["phase"] == "finished"
    assert state["winner"] == p0
    assert state["win_reason"] == "last_standing"
    assert any(e["type"] == "game_over" for e in events)


def test_countdown_to_playing(engine: BombermanEngine) -> None:
    players = make_players(2)
    state = engine.create_initial_state(players, {"countdown_sec": 3})
    assert state["phase"] == "countdown"
    state["countdown_ends_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    state, events = engine.tick(state)
    assert state["phase"] == "playing"
    assert any(e["type"] == "game_started" for e in events)


def test_powerup_pickup(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]
    other = state["players"][1]["id"]
    state["bombers"][other]["alive"] = False

    for y in range(1, 4):
        for x in range(1, 4):
            if state["grid"][y][x] != TILE_HARD:
                state["grid"][y][x] = TILE_EMPTY
    bomber["x"], bomber["y"] = 1, 1
    bomber["next_direction"] = "right"
    bomber["move_credit"] = 0.0
    state["powerups"] = [{"x": 2, "y": 1, "type": "bomb"}]
    state["bombs"] = []
    state["explosions"] = []

    state, events = engine.tick(state)
    assert state["bombers"][pid]["x"] == 2
    assert state["bombers"][pid]["max_bombs"] == 2
    assert any(e["type"] == "powerup_taken" for e in events)


def test_tick_interval(engine: BombermanEngine) -> None:
    assert engine.tick_interval_ms() == 150
