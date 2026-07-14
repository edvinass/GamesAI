import random

from app.games.poker.ai import choose_poker_action, get_ai_config
from app.games.poker.deck import make_card
from app.games.poker.engine import PokerEngine
from app.games.poker.ev_solver import choose_ev_action
from app.games.poker.ranges import preflop_hand_strength
from app.games.poker.equity import estimate_equity_vs_ranges


def test_preflop_hand_strength_ordering() -> None:
    aa = preflop_hand_strength([make_card("A", "hearts"), make_card("A", "spades")])
    ak = preflop_hand_strength([make_card("A", "hearts"), make_card("K", "hearts")])
    trash = preflop_hand_strength([make_card("7", "clubs"), make_card("2", "diamonds")])
    assert aa > ak > trash


def test_range_weighted_equity_aa_high() -> None:
    hole = [make_card("A", "hearts"), make_card("A", "spades")]
    equity = estimate_equity_vs_ranges(
        hole,
        [],
        1,
        villain_tightness=0.5,
        iterations=600,
        rng=random.Random(5),
    )
    assert equity > 0.7


def test_hard_uses_ev_strategy() -> None:
    cfg = get_ai_config("hard")
    assert cfg["strategy"] == "ev"
    assert cfg["mistake_rate"] == 0.0


def test_medium_uses_heuristic_strategy() -> None:
    cfg = get_ai_config("medium")
    assert cfg["strategy"] == "heuristic"
    assert cfg["mc_iterations"] == 700


def test_ev_solver_returns_legal_action() -> None:
    engine = PokerEngine()
    players = [
        {"id": "p0", "nickname": "AI", "is_ai": True, "team": None, "role": None, "is_connected": True},
        {"id": "p1", "nickname": "Villain", "is_ai": False, "team": None, "role": None, "is_connected": True},
    ]
    state = engine.create_initial_state(players, {"host_id": "p0", "ai_difficulty": "hard"})
    actor_id = state["current_actor_id"]
    cfg = get_ai_config("hard")

    for _ in range(15):
        if state["phase"] not in ("preflop", "flop", "turn", "river"):
            break
        if not state.get("current_actor_id"):
            break
        actor_id = state["current_actor_id"]
        action = choose_ev_action(state, actor_id, cfg)
        assert action["type"] in ("fold", "check", "call", "raise", "all_in")
        actor = {"id": actor_id, "nickname": actor_id, "is_ai": True}
        try:
            state, _ = engine.apply_action(state, action, actor)
        except ValueError:
            p = state["players"][actor_id]
            to_call = max(0, state["current_bet"] - p["bet_this_round"])
            fallback = {"type": "call"} if to_call > 0 else {"type": "check"}
            state, _ = engine.apply_action(state, fallback, actor)


def test_hard_folds_weak_river_hand() -> None:
    engine = PokerEngine()
    players = [
        {"id": "p0", "nickname": "AI", "is_ai": True, "team": None, "role": None, "is_connected": True},
        {"id": "p1", "nickname": "Villain", "is_ai": False, "team": None, "role": None, "is_connected": True},
    ]
    base = {
        "phase": "river",
        "community_cards": [
            make_card("A", "hearts"),
            make_card("K", "diamonds"),
            make_card("Q", "spades"),
            make_card("J", "clubs"),
            make_card("2", "hearts"),
        ],
        "current_bet": 80,
        "current_actor_id": "p0",
    }
    hero = {
        "hole_cards": [make_card("7", "clubs"), make_card("3", "diamonds")],
        "status": "active",
        "bet_this_round": 0,
        "chips": 500,
        "total_bet_hand": 0,
    }
    villain = {
        "hole_cards": [make_card("8", "spades"), make_card("8", "clubs")],
        "status": "active",
        "bet_this_round": 80,
        "chips": 420,
        "total_bet_hand": 80,
    }
    state = engine.create_initial_state(players, {"host_id": "p0", "big_blind": 10})
    state.update(base)
    state["players"]["p0"].update(hero)
    state["players"]["p1"].update(villain)
    action = choose_poker_action(state, "p0", difficulty="hard")
    assert action["type"] == "fold"


def test_medium_checks_trash_preflop_utg() -> None:
    engine = PokerEngine()
    players = [
        {"id": "p0", "nickname": "AI", "is_ai": True, "team": None, "role": None, "is_connected": True},
        {"id": "p1", "nickname": "Villain", "is_ai": False, "team": None, "role": None, "is_connected": True},
        {"id": "p2", "nickname": "Villain2", "is_ai": False, "team": None, "role": None, "is_connected": True},
    ]
    state = engine.create_initial_state(players, {"host_id": "p0", "big_blind": 10, "ai_difficulty": "medium"})
    state.update(
        {
            "phase": "preflop",
            "current_bet": 10,
            "current_actor_id": "p0",
            "dealer_index": 2,
            "seat_order": ["p0", "p1", "p2"],
        }
    )
    state["players"]["p0"].update(
        {
            "hole_cards": [make_card("7", "clubs"), make_card("2", "diamonds")],
            "status": "active",
            "bet_this_round": 0,
            "chips": 1000,
            "total_bet_hand": 0,
        }
    )
    state["players"]["p1"].update({"status": "active", "bet_this_round": 5, "total_bet_hand": 5})
    state["players"]["p2"].update({"status": "active", "bet_this_round": 10, "total_bet_hand": 10})

    action = choose_poker_action(state, "p0", difficulty="medium")
    assert action["type"] in ("check", "fold")
    assert action["type"] != "all_in"


def test_medium_folds_weak_river_bet() -> None:
    engine = PokerEngine()
    players = [
        {"id": "p0", "nickname": "AI", "is_ai": True, "team": None, "role": None, "is_connected": True},
        {"id": "p1", "nickname": "Villain", "is_ai": False, "team": None, "role": None, "is_connected": True},
    ]
    base = {
        "phase": "river",
        "community_cards": [
            make_card("A", "hearts"),
            make_card("K", "diamonds"),
            make_card("Q", "spades"),
            make_card("J", "clubs"),
            make_card("2", "hearts"),
        ],
        "current_bet": 80,
        "current_actor_id": "p0",
    }
    hero = {
        "hole_cards": [make_card("7", "clubs"), make_card("3", "diamonds")],
        "status": "active",
        "bet_this_round": 0,
        "chips": 500,
        "total_bet_hand": 0,
    }
    villain = {
        "hole_cards": [make_card("8", "spades"), make_card("8", "clubs")],
        "status": "active",
        "bet_this_round": 80,
        "chips": 420,
        "total_bet_hand": 80,
    }
    state = engine.create_initial_state(players, {"host_id": "p0", "big_blind": 10})
    state.update(base)
    state["players"]["p0"].update(hero)
    state["players"]["p1"].update(villain)
    action = choose_poker_action(state, "p0", difficulty="medium")
    assert action["type"] == "fold"
