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
    viewer = {"id": state["winners"][0]["player_id"], "nickname": "Winner", "is_ai": False}
    public = engine.get_public_state(state, viewer)
    winner = next(p for p in public["players"] if p["id"] == viewer["id"])
    assert "hand_description" not in winner


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


def test_big_blind_gets_option_when_everyone_limps(engine: PokerEngine) -> None:
    state = engine.create_initial_state(
        make_players(3), {"host_id": "p0", "small_blind": 5, "big_blind": 10}
    )
    bb_id = next(
        pid
        for pid in state["seat_order"]
        if state["players"][pid]["bet_this_round"] == state["current_bet"]
    )

    for _ in range(2):
        actor_id = state["current_actor_id"]
        assert actor_id is not None
        assert actor_id != bb_id
        actor = {"id": actor_id, "nickname": actor_id, "is_ai": False}
        state, _ = engine.apply_action(state, {"type": "call"}, actor)

    assert state["phase"] == "preflop"
    assert state["current_actor_id"] == bb_id

    bb = {"id": bb_id, "nickname": bb_id, "is_ai": False}
    state, _ = engine.apply_action(state, {"type": "check"}, bb)
    assert state["phase"] == "flop"
    assert len(state["community_cards"]) == 3


def test_postflop_requires_action_before_advancing(engine: PokerEngine) -> None:
    state = engine.create_initial_state(
        make_players(3), {"host_id": "p0", "small_blind": 5, "big_blind": 10}
    )
    while state["phase"] == "preflop" and state.get("current_actor_id"):
        actor_id = state["current_actor_id"]
        actor = {"id": actor_id, "nickname": actor_id, "is_ai": False}
        p = state["players"][actor_id]
        to_call = state["current_bet"] - p["bet_this_round"]
        if to_call == 0:
            state, _ = engine.apply_action(state, {"type": "check"}, actor)
        else:
            state, _ = engine.apply_action(state, {"type": "call"}, actor)

    assert state["phase"] == "flop"
    assert state["current_actor_id"] is not None

    first_actor = state["current_actor_id"]
    actor = {"id": first_actor, "nickname": first_actor, "is_ai": False}
    state, _ = engine.apply_action(state, {"type": "check"}, actor)
    assert state["phase"] == "flop"
    assert state["current_actor_id"] is not None
    assert state["current_actor_id"] != first_actor


def test_heads_up_big_blind_acts_after_small_blind_calls(engine: PokerEngine) -> None:
    state = engine.create_initial_state(
        make_players(2), {"host_id": "p0", "small_blind": 5, "big_blind": 10}
    )
    sb_id = state["seat_order"][state["dealer_index"]]
    bb_id = next(pid for pid in state["seat_order"] if pid != sb_id)

    assert state["current_actor_id"] == sb_id
    sb = {"id": sb_id, "nickname": sb_id, "is_ai": False}
    state, _ = engine.apply_action(state, {"type": "call"}, sb)

    assert state["phase"] == "preflop"
    assert state["current_actor_id"] == bb_id

    bb = {"id": bb_id, "nickname": bb_id, "is_ai": False}
    state, _ = engine.apply_action(state, {"type": "check"}, bb)
    assert state["phase"] == "flop"


def test_raise_reopens_action(engine: PokerEngine) -> None:
    state = engine.create_initial_state(
        make_players(3), {"host_id": "p0", "small_blind": 5, "big_blind": 10}
    )
    raiser_id = state["current_actor_id"]
    raiser = {"id": raiser_id, "nickname": raiser_id, "is_ai": False}
    state, _ = engine.apply_action(state, {"type": "raise", "amount": 30}, raiser)

    next_actor = state["current_actor_id"]
    assert next_actor is not None
    assert next_actor != raiser_id
    caller = {"id": next_actor, "nickname": next_actor, "is_ai": False}
    state, _ = engine.apply_action(state, {"type": "call"}, caller)

    assert state["phase"] == "preflop"
    assert state["current_actor_id"] is not None
    assert state["current_actor_id"] not in (raiser_id, next_actor)


