from datetime import datetime, timedelta, timezone

import pytest

from app.games.pacman.engine import PacmanEngine
from app.games.pacman.maps import TILE_PATH, TILE_WALL


def make_players(count: int = 2, *, ai_from: int | None = None) -> list[dict]:
    players = []
    for i in range(count):
        is_ai = ai_from is not None and i >= ai_from
        players.append(
            {
                "id": f"p{i}",
                "nickname": f"Player {i}",
                "team": None,
                "role": None,
                "is_ai": is_ai,
                "is_connected": True,
            }
        )
    return players


@pytest.fixture
def engine() -> PacmanEngine:
    return PacmanEngine()


@pytest.fixture
def state(engine: PacmanEngine) -> dict:
    players = make_players(2)
    s = engine.create_initial_state(players, {"countdown_sec": 0})
    s["phase"] = "playing"
    s["countdown_ends_at"] = None
    return s


def test_lobby_validation(engine: PacmanEngine) -> None:
    assert engine.validate_lobby(make_players(1), {}) is not None
    assert engine.validate_lobby(make_players(2), {}) is None
    assert engine.validate_lobby(make_players(5), {}) is not None
    assert engine.validate_lobby(make_players(1), {"solo_practice": True}) is None
    assert engine.validate_lobby(make_players(2), {"solo_practice": True}) is not None
    assert engine.validate_lobby(make_players(1), {"single_player": True}) is None
    assert engine.validate_lobby(make_players(2), {"single_player": True}) is not None
    # Leftover AI is allowed in lobby validation — removed when enabling mode / on start.
    assert engine.validate_lobby(make_players(2, ai_from=1), {"single_player": True}) is None


def test_single_player_settings_disable_solo_practice(engine: PacmanEngine) -> None:
    settings = engine.validate_settings(
        {"single_player": True, "solo_practice": True}
    )
    assert settings["single_player"] is True
    assert settings["solo_practice"] is False


def test_initial_state(engine: PacmanEngine) -> None:
    players = make_players(4)
    state = engine.create_initial_state(players, {})
    assert len(state["pacmen"]) == 4
    assert len(state["ghosts"]) == 4
    assert state["phase"] == "countdown"
    assert state["pellets_remaining"] > 0
    occupied: set[tuple[int, int]] = set()
    for pac in state["pacmen"].values():
        key = (pac["x"], pac["y"])
        assert key not in occupied
        occupied.add(key)
        assert state["grid"][pac["y"]][pac["x"]] == TILE_PATH


