import copy
from datetime import datetime, timedelta, timezone

import pytest

from app.games.duel.engine import DuelEngine


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
def engine() -> DuelEngine:
    return DuelEngine()


@pytest.fixture
def state(engine: DuelEngine) -> dict:
    players = make_players(2)
    s = engine.create_initial_state(players, {"countdown_sec": 0})
    s["phase"] = "playing"
    s["countdown_ends_at"] = None
    return s


def test_lobby_validation(engine: DuelEngine) -> None:
    assert engine.validate_lobby(make_players(1), {}) is not None
    assert engine.validate_lobby(make_players(2), {}) is None
    assert engine.validate_lobby(make_players(3), {}) is not None
    assert engine.validate_lobby(make_players(1), {"solo_practice": True}) is None
    assert engine.validate_lobby(make_players(2), {"solo_practice": True}) is not None


def test_initial_state_spawns_on_sides(engine: DuelEngine) -> None:
    players = make_players(2)
    game_state = engine.create_initial_state(players, {})
    fighters = game_state["fighters"]
    assert len(fighters) == 2
    left = fighters["p0"]
    right = fighters["p1"]
    assert left["side"] == "left"
    assert right["side"] == "right"
    assert left["x"] < right["x"]
    assert left["hp"] == 3
    assert game_state["phase"] == "countdown"
    assert game_state["round_scores"] == {"p0": 0, "p1": 0}


def test_move_and_shoot_actions(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]

    state, _ = engine.apply_action(state, {"type": "set_move", "direction": "up"}, player)
    assert state["fighters"][pid]["move_direction"] == "up"

    state, _ = engine.apply_action(state, {"type": "shoot"}, player)
    assert state["fighters"][pid]["pending_shoot"] is True


def test_charge_actions(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]

    state, _ = engine.apply_action(state, {"type": "charge_start"}, player)
    assert state["fighters"][pid]["charging"] is True

    state, _ = engine.apply_action(
        state, {"type": "release_charge", "charge_ticks": 10}, player
    )
    assert state["fighters"][pid]["pending_shoot"] is True
    assert state["fighters"][pid]["charge_ticks"] == 10


def test_shoot_spawns_bullet(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    left["pending_shoot"] = True
    left["cooldown_until_tick"] = 0

    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 1
    assert state["bullets"][0]["vx"] == 2
    assert state["bullets"][0]["owner_id"] == "p0"


def test_full_charge_spawns_three_fast_bullets(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    left["pending_shoot"] = True
    left["charge_ticks"] = 12
    left["cooldown_until_tick"] = 0

    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 3
    assert all(bullet["vx"] == 6 for bullet in state["bullets"])
    assert all(bullet["damage"] == 2 for bullet in state["bullets"])


def test_fighter_is_three_bars_tall(engine: DuelEngine) -> None:
    players = make_players(2)
    game_state = engine.create_initial_state(players, {})
    assert game_state["settings"]["fighter_height"] == 3
    left = game_state["fighters"]["p0"]
    assert left["y"] == (game_state["grid_height"] - 3) // 2


def test_bullet_damages_fighter_without_eliminating(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = []
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 10
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}]

    state, events = engine.tick(state)
    assert state["phase"] == "playing"
    assert state["fighters"]["p1"]["hp"] == 2
    assert state["fighters"]["p1"]["alive"] is True
    assert any(e["type"] == "player_hit" for e in events)


def test_center_hit_deals_extra_damage(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = []
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 10
    center_row = 5 + 1
    state["bullets"] = [
        {"id": 0, "x": 9, "y": center_row, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}
    ]

    state, _ = engine.tick(state)
    assert state["fighters"]["p1"]["hp"] == 1


def test_elimination_ends_round(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = []
    state["fighters"]["p1"]["hp"] = 1
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 10
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}]

    state, events = engine.tick(state)
    assert state["phase"] == "round_over"
    assert state["round_winner"] == "p0"
    assert state["round_scores"]["p0"] == 1
    assert any(e["type"] == "round_over" for e in events)


def test_quick_duel_finishes_match_on_hit(engine: DuelEngine) -> None:
    players = make_players(2)
    state = engine.create_initial_state(
        players, {"countdown_sec": 0, "match_format": "quick_duel", "mutator": "classic"}
    )
    state["phase"] = "playing"
    state["fighters"]["p1"]["hp"] = 1
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 10
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}]

    state, events = engine.tick(state)
    assert state["phase"] == "finished"
    assert state["winner"] == "p0"
    assert any(e["type"] == "game_over" for e in events)


