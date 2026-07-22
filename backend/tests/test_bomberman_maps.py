from app.games.bomberman.engine import BombermanEngine, TILE_EMPTY
from app.games.bomberman.maps import MAPS, build_map_grid, list_maps


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
