"""Tests for Klondike solitaire engine."""

from app.games.solitaire.cards import can_stack_on_tableau, is_valid_tableau_run
from app.games.solitaire.engine import SolitaireEngine

PLAYERS = [{"id": "p1", "name": "Player"}]


def _engine_state(**overrides):
    eng = SolitaireEngine()
    state = eng.create_initial_state(PLAYERS, {"draw_count": 1})
    state["stock"] = []
    state["waste"] = []
    state["foundations"] = {s: [] for s in ("hearts", "diamonds", "clubs", "spades")}
    state["tableau"] = [[] for _ in range(7)]
    state.update(overrides)
    return eng, state


def test_can_stack_on_tableau_alternating_descending():
    assert can_stack_on_tableau(
        {"rank": "7", "suit": "hearts", "face_up": True},
        {"rank": "8", "suit": "spades", "face_up": True},
    )
    assert not can_stack_on_tableau(
        {"rank": "7", "suit": "clubs", "face_up": True},
        {"rank": "8", "suit": "spades", "face_up": True},
    )


def test_is_valid_tableau_run():
    run = [
        {"rank": "9", "suit": "spades", "face_up": True},
        {"rank": "8", "suit": "hearts", "face_up": True},
        {"rank": "7", "suit": "clubs", "face_up": True},
    ]
    assert is_valid_tableau_run(run)
    run[1] = {"rank": "3", "suit": "hearts", "face_up": True}
    assert not is_valid_tableau_run(run)


def test_move_tableau_pile_onto_higher_card():
    eng, state = _engine_state(
        tableau=[
            [{"rank": "9", "suit": "hearts", "face_up": True}],
            [
                {"rank": "2", "suit": "spades", "face_up": False},
                {"rank": "8", "suit": "clubs", "face_up": True},
                {"rank": "7", "suit": "diamonds", "face_up": True},
                {"rank": "6", "suit": "spades", "face_up": True},
            ],
            [],
            [],
            [],
            [],
            [],
        ]
    )

    state, events = eng.apply_action(
        state,
        {
            "type": "move_to_tableau",
            "source": "tableau",
            "source_index": 1,
            "card_index": 1,
            "target_col": 0,
        },
        PLAYERS[0],
    )

    assert state["moves"] == 1
    assert [c["rank"] for c in state["tableau"][0]] == ["9", "8", "7", "6"]
    assert state["tableau"][1] == [{"rank": "2", "suit": "spades", "face_up": True}]
    assert any(e["type"] == "card_to_tableau" for e in events)


def test_reject_invalid_tableau_run_move():
    eng, state = _engine_state(
        tableau=[
            [{"rank": "9", "suit": "hearts", "face_up": True}],
            [
                {"rank": "8", "suit": "clubs", "face_up": True},
                {"rank": "3", "suit": "diamonds", "face_up": True},
            ],
            [],
            [],
            [],
            [],
            [],
        ]
    )

    state, events = eng.apply_action(
        state,
        {
            "type": "move_to_tableau",
            "source": "tableau",
            "source_index": 1,
            "card_index": 0,
            "target_col": 0,
        },
        PLAYERS[0],
    )

    assert state["moves"] == 0
    assert events == []
    assert len(state["tableau"][1]) == 2


def test_king_only_on_empty_column():
    eng, state = _engine_state(
        tableau=[
            [],
            [{"rank": "Q", "suit": "hearts", "face_up": True}],
            [{"rank": "K", "suit": "spades", "face_up": True}],
            [],
            [],
            [],
            [],
        ]
    )

    state, _ = eng.apply_action(
        state,
        {
            "type": "move_to_tableau",
            "source": "tableau",
            "source_index": 1,
            "card_index": 0,
            "target_col": 0,
        },
        PLAYERS[0],
    )
    assert state["moves"] == 0

    state, _ = eng.apply_action(
        state,
        {
            "type": "move_to_tableau",
            "source": "tableau",
            "source_index": 2,
            "card_index": 0,
            "target_col": 0,
        },
        PLAYERS[0],
    )
    assert state["moves"] == 1
    assert state["tableau"][0][0]["rank"] == "K"


def test_waste_fan_in_public_state_draw_three():
    eng, state = _engine_state(settings={"draw_count": 3, "min_players": 1, "max_players": 1, "single_player": True})
    state["waste"] = [
        {"rank": "A", "suit": "clubs", "face_up": True},
        {"rank": "5", "suit": "hearts", "face_up": True},
        {"rank": "9", "suit": "spades", "face_up": True},
        {"rank": "J", "suit": "diamonds", "face_up": True},
    ]

    public = eng.get_public_state(state, PLAYERS[0])
    assert public["waste_top"]["rank"] == "J"
    assert [c["rank"] for c in public["waste_fan"]] == ["5", "9", "J"]


def test_new_game_works_after_win():
    eng, state = _engine_state()
    ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
    for suit in ("hearts", "diamonds", "clubs", "spades"):
        state["foundations"][suit] = [
            {"rank": r, "suit": suit, "face_up": True} for r in ranks
        ]
    state["phase"] = "finished"
    state["winner"] = PLAYERS[0]["id"]
    state["moves"] = 99

    state, events = eng.apply_action(state, {"type": "new_game"}, PLAYERS[0])

    assert state["phase"] == "playing"
    assert state["winner"] is None
    assert state["moves"] == 0
    assert sum(len(col) for col in state["tableau"]) == 28
    assert any(e["type"] == "game_restarted" for e in events)