def test_set_direction(engine: PacmanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state, _ = engine.apply_action(
        state, {"type": "set_direction", "direction": "up"}, player
    )
    assert state["pacmen"][pid]["next_direction"] == "up"


def test_movement_blocked_by_wall(engine: PacmanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    other = state["players"][1]["id"]
    pac = state["pacmen"][pid]
    state["pacmen"][other]["x"] = state["grid_width"] - 2
    state["pacmen"][other]["y"] = state["grid_height"] - 2

    # Seal a single open cell.
    for y in range(state["grid_height"]):
        for x in range(state["grid_width"]):
            state["grid"][y][x] = TILE_WALL
    state["grid"][5][5] = TILE_PATH
    pac["x"], pac["y"] = 5, 5
    pac["direction"] = "up"
    pac["next_direction"] = "up"
    pac["move_credit"] = 0.0
    for g in state["ghosts"]:
        g["x"], g["y"] = 1, 1

    ox, oy = pac["x"], pac["y"]
    state, _ = engine.tick(state)
    assert state["pacmen"][pid]["x"] == ox
    assert state["pacmen"][pid]["y"] == oy


def test_pellet_pickup(engine: PacmanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    other = state["players"][1]["id"]
    pac = state["pacmen"][pid]
    state["pacmen"][other]["x"] = state["grid_width"] - 2
    state["pacmen"][other]["y"] = state["grid_height"] - 2

    for y in range(state["grid_height"]):
        for x in range(state["grid_width"]):
            state["pellets"][y][x] = False
            state["power_pellets"][y][x] = False
            if state["grid"][y][x] == TILE_PATH:
                state["grid"][y][x] = TILE_PATH
    state["grid"][4][4] = TILE_PATH
    state["grid"][4][5] = TILE_PATH
    state["pellets"][4][5] = True
    state["pellets_remaining"] = 1
    pac["x"], pac["y"] = 4, 4
    pac["direction"] = "right"
    pac["next_direction"] = "right"
    pac["move_credit"] = 0.0
    for g in state["ghosts"]:
        g["x"], g["y"] = 1, 1
        g["move_credit"] = -10

    state, events = engine.tick(state)
    assert state["pacmen"][pid]["x"] == 5
    assert state["pacmen"][pid]["score"] == 10
    assert state["pellets"][4][5] is False
    assert any(e["type"] == "pellet" for e in events)


def test_power_pellet_frightens_ghosts(engine: PacmanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    other = state["players"][1]["id"]
    pac = state["pacmen"][pid]
    state["pacmen"][other]["x"] = state["grid_width"] - 2
    state["pacmen"][other]["y"] = state["grid_height"] - 2

    for y in range(state["grid_height"]):
        for x in range(state["grid_width"]):
            state["pellets"][y][x] = False
            state["power_pellets"][y][x] = False
    state["grid"][4][4] = TILE_PATH
    state["grid"][4][5] = TILE_PATH
    state["power_pellets"][4][5] = True
    state["pellets_remaining"] = 1
    pac["x"], pac["y"] = 4, 4
    pac["direction"] = "right"
    pac["next_direction"] = "right"
    pac["move_credit"] = 0.0
    for g in state["ghosts"]:
        g["x"], g["y"] = 1, 1
        g["move_credit"] = -10

    state, events = engine.tick(state)
    assert state["pacmen"][pid]["powered_ticks"] > 0
    assert any(e["type"] == "power_pellet" for e in events)
    assert all(int(g["frightened_ticks"]) > 0 for g in state["ghosts"])


def test_powered_pac_eats_ghost(engine: PacmanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    other = state["players"][1]["id"]
    pac = state["pacmen"][pid]
    state["pacmen"][other]["x"] = state["grid_width"] - 2
    state["pacmen"][other]["y"] = state["grid_height"] - 2
    pac["x"], pac["y"] = 6, 6
    pac["powered_ticks"] = 20
    pac["invuln_ticks"] = 0
    pac["respawn_ticks"] = 0
    ghost = state["ghosts"][0]
    ghost["x"], ghost["y"] = 6, 6
    ghost["frightened_ticks"] = 20
    ghost["mode"] = "frightened"
    ghost["eaten"] = False
    for g in state["ghosts"][1:]:
        g["x"], g["y"] = 1, 1

    events = engine._resolve_collisions(state)
    assert any(e["type"] == "ghost_eaten" for e in events)
    assert ghost["eaten"] is True
    assert state["pacmen"][pid]["score"] >= 200


def test_ghost_hurts_pac(engine: PacmanEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    other = state["players"][1]["id"]
    pac = state["pacmen"][pid]
    state["pacmen"][other]["x"] = state["grid_width"] - 2
    state["pacmen"][other]["y"] = state["grid_height"] - 2
    lives_before = pac["lives"]
    pac["x"], pac["y"] = 6, 6
    pac["powered_ticks"] = 0
    pac["invuln_ticks"] = 0
    pac["respawn_ticks"] = 0
    ghost = state["ghosts"][0]
    ghost["x"], ghost["y"] = 6, 6
    ghost["frightened_ticks"] = 0
    ghost["mode"] = "chase"
    ghost["eaten"] = False

    events = engine._resolve_collisions(state)
    assert any(e["type"] == "life_lost" for e in events)
    assert state["pacmen"][pid]["lives"] == lives_before - 1


def test_powered_pac_eats_rival(engine: PacmanEngine, state: dict) -> None:
    a = state["players"][0]
    b = state["players"][1]
    pa = state["pacmen"][a["id"]]
    pb = state["pacmen"][b["id"]]
    pa["x"], pa["y"] = 7, 7
    pb["x"], pb["y"] = 7, 7
    pa["powered_ticks"] = 20
    pb["powered_ticks"] = 0
    pa["invuln_ticks"] = pb["invuln_ticks"] = 0
    pa["respawn_ticks"] = pb["respawn_ticks"] = 0
    for g in state["ghosts"]:
        g["x"], g["y"] = 1, 1

    lives_before = pb["lives"]
    events = engine._resolve_collisions(state)
    assert any(e["type"] == "pac_eaten" for e in events)
    assert state["pacmen"][b["id"]]["lives"] == lives_before - 1
    assert state["pacmen"][a["id"]]["score"] >= 500


def test_tunnel_wrap(engine: PacmanEngine, state: dict) -> None:
    from app.games.pacman.maps import wrap_through_tunnel

    tunnels = state["tunnels"]
    assert tunnels
    t = tunnels[0]
    x, y = wrap_through_tunnel(
        t["left_x"],
        t["y"],
        -1,
        0,
        state["grid_width"],
        state["grid_height"],
        tunnels,
    )
    assert x == t["right_x"]
    assert y == t["y"]


def test_last_standing_wins(engine: PacmanEngine, state: dict) -> None:
    a = state["players"][0]["id"]
    b = state["players"][1]["id"]
    state["pacmen"][b]["alive"] = False
    state["pacmen"][b]["lives"] = 0
    events = engine._maybe_finish(state)
    assert state["phase"] == "finished"
    assert state["winner"] == a
    assert state["win_reason"] == "last_standing"
    assert any(e["type"] == "game_over" for e in events)


def test_single_player_does_not_end_while_alive(engine: PacmanEngine) -> None:
    players = make_players(1)
    state = engine.create_initial_state(
        players, {"countdown_sec": 0, "single_player": True}
    )
    state["phase"] = "playing"
    events = engine._maybe_finish(state)
    assert state["phase"] == "playing"
    assert events == []


def test_single_player_ends_out_of_lives(engine: PacmanEngine) -> None:
    players = make_players(1)
    state = engine.create_initial_state(
        players, {"countdown_sec": 0, "single_player": True}
    )
    state["phase"] = "playing"
    pid = players[0]["id"]
    state["pacmen"][pid]["alive"] = False
    state["pacmen"][pid]["lives"] = 0
    state["pacmen"][pid]["score"] = 420
    events = engine._maybe_finish(state)
    assert state["phase"] == "finished"
    assert state["winner"] == pid
    assert state["win_reason"] == "out_of_lives"
    assert any(e["type"] == "game_over" for e in events)


def test_single_player_maze_clear(engine: PacmanEngine) -> None:
    players = make_players(1)
    state = engine.create_initial_state(
        players, {"countdown_sec": 0, "single_player": True}
    )
    state["phase"] = "playing"
    pid = players[0]["id"]
    state["pacmen"][pid]["score"] = 999
    state["pellets_remaining"] = 0
    for y in range(state["grid_height"]):
        for x in range(state["grid_width"]):
            state["pellets"][y][x] = False
            state["power_pellets"][y][x] = False
    events = engine._maybe_finish(state)
    assert state["phase"] == "finished"
    assert state["winner"] == pid
    assert state["win_reason"] == "maze_clear"
    assert any(e["type"] == "game_over" for e in events)


def test_maze_clear_highest_score(engine: PacmanEngine, state: dict) -> None:
    a = state["players"][0]["id"]
    b = state["players"][1]["id"]
    state["pacmen"][a]["score"] = 100
    state["pacmen"][b]["score"] = 50
    state["pellets_remaining"] = 0
    for y in range(state["grid_height"]):
        for x in range(state["grid_width"]):
            state["pellets"][y][x] = False
            state["power_pellets"][y][x] = False
    events = engine._maybe_finish(state)
    assert state["phase"] == "finished"
    assert state["winner"] == a
    assert state["win_reason"] == "maze_clear"


def test_countdown_starts_game(engine: PacmanEngine) -> None:
    players = make_players(2)
    state = engine.create_initial_state(players, {"countdown_sec": 3})
    assert state["phase"] == "countdown"
    state["countdown_ends_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    state, events = engine.tick(state)
    assert state["phase"] == "playing"
    assert any(e["type"] == "game_started" for e in events)


def test_tick_interval(engine: PacmanEngine) -> None:
    assert engine.tick_interval_ms() == 120


def test_public_state_hides_private_fields(engine: PacmanEngine, state: dict) -> None:
    state["ghosts"][0]["_force_reverse"] = True
    public = engine.get_public_state(state, state["players"][0])
    assert "viewer_id" in public
    assert all("_force_reverse" not in g for g in public["ghosts"])