def test_raises_must_use_big_blind_increments(engine: PokerEngine) -> None:
    state = engine.create_initial_state(
        make_players(3), {"host_id": "p0", "small_blind": 5, "big_blind": 10}
    )
    raiser_id = state["current_actor_id"]
    raiser = {"id": raiser_id, "nickname": raiser_id, "is_ai": False}

    with pytest.raises(ValueError, match="increments"):
        engine.apply_action(state, {"type": "raise", "amount": 25}, raiser)


def test_legal_raise_options_are_big_blind_steps(engine: PokerEngine, state: dict) -> None:
    viewer = {"id": state["current_actor_id"], "nickname": "Actor", "is_ai": False}
    public = engine.get_public_state(state, viewer)
    options = public["raise_options"]

    assert options
    assert all(amount % 10 == 0 for amount in options)
    assert options[0] == public["min_raise_to"]
    assert options[1] - options[0] == 10


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


def test_higher_trips_wins_showdown(engine: PokerEngine) -> None:
    from app.games.poker.deck import make_card

    state = {
        "seat_order": ["a", "b"],
        "players": {
            "a": {
                "hole_cards": [make_card("K", "hearts"), make_card("K", "clubs")],
                "status": "active",
                "chips": 500,
                "total_bet_hand": 100,
                "bet_this_round": 0,
            },
            "b": {
                "hole_cards": [make_card("7", "diamonds"), make_card("7", "spades")],
                "status": "active",
                "chips": 500,
                "total_bet_hand": 100,
                "bet_this_round": 0,
            },
        },
        "community_cards": [
            make_card("K", "diamonds"),
            make_card("7", "hearts"),
            make_card("2", "spades"),
            make_card("4", "clubs"),
            make_card("9", "diamonds"),
        ],
        "phase": "showdown",
    }
    resolved = engine._resolve_showdown(state)
    assert resolved["winners"] == [
        {
            "player_id": "a",
            "amount": 200,
            "hand": "Three of a Kind, Kings",
        }
    ]


def test_next_hand_requires_host(engine: PokerEngine, state: dict) -> None:
    state["phase"] = "hand_complete"
    host = {"id": "p0", "nickname": "Host", "is_ai": False}
    state, events = engine.apply_action(state, {"type": "next_hand"}, host)
    assert state["hand_number"] == 2
    assert state["phase"] == "preflop"


def test_assign_lobby_roles_sets_ai_difficulty(engine: PokerEngine) -> None:
    players = make_players(3, ai_indices={1, 2})
    settings = {
        "host_id": "p0",
        "ai_difficulties": {"p1": "easy", "p2": "hard"},
    }
    result = engine.assign_lobby_roles(players, engine.validate_settings(settings))
    assert result[1]["ai_difficulty"] == "easy"
    assert result[2]["ai_difficulty"] == "hard"


def test_create_initial_state_stores_per_player_ai_difficulty(engine: PokerEngine) -> None:
    players = make_players(2, ai_indices={1})
    players[1]["ai_difficulty"] = "hard"
    state = engine.create_initial_state(players, {"host_id": "p0"})
    assert state["players"]["p1"]["ai_difficulty"] == "hard"


def test_get_current_actor_ai_only(engine: PokerEngine, state: dict) -> None:
    state["players"][state["current_actor_id"]]["is_ai"] = True
    actor = engine.get_current_actor(state)
    assert actor is not None
    assert actor["is_ai"] is True

    state["players"][state["current_actor_id"]]["is_ai"] = False
    assert engine.get_current_actor(state) is None


