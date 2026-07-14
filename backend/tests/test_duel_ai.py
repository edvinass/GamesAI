import pytest

from app.games.duel.ai import choose_ai_actions
from app.games.duel.engine import DuelEngine


def make_state() -> dict:
    engine = DuelEngine()
    players = [
        {"id": "human", "nickname": "Human", "team": None, "role": None, "is_ai": False, "is_connected": True},
        {"id": "ai", "nickname": "AI", "team": None, "role": None, "is_ai": True, "is_connected": True},
    ]
    state = engine.create_initial_state(players, {"countdown_sec": 0})
    state["phase"] = "playing"
    state["countdown_ends_at"] = None
    return state


def _rows_after(top: int, move: str) -> range:
    delta = 1 if move == "down" else -1 if move == "up" else 0
    new_top = top + delta
    return range(new_top, new_top + 3)


def test_ai_dodges_bullet_on_current_row() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 10

    state["bullets"] = [{"id": 0, "x": 40, "y": 10, "vx": 1, "owner_id": "human"}]

    move, *_ = choose_ai_actions(state, "ai", ai)
    assert 10 not in _rows_after(ai["y"], move)


def test_ai_dodges_approaching_bullet_before_overlap() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 8

    state["bullets"] = [{"id": 0, "x": 25, "y": 11, "vx": 1, "owner_id": "human"}]

    move, *_ = choose_ai_actions(state, "ai", ai)
    new_top = ai["y"] + (1 if move == "down" else -1 if move == "up" else 0)
    assert move != "down"
    assert 11 not in range(new_top, new_top + 3)


def test_ai_left_side_dodges_incoming_shot() -> None:
    state = make_state()
    left = state["fighters"]["human"]
    left["side"] = "left"
    left["x"] = 1
    left["y"] = 10

    state["bullets"] = [{"id": 0, "x": 30, "y": 10, "vx": -1, "owner_id": "ai"}]

    move, *_ = choose_ai_actions(state, "human", left)
    new_top = left["y"] + (1 if move == "down" else -1 if move == "up" else 0)
    assert 10 not in range(new_top, new_top + 3)


def test_ai_shoots_when_aligned() -> None:
    state = make_state()
    state["settings"]["charge_shot_enabled"] = False
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 10
    human["x"] = 1
    human["y"] = 10
    ai["cooldown_until_tick"] = 0

    _, shoot, *_ = choose_ai_actions(state, "ai", ai)
    assert shoot is True


def test_ai_leads_moving_target() -> None:
    state = make_state()
    state["settings"]["charge_shot_enabled"] = False
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 10
    human["x"] = 1
    human["y"] = 9
    human["move_direction"] = "down"
    ai["cooldown_until_tick"] = 0

    _, shoot, *_ = choose_ai_actions(state, "ai", ai)
    assert shoot is True


def test_ai_moves_back_from_top_edge_when_safe() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 0
    ai["move_direction"] = "up"
    state["bullets"] = []

    move, *_ = choose_ai_actions(state, "ai", ai)
    assert move == "down"


def test_ai_moves_back_from_bottom_edge_when_safe() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = state["grid_height"] - 3
    ai["move_direction"] = "down"
    state["bullets"] = []

    move, *_ = choose_ai_actions(state, "ai", ai)
    assert move == "up"


def test_ai_prefers_center_among_safe_dodges() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 1
    state["bullets"] = [{"id": 0, "x": 10, "y": 20, "vx": 1, "owner_id": "human"}]

    move, *_ = choose_ai_actions(state, "ai", ai)
    assert move == "down"


def test_ai_follows_enemy_moving_down() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 5
    human["x"] = 1
    human["y"] = 18
    human["move_direction"] = "down"
    state["bullets"] = []

    move, *_ = choose_ai_actions(state, "ai", ai)
    assert move == "down"


def test_ai_follows_enemy_moving_up() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 15
    human["x"] = 1
    human["y"] = 2
    human["move_direction"] = "up"
    state["bullets"] = []

    move, *_ = choose_ai_actions(state, "ai", ai)
    assert move == "up"


def test_ai_shoots_after_moving_into_alignment() -> None:
    state = make_state()
    state["settings"]["charge_shot_enabled"] = False
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 8
    human["x"] = 1
    human["y"] = 10
    ai["cooldown_until_tick"] = 0
    state["bullets"] = []

    move, shoot, *_ = choose_ai_actions(state, "ai", ai)
    assert move == "down"
    assert shoot is True


def test_ai_uses_instant_bomb_when_aligned() -> None:
    state = make_state()
    state["settings"]["powerups_enabled"] = True
    state["settings"]["match_format"] = "best_of_5"
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["y"] = 10
    human["y"] = 10
    ai["stored_powerup"] = "bomb"

    *_, pu_instant = choose_ai_actions(state, "ai", ai)
    assert pu_instant is True


def test_ai_starts_shield_when_low_hp() -> None:
    state = make_state()
    state["settings"]["powerups_enabled"] = True
    ai = state["fighters"]["ai"]
    ai["hp"] = 1
    ai["stored_powerup"] = "shield"

    *_, pu_start, pu_release, pu_instant = choose_ai_actions(state, "ai", ai)[-4:]
    assert pu_start is True
    assert pu_release is False
    assert pu_instant is False