def test_can_auto_complete_requires_movable_card():
    eng, state = _engine_state(
        tableau=[
            [
                {"rank": "K", "suit": "hearts", "face_up": True},
                {"rank": "Q", "suit": "spades", "face_up": True},
            ],
            [],
            [],
            [],
            [],
            [],
            [],
        ]
    )
    public = eng.get_public_state(state, PLAYERS[0])
    assert public["can_auto_complete"] is False

    state["tableau"] = [[{"rank": "A", "suit": "hearts", "face_up": True}], [], [], [], [], [], []]
    public = eng.get_public_state(state, PLAYERS[0])
    assert public["can_auto_complete"] is True


def test_waste_to_tableau_and_foundation():
    eng, state = _engine_state(
        waste=[{"rank": "5", "suit": "diamonds", "face_up": True}],
        tableau=[[{"rank": "2", "suit": "clubs", "face_up": True}], [], [], [], [], [], []],
    )

    state, _ = eng.apply_action(
        state,
        {
            "type": "move_to_tableau",
            "source": "waste",
            "source_index": None,
            "card_index": 0,
            "target_col": 0,
        },
        PLAYERS[0],
    )
    assert state["moves"] == 0
    assert len(state["waste"]) == 1

    state["waste"] = [{"rank": "A", "suit": "diamonds", "face_up": True}]
    state, events = eng.apply_action(
        state,
        {"type": "move_to_foundation", "source": "waste"},
        PLAYERS[0],
    )
    assert state["moves"] == 1
    assert len(state["foundations"]["diamonds"]) == 1
    assert any(e["type"] == "card_to_foundation" for e in events)


def test_noop_draw_and_reset_do_not_emit():
    eng, state = _engine_state(stock=[], waste=[])
    state, events = eng.apply_action(state, {"type": "draw"}, PLAYERS[0])
    assert events == []

    state, events = eng.apply_action(state, {"type": "reset_stock"}, PLAYERS[0])
    assert events == []


def test_hint_suggests_foundation_ace():
    eng, state = _engine_state(
        waste=[{"rank": "A", "suit": "hearts", "face_up": True}],
    )

    state, events = eng.apply_action(state, {"type": "hint"}, PLAYERS[0])

    assert any(e["type"] == "hint_shown" for e in events)
    assert state["hint"]["type"] == "move_to_foundation"
    assert state["hint"]["source"] == "waste"
    assert "Ace" in state["hint"]["reason"] or "foundation" in state["hint"]["reason"].lower()
    assert state["moves"] == 0
    assert len(state["waste"]) == 1


def test_hint_cleared_on_manual_move():
    eng, state = _engine_state(
        waste=[{"rank": "A", "suit": "clubs", "face_up": True}],
    )
    state, _ = eng.apply_action(state, {"type": "hint"}, PLAYERS[0])
    assert state["hint"] is not None

    state, _ = eng.apply_action(
        state,
        {"type": "move_to_foundation", "source": "waste"},
        PLAYERS[0],
    )
    assert state["hint"] is None
    assert state["moves"] == 1


def test_autoplay_tick_applies_move():
    eng, state = _engine_state(
        waste=[{"rank": "A", "suit": "spades", "face_up": True}],
        autoplay=True,
    )

    state, events = eng.tick(state)

    assert state["moves"] == 1
    assert len(state["foundations"]["spades"]) == 1
    assert any(e["type"] == "card_to_foundation" for e in events)
    assert state["autoplay"] is True


def test_autoplay_tick_noop_when_disabled():
    eng, state = _engine_state(
        waste=[{"rank": "A", "suit": "spades", "face_up": True}],
        autoplay=False,
    )
    state, events = eng.tick(state)
    assert events == []
    assert state["moves"] == 0
    assert len(state["waste"]) == 1


def test_autoplay_stuck_disables_watch():
    eng, state = _engine_state(
        stock=[],
        waste=[],
        tableau=[
            [{"rank": "5", "suit": "hearts", "face_up": True}],
            [{"rank": "9", "suit": "clubs", "face_up": True}],
            [],
            [],
            [],
            [],
            [],
        ],
        autoplay=True,
    )

    state, events = eng.tick(state)

    assert state["autoplay"] is False
    assert any(e["type"] == "autoplay_stuck" for e in events)
    assert state["hint"]["type"] == "none"


def test_set_autoplay_and_public_fields():
    eng, state = _engine_state()
    state, events = eng.apply_action(
        state, {"type": "set_autoplay", "enabled": True}, PLAYERS[0]
    )
    assert state["autoplay"] is True
    assert state["hint"] is None
    assert any(e["type"] == "autoplay_changed" for e in events)

    public = eng.get_public_state(state, PLAYERS[0])
    assert public["autoplay"] is True
    assert public["hint"] is None


def test_choose_action_exposes_face_down():
    from app.games.solitaire.ai import choose_action

    eng, state = _engine_state(
        tableau=[
            [{"rank": "8", "suit": "spades", "face_up": True}],
            [
                {"rank": "3", "suit": "hearts", "face_up": False},
                {"rank": "7", "suit": "diamonds", "face_up": True},
            ],
            [],
            [],
            [],
            [],
            [],
        ]
    )

    action, reason = choose_action(state)
    assert action is not None
    assert action["type"] == "move_to_tableau"
    assert action["source_index"] == 1
    assert action["target_col"] == 0
    assert "Expose" in reason
