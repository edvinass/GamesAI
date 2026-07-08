from app.games.poker.ai import choose_poker_action
from app.games.poker.engine import PokerEngine


def make_state(*, difficulty: str = "medium") -> dict:
    engine = PokerEngine()
    players = [
        {"id": "p0", "nickname": "Human", "is_ai": False, "team": None, "role": None, "is_connected": True},
        {"id": "p1", "nickname": "AI", "is_ai": True, "team": None, "role": None, "is_connected": True},
        {"id": "p2", "nickname": "AI2", "is_ai": True, "team": None, "role": None, "is_connected": True},
    ]
    return engine.create_initial_state(
        players,
        {"host_id": "p0", "ai_difficulty": difficulty},
    )


def test_ai_returns_legal_action() -> None:
    state = make_state()
    actor_id = state["current_actor_id"]
    for _ in range(20):
        if state["phase"] not in ("preflop", "flop", "turn", "river"):
            break
        if not state.get("current_actor_id"):
            break
        actor_id = state["current_actor_id"]
        action = choose_poker_action(state, actor_id)
        assert action["type"] in ("fold", "check", "call", "raise", "all_in")
        engine = PokerEngine()
        actor = {"id": actor_id, "nickname": actor_id, "is_ai": True}
        try:
            state, _ = engine.apply_action(state, action, actor)
        except ValueError:
            p = state["players"][actor_id]
            to_call = state["current_bet"] - p["bet_this_round"]
            fallback = {"type": "call"} if to_call > 0 else {"type": "check"}
            state, _ = engine.apply_action(state, fallback, actor)


def test_ai_raise_amount_is_legal() -> None:
    state = make_state(difficulty="hard")
    engine = PokerEngine()
    for _ in range(30):
        if state["phase"] not in ("preflop", "flop", "turn", "river"):
            break
        actor_id = state.get("current_actor_id")
        if not actor_id:
            break
        action = choose_poker_action(state, actor_id)
        actor = {"id": actor_id, "nickname": actor_id, "is_ai": True}
        if action["type"] == "raise":
            legal = engine._legal_raise_to_amounts(state, actor_id)
            assert action["amount"] in legal
        try:
            state, _ = engine.apply_action(state, action, actor)
        except ValueError:
            p = state["players"][actor_id]
            to_call = max(0, state["current_bet"] - p["bet_this_round"])
            fallback = {"type": "call"} if to_call > 0 else {"type": "check"}
            state, _ = engine.apply_action(state, fallback, actor)
