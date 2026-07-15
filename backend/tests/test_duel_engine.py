import copy
from datetime import datetime, timedelta, timezone

import pytest

from app.games.duel.engine import HOMING_LOCK_ON_TICKS, DuelEngine


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
    game_state = engine.create_initial_state(players, {"match_format": "quick_duel"})
    fighters = game_state["fighters"]
    assert len(fighters) == 2
    left = fighters["p0"]
    right = fighters["p1"]
    assert left["side"] == "left"
    assert right["side"] == "right"
    assert left["x"] < right["x"]
    assert left["hp"] == 1
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
    state["fighters"][pid]["charge_ticks"] = 10

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
    assert state["bullets"][0]["x"] == left["x"] + 1 + state["bullets"][0]["vx"]


def test_full_charge_spawns_three_fast_bullets(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    left["pending_shoot"] = True
    left["charge_ticks"] = 12
    left["cooldown_until_tick"] = 0

    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 3
    assert all(bullet["vx"] == 6 for bullet in state["bullets"])
    assert all(bullet["damage"] == 2 for bullet in state["bullets"])
    assert all(bullet.get("pierce_obstacles") for bullet in state["bullets"])
    assert all(bullet["x"] == left["x"] + 1 + bullet["vx"] for bullet in state["bullets"])


def test_full_charge_hits_all_rows_through_lane_cover(engine: DuelEngine, state: dict) -> None:
    right = state["fighters"]["p1"]
    right["hp"] = 20
    enemy_x = right["x"]
    right_rows = [right["y"], right["y"] + 1, right["y"] + 2]
    state["obstacles"] = [
        {"x": enemy_x, "y": right_rows[0], "w": 1, "h": 1},
        {"x": enemy_x, "y": right_rows[2], "w": 1, "h": 1},
    ]

    left = state["fighters"]["p0"]
    left["pending_shoot"] = True
    left["charge_ticks"] = 12
    left["cooldown_until_tick"] = 0

    state, _ = engine.tick(state)
    hits = 0
    for _ in range(12):
        state, events = engine.tick(state)
        hits += sum(1 for event in events if event.get("type") == "player_hit")
        if not state["bullets"]:
            break

    assert hits == 3
    assert right["hp"] == 20 - (2 + 3 + 2)


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
    state["settings"]["powerup_draft_enabled"] = False
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
    state["fighters"]["p1"]["effects"]["shield_until"] = state["tick"] + 80
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 10
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}]

    state, events = engine.tick(state)
    assert state["fighters"]["p1"]["hp"] == 3
    assert state["fighters"]["p1"]["effects"]["shield_until"] > state["tick"]
    assert any(e["type"] == "shield_blocked" for e in events)


