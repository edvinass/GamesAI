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
    # Place a hard wall north of the bomber
    state["grid"][0][1] = TILE_HARD
    state["grid"][1][1] = TILE_EMPTY
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


def test_blocked_turn_faces_wall_and_stops(engine: BombermanEngine, state: dict) -> None:
    """Holding up into a wall while moving right should face up and stop — not slide."""
    player = state["players"][0]
    pid = player["id"]
    other = state["players"][1]["id"]
    state["bombers"][other]["alive"] = False
    bomber = state["bombers"][pid]

    for x in range(1, 6):
        state["grid"][1][x] = TILE_EMPTY
    # Hard wall directly above the bomber (blocks the held "up" turn)
    state["grid"][0][2] = TILE_HARD

    bomber["x"], bomber["y"] = 2, 1
    bomber["direction"] = "right"
    bomber["next_direction"] = "up"  # blocked — face it, do not keep walking right
    bomber["move_credit"] = 0.0
    state["bombs"] = []
    state["explosions"] = []

    state, _ = engine.tick(state)
    assert state["bombers"][pid]["x"] == 2
    assert state["bombers"][pid]["y"] == 1
    assert state["bombers"][pid]["direction"] == "up"
    assert state["bombers"][pid]["facing"] == "up"


def test_perpetual_still_slides_when_turn_blocked(
    engine: BombermanEngine, state: dict
) -> None:
    """Perpetual disease may keep sliding so a wall cannot fully pin the bomber."""
    player = state["players"][0]
    pid = player["id"]
    other = state["players"][1]["id"]
    state["bombers"][other]["alive"] = False
    bomber = state["bombers"][pid]

    for x in range(1, 6):
        state["grid"][1][x] = TILE_EMPTY
    state["grid"][0][2] = TILE_HARD

    bomber["x"], bomber["y"] = 2, 1
    bomber["direction"] = "right"
    bomber["next_direction"] = "up"
    bomber["disease"] = "perpetual"
    bomber["disease_ticks"] = 100
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

    for x in range(0, 5):
        state["grid"][1][x] = TILE_EMPTY
    bomber["x"], bomber["y"] = 0, 1
    bomber["next_direction"] = "left"  # out of bounds
    bomber["direction"] = "left"
    bomber["move_credit"] = 0.0
    state["bombs"] = []
    state["explosions"] = []

    state, _ = engine.tick(state)
    assert state["phase"] == "playing"
    assert state["bombers"][pid]["x"] == 0
    assert state["bombers"][pid]["move_credit"] >= 0.99

    bomber["next_direction"] = "right"
    state, _ = engine.tick(state)
    assert state["bombers"][pid]["x"] == 1


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


def test_throw_powerup_pickup_and_throw(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]
    other = state["players"][1]["id"]
    # Keep both alive so the match does not end mid-test.
    state["bombers"][other]["x"], state["bombers"][other]["y"] = 13, 11
    state["bombers"][other]["next_direction"] = "stop"

    for y in range(1, 4):
        for x in range(1, 8):
            if state["grid"][y][x] != TILE_HARD:
                state["grid"][y][x] = TILE_EMPTY

    bomber["x"], bomber["y"] = 1, 1
    bomber["next_direction"] = "right"
    bomber["facing"] = "right"
    bomber["move_credit"] = 0.0
    bomber["can_throw"] = False
    state["powerups"] = [{"x": 2, "y": 1, "type": "throw"}]
    state["bombs"] = []
    state["explosions"] = []

    state, events = engine.tick(state)
    assert state["phase"] == "playing"
    assert state["bombers"][pid]["x"] == 2
    assert state["bombers"][pid]["can_throw"] is True
    assert any(e["type"] == "powerup_taken" and e.get("powerup_type") == "throw" for e in events)

    # Plant, then pick up, then throw (classic Power Glove)
    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert any(e["type"] == "bomb_placed" for e in events)
    bomb = state["bombs"][0]
    assert bomb["x"] == 2 and bomb["y"] == 1

    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert any(e["type"] == "bomb_picked_up" for e in events)
    assert bomber["carrying_bomb_id"] == bomb["id"]
    assert bomb["flight"] == "carried"

    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert any(e["type"] == "bomb_thrown" for e in events)
    assert bomber["carrying_bomb_id"] is None
    assert bomb["flight"] == "throw"
    assert bomb["slide_dir"] == "right"
    assert bomb["x"] == 3 and bomb["y"] == 1
    assert bomb["land_x"] == 5 and bomb["land_y"] == 1

    # Continues flying toward landing each tick
    state, _ = engine.tick(state)
    assert bomb["x"] == 4 and bomb["y"] == 1


