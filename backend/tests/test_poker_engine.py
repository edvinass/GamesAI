import copy

import pytest

from app.games.poker.engine import PokerEngine


def make_players(count: int = 3, *, ai_indices: set[int] | None = None) -> list[dict]:
    ai_indices = ai_indices or set()
    return [
        {
            "id": f"p{i}",
            "nickname": f"Player {i}",
            "team": None,
            "role": None,
            "is_ai": i in ai_indices,
            "is_connected": True,
        }
        for i in range(count)
    ]


@pytest.fixture
def engine() -> PokerEngine:
    return PokerEngine()


@pytest.fixture
def state(engine: PokerEngine) -> dict:
    players = make_players(3)
    settings = {"host_id": "p0", "small_blind": 5, "big_blind": 10}
    return engine.create_initial_state(players, settings)


def test_lobby_validation(engine: PokerEngine) -> None:
    assert engine.validate_lobby(make_players(1), {}) is not None
    assert engine.validate_lobby(make_players(2), {}) is None
    assert engine.validate_lobby(make_players(7), {}) is not None
    assert engine.validate_lobby(make_players(1), {"solo_practice": True}) is None


def test_blinds_posted(engine: PokerEngine, state: dict) -> None:
    assert state["phase"] == "preflop"
    assert state["current_bet"] == 10
    total_chips = sum(p["chips"] for p in state["players"].values())
    total_bets = sum(p["total_bet_hand"] for p in state["players"].values())
    assert total_bets == 15
    assert total_chips + total_bets == 3000


def test_hole_cards_hidden(engine: PokerEngine, state: dict) -> None:
    viewer = {"id": "p0", "nickname": "Player 0", "is_ai": False}
    other = {"id": "p1", "nickname": "Player 1", "is_ai": False}
    self_view = engine.get_public_state(state, viewer)
    other_view = engine.get_public_state(state, other)
    assert len(self_view["players"][0]["hole_cards"]) == 2
    assert other_view["players"][0]["hole_cards"] == []


def test_fold_wins_pot(engine: PokerEngine, state: dict) -> None:
    actor_id = state["current_actor_id"]
    actor = {"id": actor_id, "nickname": "Actor", "is_ai": False}
    state, events = engine.apply_action(state, {"type": "fold"}, actor)
    if state["phase"] != "hand_complete":
        actor_id = state["current_actor_id"]
        actor = {"id": actor_id, "nickname": "Actor", "is_ai": False}
        state, events = engine.apply_action(state, {"type": "fold"}, actor)
    assert state["phase"] in ("hand_complete", "game_over")
    assert state["winners"]


def test_check_advances_when_possible(engine: PokerEngine, state: dict) -> None:
    while state["phase"] == "preflop" and state.get("current_actor_id"):
        actor_id = state["current_actor_id"]
        actor = {"id": actor_id, "nickname": actor_id, "is_ai": False}
        p = state["players"][actor_id]
        to_call = state["current_bet"] - p["bet_this_round"]
        if to_call == 0:
            state, _ = engine.apply_action(state, {"type": "check"}, actor)
        else:
            state, _ = engine.apply_action(state, {"type": "call"}, actor)
        if state["phase"] != "preflop":
            break
    assert state["phase"] in ("flop", "turn", "river", "showdown", "hand_complete")


def test_side_pot_calculation(engine: PokerEngine) -> None:
    state = {
        "seat_order": ["a", "b", "c"],
        "players": {
            "a": {"total_bet_hand": 100, "status": "all_in"},
            "b": {"total_bet_hand": 200, "status": "all_in"},
            "c": {"total_bet_hand": 200, "status": "active"},
        },
        "community_cards": [],
        "phase": "showdown",
    }
    pots = engine._calculate_side_pots(state)
    assert sum(p["amount"] for p in pots) == 500


def test_next_hand_requires_host(engine: PokerEngine, state: dict) -> None:
    state["phase"] = "hand_complete"
    host = {"id": "p0", "nickname": "Host", "is_ai": False}
    state, events = engine.apply_action(state, {"type": "next_hand"}, host)
    assert state["hand_number"] == 2
    assert state["phase"] == "preflop"


def test_get_current_actor_ai_only(engine: PokerEngine, state: dict) -> None:
    state["players"][state["current_actor_id"]]["is_ai"] = True
    actor = engine.get_current_actor(state)
    assert actor is not None
    assert actor["is_ai"] is True

    state["players"][state["current_actor_id"]]["is_ai"] = False
    assert engine.get_current_actor(state) is None