def test_shield_blocks_multiple_hits_during_duration(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = []
    state["fighters"]["p1"]["effects"]["shield_until"] = state["tick"] + 80
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 10

    for x in (9, 9):
        state["bullets"] = [
            {"id": 0, "x": x, "y": 5, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}
        ]
        state, events = engine.tick(state)
        assert state["fighters"]["p1"]["hp"] == 3
        assert any(e["type"] == "shield_blocked" for e in events)


def test_wide_shot_lasts_for_duration(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    left["effects"]["wide_shot_until"] = state["tick"] + 80
    left["pending_shoot"] = True
    left["cooldown_until_tick"] = 0

    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 3
    assert left["effects"]["wide_shot_until"] > state["tick"]

    left["pending_shoot"] = True
    left["cooldown_until_tick"] = 0
    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 6


def test_obstacle_blocks_bullet(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = [{"x": 10, "y": 4, "w": 1, "h": 2}]
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 1, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}]

    state, _ = engine.tick(state)
    assert state["bullets"] == []


def test_fast_bullet_hits_obstacle(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = [{"x": 10, "y": 4, "w": 1, "h": 2}]
    state["bullets"] = [{"id": 0, "x": 9, "y": 5, "vx": 2, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}]

    state, _ = engine.tick(state)
    assert state["bullets"] == []


def test_fast_bullet_hits_opponent(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = []
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 46
    state["bullets"] = [
        {"id": 0, "x": 44, "y": 6, "vx": 2, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}
    ]

    state, events = engine.tick(state)
    assert state["fighters"]["p1"]["hp"] < state["fighters"]["p1"]["max_hp"]
    assert any(e["type"] == "player_hit" for e in events)


def test_default_speed_shot_damages_opponent(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = []
    left = state["fighters"]["p0"]
    right = state["fighters"]["p1"]
    right["y"] = left["y"] + 1
    left["pending_shoot"] = True
    left["cooldown_until_tick"] = 0

    for _ in range(30):
        if right["hp"] < right["max_hp"]:
            break
        state, events = engine.tick(state)
    else:
        raise AssertionError("bullet never hit opponent at default speed")

    assert any(e["type"] == "player_hit" for e in events)


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
    assert state["fighters"]["p0"]["effects"].get("shield_until", 0) == 0
    assert any(e["type"] == "powerup_collected" for e in events)


def test_powerup_activation(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["stored_powerup"] = "shield"

    state, events = engine.apply_action(state, {"type": "powerup_activate"}, player)
    assert state["fighters"][pid]["stored_powerup"] is None
    assert state["fighters"][pid]["effects"]["shield_until"] > state["tick"]
    assert any(e["type"] == "powerup_activated" for e in events)


def test_jam_blocks_movement_and_shooting(engine: DuelEngine, state: dict) -> None:
    fighter = state["fighters"]["p0"]
    fighter["move_direction"] = "down"
    fighter["effects"]["jam_until"] = state["tick"] + 50
    fighter["pending_shoot"] = True
    fighter["cooldown_until_tick"] = 0
    start_y = fighter["y"]

    state, _ = engine.tick(state)
    assert fighter["y"] == start_y
    assert not state["bullets"]


def test_heal_at_max_hp_is_blocked(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["hp"] = state["fighters"][pid]["max_hp"]
    state["fighters"][pid]["stored_powerup"] = "heal"

    state, events = engine.apply_action(state, {"type": "powerup_activate"}, player)
    assert state["fighters"][pid]["stored_powerup"] == "heal"
    assert not any(e["type"] == "powerup_activated" for e in events)
    assert state["last_action"]["type"] == "powerup_blocked"


def test_ricochet_adds_bounces(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    left["effects"]["ricochet_until"] = state["tick"] + 80
    left["pending_shoot"] = True
    left["cooldown_until_tick"] = 0

    state, _ = engine.tick(state)
    assert len(state["bullets"]) >= 1
    assert all(b.get("bounces_remaining", 0) >= 3 for b in state["bullets"])


def test_timed_effect_extends_instead_of_shortening(engine: DuelEngine, state: dict) -> None:
    fighter = state["fighters"]["p0"]
    fighter["effects"]["shield_until"] = state["tick"] + 60
    fighter["stored_powerup"] = "shield"
    events: list[dict] = []
    engine._activate_stored_powerup(state, fighter, "p0", events)
    assert fighter["effects"]["shield_until"] >= state["tick"] + 200


def test_heal_powerup(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["hp"] = 1
    state["fighters"][pid]["stored_powerup"] = "heal"

    state, events = engine.apply_action(state, {"type": "powerup_activate"}, player)
    assert state["fighters"][pid]["hp"] == 2
    assert any(e["type"] == "powerup_activated" for e in events)


def test_powerup_valid_cell_rejects_obstacle_and_red_zone(engine: DuelEngine, state: dict) -> None:
    state["playable_y_min"] = 2
    state["playable_y_max"] = 20
    state["obstacles"] = [{"x": 10, "y": 8, "w": 2, "h": 2}]

    assert engine._powerup_in_red_zone(1, state) is True
    assert engine._powerup_in_red_zone(21, state) is True
    assert engine._powerup_in_red_zone(10, state) is False

    assert engine._is_valid_powerup_cell(10, 8, state) is False
    assert engine._is_valid_powerup_cell(10, 1, state) is False
    assert engine._is_valid_powerup_cell(1, 10, state) is False
    assert engine._is_valid_powerup_cell(12, 10, state) is True


def test_powerup_spawns_at_random_valid_location(engine: DuelEngine, state: dict) -> None:
    state["settings"]["powerups_enabled"] = True
    state["powerup"] = None
    state["next_powerup_at_tick"] = 0
    state["obstacles"] = [{"x": 24, "y": 12, "w": 2, "h": 2}]

    events: list[dict] = []
    engine._update_powerups(state, events)

    assert state["powerup"] is not None
    assert any(e["type"] == "powerup_spawned" for e in events)
    loc = state["powerup"]
    assert engine._is_valid_powerup_cell(loc["x"], loc["y"], state)
    assert "despawn_at_tick" in loc


def test_powerup_despawns_after_lifetime(engine: DuelEngine, state: dict) -> None:
    state["settings"]["powerups_enabled"] = True
    state["powerup"] = {
        "x": 12,
        "y": 10,
        "type": "shield",
        "despawn_at_tick": state["tick"],
    }
    state["next_powerup_at_tick"] = 9999

    state, events = engine.tick(state)
    assert state["powerup"] is None
    assert any(e["type"] == "powerup_despawned" for e in events)
    assert state["next_powerup_at_tick"] > state["tick"]


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


def test_release_charge_rejects_inflated_client_ticks(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    fighter = state["fighters"][pid]
    fighter["cooldown_until_tick"] = 0

    state, _ = engine.apply_action(state, {"type": "charge_start"}, player)
    state, _ = engine.apply_action(
        state, {"type": "release_charge", "charge_ticks": 15}, player
    )
    assert state["fighters"][pid]["charge_ticks"] <= 4

    fighter["pending_shoot"] = True
    fighter["cooldown_until_tick"] = 0
    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 1
    assert state["bullets"][0]["damage"] == 1


def test_full_charge_after_holding_ticks(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["cooldown_until_tick"] = 0

    state, _ = engine.apply_action(state, {"type": "charge_start"}, player)
    for _ in range(11):
        state, _ = engine.tick(state)
    assert state["fighters"][pid]["charge_ticks"] >= 11

    state, _ = engine.apply_action(
        state, {"type": "release_charge", "charge_ticks": 11}, player
    )
    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 3
    assert all(bullet["damage"] == 2 for bullet in state["bullets"])


def test_release_charge_lag_compensation_grants_spread(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    fighter = state["fighters"][pid]
    fighter["cooldown_until_tick"] = 0

    state, _ = engine.apply_action(state, {"type": "charge_start"}, player)
    for _ in range(9):
        state, _ = engine.tick(state)
    assert state["fighters"][pid]["charge_ticks"] == 9

    state, _ = engine.apply_action(
        state, {"type": "release_charge", "charge_ticks": 11}, player
    )
    assert state["fighters"][pid]["charge_ticks"] == 11

    fighter["pending_shoot"] = True
    fighter["cooldown_until_tick"] = 0
    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 3


def test_charge_start_rejected_on_cooldown(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["cooldown_until_tick"] = state["tick"] + 5

    state, _ = engine.apply_action(state, {"type": "charge_start"}, player)
    assert state["fighters"][pid].get("charging") is not True
    assert state["last_action"]["type"] == "action_rejected"
    assert state["last_action"]["reason"] == "on_cooldown"


def test_powerup_release_without_hold_does_not_activate(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["stored_powerup"] = "shield"

    state, events = engine.apply_action(
        state,
        {"type": "powerup_hold_release", "powerup_activation_ticks": 8},
        player,
    )
    assert state["fighters"][pid]["stored_powerup"] == "shield"
    assert state["fighters"][pid]["effects"].get("shield_until", 0) == 0
    assert not any(e["type"] == "powerup_activated" for e in events)


def test_buff_powerup_activate(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["stored_powerup"] = "ricochet"
    state["fighters"][pid]["activating_powerup"] = True
    state["fighters"][pid]["powerup_activation_ticks"] = 7

    state, events = engine.apply_action(
        state,
        {"type": "powerup_hold_release", "powerup_activation_ticks": 7},
        player,
    )
    assert state["fighters"][pid]["stored_powerup"] is None
    assert state["fighters"][pid]["effects"]["ricochet_until"] > state["tick"]
    assert any(e["type"] == "powerup_activated" for e in events)


def test_powerup_release_uses_server_activation_progress(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["stored_powerup"] = "shield"

    state, _ = engine.apply_action(state, {"type": "powerup_hold_start"}, player)
    state["fighters"][pid]["powerup_activation_ticks"] = 8

    state, events = engine.apply_action(
        state,
        {"type": "powerup_hold_release", "powerup_activation_ticks": 8},
        player,
    )
    assert state["fighters"][pid]["stored_powerup"] is None
    assert state["fighters"][pid]["effects"]["shield_until"] > state["tick"]
    assert any(e["type"] == "powerup_activated" for e in events)


def test_powerup_activation_with_realistic_server_lag(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["stored_powerup"] = "shield"

    state, _ = engine.apply_action(state, {"type": "powerup_hold_start"}, player)
    for _ in range(8):
        state, _ = engine.tick(state)

    state, events = engine.apply_action(
        state,
        {"type": "powerup_hold_release", "powerup_activation_ticks": 8},
        player,
    )
    assert state["fighters"][pid]["stored_powerup"] is None
    assert any(e["type"] == "powerup_activated" for e in events)


def test_instant_bomb_powerup(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["stored_powerup"] = "bomb"
    state["fighters"][pid]["powerup_charges"] = 3

    state, events = engine.apply_action(state, {"type": "powerup_activate"}, player)
    assert state["fighters"][pid]["stored_powerup"] == "bomb"
    assert state["fighters"][pid]["powerup_charges"] == 2
    assert len(state["bullets"]) == 1
    assert state["bullets"][0]["kind"] == "bomb"
    activated = next(e for e in events if e["type"] == "powerup_activated")
    assert activated["charges_remaining"] == 2


def test_bomb_powerup_depletes_after_three_uses(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["stored_powerup"] = "bomb"
    state["fighters"][pid]["powerup_charges"] = 3

    for expected_remaining in (2, 1, None):
        state, events = engine.apply_action(state, {"type": "powerup_activate"}, player)
        activated = next(e for e in events if e["type"] == "powerup_activated")
        if expected_remaining is None:
            assert state["fighters"][pid]["stored_powerup"] is None
            assert "powerup_charges" not in state["fighters"][pid]
            assert "charges_remaining" not in activated
        else:
            assert state["fighters"][pid]["stored_powerup"] == "bomb"
            assert state["fighters"][pid]["powerup_charges"] == expected_remaining
            assert activated["charges_remaining"] == expected_remaining

    assert len(state["bullets"]) == 3


def test_fighter_walkover_collects_powerup(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = []
    state["powerup"] = {"x": 20, "y": 11, "type": "shield", "despawn_at_tick": 999}
    state["fighters"]["p0"]["x"] = 20
    state["fighters"]["p0"]["y"] = 9
    state["fighters"]["p0"]["move_direction"] = "down"

    state, events = engine.tick(state)
    assert state["fighters"]["p0"]["stored_powerup"] == "shield"
    assert state["powerup"] is None
    assert any(e["type"] == "powerup_collected" for e in events)


def test_initial_powerup_spawn_is_sooner_than_interval(engine: DuelEngine) -> None:
    players = make_players(2)
    state = engine.create_initial_state(players, {"match_format": "best_of_5"})
    first_spawn = state["next_powerup_at_tick"]
    assert 15 <= first_spawn <= 40


def test_bomb_detonates_on_wall_with_wide_blast(engine: DuelEngine, state: dict) -> None:
    state["settings"]["powerup_draft_enabled"] = False
    state["settings"]["best_of"] = 1
    state["obstacles"] = []
    state["fighters"]["p0"]["x"] = 2
    state["fighters"]["p0"]["side"] = "left"
    state["fighters"]["p1"]["y"] = 10
    state["fighters"]["p1"]["x"] = 44
    state["bullets"] = [
        {
            "id": 0,
            "x": 47,
            "y": 10,
            "vx": 1,
            "vy": 0,
            "owner_id": "p0",
            "damage": 0,
            "bounces_remaining": 0,
            "kind": "bomb",
        }
    ]

    state, events = engine.tick(state)
    assert not state["bullets"]
    detonation = next(e for e in events if e["type"] == "bomb_detonated")
    assert detonation["wall_hit"] is True
    assert detonation["x"] == state["grid_width"] - 1
    assert state["fighters"]["p1"]["hp"] < state["fighters"]["p1"]["max_hp"]


def test_bomb_detonates_on_fighter(engine: DuelEngine, state: dict) -> None:
    state["settings"]["powerup_draft_enabled"] = False
    state["settings"]["best_of"] = 1
    state["obstacles"] = []
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 20
    state["bullets"] = [
        {
            "id": 0,
            "x": 19,
            "y": 6,
            "vx": 1,
            "vy": 0,
            "owner_id": "p0",
            "damage": 0,
            "bounces_remaining": 0,
            "kind": "bomb",
        }
    ]

    state, events = engine.tick(state)
    assert not state["bullets"]
    assert any(e["type"] == "bomb_detonated" for e in events)
    assert state["fighters"]["p1"]["hp"] < state["fighters"]["p1"]["max_hp"]


def test_machine_gun_spawns_fast_bullets(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    left["effects"]["machine_gun_until"] = state["tick"] + 80
    left["pending_shoot"] = True
    left["cooldown_until_tick"] = 0

    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 1
    assert state["bullets"][0]["vx"] == 4
    assert state["bullets"][0]["damage"] == 1


def test_pierce_passes_through_obstacle(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = [{"x": 10, "y": 4, "w": 1, "h": 2}]
    state["fighters"]["p0"]["effects"]["pierce_until"] = state["tick"] + 80
    state["fighters"]["p0"]["y"] = 5
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 12
    state["bullets"] = [
        {"id": 0, "x": 9, "y": 5, "vx": 3, "vy": 0, "owner_id": "p0", "damage": 1, "bounces_remaining": 0}
    ]

    state, events = engine.tick(state)
    assert any(e["type"] == "player_hit" for e in events)


def test_burst_fires_multiple_shots(engine: DuelEngine, state: dict) -> None:
    state["fighters"]["p0"]["burst_shots_remaining"] = 3
    state["fighters"]["p0"]["burst_next_at_tick"] = state["tick"]

    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 1
    assert state["fighters"]["p0"]["burst_shots_remaining"] == 2

    state, _ = engine.tick(state)
    state, _ = engine.tick(state)
    state, _ = engine.tick(state)
    assert len(state["bullets"]) == 2
    assert state["fighters"]["p0"]["burst_shots_remaining"] == 1


def test_burst_shots_spawn_after_move(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    fighter_height = state["settings"]["fighter_height"]
    left["move_direction"] = "down"
    left["burst_shots_remaining"] = 1
    left["burst_next_at_tick"] = state["tick"]
    y_before = left["y"]

    state, _ = engine.tick(state)

    assert left["y"] == y_before + 1
    assert len(state["bullets"]) == 1
    assert state["bullets"][0]["y"] == left["y"] + fighter_height // 2


def test_shoot_spawns_from_post_move_row(engine: DuelEngine, state: dict) -> None:
    left = state["fighters"]["p0"]
    fighter_height = state["settings"]["fighter_height"]
    left["move_direction"] = "up"
    left["pending_shoot"] = True
    left["cooldown_until_tick"] = 0
    y_before = left["y"]

    state, _ = engine.tick(state)

    assert left["y"] == y_before - 1
    assert len(state["bullets"]) == 1
    assert state["bullets"][0]["y"] == left["y"] + fighter_height // 2


def test_railgun_pierces_obstacle(engine: DuelEngine, state: dict) -> None:
    state["obstacles"] = [{"x": 10, "y": 4, "w": 1, "h": 2}]
    state["fighters"]["p0"]["y"] = 5
    state["fighters"]["p1"]["y"] = 5
    state["fighters"]["p1"]["x"] = 15
    events: list[dict] = []
    engine._activate_stored_powerup(
        state,
        {**state["fighters"]["p0"], "stored_powerup": "railgun"},
        "p0",
        events,
    )

    assert any(e["type"] == "player_hit" for e in events)
    assert state["fighters"]["p1"]["hp"] < state["fighters"]["p1"]["max_hp"]


def test_hazard_damage_applies_in_red_zone(engine: DuelEngine, state: dict) -> None:
    state["settings"]["shrinking_arena"] = True
    state["settings"]["hazard_damage"] = 1
    state["settings"]["hazard_damage_interval_ticks"] = 1
    state["playable_y_min"] = 2
    state["playable_y_max"] = state["grid_height"] - 3
    fighter = state["fighters"]["p0"]
    fighter["y"] = 0
    hp_before = fighter["hp"]

    state, events = engine.tick(state)

    assert fighter["hp"] < hp_before
    assert any(e["type"] == "hazard_damage" for e in events)


def test_hazard_damage_respects_interval(engine: DuelEngine, state: dict) -> None:
    state["settings"]["shrinking_arena"] = True
    state["settings"]["hazard_damage"] = 1
    state["settings"]["hazard_damage_interval_ticks"] = 20
    state["playable_y_min"] = 2
    state["playable_y_max"] = state["grid_height"] - 3
    fighter = state["fighters"]["p0"]
    fighter["y"] = 0
    events: list[dict] = []

    state["tick"] = 19
    engine._apply_hazard_damage(state, events)
    assert fighter["hp"] == state["fighters"]["p0"]["max_hp"]
    assert not any(e["type"] == "hazard_damage" for e in events)

    state["tick"] = 20
    engine._apply_hazard_damage(state, events)
    assert fighter["hp"] < state["fighters"]["p0"]["max_hp"]
    assert any(e["type"] == "hazard_damage" for e in events)


def test_hazard_damage_on_aligned_interval_tick(engine: DuelEngine, state: dict) -> None:
    state["settings"]["shrinking_arena"] = True
    state["settings"]["hazard_damage"] = 1
    state["settings"]["hazard_damage_interval_ticks"] = 20
    state["settings"]["shrink_start_tick"] = 250
    state["settings"]["shrink_interval_ticks"] = 80
    state["tick"] = 320
    state["playable_y_min"] = 1
    state["playable_y_max"] = state["grid_height"] - 2
    fighter = state["fighters"]["p0"]
    fighter["y"] = 0
    hp_before = fighter["hp"]

    state, events = engine.tick(state)

    assert fighter["hp"] < hp_before
    assert any(e["type"] == "hazard_damage" for e in events)


def test_hazard_damage_blocked_by_shield(engine: DuelEngine, state: dict) -> None:
    state["settings"]["shrinking_arena"] = True
    state["settings"]["hazard_damage"] = 1
    state["settings"]["hazard_damage_interval_ticks"] = 1
    state["playable_y_min"] = 2
    state["playable_y_max"] = state["grid_height"] - 3
    fighter = state["fighters"]["p0"]
    fighter["y"] = 0
    fighter.setdefault("effects", {})["shield_until"] = state["tick"] + 50
    hp_before = fighter["hp"]

    state, events = engine.tick(state)

    assert fighter["hp"] == hp_before
    assert not any(e["type"] == "hazard_damage" for e in events)


def test_ghost_scrambles_homing_steering(engine: DuelEngine, state: dict) -> None:
    target = state["fighters"]["p1"]
    target["y"] = 10
    target.setdefault("effects", {})["ghost_until"] = state["tick"] + 50
    bullet = {
        "x": 20,
        "y": 8,
        "vx": 1,
        "vy": 0,
        "homing": True,
        "homing_age": HOMING_LOCK_ON_TICKS,
        "owner_id": "p0",
    }

    engine._steer_homing_bullet(state, bullet)

    assert bullet["vy"] != 0


def test_homing_missile_locks_on_after_initial_flight(engine: DuelEngine, state: dict) -> None:
    state["fighters"]["p1"]["y"] = 12
    bullet = {
        "x": 10,
        "y": 8,
        "vx": 2,
        "vy": 0,
        "homing": True,
        "homing_age": 0,
        "owner_id": "p0",
    }

    engine._steer_homing_bullet(state, bullet)
    assert bullet["vy"] == 0
    assert bullet["homing_age"] == 1

    bullet["homing_age"] = HOMING_LOCK_ON_TICKS
    engine._steer_homing_bullet(state, bullet)
    assert bullet["vy"] == 1


def test_homing_missile_leads_moving_target(engine: DuelEngine, state: dict) -> None:
    target = state["fighters"]["p1"]
    target["y"] = 8
    target["move_direction"] = "down"
    bullet = {
        "x": 10,
        "y": 8,
        "vx": 2,
        "vy": 0,
        "homing": True,
        "homing_age": HOMING_LOCK_ON_TICKS,
        "owner_id": "p0",
    }

    engine._steer_homing_bullet(state, bullet)

    assert bullet["vy"] == 1


def test_ai_difficulty_attached_to_ai_players(engine: DuelEngine) -> None:
    players = [
        {"id": "human", "nickname": "Human", "team": None, "role": None, "is_ai": False, "is_connected": True},
        {"id": "ai", "nickname": "AI", "team": None, "role": None, "is_ai": True, "is_connected": True},
    ]
    game_state = engine.create_initial_state(players, {"ai_difficulty": "hard"})
    ai_player = next(p for p in game_state["players"] if p["id"] == "ai")
    assert ai_player["ai_difficulty"] == "hard"


def test_layout_seed_produces_deterministic_obstacles(engine: DuelEngine) -> None:
    players = make_players(2)
    settings = {"layout_seed": 424242, "obstacles_enabled": True, "obstacle_count": 3}
    a = engine.create_initial_state(players, settings)
    b = engine.create_initial_state(players, settings)
    assert a["obstacles"] == b["obstacles"]
    assert a["settings"]["layout_seed"] == 424242


def test_effective_shrink_interval_halves_after_sudden_death(engine: DuelEngine, state: dict) -> None:
    state["settings"]["shrinking_arena"] = True
    state["settings"]["shrink_interval_ticks"] = 80
    state["settings"]["sudden_death_after_round"] = 3
    state["round"] = 3
    assert engine._effective_shrink_interval(state) == 40

    public = engine.get_public_state(state, state["players"][0])
    assert public["shrink_interval_ticks"] == 40


def test_round_end_skips_draft_when_disabled(engine: DuelEngine, state: dict) -> None:
    state["settings"]["powerup_draft_enabled"] = False
    state["settings"]["best_of"] = 5
    state["settings"]["match_format"] = "best_of_5"
    state["fighters"]["p0"]["alive"] = False
    events: list[dict] = []
    engine._end_round(state, "p1", events)
    assert state["phase"] != "powerup_draft"
    assert state["phase"] == "round_over"
    assert state["round"] == 2


def test_round_end_enters_powerup_draft(engine: DuelEngine, state: dict) -> None:
    state["settings"]["powerup_draft_enabled"] = True
    state["settings"]["best_of"] = 5
    state["settings"]["match_format"] = "best_of_5"
    state["fighters"]["p0"]["alive"] = False
    events: list[dict] = []
    engine._end_round(state, "p1", events)
    assert state["phase"] == "powerup_draft"
    assert state["fighters"]["p0"]["alive"] is True
    assert state["fighters"]["p1"]["alive"] is True
    assert state["round"] == 2


def test_powerup_draft_tick_completion_resets_fighters(engine: DuelEngine, state: dict) -> None:
    state["settings"]["powerup_draft_enabled"] = True
    state["settings"]["best_of"] = 5
    state["settings"]["match_format"] = "best_of_5"
    state["fighters"]["p0"]["alive"] = False
    events: list[dict] = []
    engine._end_round(state, "p1", events)
    assert state["phase"] == "powerup_draft"

    human = state["players"][0]
    ai = state["players"][1]
    ai["is_ai"] = True
    state, _ = engine.apply_action(
        state, {"type": "ban_powerup", "powerup_type": "shield"}, human
    )
    assert state["phase"] == "powerup_draft"

    state, _ = engine.tick(state)
    assert state["phase"] == "countdown"
    assert state["fighters"]["p0"]["alive"] is True
    assert state["fighters"]["p1"]["alive"] is True
    assert state["round_scores"]["p1"] == 1


def test_draw_round_increments_without_score_change(engine: DuelEngine, state: dict) -> None:
    state["fighters"]["p0"]["alive"] = False
    state["fighters"]["p1"]["alive"] = False
    events: list[dict] = []
    engine._end_round(state, None, events)
    assert state["round_scores"]["p0"] == 0
    assert state["round_scores"]["p1"] == 0
    assert state["round"] == 2


def test_burst_shots_respect_bullet_cap(engine: DuelEngine, state: dict) -> None:
    state["settings"]["max_bullets_per_player"] = 2
    fighter = state["fighters"]["p0"]
    fighter["burst_shots_remaining"] = 6
    fighter["burst_next_at_tick"] = state["tick"]
    state["bullets"] = [
        {"id": 1, "x": 5, "y": 3, "vx": 1, "owner_id": "p0"},
        {"id": 2, "x": 6, "y": 3, "vx": 1, "owner_id": "p0"},
    ]
    engine._process_burst_shots(state)
    assert len([b for b in state["bullets"] if b["owner_id"] == "p0"]) == 2


def test_duplicate_ban_returns_rejection(engine: DuelEngine, state: dict) -> None:
    state["phase"] = "powerup_draft"
    state["powerup_bans"] = {"p0": "shield"}
    player = state["players"][0]
    state, _ = engine.apply_action(
        state, {"type": "ban_powerup", "powerup_type": "ghost"}, player
    )
    assert state["last_action"]["type"] == "action_rejected"
    assert state["last_action"]["reason"] == "already_banned"


def test_afterburner_moves_two_rows(engine: DuelEngine, state: dict) -> None:
    fighter = state["fighters"]["p0"]
    fighter["move_direction"] = "down"
    fighter["effects"]["afterburner_until"] = state["tick"] + 50
    start_y = fighter["y"]

    engine._move_fighter(
        fighter,
        state["grid_height"],
        engine._fighter_height(state),
        state.get("obstacles", []),
        state.get("playable_y_min", 0),
        state.get("playable_y_max", state["grid_height"] - 1),
        state["tick"],
    )
    assert fighter["y"] == start_y + 2


def test_snipe_spawns_piercing_shot(engine: DuelEngine, state: dict) -> None:
    fighter = state["fighters"]["p0"]
    fighter["stored_powerup"] = "snipe"
    events: list[dict] = []
    engine._activate_stored_powerup(state, fighter, "p0", events)
    assert len(state["bullets"]) == 1
    bullet = state["bullets"][0]
    assert bullet["damage"] == 3
    assert bullet.get("pierce_obstacles") is True


def test_shockwave_pushes_enemy(engine: DuelEngine, state: dict) -> None:
    caster = state["fighters"]["p0"]
    enemy = state["fighters"]["p1"]
    caster["y"] = 5
    enemy["y"] = 8
    enemy_start = enemy["y"]
    caster["stored_powerup"] = "shockwave"
    events: list[dict] = []
    engine._activate_stored_powerup(state, caster, "p0", events)
    assert enemy["y"] > enemy_start
    assert any(e["type"] == "shockwave_hit" for e in events)


def test_expose_reveals_enemy_in_fog(engine: DuelEngine, state: dict) -> None:
    state["settings"]["fog"] = True
    caster = state["fighters"]["p0"]
    enemy = state["fighters"]["p1"]
    caster["stored_powerup"] = "expose"
    engine._activate_stored_powerup(state, caster, "p0", [])
    public = engine.get_public_state(state, state["players"][0])
    assert public["fighters"]["p1"]["display_y"] == enemy["y"]


def test_aim_trainer_blocks_human_movement(engine: DuelEngine, state: dict) -> None:
    state["settings"]["training_drill"] = "aim_trainer"
    player = state["players"][0]
    state, _ = engine.apply_action(state, {"type": "set_move", "direction": "up"}, player)
    assert state["fighters"][player["id"]]["move_direction"] != "up"


def test_disconnect_forfeit_awards_round(engine: DuelEngine, state: dict) -> None:
    events: list[dict] = []
    assert engine.handle_disconnect_forfeit(state, "p0", events) is True
    assert state["round_scores"]["p1"] == 1
    assert events


def test_sniper_instant_kill(engine: DuelEngine, state: dict) -> None:
    state["settings"]["instant_kill"] = True
    right = state["fighters"]["p1"]
    right["hp"] = 3
    bullet = {
        "id": 1,
        "x": right["x"],
        "y": right["y"],
        "vx": 0,
        "vy": 0,
        "owner_id": "p0",
        "damage": 1,
        "kind": "normal",
    }
    events: list[dict] = []
    damage, crit = engine._hit_damage(
        state, bullet, right, engine._fighter_height(state)
    )
    engine._apply_damage(state, right, "p0", "p1", damage, crit, events, hit_y=right["y"])
    assert right["alive"] is False


def test_bounce_self_damage_on_ricochet(engine: DuelEngine, state: dict) -> None:
    state["settings"]["bounce_self_damage"] = True
    state["settings"]["ricochet_bounces"] = 2
    left = state["fighters"]["p0"]
    row = left["y"] + 1
    state["obstacles"] = [{"x": left["x"] + 2, "y": row, "w": 1, "h": 1, "vy": 0}]
    bullet = {
        "id": 1,
        "x": left["x"] + 1,
        "y": row,
        "vx": 1,
        "vy": 0,
        "owner_id": "p0",
        "damage": 1,
        "bounces_remaining": 1,
        "kind": "normal",
    }
    state["bullets"] = [bullet]
    events: list[dict] = []
    engine._process_bullet(
        state,
        bullet,
        state["fighters"],
        engine._fighter_height(state),
        state["obstacles"],
        events,
    )
    assert bullet.get("can_hit_owner") is True
    assert bullet["vx"] == -1


def test_side_swap_every_two_rounds(engine: DuelEngine) -> None:
    players = make_players(2)
    game_state = engine.create_initial_state(
        players,
        {"match_format": "best_of_7", "countdown_sec": 0},
    )
    game_state["phase"] = "playing"
    initial_sides = (
        game_state["fighters"]["p0"]["side"],
        game_state["fighters"]["p1"]["side"],
    )
    initial_colors = (
        game_state["fighters"]["p0"]["color"],
        game_state["fighters"]["p1"]["color"],
    )
    game_state["round"] = 2
    engine._reset_round(game_state)
    swapped_sides = (
        game_state["fighters"]["p0"]["side"],
        game_state["fighters"]["p1"]["side"],
    )
    assert initial_sides != swapped_sides
    assert (
        game_state["fighters"]["p0"]["color"],
        game_state["fighters"]["p1"]["color"],
    ) == initial_colors


def test_jam_rejects_shoot_action(engine: DuelEngine, state: dict) -> None:
    player = state["players"][0]
    pid = player["id"]
    state["fighters"][pid]["effects"]["jam_until"] = state["tick"] + 50
    state, _ = engine.apply_action(state, {"type": "shoot"}, player)
    assert state["last_action"]["type"] == "action_rejected"
    assert state["last_action"]["reason"] == "jammed"


def test_obstacle_rotation_deterministic_with_layout_seed(engine: DuelEngine, state: dict) -> None:
    state["settings"]["layout_seed"] = 42
    state["settings"]["obstacle_rotation"] = True
    state["tick"] = 120
    state["obstacles"] = [{"x": 10, "y": 5, "w": 1, "h": 2, "vy": 0}]
    a = copy.deepcopy(state)
    b = copy.deepcopy(state)
    engine._rotate_obstacles(a)
    engine._rotate_obstacles(b)
    assert a["obstacles"][0]["vy"] == b["obstacles"][0]["vy"]


def test_ai_channels_powerup_before_activation(engine: DuelEngine, state: dict) -> None:
    ai_player = state["players"][1]
    ai_player["is_ai"] = True
    fighter = state["fighters"]["p1"]
    fighter["stored_powerup"] = "shield"
    fighter["hp"] = 1
    state["fighters"]["p0"]["x"] = 2
    state["fighters"]["p1"]["x"] = 20

    from app.games.duel import ai as duel_ai

    original = duel_ai._should_use_powerup
    duel_ai._should_use_powerup = lambda *args, **kwargs: True  # type: ignore[assignment]
    try:
        engine._apply_ai_inputs(state, [])
        assert fighter.get("activating_powerup") is True
        assert fighter.get("stored_powerup") == "shield"
        for _ in range(10):
            state, _ = engine.tick(state)
        assert fighter.get("stored_powerup") is None or fighter.get("effects", {}).get("shield_until", 0) > state["tick"]
    finally:
        duel_ai._should_use_powerup = original


def test_request_rematch_when_finished(engine: DuelEngine, state: dict) -> None:
    state["phase"] = "finished"
    state["winner"] = "p1"
    player = state["players"][0]
    state, _ = engine.apply_action(state, {"type": "request_rematch"}, player)
    assert "p0" in state["rematch_requests"]
    state, _ = engine.apply_action(state, {"type": "request_rematch"}, player)
    assert state["rematch_requests"].count("p0") == 1