def test_show_cards_on_fold_setting_default_hides_cards(engine: PokerEngine) -> None:
    """By default, winner's cards should not be revealed when everyone folds."""
    state = engine.create_initial_state(
        make_players(3), {"host_id": "p0", "small_blind": 5, "big_blind": 10}
    )
    # Fold until hand is complete
    while state["phase"] not in ("hand_complete", "game_over"):
        actor_id = state["current_actor_id"]
        actor = {"id": actor_id, "nickname": "Actor", "is_ai": False}
        state, _ = engine.apply_action(state, {"type": "fold"}, actor)

    assert state["win_by_fold"] is True
    winner_id = state["winners"][0]["player_id"]
    loser_id = next(pid for pid in state["seat_order"] if pid != winner_id)

    # Winner viewing should see their own cards
    winner = {"id": winner_id, "nickname": "Winner", "is_ai": False}
    public_winner = engine.get_public_state(state, winner)
    winner_entry = next(p for p in public_winner["players"] if p["id"] == winner_id)
    assert len(winner_entry["hole_cards"]) == 2

    # Loser should NOT see winner's cards by default
    loser = {"id": loser_id, "nickname": "Loser", "is_ai": False}
    public_loser = engine.get_public_state(state, loser)
    winner_from_loser = next(p for p in public_loser["players"] if p["id"] == winner_id)
    assert winner_from_loser["hole_cards"] == []


def test_show_cards_on_fold_setting_enabled_reveals_cards(engine: PokerEngine) -> None:
    """When show_cards_on_fold is True, winner's cards should be revealed on fold."""
    state = engine.create_initial_state(
        make_players(3), {"host_id": "p0", "small_blind": 5, "big_blind": 10, "show_cards_on_fold": True}
    )
    # Fold until hand is complete
    while state["phase"] not in ("hand_complete", "game_over"):
        actor_id = state["current_actor_id"]
        actor = {"id": actor_id, "nickname": "Actor", "is_ai": False}
        state, _ = engine.apply_action(state, {"type": "fold"}, actor)

    assert state["win_by_fold"] is True
    winner_id = state["winners"][0]["player_id"]
    loser_id = next(pid for pid in state["seat_order"] if pid != winner_id)

    # Loser SHOULD see winner's cards when setting is enabled
    loser = {"id": loser_id, "nickname": "Loser", "is_ai": False}
    public_loser = engine.get_public_state(state, loser)
    winner_from_loser = next(p for p in public_loser["players"] if p["id"] == winner_id)
    assert len(winner_from_loser["hole_cards"]) == 2


def test_showdown_always_reveals_cards(engine: PokerEngine) -> None:
    """Even with show_cards_on_fold=False, showdown should always reveal cards."""
    from app.games.poker.deck import make_card

    state = {
        "seat_order": ["a", "b"],
        "players": {
            "a": {
                "id": "a",
                "nickname": "A",
                "is_ai": False,
                "ai_difficulty": None,
                "hole_cards": [make_card("K", "hearts"), make_card("K", "clubs")],
                "status": "active",
                "chips": 500,
                "total_bet_hand": 100,
                "bet_this_round": 0,
            },
            "b": {
                "id": "b",
                "nickname": "B",
                "is_ai": False,
                "ai_difficulty": None,
                "hole_cards": [make_card("7", "diamonds"), make_card("7", "spades")],
                "status": "active",
                "chips": 500,
                "total_bet_hand": 100,
                "bet_this_round": 0,
            },
        },
        "community_cards": [
            make_card("K", "diamonds"),
            make_card("7", "hearts"),
            make_card("2", "spades"),
            make_card("4", "clubs"),
            make_card("9", "diamonds"),
        ],
        "phase": "showdown",
        "hand_number": 1,
        "dealer_index": 0,
        "current_bet": 0,
        "min_raise": 10,
        "current_actor_id": None,
        "last_action": None,
        "host_id": "a",
        "settings": {"show_cards_on_fold": False, "big_blind": 10},
        "win_by_fold": False,
    }
    resolved = engine._resolve_showdown(state)

    # Cards should be visible at showdown regardless of setting
    viewer = {"id": "b", "nickname": "B", "is_ai": False}
    public = engine.get_public_state(resolved, viewer)
    player_a = next(p for p in public["players"] if p["id"] == "a")
    assert len(player_a["hole_cards"]) == 2