def test_shield_blocks_damage(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = []
    state["fighters"]["p1"]["effects"]["shield"] = True
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 10
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}]

    state, events = engine.tick(state)
    assert state["fighters"]["p1"]["hp"] == 3
    assert any(e["type"] == "shield_blocked" for e in events)


def test_obstacle_blocks_bullet(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = [{"x": 10, "y": 4, "w": 1, "h": 2}]
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}]

    state, _ = engine.tick(state)
    assert state["bullets"] == []


def test_ricochet_off_obstacle(engine: DuelEngine, state: dict) -> None:
    state["settings"]["ricochet_bounces"] = 1
    state["obstacles"] = [{"x": 10, "y": 4, "w": 1, "h": 2}]
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 1}]

    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 1
    assert state["bullets"][0]["vx"] == -1
    assert state["bullets"][0]["bounces_remaining"] == 0


def test_powerup_collected_by_bullet(engine: DuelEngine, state: dict) -> None:
    state["powerup"] = {"x": 20, "y": 8, "type": "shield"}
    state["bullets"] = [{"id": 0, "x": 19, "y": 8, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}]

    state, events = engine.tick(state)
    assert state["powerup"] is None
    assert state["fighters"]["p0"]["stored_powerup"] == "shield"
    assert state["fighters"]["p0"]["effects"]["shield"] is False
    assert any(e["type"] == "powerup_collected" for e in events)


def test_powerup_activation(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["stored_powerup"] = "shield"

    state, _ = engine.apply_action(state, {"type": "powerup_hold_start"}, player)
    fighter = state["fighters"][pid]
    assert fighter["activating_powerup"] is True

    fighter["powerup_activation_ticks"] = 12
    state, events = engine.apply_action(state, {"type": "powerup_hold_release"}, player)
    assert state["fighters"][pid]["stored_powerup"] is None
    assert state["fighters"][pid]["effects"]["shield"] is True
    assert any(e["type"] == "powerup_activated" for e in events)


def test_freeze_blocks_movement(engine: DuelEngine, state: dict) -> None:
    fighter = state["fighters"]["p0"]
    fighter["move_direction"] = "down"
    fighter["effects"]["freeze_until"] = state["tick"] + 50
    start_y = fighter["y"]

    state, _ = engine.tick(state)
    assert fighter["y"] == start_y


def test_heal_powerup(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["hp"] = 1
    state["fighters"][pid]["stored_powerup"] = "heal"
    state["fighters"][pid]["powerup_activation_ticks"] = 12
    state["fighters"][pid]["activating_powerup"] = True

    state, events = engine.apply_action(state, {"type": "powerup_hold_release"}, player)
    assert state["fighters"][pid]["hp"] == 2
    assert any(e["type"] == "powerup_activated" for e in events)


def test_ai_moves_slower_than_humans(engine: DuelEngine, state: dict) -> None:
    state["settings"]["ai_move_interval_ticks"] = 2
    state["players"][1]["is_ai"] = True
    human = state["fighters"]["p0"]
    ai = state["fighters"]["p1"]
    human["move_direction"] = "down"
    ai["move_direction"] = "down"
    human_y = human["y"]
    ai_y = ai["y"]

    state, _ = engine.tick(state)
    assert human["y"] == human_y + 1
    assert ai["y"] == ai_y + 1

    state, _ = engine.tick(state)
    assert human["y"] == human_y + 2
    assert ai["y"] == ai_y + 1


def test_cooldown_blocks_rapid_fire(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    left["pending_shoot"] = True
    left["cooldown_until_tick"] = 0

    state, _ = engine.tick(state)
    first_count = len(state["bullets"])

    left["pending_shoot"] = True
    state, _ = engine.tick(state)
    assert len(state["bullets"]) == first_count


def test_generated_obstacles_are_at_most_two_by_two(engine: DuelEngine) -> None:
    players = make_players(2)
    for _ in range(20):
        state = engine.create_initial_state(players, {"obstacle_count": 4})
        for obstacle in state["obstacles"]:
            assert 1 <= obstacle["w"] <= 2
            assert 1 <= obstacle["h"] <= 2


def test_match_won_after_enough_rounds(engine: DuelEngine) -> None:
    players = make_players(2)
    state = engine.create_initial_state(
        players, {"countdown_sec": 0, "match_format": "best_of_3", "mutator": "classic"}
    )
    state["phase"] = "playing"
    state["round_scores"] = {"p0": 1, "p1": 0}
    state["fighters"]["p1"]["hp"] = 1
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 10
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}]

    state, events = engine.tick(state)
    assert state["phase"] == "finished"
    assert state["winner"] == "p0"
    assert state["round_scores"]["p0"] == 2
