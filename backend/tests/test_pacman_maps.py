from collections import deque

from app.games.pacman.engine import PacmanEngine
from app.games.pacman.maps import (
    MAPS,
    TILE_PATH,
    build_map,
    list_maps,
    pellet_count,
)


def _reachable_from_spawns(built: dict) -> set[tuple[int, int]]:
    grid = built["grid"]
    width = built["width"]
    height = built["height"]
    seen: set[tuple[int, int]] = set()
    q: deque[tuple[int, int]] = deque(built["pac_spawns"])
    for spawn in built["pac_spawns"]:
        seen.add(spawn)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if ny < 0 or ny >= height:
                continue
            if nx < 0:
                nx = width - 1
            elif nx >= width:
                nx = 0
            if (nx, ny) in seen or grid[ny][nx] != TILE_PATH:
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return seen


def test_list_maps_covers_all() -> None:
    listed = list_maps()
    assert len(listed) == len(MAPS)
    ids = {m["id"] for m in listed}
    assert ids == set(MAPS)


def test_every_map_builds() -> None:
    for map_id in MAPS:
        built = build_map(map_id)
        assert built["width"] == MAPS[map_id]["width"]
        assert built["height"] == MAPS[map_id]["height"]
        assert len(built["pac_spawns"]) >= 4
        assert len(built["ghost_homes"]) >= 1
        assert built["gate"] is not None
        for sx, sy in built["pac_spawns"]:
            assert built["grid"][sy][sx] == TILE_PATH
        remaining = pellet_count(built["pellets"], built["power_pellets"])
        assert remaining > 0
        power = sum(sum(1 for c in row if c) for row in built["power_pellets"])
        assert power >= 4


def test_classic_has_tunnels() -> None:
    built = build_map("classic")
    assert len(built["tunnels"]) >= 1


def test_all_pellets_reachable() -> None:
    for map_id in MAPS:
        built = build_map(map_id)
        reachable = _reachable_from_spawns(built)
        for y, row in enumerate(built["pellets"]):
            for x, has in enumerate(row):
                if has:
                    assert (x, y) in reachable, f"{map_id}: pellet at {(x, y)} unreachable"
        for y, row in enumerate(built["power_pellets"]):
            for x, has in enumerate(row):
                if has:
                    assert (x, y) in reachable, f"{map_id}: power at {(x, y)} unreachable"


def test_engine_uses_selected_map() -> None:
    engine = PacmanEngine()
    players = [
        {
            "id": "p0",
            "nickname": "P0",
            "team": None,
            "role": None,
            "is_ai": False,
            "is_connected": True,
        },
        {
            "id": "p1",
            "nickname": "P1",
            "team": None,
            "role": None,
            "is_ai": True,
            "is_connected": True,
        },
    ]
    state = engine.create_initial_state(
        players, {"map_id": "labyrinth", "countdown_sec": 0}
    )
    assert state["map_id"] == "labyrinth"
    assert state["map_name"] == "Labyrinth"
    public = engine.get_public_state(state, players[0])
    assert public["map_id"] == "labyrinth"


def test_unknown_map_falls_back_to_classic() -> None:
    engine = PacmanEngine()
    settings = engine.validate_settings({"map_id": "does_not_exist"})
    assert settings["map_id"] == "classic"
