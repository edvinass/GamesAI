"""Tests for Pac-Man ghost targeting and seat AI."""

from app.games.pacman.ai import (
    choose_ghost_direction,
    choose_pacman_direction,
    ghost_target_tile,
)
from app.games.pacman.engine import PacmanEngine
from app.games.pacman.maps import TILE_PATH, TILE_WALL


def _base_state() -> dict:
    engine = PacmanEngine()
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
    state = engine.create_initial_state(players, {"countdown_sec": 0})
    state["phase"] = "playing"
    state["countdown_ends_at"] = None
    return state


def test_blinky_targets_nearest_pac() -> None:
    state = _base_state()
    state["mode"] = "chase"
    pac = state["pacmen"]["human"]
    pac["x"], pac["y"] = 8, 8
    pac["powered_ticks"] = 0
    state["pacmen"]["ai"]["x"], state["pacmen"]["ai"]["y"] = 1, 1
    blinky = next(g for g in state["ghosts"] if g["name"] == "blinky")
    blinky["x"], blinky["y"] = 10, 8
    blinky["mode"] = "chase"
    blinky["frightened_ticks"] = 0
    blinky["eaten"] = False
    tx, ty = ghost_target_tile(state, blinky)
    assert (tx, ty) == (8, 8)


def test_frightened_ghost_picks_valid_dir() -> None:
    state = _base_state()
    ghost = state["ghosts"][0]
    ghost["mode"] = "frightened"
    ghost["frightened_ticks"] = 20
    ghost["eaten"] = False
    # Place in open area
    for y in range(3, 8):
        for x in range(3, 8):
            state["grid"][y][x] = TILE_PATH
    ghost["x"], ghost["y"] = 5, 5
    ghost["direction"] = "left"
    d = choose_ghost_direction(state, ghost)
    assert d in ("up", "down", "left", "right")


def test_eaten_ghost_targets_home() -> None:
    state = _base_state()
    ghost = state["ghosts"][0]
    ghost["eaten"] = True
    ghost["home"] = [9, 9]
    ghost["x"], ghost["y"] = 3, 3
    tx, ty = ghost_target_tile(state, ghost)
    assert (tx, ty) == (9, 9)


def test_ai_pac_avoids_adjacent_ghost() -> None:
    state = _base_state()
    pac = state["pacmen"]["ai"]
    # Corridor: left is ghost, right is open pellet
    for y in range(0, 7):
        for x in range(0, 7):
            state["grid"][y][x] = TILE_WALL
    state["grid"][3][1] = TILE_PATH
    state["grid"][3][2] = TILE_PATH
    state["grid"][3][3] = TILE_PATH
    state["grid"][3][4] = TILE_PATH
    state["pellets"][3][4] = True
    pac["x"], pac["y"] = 3, 3
    pac["facing"] = "right"
    pac["direction"] = "right"
    pac["powered_ticks"] = 0
    ghost = state["ghosts"][0]
    ghost["x"], ghost["y"] = 1, 3
    ghost["frightened_ticks"] = 0
    ghost["mode"] = "chase"
    ghost["eaten"] = False
    for g in state["ghosts"][1:]:
        g["x"], g["y"] = 0, 0
        g["eaten"] = True

    d = choose_pacman_direction(state, "ai", pac)
    assert d == "right"


def test_ai_pac_chases_frightened_ghost() -> None:
    state = _base_state()
    pac = state["pacmen"]["ai"]
    for y in range(0, 7):
        for x in range(0, 7):
            state["grid"][y][x] = TILE_WALL
    for x in range(1, 6):
        state["grid"][3][x] = TILE_PATH
        state["pellets"][3][x] = False
        state["power_pellets"][3][x] = False
    pac["x"], pac["y"] = 2, 3
    pac["facing"] = "right"
    pac["direction"] = "right"
    pac["powered_ticks"] = 30
    ghost = state["ghosts"][0]
    ghost["x"], ghost["y"] = 5, 3
    ghost["frightened_ticks"] = 30
    ghost["mode"] = "frightened"
    ghost["eaten"] = False
    for g in state["ghosts"][1:]:
        g["eaten"] = True
        g["x"], g["y"] = 0, 0

    d = choose_pacman_direction(state, "ai", pac)
    assert d == "right"