def test_throw_flies_over_soft_walls(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    other = state["players"][1]["id"]
    state["bombers"][other]["x"], state["bombers"][other]["y"] = 13, 11
    state["bombers"][other]["next_direction"] = "stop"

    bomber = state["bombers"][player["id"]]
    # Soft walls between thrower and the preferred 3-tile landing.
    for x in range(1, 10):
        state["grid"][1][x] = TILE_EMPTY
    state["grid"][1][3] = TILE_SOFT
    state["grid"][1][4] = TILE_SOFT
    bomber["x"], bomber["y"] = 2, 1
    bomber["facing"] = "right"
    bomber["direction"] = "right"
    bomber["can_throw"] = True
    state["bombs"] = [
        {
            "id": "bomb-1",
            "x": 2,
            "y": 1,
            "owner_id": player["id"],
            "range": 1,
            "fuse": 20,
            "flight": None,
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        },
    ]
    state["explosions"] = []
    state["_bomb_seq"] = 1

    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert any(e["type"] == "bomb_picked_up" for e in events)
    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert any(e["type"] == "bomb_thrown" for e in events)
    bomb = next(b for b in state["bombs"] if b["id"] == "bomb-1")
    # Preferred 2+3=5 is empty (soft walls are only at 3–4).
    assert bomb["land_x"] == 5
    assert bomb["land_y"] == 1

    # Fly until landed past the soft walls
    for _ in range(12):
        if bomb.get("flight") != "throw":
            break
        state, _ = engine.tick(state)
    assert bomb["flight"] is None
    assert bomb["x"] == 5 and bomb["y"] == 1
    assert state["grid"][1][3] == TILE_SOFT
    assert state["grid"][1][4] == TILE_SOFT


def test_throw_skips_blocked_preferred_landing(engine: BombermanEngine, state: dict) -> None:
    """If the 3-tile cell is blocked, land on the next empty tile beyond it."""
    player = state["players"][0]
    other = state["players"][1]["id"]
    state["bombers"][other]["x"], state["bombers"][other]["y"] = 13, 11
    state["bombers"][other]["next_direction"] = "stop"

    bomber = state["bombers"][player["id"]]
    for x in range(1, 12):
        state["grid"][1][x] = TILE_EMPTY
    # Preferred landing (2+3=5) is a soft wall; next empty is 6, then a bomb at 7.
    state["grid"][1][5] = TILE_SOFT
    bomber["x"], bomber["y"] = 2, 1
    bomber["facing"] = "right"
    bomber["direction"] = "right"
    bomber["can_throw"] = True
    state["bombs"] = [
        {
            "id": "bomb-1",
            "x": 2,
            "y": 1,
            "owner_id": player["id"],
            "range": 1,
            "fuse": 20,
            "flight": None,
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        },
        {
            "id": "blocker",
            "x": 7,
            "y": 1,
            "owner_id": other,
            "range": 1,
            "fuse": 20,
            "flight": None,
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        },
    ]
    state["explosions"] = []
    state["_bomb_seq"] = 2

    state, _ = engine.apply_action(state, {"type": "place_bomb"}, player)
    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert any(e["type"] == "bomb_thrown" for e in events)
    bomb = next(b for b in state["bombs"] if b["id"] == "bomb-1")
    assert bomb["land_x"] == 6
    assert bomb["land_y"] == 1

    for _ in range(12):
        if bomb.get("flight") != "throw":
            break
        state, _ = engine.tick(state)
    assert bomb["flight"] is None
    assert bomb["x"] == 6 and bomb["y"] == 1


def test_throw_skips_bomb_on_preferred_landing(engine: BombermanEngine, state: dict) -> None:
    """If another bomb sits on the 3-tile cell, land on the next empty beyond it."""
    player = state["players"][0]
    other = state["players"][1]["id"]
    state["bombers"][other]["x"], state["bombers"][other]["y"] = 13, 11
    state["bombers"][other]["next_direction"] = "stop"

    bomber = state["bombers"][player["id"]]
    for x in range(1, 12):
        state["grid"][1][x] = TILE_EMPTY
    bomber["x"], bomber["y"] = 2, 1
    bomber["facing"] = "right"
    bomber["direction"] = "right"
    bomber["can_throw"] = True
    state["bombs"] = [
        {
            "id": "bomb-1",
            "x": 2,
            "y": 1,
            "owner_id": player["id"],
            "range": 1,
            "fuse": 20,
            "flight": None,
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        },
        {
            "id": "blocker",
            "x": 5,
            "y": 1,
            "owner_id": other,
            "range": 1,
            "fuse": 20,
            "flight": None,
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        },
    ]
    state["explosions"] = []
    state["_bomb_seq"] = 2

    # Preferred landing (2+3=5) is occupied by blocker → bounce to 6.
    assert engine._find_throw_landing(
        state, 2, 1, "right", ignore_bomb_id="bomb-1"
    ) == (6, 1)

    state, _ = engine.apply_action(state, {"type": "place_bomb"}, player)
    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert any(e["type"] == "bomb_thrown" for e in events)
    bomb = next(b for b in state["bombs"] if b["id"] == "bomb-1")
    blocker = next(b for b in state["bombs"] if b["id"] == "blocker")
    assert bomb["land_x"] == 6
    assert bomb["land_y"] == 1

    for _ in range(12):
        if bomb.get("flight") != "throw":
            break
        state, _ = engine.tick(state)
    assert bomb["flight"] is None
    assert bomb["x"] == 6 and bomb["y"] == 1
    assert blocker["x"] == 5 and blocker["y"] == 1
    # Must not stack on the blocking bomb.
    assert (bomb["x"], bomb["y"]) != (blocker["x"], blocker["y"])


def test_throw_landing_treats_bomb_as_obstacle(engine: BombermanEngine, state: dict) -> None:
    """Direct landing helper: bombs block the preferred tile and force a bounce."""
    for x in range(1, 12):
        state["grid"][1][x] = TILE_EMPTY
    state["bombs"] = [
        {
            "id": "thrown",
            "x": 1,
            "y": 1,
            "owner_id": state["players"][0]["id"],
            "range": 1,
            "fuse": 20,
            "flight": "carried",
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        },
        {
            "id": "blocker",
            "x": 4,
            "y": 1,
            "owner_id": state["players"][1]["id"],
            "range": 1,
            "fuse": 20,
            "flight": None,
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        },
    ]
    # From x=1, preferred is x=4 (occupied) → next empty x=5.
    assert engine._throw_cell_landable(state, 4, 1, ignore_bomb_id="thrown") is False
    assert engine._find_throw_landing(
        state, 1, 1, "right", ignore_bomb_id="thrown"
    ) == (5, 1)

def test_throw_opponent_bomb(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    other = state["players"][1]["id"]
    state["bombers"][other]["x"], state["bombers"][other]["y"] = 13, 11
    state["bombers"][other]["next_direction"] = "stop"

    bomber = state["bombers"][player["id"]]
    for x in range(1, 10):
        state["grid"][1][x] = TILE_EMPTY
    bomber["x"], bomber["y"] = 1, 1
    bomber["facing"] = "right"
    bomber["can_throw"] = True
    bomber["next_direction"] = "stop"
    bomber["move_credit"] = 0.0
    state["bombs"] = [
        {
            "id": "enemy-bomb",
            "x": 2,
            "y": 1,
            "owner_id": other,
            "range": 2,
            "fuse": 12,
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        }
    ]
    state["explosions"] = []

    # Walking onto a bomb no longer picks it up — bombs block without kick/passable.
    assert not engine._is_walkable(state, bomber, 2, 1)
    bomber["next_direction"] = "right"
    bomber["move_credit"] = 1.0
    state, events = engine.tick(state)
    assert bomber["x"] == 1 and bomber["y"] == 1
    assert bomber["carrying_bomb_id"] is None
    assert not any(e["type"] == "bomb_picked_up" for e in events)

    # Face the bomb and press Space to pick it up.
    bomber["facing"] = "right"
    bomber["next_direction"] = "stop"
    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert bomber["carrying_bomb_id"] == "enemy-bomb"
    assert any(e["type"] == "bomb_picked_up" for e in events)

    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert any(e["type"] == "bomb_thrown" for e in events)
    bomb = state["bombs"][0]
    assert bomb["owner_id"] == other
    assert bomb["flight"] == "throw"
    assert bomb["x"] == 2
    assert bomb["land_x"] == 4 and bomb["land_y"] == 1

def test_throw_blocked_without_powerup(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]
    other = state["players"][1]["id"]
    state["bombers"][other]["x"], state["bombers"][other]["y"] = 13, 11
    bomber["can_throw"] = False
    bomber["x"], bomber["y"] = 1, 1
    for x in range(1, 4):
        if state["grid"][1][x] != TILE_HARD:
            state["grid"][1][x] = TILE_EMPTY

    state, _ = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert len(state["bombs"]) == 1
    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert not any(e["type"] == "bomb_thrown" for e in events)
    assert state["bombs"][0]["x"] == bomber["x"]


def test_kick_bomb_along_ground(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    other = state["players"][1]["id"]
    state["bombers"][other]["x"], state["bombers"][other]["y"] = 13, 11
    state["bombers"][other]["next_direction"] = "stop"

    bomber = state["bombers"][player["id"]]
    for x in range(1, 8):
        state["grid"][1][x] = TILE_EMPTY
    # Soft wall stops a kick (unlike throw)
    state["grid"][1][6] = TILE_SOFT

    bomber["x"], bomber["y"] = 1, 1
    bomber["facing"] = "right"
    bomber["next_direction"] = "right"
    bomber["move_credit"] = 1.0
    bomber["can_kick"] = True
    bomber["can_throw"] = False
    state["bombs"] = [
        {
            "id": "bomb-1",
            "x": 2,
            "y": 1,
            "owner_id": other,
            "range": 1,
            "fuse": 20,
            "flight": None,
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        }
    ]
    state["explosions"] = []
    state["powerups"] = []

    state, events = engine.tick(state)
    assert any(e["type"] == "bomb_kicked" for e in events)
    bomb = state["bombs"][0]
    assert bomb["flight"] == "kick"
    assert bomb["x"] == 3
    assert bomber["x"] == 2  # walked into vacated cell

    # Continues sliding on the floor; stops before soft wall at x=6
    for _ in range(10):
        if not bomb.get("flight"):
            break
        state, _ = engine.tick(state)
    assert bomb["flight"] is None
    assert bomb["x"] == 5
    assert state["grid"][1][6] == TILE_SOFT


def test_kick_stops_at_hard_wall(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    other = state["players"][1]["id"]
    state["bombers"][other]["x"], state["bombers"][other]["y"] = 13, 11

    bomber = state["bombers"][player["id"]]
    bomber["can_kick"] = True
    bomber["x"], bomber["y"] = 1, 1
    bomber["facing"] = "left"
    # Bomb on the left edge — cannot kick further left (out of bounds)
    state["grid"][1][0] = TILE_EMPTY
    state["bombs"] = [
        {
            "id": "bomb-1",
            "x": 0,
            "y": 1,
            "owner_id": player["id"],
            "range": 1,
            "fuse": 10,
            "flight": None,
            "sliding": False,
            "slide_dir": None,
            "land_x": None,
            "land_y": None,
        }
    ]
    assert engine._can_kick_bomb(state, state["bombs"][0], "left") is False
    assert engine._is_walkable(state, bomber, 0, 1) is False


def test_tick_interval(engine: BombermanEngine) -> None:
    assert engine.tick_interval_ms() == 150


def _clear_arena(state: dict, x0: int = 1, y0: int = 1, x1: int = 6, y1: int = 4) -> None:
    for y in range(y0, y1):
        for x in range(x0, x1):
            if state["grid"][y][x] != TILE_HARD:
                state["grid"][y][x] = TILE_EMPTY


def test_skull_pickup_infects(engine: BombermanEngine, state: dict) -> None:
    from app.games.bomberman.engine import DISEASE_TYPES, DISEASE_DURATION_TICKS

    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]
    other = state["players"][1]["id"]
    state["bombers"][other]["alive"] = False

    _clear_arena(state)
    bomber["x"], bomber["y"] = 1, 1
    bomber["next_direction"] = "right"
    bomber["move_credit"] = 0.0
    state["powerups"] = [{"x": 2, "y": 1, "type": "skull"}]
    state["bombs"] = []
    state["explosions"] = []

    state, events = engine.tick(state)
    assert state["bombers"][pid]["x"] == 2
    assert state["bombers"][pid]["disease"] in DISEASE_TYPES
    assert state["bombers"][pid]["disease_ticks"] == DISEASE_DURATION_TICKS
    assert any(e["type"] == "powerup_taken" and e.get("powerup_type") == "skull" for e in events)
    assert any(e["type"] == "disease_infected" for e in events)


def test_constipation_blocks_plant(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]
    engine._infect(bomber, "constipation")
    bomber["x"], bomber["y"] = 1, 1
    _clear_arena(state)
    state["bombs"] = []

    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert state["bombs"] == []
    assert not any(e["type"] == "bomb_placed" for e in events)


def test_short_fuse_disease(engine: BombermanEngine, state: dict) -> None:
    from app.games.bomberman.engine import SHORT_FUSE

    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]
    engine._infect(bomber, "short_fuse")
    bomber["x"], bomber["y"] = 1, 1
    _clear_arena(state)
    state["bombs"] = []

    state, events = engine.apply_action(state, {"type": "place_bomb"}, player)
    assert len(state["bombs"]) == 1
    assert state["bombs"][0]["fuse"] == SHORT_FUSE
    assert any(e["type"] == "bomb_placed" for e in events)


def test_reverse_flips_controls(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]
    engine._infect(bomber, "reverse")

    state, _ = engine.apply_action(state, {"type": "set_direction", "direction": "up"}, player)
    assert state["bombers"][pid]["next_direction"] == "down"
    assert state["bombers"][pid]["facing"] == "down"


def test_slow_reduces_move_rate(engine: BombermanEngine, state: dict) -> None:
    from app.games.bomberman.engine import BASE_MOVE_RATE, SLOW_MOVE_RATE

    bomber = state["bombers"][state["players"][0]["id"]]
    bomber["speed_level"] = 3
    assert engine._move_rate(bomber) > BASE_MOVE_RATE
    engine._infect(bomber, "slow")
    assert engine._move_rate(bomber) == SLOW_MOVE_RATE


def test_diarrhea_plants_on_step(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]
    other = state["players"][1]["id"]
    state["bombers"][other]["alive"] = False

    _clear_arena(state)
    engine._infect(bomber, "diarrhea")
    bomber["x"], bomber["y"] = 1, 1
    bomber["next_direction"] = "right"
    bomber["move_credit"] = 0.0
    bomber["max_bombs"] = 4
    state["bombs"] = []
    state["explosions"] = []
    state["powerups"] = []

    state, events = engine.tick(state)
    assert state["bombers"][pid]["x"] == 2
    assert any(e["type"] == "bomb_placed" for e in events)
    assert any(b["x"] == 2 and b["y"] == 1 for b in state["bombs"])


def test_perpetual_keeps_moving(engine: BombermanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    bomber = state["bombers"][pid]
    other = state["players"][1]["id"]
    state["bombers"][other]["alive"] = False

    _clear_arena(state)
    engine._infect(bomber, "perpetual")
    bomber["x"], bomber["y"] = 1, 1
    bomber["facing"] = "right"
    bomber["direction"] = "right"
    bomber["next_direction"] = "stop"
    bomber["move_credit"] = 0.0
    state["bombs"] = []
    state["explosions"] = []
    state["powerups"] = []

    state, _ = engine.tick(state)
    assert state["bombers"][pid]["x"] == 2
    assert engine._desired_move_direction(state["bombers"][pid]) == "right"


def test_disease_transfers_on_contact(engine: BombermanEngine, state: dict) -> None:
    p0 = state["players"][0]["id"]
    p1 = state["players"][1]["id"]
    a = state["bombers"][p0]
    b = state["bombers"][p1]
    a["x"], a["y"] = 3, 3
    b["x"], b["y"] = 3, 3
    a["alive"] = b["alive"] = True
    engine._infect(a, "reverse", ticks=20)
    engine._clear_disease(b)

    events = engine._spread_diseases(state)
    assert a.get("disease") is None
    assert b.get("disease") == "reverse"
    assert b.get("disease_ticks") == 20
    assert any(e["type"] == "disease_infected" and e["player_id"] == p1 for e in events)
