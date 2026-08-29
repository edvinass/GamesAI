"""Tests for Monopoly engine and AI."""

from app.games.monopoly.ai import choose_monopoly_action
from app.games.monopoly.engine import MonopolyEngine


def _players(n=2):
    return [
        {"id": f"p{i}", "nickname": f"P{i}", "is_ai": i > 0}
        for i in range(1, n + 1)
    ]


def _engine_state(n=2, **settings):
    engine = MonopolyEngine()
    state = engine.create_initial_state(_players(n), settings)
    return engine, state


def test_initial_state():
    engine, state = _engine_state()
    assert state["phase"] == "awaiting_roll"
    assert state["current_actor_id"] == "p1"
    assert state["players"]["p1"]["cash"] == 1500
    assert len(state["properties"]) == 28
    assert engine.tick_interval_ms() is None


def test_lobby_validation():
    engine = MonopolyEngine()
    assert engine.validate_lobby(_players(1), {}) is not None
    assert engine.validate_lobby(_players(2), {}) is None
    assert engine.validate_lobby(
        [{"id": "h", "nickname": "H", "is_ai": False}], {"solo_practice": True}
    ) is None


def test_roll_and_buy():
    engine, state = _engine_state(seed=1)
    # Force land on Mediterranean (1): from 0 roll 1+0 invalid — use d1=1,d2=0 no
    # Roll 1+0 not valid. Position 0 + 1 = need total 1 — use two dice min 2.
    # Land on Baltic (3): roll 1+2
    state, _ = engine.apply_action(state, {"type": "roll", "d1": 1, "d2": 2}, {"id": "p1"})
    assert state["players"]["p1"]["position"] == 3
    assert state["phase"] == "awaiting_buy"
    state, _ = engine.apply_action(state, {"type": "buy"}, {"id": "p1"})
    assert state["properties"]["3"]["owner_id"] == "p1"
    assert state["players"]["p1"]["cash"] == 1500 - 60


def test_decline_starts_auction():
    engine, state = _engine_state()
    state, _ = engine.apply_action(state, {"type": "roll", "d1": 1, "d2": 2}, {"id": "p1"})
    state, _ = engine.apply_action(state, {"type": "decline"}, {"id": "p1"})
    assert state["phase"] == "auction"
    assert state["auction"]["space_id"] == 3


def test_auction_award():
    engine, state = _engine_state()
    state, _ = engine.apply_action(state, {"type": "roll", "d1": 1, "d2": 2}, {"id": "p1"})
    state, _ = engine.apply_action(state, {"type": "decline"}, {"id": "p1"})
    # p1 is first bidder
    assert state["current_actor_id"] == "p1"
    state, _ = engine.apply_action(state, {"type": "bid", "amount": 40}, {"id": "p1"})
    # p2 passes → auction ends (1 pass with 2 players and a high bid)
    assert state["current_actor_id"] == "p2"
    state, _ = engine.apply_action(state, {"type": "pass_auction"}, {"id": "p2"})
    assert state["properties"]["3"]["owner_id"] == "p1"
    assert state["players"]["p1"]["cash"] == 1500 - 40
    assert state["auction"] is None


def test_rent_with_monopoly():
    engine, state = _engine_state()
    # Give p2 both browns
    state["properties"]["1"]["owner_id"] = "p2"
    state["properties"]["3"]["owner_id"] = "p2"
    # p1 lands on Baltic
    state["players"]["p1"]["position"] = 0
    state, _ = engine.apply_action(state, {"type": "roll", "d1": 1, "d2": 2}, {"id": "p1"})
    # Base rent 4 * 2 = 8 for monopoly
    assert state["players"]["p1"]["cash"] == 1500 - 8
    assert state["players"]["p2"]["cash"] == 1500 + 8


def test_jail_on_three_doubles():
    engine, state = _engine_state()
    state, _ = engine.apply_action(state, {"type": "roll", "d1": 1, "d2": 1}, {"id": "p1"})
    # May be awaiting_buy or awaiting_roll depending on landing
    # Force clear phase for next doubles
    while state["phase"] == "awaiting_buy":
        state, _ = engine.apply_action(state, {"type": "decline"}, {"id": state["current_actor_id"]})
        while state["phase"] == "auction":
            state, _ = engine.apply_action(
                state, {"type": "pass_auction"}, {"id": state["current_actor_id"]}
            )
    if state["phase"] == "awaiting_end":
        # doubles should allow roll again — if not in jail
        pass
    if state["phase"] == "awaiting_roll" and state["can_roll_again"]:
        state, _ = engine.apply_action(state, {"type": "roll", "d1": 2, "d2": 2}, {"id": "p1"})
        while state["phase"] == "awaiting_buy":
            state, _ = engine.apply_action(state, {"type": "decline"}, {"id": "p1"})
            while state["phase"] == "auction":
                state, _ = engine.apply_action(
                    state, {"type": "pass_auction"}, {"id": state["current_actor_id"]}
                )
        if state["phase"] == "awaiting_roll" and state["can_roll_again"]:
            state, _ = engine.apply_action(state, {"type": "roll", "d1": 3, "d2": 3}, {"id": "p1"})
            assert state["players"]["p1"]["in_jail"] is True
            assert state["players"]["p1"]["position"] == 10


