import random

from app.games.bomberman.engine import BombermanEngine, TILE_EMPTY, TILE_HARD
from app.games.bomberman.maps import MAPS, _non_hard_reachable, build_map_grid, list_maps


def test_list_maps_covers_all() -> None:
    listed = list_maps()
    assert len(listed) == len(MAPS)
    ids = {m["id"] for m in listed}
    assert ids == set(MAPS)


def test_every_map_builds_and_has_clear_spawns() -> None:
    for map_id in MAPS:
        grid, spawns, meta = build_map_grid(map_id)
        assert len(grid) == meta["height"]
        assert len(grid[0]) == meta["width"]
        assert len(spawns) >= 4
        for sx, sy in spawns:
            assert grid[sy][sx] == TILE_EMPTY
        # Edges are playable (no solid hard-wall ring)
        height = len(grid)
        width = len(grid[0])
        edge_empty = 0
        for x in range(width):
            if grid[0][x] == TILE_EMPTY:
                edge_empty += 1
            if grid[height - 1][x] == TILE_EMPTY:
                edge_empty += 1
        for y in range(height):
            if grid[y][0] == TILE_EMPTY:
                edge_empty += 1
            if grid[y][width - 1] == TILE_EMPTY:
                edge_empty += 1
        assert edge_empty > 0


def test_spawns_not_sealed_by_hard_walls() -> None:
    """Hard walls must not trap a bomber in a pocket cut off from center."""
    for map_id in MAPS:
        for seed in range(8):
            random.seed(seed)
            grid, spawns, meta = build_map_grid(map_id)
            height = len(grid)
            width = len(grid[0])
            cx, cy = width // 2, height // 2
            if grid[cy][cx] == TILE_HARD:
                # Same fallback as ensure_spawn_access: nearest non-hard cell.
                target = None
                for radius in range(1, max(width, height)):
                    for dy in range(-radius, radius + 1):
                        for dx in range(-radius, radius + 1):
                            x, y = cx + dx, cy + dy
                            if 0 <= x < width and 0 <= y < height and grid[y][x] != TILE_HARD:
                                target = (x, y)
                                break
                        if target:
                            break
                    if target:
                        break
                assert target is not None
                cx, cy = target
            for sx, sy in spawns:
                assert grid[sy][sx] != TILE_HARD
                region = _non_hard_reachable(grid, sx, sy)
                assert (cx, cy) in region, f"{map_id} seed={seed} spawn={(sx, sy)}"
                assert len(region) >= 12, f"{map_id} seed={seed} spawn={(sx, sy)} region={len(region)}"


def test_engine_uses_selected_map() -> None:
    engine = BombermanEngine()
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
    state = engine.create_initial_state(players, {"map_id": "fortress", "countdown_sec": 0})
    assert state["map_id"] == "fortress"
    assert state["map_name"] == "Fortress"
    public = engine.get_public_state(state, players[0])
    assert public["map_id"] == "fortress"
    assert public["map_name"] == "Fortress"


def test_unknown_map_falls_back_to_classic() -> None:
    engine = BombermanEngine()
    settings = engine.validate_settings({"map_id": "does_not_exist"})
    assert settings["map_id"] == "classic"
