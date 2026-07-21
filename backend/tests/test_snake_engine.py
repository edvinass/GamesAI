import copy
from datetime import datetime, timedelta, timezone

import pytest

from app.games.snake.engine import SnakeEngine


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
def engine() -> SnakeEngine:
    return SnakeEngine()


@pytest.fixture
def state(engine: SnakeEngine) -> dict:
    players = make_players(2)
    s = engine.create_initial_state(players, {"countdown_sec": 0})
    s["phase"] = "playing"
    s["countdown_ends_at"] = None
    return s


def test_lobby_validation(engine: SnakeEngine) -> None:
    assert engine.validate_lobby(make_players(1), {}) is not None
    assert engine.validate_lobby(make_players(2), {}) is None
    assert engine.validate_lobby(make_players(9), {}) is not None
    assert engine.validate_lobby(make_players(1), {"solo_practice": True}) is None
    assert engine.validate_lobby(make_players(2), {"solo_practice": True}) is not None


def test_initial_state_spawns(engine: SnakeEngine) -> None:
    players = make_players(3)
    state = engine.create_initial_state(players, {})
    assert len(state["snakes"]) == 3
    assert state["phase"] == "countdown"
    assert len(state["foods"]) == 3
    assert all(f["type"] in ("apple", "golden", "poison", "ghost", "ammo") for f in state["foods"])

    occupied: set[tuple[int, int]] = set()
    for snake in state["snakes"].values():
        for seg in snake["body"]:
            key = (seg[0], seg[1])
            assert key not in occupied
            occupied.add(key)
    for food in state["foods"]:
        key = (food["x"], food["y"])
        assert key not in occupied
        occupied.add(key)


