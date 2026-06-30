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

    move, _ = choose_ai_actions(state, "ai", ai)
    assert 10 not in _rows_after(ai["y"], move)


def test_ai_dodges_approaching_bullet_before_overlap() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 8

    state["bullets"] = [{"id": 0, "x": 25, "y": 11, "vx": 1, "owner_id": "human"}]

    move, _ = choose_ai_actions(state, "ai", ai)
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

    move, _ = choose_ai_actions(state, "human", left)
    new_top = left["y"] + (1 if move == "down" else -1 if move == "up" else 0)
    assert 10 not in range(new_top, new_top + 3)


def test_ai_shoots_when_aligned() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 10
    human["x"] = 1
    human["y"] = 10
    ai["cooldown_until_tick"] = 0

    _, shoot = choose_ai_actions(state, "ai", ai)
    assert shoot is True


def test_ai_leads_moving_target() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    human = state["fighters"]["human"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 10
    human["x"] = 1
    human["y"] = 9
    human["move_direction"] = "down"
    ai["cooldown_until_tick"] = 0

    _, shoot = choose_ai_actions(state, "ai", ai)
    assert shoot is True


def test_ai_moves_back_from_top_edge_when_safe() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 0
    ai["move_direction"] = "up"
    state["bullets"] = []

    move, _ = choose_ai_actions(state, "ai", ai)
    assert move == "down"


def test_ai_moves_back_from_bottom_edge_when_safe() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = state["grid_height"] - 3
    ai["move_direction"] = "down"
    state["bullets"] = []

    move, _ = choose_ai_actions(state, "ai", ai)
    assert move == "up"


def test_ai_prefers_center_among_safe_dodges() -> None:
    state = make_state()
    ai = state["fighters"]["ai"]
    ai["side"] = "right"
    ai["x"] = 46
    ai["y"] = 1
    # Bullet aimed low — both up (toward center) and staying are safe from row 20
    state["bullets"] = [{"id": 0, "x": 10, "y": 20, "vx": 1, "owner_id": "human"}]

    move, _ = choose_ai_actions(state, "ai", ai)
    assert move == "down"