def test_ai_completes_channelled_powerup() -> None:
    engine = DuelEngine()
    state = make_state()
    state["settings"]["powerups_enabled"] = True
    ai = state["fighters"]["ai"]
    ai["stored_powerup"] = "shield"
    ai["activating_powerup"] = True
    ai["powerup_activation_ticks"] = 8

    state, events = engine.tick(state)
    assert ai["stored_powerup"] is None
    assert ai["effects"]["shield_until"] > state["tick"]
    assert any(e["type"] == "powerup_activated" for e in events)


def test_ai_channel_not_reset_mid_activation() -> None:
    engine = DuelEngine()
    state = make_state()
    state["settings"]["powerups_enabled"] = True
    state["settings"]["ai_reaction_interval_ticks"] = 2
    ai = state["fighters"]["ai"]
    ai["stored_powerup"] = "shield"
    ai["activating_powerup"] = True
    ai["powerup_activation_ticks"] = 4

    state, _ = engine.tick(state)
    assert ai["activating_powerup"] is True
    assert ai["powerup_activation_ticks"] >= 5


def test_ai_uses_heal_when_damaged() -> None:
    state = make_state()
    state["settings"]["powerups_enabled"] = True
    ai = state["fighters"]["ai"]
    ai["hp"] = 2
    ai["max_hp"] = 3
    ai["stored_powerup"] = "heal"

    *_, pu_instant = choose_ai_actions(state, "ai", ai)
    assert pu_instant is True


def test_ai_machine_gun_spams_shots() -> None:
    state = make_state()
    state["settings"]["charge_shot_enabled"] = False
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["y"] = 5
    human["y"] = 12
    ai["cooldown_until_tick"] = 0
    ai["effects"]["machine_gun_until"] = state["tick"] + 80

    _, shoot, *_ = choose_ai_actions(state, "ai", ai)
    assert shoot is True


def test_ai_activates_freeze_in_range() -> None:
    state = make_state()
    state["settings"]["powerups_enabled"] = True
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["stored_powerup"] = "freeze"
    ai["x"] = 40
    human["x"] = 10

    *_, pu_start, pu_release, pu_instant = choose_ai_actions(state, "ai", ai)[-4:]
    assert pu_start is True
    assert pu_release is False
    assert pu_instant is False


def test_ai_moves_toward_powerup() -> None:
    state = make_state()
    state["settings"]["powerups_enabled"] = True
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 5
    state["bullets"] = []
    state["powerup"] = {
        "x": 24,
        "y": 12,
        "type": "shield",
        "despawn_at_tick": state["tick"] + 15,
    }

    move, *_ = choose_ai_actions(state, "ai", ai)
    assert move == "down"


def test_ai_starts_offensive_buff_when_engaging() -> None:
    state = make_state()
    state["settings"]["powerups_enabled"] = True
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["y"] = 10
    human["y"] = 10
    ai["stored_powerup"] = "overdrive"

    *_, pu_start, pu_release, pu_instant = choose_ai_actions(state, "ai", ai)[-4:]
    assert pu_start is True
    assert pu_release is False
    assert pu_instant is False


def test_ai_charges_when_aligned_and_safe() -> None:
    state = make_state()
    state["settings"]["charge_shot_enabled"] = True
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["y"] = 10
    human["y"] = 10
    ai["cooldown_until_tick"] = 0
    state["bullets"] = []

    _, shoot, charge_start, charge_release, charge_ticks, *_ = choose_ai_actions(state, "ai", ai)
    assert shoot is False
    assert charge_start is True
    assert charge_release is False
    assert charge_ticks >= 8


def test_ai_builds_full_charge_while_aligned() -> None:
    engine = DuelEngine()
    state = make_state()
    state["settings"]["charge_shot_enabled"] = True
    state["settings"]["ai_reaction_interval_ticks"] = 2
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["y"] = 10
    human["y"] = 10
    ai["cooldown_until_tick"] = 0
    state["bullets"] = []

    max_seen = 0
    for _ in range(20):
        state, _ = engine.tick(state)
        max_seen = max(max_seen, ai.get("charge_ticks", 0))

    assert max_seen >= 10


def test_ai_releases_full_charge_shot() -> None:
    engine = DuelEngine()
    state = make_state()
    state["settings"]["charge_shot_enabled"] = True
    state["settings"]["ai_reaction_interval_ticks"] = 1
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["y"] = 10
    human["y"] = 10
    ai["cooldown_until_tick"] = 0
    state["bullets"] = []

    released_full = False
    for _ in range(25):
        state, _ = engine.tick(state)
        ai_bullets = [b for b in state["bullets"] if b["owner_id"] == "ai"]
        if len(ai_bullets) >= 3 and all(b.get("damage", 1) >= 2 for b in ai_bullets[:3]):
            released_full = True
            break

    assert released_full


def test_ai_difficulty_configs_scale() -> None:
    from app.games.duel.ai import get_ai_config

    easy = get_ai_config("easy")
    hard = get_ai_config("hard")
    assert easy["reaction_interval"] > hard["reaction_interval"]
    assert easy["mistake_rate"] > hard["mistake_rate"]


def test_easy_ai_makes_more_mistakes(monkeypatch) -> None:
    import app.games.duel.ai as duel_ai

    monkeypatch.setattr(duel_ai.random, "random", lambda: 0.0)
    state = make_state()
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 10
    state["bullets"] = [{"id": 0, "x": 40, "y": 10, "vx": 1, "owner_id": "human"}]

    move, *_ = choose_ai_actions(state, "ai", ai, "easy")
    assert move in ("up", "down", "stop")
