import random

from app.games.poker.ai import choose_poker_action, get_ai_config
from app.games.poker.benchmark import run_ai_benchmark
from app.games.poker.deck import make_card
from app.games.poker.engine import PokerEngine
from app.games.poker.opponent_model import get_opponent_profile, get_player_stats


def test_benchmark_completes_hands() -> None:
    result = run_ai_benchmark(hands=20, num_players=3, difficulty="medium", seed=99)
    assert result["hands_completed"] >= 10
    # Chip total may drift slightly due to blind posting rounding in short stacks.
    assert result["total_chips"] >= 2970
    assert not result["illegal_actions"]


def test_weak_hand_folds_at_all_difficulties() -> None:
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

    for difficulty in ("easy", "medium", "hard"):
        state = engine.create_initial_state(players, {"host_id": "p0", "big_blind": 10})
        state.update(base)
        state["players"]["p0"].update(hero)
        state["players"]["p1"].update(villain)
        random.seed(42)
        action = choose_poker_action(state, "p0", difficulty=difficulty)
        assert action["type"] == "fold"


def test_difficulty_configs_scale_aggression() -> None:
    easy = get_ai_config("easy")
    medium = get_ai_config("medium")
    hard = get_ai_config("hard")
    assert medium["call_margin"] > easy["call_margin"]
    assert medium["mc_iterations"] > easy["mc_iterations"]
    assert easy["mistake_rate"] > medium["mistake_rate"]
    assert hard["strategy"] == "ev"
    assert hard["mc_iterations"] > medium["mc_iterations"]


def test_opponent_stats_recorded_on_action() -> None:
    engine = PokerEngine()
    players = [
        {"id": "p0", "nickname": "Human", "is_ai": False, "team": None, "role": None, "is_connected": True},
        {"id": "p1", "nickname": "AI", "is_ai": True, "team": None, "role": None, "is_connected": True},
    ]
    state = engine.create_initial_state(players, {"host_id": "p0"})
    actor_id = state["current_actor_id"]
    actor = {"id": actor_id, "nickname": actor_id, "is_ai": False}
    state, _ = engine.apply_action(state, {"type": "fold"}, actor)
    stats = get_player_stats(state, actor_id)
    assert stats["preflop_hands"] >= 1
    profile = get_opponent_profile(state, actor_id)
    assert "fold_to_bet_rate" in profile


def test_difficulty_config_aliases() -> None:
    assert get_ai_config("normal") == get_ai_config("medium")
