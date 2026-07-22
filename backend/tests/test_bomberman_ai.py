"""Tests for Bomberman AI survival / escape logic."""

from app.games.bomberman.ai import (
    choose_ai_action,
    _can_escape_after_bomb,
    _danger_times,
)
from app.games.bomberman.engine import TILE_EMPTY, TILE_HARD, TILE_SOFT, BombermanEngine


def _empty_corridor_state() -> dict:
    """3-wide open pocket: safe escape sideways when bombing the center lane."""
    engine = BombermanEngine()
    players = [
        {
            "id": "ai",
            "nickname": "AI",
            "team": None,
            "role": None,
            "is_ai": True,
            "is_connected": True,
        },
        {
            "id": "human",
            "nickname": "Human",
            "team": None,
            "role": None,
            "is_ai": False,
            "is_connected": True,
        },
    ]
    state = engine.create_initial_state(players, {"countdown_sec": 0, "soft_fill": 0.0})
    state["phase"] = "playing"
    state["countdown_ends_at"] = None
    # Clear a region
    for y in range(1, 6):
        for x in range(1, 6):
            if state["grid"][y][x] != TILE_HARD:
                state["grid"][y][x] = TILE_EMPTY
    state["bombs"] = []
    state["explosions"] = []
    state["powerups"] = []
    return state


def test_escape_fails_in_single_tile_dead_end() -> None:
    state = _empty_corridor_state()
    bomber = state["bombers"]["ai"]
    # Trap: only one empty cell surrounded by hard/soft — no exit after bomb.
    for y in range(1, 6):
        for x in range(1, 6):
            state["grid"][y][x] = TILE_HARD
    state["grid"][2][2] = TILE_EMPTY
    bomber["x"], bomber["y"] = 2, 2
    bomber["bomb_range"] = 2

    ok, direction = _can_escape_after_bomb(state, "ai", bomber)
    assert ok is False
    assert direction is None


def test_escape_succeeds_with_side_alley() -> None:
    state = _empty_corridor_state()
    bomber = state["bombers"]["ai"]
    # Vertical corridor; escape two steps right (beyond range-1 blast).
    for y in range(1, 6):
        for x in range(1, 6):
            state["grid"][y][x] = TILE_HARD
    state["grid"][1][2] = TILE_EMPTY
    state["grid"][2][2] = TILE_EMPTY
    state["grid"][3][2] = TILE_EMPTY
    state["grid"][2][3] = TILE_EMPTY  # transit (in blast)
    state["grid"][2][4] = TILE_EMPTY  # safe alcove (beyond range 1)
    bomber["x"], bomber["y"] = 2, 2
    bomber["bomb_range"] = 1
    bomber["passable_bomb_ids"] = []

    ok, direction = _can_escape_after_bomb(state, "ai", bomber)
    assert ok is True
    assert direction == "right"


def test_ai_flees_own_bomb_blast() -> None:
    state = _empty_corridor_state()
    bomber = state["bombers"]["ai"]
    for y in range(1, 5):
        for x in range(1, 5):
            if state["grid"][y][x] != TILE_HARD:
                state["grid"][y][x] = TILE_EMPTY
    bomber["x"], bomber["y"] = 2, 2
    bomber["bomb_range"] = 2
    state["bombs"] = [
        {
            "id": "bomb-1",
            "x": 2,
            "y": 2,
            "owner_id": "ai",
            "range": 2,
            "fuse": 6,
        }
    ]
    bomber["passable_bomb_ids"] = ["bomb-1"]
    # Soft block to the right so fleeing left/up/down into empty is preferred
    state["grid"][2][4] = TILE_SOFT

    direction, place = choose_ai_action(state, "ai", bomber)
    assert place is False
    assert direction in ("up", "down", "left", "right")
    assert direction != "stop"


def test_ai_does_not_bomb_without_escape() -> None:
    state = _empty_corridor_state()
    bomber = state["bombers"]["ai"]
    for y in range(1, 6):
        for x in range(1, 6):
            state["grid"][y][x] = TILE_HARD
    state["grid"][2][2] = TILE_EMPTY
    state["grid"][2][3] = TILE_SOFT  # adjacent soft tempts a bomb
    bomber["x"], bomber["y"] = 2, 2
    bomber["bomb_range"] = 2

    # Force many rolls — should never place
    for _ in range(40):
        _direction, place = choose_ai_action(state, "ai", bomber)
        assert place is False


def test_danger_times_marks_blast_lane() -> None:
    state = _empty_corridor_state()
    for y in range(1, 4):
        for x in range(1, 6):
            if state["grid"][y][x] != TILE_HARD:
                state["grid"][y][x] = TILE_EMPTY
    state["bombs"] = [
        {"id": "b1", "x": 2, "y": 1, "owner_id": "ai", "range": 2, "fuse": 5}
    ]
    danger = _danger_times(state)
    assert danger.get((2, 1)) == 5
    assert danger.get((3, 1)) == 5
    assert danger.get((4, 1)) == 5
