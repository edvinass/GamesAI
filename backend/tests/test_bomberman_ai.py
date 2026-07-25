"""Tests for Bomberman AI survival / escape logic."""

from app.games.bomberman.ai import (
    choose_ai_action,
    _best_throw_direction,
    _can_escape_after_bomb,
    _danger_times,
    _predicted_enemy_cells,
    _trap_positions,
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
    for y in range(0, 7):
        for x in range(0, 7):
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
    # Seal rows/cols around the pocket (no map border walls anymore).
    for y in range(0, 7):
        for x in range(0, 7):
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


def test_ai_bombs_when_enemy_in_range_with_escape() -> None:
    state = _empty_corridor_state()
    bomber = state["bombers"]["ai"]
    human = state["bombers"]["human"]
    for y in range(1, 6):
        for x in range(1, 8):
            if state["grid"][y][x] != TILE_HARD:
                state["grid"][y][x] = TILE_EMPTY
    # Open pocket with side escape
    bomber["x"], bomber["y"] = 2, 2
    bomber["bomb_range"] = 2
    bomber["max_bombs"] = 1
    human["x"], human["y"] = 4, 2
    human["alive"] = True
    state["grid"][2][3] = TILE_EMPTY
    state["grid"][2][4] = TILE_EMPTY
    state["grid"][3][2] = TILE_EMPTY  # escape south
    state["grid"][4][2] = TILE_EMPTY

    placed = 0
    for _ in range(30):
        _direction, place = choose_ai_action(state, "ai", bomber)
        if place:
            placed += 1
    assert placed >= 10  # should bomb aggressively when escape exists


def test_ai_starts_with_stat_boost() -> None:
    engine = BombermanEngine()
    players = [
        {
            "id": "h",
            "nickname": "H",
            "team": None,
            "role": None,
            "is_ai": False,
            "is_connected": True,
        },
        {
            "id": "a",
            "nickname": "A",
            "team": None,
            "role": None,
            "is_ai": True,
            "is_connected": True,
        },
    ]
    state = engine.create_initial_state(players, {})
    assert state["bombers"]["h"]["bomb_range"] == 1
    assert state["bombers"]["h"]["max_bombs"] == 1
    assert state["bombers"]["a"]["bomb_range"] == 2
    assert state["bombers"]["a"]["max_bombs"] == 2
    # No free speed — AI acts at base move rate and thinks on an interval.
    assert state["bombers"]["a"]["speed_level"] == 0


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


def test_predicted_enemy_cells_follow_facing() -> None:
    state = _empty_corridor_state()
    # Force an open lane (including hard pillars).
    for y in range(1, 5):
        for x in range(1, 8):
            state["grid"][y][x] = TILE_EMPTY
    human = state["bombers"]["human"]
    human["x"], human["y"] = 2, 2
    human["next_direction"] = "right"
    human["facing"] = "right"
    cells = _predicted_enemy_cells(state, human)
    assert (2, 2) in cells
    assert (3, 2) in cells
    assert (4, 2) in cells


def test_aimed_throw_prefers_enemy_lane() -> None:
    state = _empty_corridor_state()
    bomber = state["bombers"]["ai"]
    human = state["bombers"]["human"]
    for y in range(1, 6):
        for x in range(1, 10):
            state["grid"][y][x] = TILE_EMPTY
    bomber["x"], bomber["y"] = 2, 2
    bomber["bomb_range"] = 3
    bomber["can_throw"] = True
    bomber["carrying_bomb_id"] = "held"
    human["x"], human["y"] = 6, 2
    human["alive"] = True
    state["bombs"] = [
        {
            "id": "held",
            "x": 2,
            "y": 2,
            "owner_id": "ai",
            "range": 3,
            "fuse": 10,
            "flight": "carried",
        }
    ]

    direction = _best_throw_direction(state, "ai", bomber)
    assert direction == "right"


def test_ai_throws_toward_enemy_when_carrying() -> None:
    state = _empty_corridor_state()
    bomber = state["bombers"]["ai"]
    human = state["bombers"]["human"]
    for y in range(1, 6):
        for x in range(1, 10):
            state["grid"][y][x] = TILE_EMPTY
    state["powerups"] = []
    bomber["x"], bomber["y"] = 2, 2
    bomber["bomb_range"] = 3
    bomber["can_throw"] = True
    bomber["carrying_bomb_id"] = "held"
    human["x"], human["y"] = 6, 2
    human["alive"] = True
    state["bombs"] = [
        {
            "id": "held",
            "x": 2,
            "y": 2,
            "owner_id": "ai",
            "range": 3,
            "fuse": 10,
            "flight": "carried",
        }
    ]

    direction, place = choose_ai_action(state, "ai", bomber)
    assert place is True
    assert direction == "right"


def test_trap_positions_include_choke_tile() -> None:
    state = _empty_corridor_state()
    bomber = state["bombers"]["ai"]
    human = state["bombers"]["human"]
    # Dead-end pocket: enemy at (2,2) with only escape through (3,2); AI can plant at (4,2).
    for y in range(0, 7):
        for x in range(0, 8):
            state["grid"][y][x] = TILE_HARD
    state["grid"][2][2] = TILE_EMPTY
    state["grid"][2][3] = TILE_EMPTY
    state["grid"][2][4] = TILE_EMPTY
    state["grid"][2][5] = TILE_EMPTY
    state["grid"][3][4] = TILE_EMPTY  # AI escape south
    state["grid"][4][4] = TILE_EMPTY
    bomber["x"], bomber["y"] = 5, 2
    bomber["bomb_range"] = 3
    human["x"], human["y"] = 2, 2
    human["alive"] = True
    human["next_direction"] = "stop"
    human["facing"] = "right"

    danger = _danger_times(state)
    traps = _trap_positions(state, "ai", bomber, danger)
    assert (4, 2) in traps or (3, 2) in traps


def test_ai_steps_onto_kill_tile_before_bombing() -> None:
    state = _empty_corridor_state()
    bomber = state["bombers"]["ai"]
    human = state["bombers"]["human"]
    for y in range(1, 6):
        for x in range(1, 9):
            state["grid"][y][x] = TILE_EMPTY
    state["powerups"] = []
    state["bombs"] = []
    # Current tile does not cover enemy (or predicted path); one step right does.
    bomber["x"], bomber["y"] = 3, 2
    bomber["bomb_range"] = 2
    bomber["max_bombs"] = 1
    human["x"], human["y"] = 6, 2
    human["alive"] = True
    human["next_direction"] = "stop"
    human["facing"] = "right"  # predicts away from AI

    direction, place = choose_ai_action(state, "ai", bomber)
    assert place is False
    assert direction == "right"