def test_direction_queuing(engine: SnakeEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    snake = state["snakes"][pid]
    snake["direction"] = "right"
    snake["next_direction"] = "right"

    state, _ = engine.apply_action(state, {"type": "set_direction", "direction": "left"}, player)
    assert state["snakes"][pid]["next_direction"] == "right"

    state, _ = engine.apply_action(state, {"type": "set_direction", "direction": "up"}, player)
    assert state["snakes"][pid]["next_direction"] == "up"


def test_rapid_corner_turn(engine: SnakeEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    snake = state["snakes"][pid]
    snake["direction"] = "right"
    snake["next_direction"] = "right"

    state, _ = engine.apply_action(state, {"type": "set_direction", "direction": "up"}, player)
    assert state["snakes"][pid]["next_direction"] == "up"

    state, _ = engine.apply_action(state, {"type": "set_direction", "direction": "left"}, player)
    assert state["snakes"][pid]["next_direction"] == "left"


def test_direction_ignored_when_dead(engine: SnakeEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["snakes"][pid]["alive"] = False

    state, _ = engine.apply_action(state, {"type": "set_direction", "direction": "up"}, player)
    assert state["snakes"][pid]["next_direction"] == state["snakes"][pid]["direction"]


def test_wrap_around(engine: SnakeEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    snake = state["snakes"][pid]
    grid_width = state["grid_width"]
    snake["body"] = [[0, 5], [1, 5], [2, 5]]
    snake["direction"] = "left"
    snake["next_direction"] = "left"
    state["snakes"][state["players"][1]["id"]]["alive"] = False

    state, events = engine.tick(state)
    assert state["snakes"][pid]["alive"]
    assert state["snakes"][pid]["body"][0] == [grid_width - 1, 5]
    assert not any(e["type"] == "player_died" for e in events)


def test_food_eaten_grows_score(engine: SnakeEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    snake = state["snakes"][pid]
    snake["body"] = [[5, 5], [4, 5], [3, 5]]
    snake["direction"] = "right"
    snake["next_direction"] = "right"
    state["foods"] = [{"x": 6, "y": 5, "type": "apple"}]
    state["snakes"][state["players"][1]["id"]]["alive"] = False

    initial_len = len(snake["body"])
    state, events = engine.tick(state)
    assert state["snakes"][pid]["score"] == 1
    assert len(state["snakes"][pid]["body"]) == initial_len + 1
    assert any(e["type"] == "food_eaten" and e.get("food_type") == "apple" for e in events)
    assert len(state["foods"]) == 3


def test_golden_food_grows_extra(engine: SnakeEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    other = state["players"][1]["id"]
    snake = state["snakes"][pid]
    snake["body"] = [[5, 5], [4, 5], [3, 5]]
    snake["direction"] = "right"
    snake["next_direction"] = "right"
    # Keep another snake alive so the match continues for the second growth tick.
    state["snakes"][other]["body"] = [[40, 20], [41, 20], [42, 20]]
    state["snakes"][other]["direction"] = "left"
    state["snakes"][other]["next_direction"] = "left"
    state["foods"] = [{"x": 6, "y": 5, "type": "golden"}]

    state, events = engine.tick(state)
    assert state["snakes"][pid]["score"] == 3
    assert len(state["snakes"][pid]["body"]) == 4
    assert state["snakes"][pid]["pending_grow"] == 1
    assert any(e.get("food_type") == "golden" for e in events)

    snake = state["snakes"][pid]
    snake["direction"] = "right"
    snake["next_direction"] = "right"
    state["foods"] = []
    state, _ = engine.tick(state)
    assert len(state["snakes"][pid]["body"]) == 5
    assert state["snakes"][pid]["pending_grow"] == 0


def test_poison_food_shrinks(engine: SnakeEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    snake = state["snakes"][pid]
    snake["body"] = [[8, 5], [7, 5], [6, 5], [5, 5], [4, 5], [3, 5]]
    snake["direction"] = "right"
    snake["next_direction"] = "right"
    state["foods"] = [{"x": 9, "y": 5, "type": "poison"}]
    state["snakes"][state["players"][1]["id"]]["alive"] = False

    state, events = engine.tick(state)
    assert state["snakes"][pid]["score"] == 0
    assert len(state["snakes"][pid]["body"]) == 4
    assert any(e.get("food_type") == "poison" for e in events)


def test_poison_respects_min_length(engine: SnakeEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    snake = state["snakes"][pid]
    snake["body"] = [[5, 5], [4, 5], [3, 5]]
    snake["direction"] = "right"
    snake["next_direction"] = "right"
    state["foods"] = [{"x": 6, "y": 5, "type": "poison"}]
    state["snakes"][state["players"][1]["id"]]["alive"] = False

    state, _ = engine.tick(state)
    assert len(state["snakes"][pid]["body"]) == 3


def test_ghost_food_ignores_own_body(engine: SnakeEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    snake = state["snakes"][pid]
    # Coil so next move would hit own body without ghost
    snake["body"] = [[5, 5], [5, 6], [4, 6], [4, 5], [4, 4], [5, 4]]
    snake["direction"] = "left"
    snake["next_direction"] = "left"
    snake["ghost_until_tick"] = 999
    state["foods"] = []
    state["snakes"][state["players"][1]["id"]]["alive"] = False

    state, events = engine.tick(state)
    assert state["snakes"][pid]["alive"]
    assert state["snakes"][pid]["body"][0] == [4, 5]
    assert not any(e["type"] == "player_died" for e in events)


def test_ghost_food_grants_buff(engine: SnakeEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    snake = state["snakes"][pid]
    snake["body"] = [[5, 5], [4, 5], [3, 5]]
    snake["direction"] = "right"
    snake["next_direction"] = "right"
    state["tick"] = 10
    state["foods"] = [{"x": 6, "y": 5, "type": "ghost"}]
    state["snakes"][state["players"][1]["id"]]["alive"] = False

    state, events = engine.tick(state)
    assert state["snakes"][pid]["ghost_until_tick"] == 40
    assert any(e.get("food_type") == "ghost" for e in events)


def test_ammo_food_grants_shots(engine: SnakeEngine, state: dict) -> None:
    pid = state["players"][0]["id"]
    snake = state["snakes"][pid]
    snake["body"] = [[5, 5], [4, 5], [3, 5]]
    snake["direction"] = "right"
    snake["next_direction"] = "right"
    snake["ammo"] = 0
    state["foods"] = [{"x": 6, "y": 5, "type": "ammo"}]
    state["snakes"][state["players"][1]["id"]]["alive"] = False

    state, events = engine.tick(state)
    assert state["snakes"][pid]["ammo"] == 2
    assert state["snakes"][pid]["score"] == 1
    assert len(state["snakes"][pid]["body"]) == 3
    assert any(e.get("food_type") == "ammo" for e in events)


def test_shoot_removes_score(engine: SnakeEngine, state: dict) -> None:
    p0, p1 = state["players"][0]["id"], state["players"][1]["id"]
    shooter = state["snakes"][p0]
    target = state["snakes"][p1]
    shooter["body"] = [[5, 5], [4, 5], [3, 5]]
    shooter["direction"] = "right"
    shooter["next_direction"] = "right"
    shooter["ammo"] = 1
    target["body"] = [[8, 5], [9, 5], [10, 5], [11, 5]]
    target["direction"] = "up"
    target["next_direction"] = "up"
    target["score"] = 3
    state["foods"] = []
    state["projectiles"] = []

    player = state["players"][0]
    state, events = engine.apply_action(state, {"type": "shoot"}, player)
    assert shooter["ammo"] == 0
    assert any(e["type"] == "shot_fired" for e in events)
    assert len(state["projectiles"]) == 1
    assert state["projectiles"][0]["x"] == 6

    state["projectiles"][0]["x"] = 8
    state["projectiles"][0]["y"] = 5
    hit_events = engine._apply_projectile_hits(state)
    assert target["score"] == 2
    assert target["alive"]
    assert any(e["type"] == "snake_hit" for e in hit_events)
    assert state["projectiles"] == []


def test_shot_kills_on_negative_score(engine: SnakeEngine, state: dict) -> None:
    p0, p1 = state["players"][0]["id"], state["players"][1]["id"]
    shooter = state["snakes"][p0]
    target = state["snakes"][p1]
    shooter["body"] = [[2, 10], [1, 10], [0, 10]]
    shooter["direction"] = "right"
    shooter["next_direction"] = "right"
    shooter["ammo"] = 1
    shooter["score"] = 0
    target["body"] = [[4, 10], [5, 10], [6, 10]]
    target["direction"] = "down"
    target["next_direction"] = "down"
    target["score"] = 0
    state["foods"] = []
    state["projectiles"] = []

    player = state["players"][0]
    state, _ = engine.apply_action(state, {"type": "shoot"}, player)
    assert state["projectiles"][0]["x"] == 3

    state["projectiles"][0]["x"] = 4
    state["projectiles"][0]["y"] = 10
    hit_events = engine._apply_projectile_hits(state)
    assert target["score"] == -1
    assert not target["alive"]
    assert any(e.get("reason") == "shot" for e in hit_events)
    assert shooter["score"] == 2


def test_shoot_without_ammo_noop(engine: SnakeEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["snakes"][pid]["ammo"] = 0
    state["projectiles"] = []
    state, events = engine.apply_action(state, {"type": "shoot"}, player)
    assert state["projectiles"] == []
    assert events == []


def test_countdown_to_playing(engine: SnakeEngine) -> None:
    players = make_players(2)
    state = engine.create_initial_state(players, {"countdown_sec": 3})
    assert state["phase"] == "countdown"

    state["countdown_ends_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    state, events = engine.tick(state)
    assert state["phase"] == "playing"
    assert any(e["type"] == "game_started" for e in events)


def test_winner_last_standing(engine: SnakeEngine, state: dict) -> None:
    p0, p1 = state["players"][0]["id"], state["players"][1]["id"]
    state["snakes"][p0]["alive"] = False
    state["snakes"][p1]["alive"] = True

    engine._resolve_winner(state)
    assert state["winner"] == p1
    assert state["win_reason"] == "last_standing"
    assert state["phase"] == "finished"


def test_winner_highest_score_on_mutual_death(engine: SnakeEngine, state: dict) -> None:
    p0, p1 = state["players"][0]["id"], state["players"][1]["id"]
    state["snakes"][p0]["alive"] = False
    state["snakes"][p0]["score"] = 5
    state["snakes"][p1]["alive"] = False
    state["snakes"][p1]["score"] = 2

    engine._resolve_winner(state)
    assert state["winner"] == p0
    assert state["win_reason"] == "highest_score"


def test_tick_interval(engine: SnakeEngine) -> None:
    assert engine.tick_interval_ms() == 130


def test_default_grid_is_dense(engine: SnakeEngine) -> None:
    settings = engine.default_settings()
    assert settings["grid_width"] == 48
    assert settings["grid_height"] == 32
    state = engine.create_initial_state(make_players(2), {})
    assert state["grid_width"] == 48
    assert state["grid_height"] == 32
    assert state["tick_ms"] == 130
    public = engine.get_public_state(state, None)
    assert public["tick_ms"] == 130


def test_check_winner(engine: SnakeEngine, state: dict) -> None:
    assert engine.check_winner(state) is None
    state["phase"] = "finished"
    state["winner"] = state["players"][0]["id"]
    assert engine.check_winner(state) == state["players"][0]["id"]