def test_build_evenness():
    engine, state = _engine_state()
    state["properties"]["1"]["owner_id"] = "p1"
    state["properties"]["3"]["owner_id"] = "p1"
    state["phase"] = "awaiting_end"
    state["current_actor_id"] = "p1"
    state["can_roll_again"] = False
    state, _ = engine.apply_action(state, {"type": "build", "space_id": 1}, {"id": "p1"})
    assert state["properties"]["1"]["houses"] == 1
    try:
        engine.apply_action(state, {"type": "build", "space_id": 1}, {"id": "p1"})
        assert False, "expected evenness error"
    except ValueError as e:
        assert "even" in str(e).lower()
    state, _ = engine.apply_action(state, {"type": "build", "space_id": 3}, {"id": "p1"})
    assert state["properties"]["3"]["houses"] == 1


def test_trade_accept():
    engine, state = _engine_state()
    state["properties"]["1"]["owner_id"] = "p1"
    state["properties"]["6"]["owner_id"] = "p2"
    state["phase"] = "awaiting_end"
    state["current_actor_id"] = "p1"
    state["can_roll_again"] = False
    state, _ = engine.apply_action(
        state,
        {
            "type": "propose_trade",
            "to_id": "p2",
            "offer_cash": 50,
            "request_cash": 0,
            "offer_props": [1],
            "request_props": [6],
        },
        {"id": "p1"},
    )
    assert state["phase"] == "trade_pending"
    assert state["current_actor_id"] == "p2"
    state, _ = engine.apply_action(state, {"type": "accept_trade"}, {"id": "p2"})
    assert state["properties"]["1"]["owner_id"] == "p2"
    assert state["properties"]["6"]["owner_id"] == "p1"
    assert state["players"]["p2"]["cash"] == 1500 + 50
    assert state["players"]["p1"]["cash"] == 1500 - 50


def test_bankruptcy():
    engine, state = _engine_state()
    state["properties"]["39"]["owner_id"] = "p2"
    state["properties"]["39"]["houses"] = 5  # hotel on Boardwalk
    state["players"]["p1"]["cash"] = 10
    state["players"]["p1"]["position"] = 0
    # Land on Boardwalk: from 0 need 39 — roll won't work in one roll. Place and resolve manually.
    state["players"]["p1"]["position"] = 39
    state["last_dice"] = [1, 2]
    engine._resolve_landing(state, "p1", [], 3)
    assert state["phase"] == "awaiting_payment"
    assert state["debt"]["amount"] == 2000  # hotel rent
    state, _ = engine.apply_action(state, {"type": "declare_bankruptcy"}, {"id": "p1"})
    assert state["players"]["p1"]["bankrupt"] is True
    assert state["winner"] == "p2"


def test_ai_returns_legal_actions():
    engine, state = _engine_state()
    state["players"]["p2"]["is_ai"] = True
    state["players"]["p2"]["ai_difficulty"] = "medium"
    # End p1 turn quickly
    state["phase"] = "awaiting_end"
    state["current_actor_id"] = "p1"
    state["can_roll_again"] = False
    state, _ = engine.apply_action(state, {"type": "end_turn"}, {"id": "p1"})
    assert state["current_actor_id"] == "p2"
    actor = engine.get_current_actor(state)
    assert actor is not None
    action = choose_monopoly_action(state, "p2")
    assert action["type"] in ("roll", "roll_jail", "pay_jail", "use_jail_card")
    state, _ = engine.apply_action(state, action, {"id": "p2"})


def test_go_to_jail_space():
    engine, state = _engine_state()
    state["players"]["p1"]["position"] = 28
    state, _ = engine.apply_action(state, {"type": "roll", "d1": 1, "d2": 1}, {"id": "p1"})
    # 28+2=30 go to jail
    assert state["players"]["p1"]["in_jail"] is True
    assert state["players"]["p1"]["position"] == 10
    assert state["can_roll_again"] is False


def test_mortgage():
    engine, state = _engine_state()
    state["properties"]["1"]["owner_id"] = "p1"
    state["phase"] = "awaiting_end"
    state["current_actor_id"] = "p1"
    state, _ = engine.apply_action(state, {"type": "mortgage", "space_id": 1}, {"id": "p1"})
    assert state["properties"]["1"]["mortgaged"] is True
    assert state["players"]["p1"]["cash"] == 1500 + 30
