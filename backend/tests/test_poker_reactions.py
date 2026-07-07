from app.games.poker.reactions import (
    POKER_REACTIONS,
    choose_action_reaction,
    choose_game_winner_reaction,
    choose_loser_reaction,
    choose_winner_reaction,
)


def _ai_state(**overrides):
    state = {
        "settings": {"big_blind": 10},
        "players": {
            "ai1": {
                "id": "ai1",
                "is_ai": True,
                "bet_this_round": 0,
                "status": "active",
            },
            "human": {
                "id": "human",
                "is_ai": False,
                "bet_this_round": 0,
                "status": "active",
            },
        },
        "seat_order": ["human", "ai1"],
        "current_bet": 0,
        "last_action": None,
    }
    state.update(overrides)
    return state


def test_action_reaction_only_for_ai():
    state = _ai_state()
    assert choose_action_reaction(state, "human", {"type": "all_in"}) is None


def test_all_in_always_reacts():
    state = _ai_state()
    emoji = choose_action_reaction(state, "ai1", {"type": "all_in"})
    assert emoji in POKER_REACTIONS


def test_winner_reaction_big_pot():
    state = _ai_state()
    emoji = choose_winner_reaction(state, {"player_id": "ai1", "amount": 250, "hand": "Pair of Aces"})
    assert emoji in {"🔥", "💰", "👏"}


def test_winner_reaction_fold_win():
    state = _ai_state()
    emoji = choose_winner_reaction(state, {"player_id": "ai1", "amount": 30, "hand": None})
    assert emoji in {"😎", "🫡", "💰", "🃏"}


def test_loser_and_game_winner_reactions():
    assert choose_loser_reaction() in POKER_REACTIONS
    assert choose_game_winner_reaction() in POKER_REACTIONS


def test_hand_ended_on_showdown_event():
    from app.services.poker_reactions import _hand_ended

    state = {"phase": "hand_complete", "winners": [{"player_id": "ai1", "amount": 50}]}
    events = [{"type": "showdown"}]
    assert _hand_ended(state, events) is True


def test_hand_ended_on_showdown_phase_before_event_fix():
    from app.services.poker_reactions import _hand_ended

    state = {"phase": "hand_complete"}
    events = [{"type": "showdown"}]
    assert _hand_ended(state, events) is True
