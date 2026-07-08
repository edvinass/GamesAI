import random

from app.games.poker.deck import make_card
from app.games.poker.equity import estimate_equity, estimate_equity_from_state
from app.games.poker.engine import PokerEngine


def test_aa_preflop_equity_vs_one_opponent() -> None:
    hole = [make_card("A", "hearts"), make_card("A", "spades")]
    equity = estimate_equity(hole, [], 1, iterations=1500, rng=random.Random(7))
    assert equity > 0.72


def test_weak_hand_low_equity_postflop() -> None:
    hole = [make_card("7", "clubs"), make_card("2", "diamonds")]
    board = [
        make_card("A", "hearts"),
        make_card("K", "diamonds"),
        make_card("Q", "spades"),
        make_card("J", "clubs"),
        make_card("3", "hearts"),
    ]
    equity = estimate_equity(hole, board, 1, iterations=1000, rng=random.Random(11))
    assert equity < 0.12


def test_flush_draw_reasonable_equity() -> None:
    hole = [make_card("A", "hearts"), make_card("K", "hearts")]
    board = [
        make_card("2", "hearts"),
        make_card("7", "diamonds"),
        make_card("9", "clubs"),
    ]
    equity = estimate_equity(hole, board, 1, iterations=1500, rng=random.Random(19))
    assert 0.30 <= equity <= 0.65


def test_equity_from_state_uses_active_opponents() -> None:
    engine = PokerEngine()
    players = [
        {"id": "p0", "nickname": "Hero", "is_ai": True, "team": None, "role": None, "is_connected": True},
        {"id": "p1", "nickname": "V1", "is_ai": True, "team": None, "role": None, "is_connected": True},
        {"id": "p2", "nickname": "V2", "is_ai": True, "team": None, "role": None, "is_connected": True},
    ]
    state = engine.create_initial_state(players, {"host_id": "p0"})
    state["players"]["p2"]["status"] = "folded"

    equity = estimate_equity_from_state(state, "p0", iterations=400, rng=random.Random(3))
    assert 0.0 <= equity <= 1.0
