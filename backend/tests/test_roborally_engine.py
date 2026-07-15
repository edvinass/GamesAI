from app.games.roborally.ai import choose_ai_actions
from app.games.roborally.engine import RoboRallyEngine


def _players(count: int = 2):
    return [
        {"id": f"p{i + 1}", "nickname": f"Player {i + 1}", "is_ai": i > 0}
        for i in range(count)
    ]


def test_initial_state():
    engine = RoboRallyEngine()
    state = engine.create_initial_state(_players(2), {})
    assert state["phase"] == "programming"
    assert state["round"] == 1
    assert len(state["player_order"]) == 2
    assert len(state["hands"]["p1"]) == 9
    assert len(state["programs"]["p1"]) == 5
    assert state["robots"]["p1"]["checkpoints_reached"] == 0


def test_place_and_lock_program():
    engine = RoboRallyEngine()
    state = engine.create_initial_state(_players(2), {"register_size": 3})
    hand = state["hands"]["p1"]
    for i in range(3):
        state, _ = engine.apply_action(
            state,
            {"type": "place_card", "slot_index": i, "card_id": hand[i]["id"]},
            {"id": "p1"},
        )
    state, events = engine.apply_action(state, {"type": "lock_program"}, {"id": "p1"})
    assert "p1" in state["locked_players"]
    assert any(e["type"] == "program_locked" for e in events)


def test_full_round_execution():
    engine = RoboRallyEngine()
    state = engine.create_initial_state(_players(2), {"register_size": 3})

    for pid in ("p1", "p2"):
        hand = state["hands"][pid]
        for i in range(3):
            state, _ = engine.apply_action(
                state,
                {"type": "place_card", "slot_index": i, "card_id": hand[i]["id"]},
                {"id": pid},
            )
        state, events = engine.apply_action(state, {"type": "lock_program"}, {"id": pid})

    assert state["phase"] == "programming"
    assert state["round"] == 2
    assert any(e["type"] == "execution_started" for e in events)
    assert len(state["execution_log"]) > 0


def test_illegal_lock_incomplete():
    engine = RoboRallyEngine()
    state = engine.create_initial_state(_players(2), {"register_size": 3})
    try:
        engine.apply_action(state, {"type": "lock_program"}, {"id": "p1"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_public_state_hides_opponent_hand():
    engine = RoboRallyEngine()
    state = engine.create_initial_state(_players(2), {})
    public = engine.get_public_state(state, {"id": "p1"})
    assert public["hands"]["p1"][0].get("type")
    assert public["hands"]["p2"][0].get("hidden")


def test_ai_chooses_full_program():
    engine = RoboRallyEngine()
    state = engine.create_initial_state(_players(2), {"register_size": 3})
    actions = choose_ai_actions(state, "p2")
    assert len(actions) == 4
    assert actions[-1]["type"] == "lock_program"


def test_resign_two_player():
    engine = RoboRallyEngine()
    state = engine.create_initial_state(_players(2), {})
    state, events = engine.apply_action(state, {"type": "resign"}, {"id": "p1"})
    assert state["winner"] == "p2"
    assert state["win_reason"] == "resign"


def test_move_cards_interleave_by_priority():
    """Move 2/3 must advance one square at a time in priority order, not per-robot."""
    from app.games.roborally.simulation import execute_register

    board = {
        "width": 11,
        "height": 9,
        "walls": (
            [[x, 0] for x in range(11)]
            + [[x, 8] for x in range(11)]
            + [[0, y] for y in range(1, 8)]
            + [[10, y] for y in range(1, 8)]
        ),
        "checkpoints": [],
        "antenna": [5, 4],
    }
    robots = {
        "p1": {"x": 2, "y": 7, "facing": "N", "checkpoints_reached": 0},
        "p2": {"x": 2, "y": 6, "facing": "N", "checkpoints_reached": 0},
    }
    programs = {
        "p1": [{"id": "1", "type": "move_1"}],
        "p2": [{"id": "2", "type": "move_1"}],
    }

    # Lower priority p1 goes first: blocked by p2, only p2 moves.
    state_blocked = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": {k: dict(v) for k, v in robots.items()},
        "register_order": ["p1", "p2"],
        "programs": programs,
    }
    execute_register(state_blocked)
    assert state_blocked["robots"]["p1"]["y"] == 7
    assert state_blocked["robots"]["p2"]["y"] == 5

    # Higher priority p2 goes first: p2 vacates, then p1 can enter former p2 square.
    state_chain = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": {k: dict(v) for k, v in robots.items()},
        "register_order": ["p2", "p1"],
        "programs": programs,
    }
    execute_register(state_chain)
    assert state_chain["robots"]["p2"]["y"] == 5
    assert state_chain["robots"]["p1"]["y"] == 6


def test_move_three_uses_three_substeps():
    from app.games.roborally.simulation import execute_register

    board = {
        "width": 11,
        "height": 9,
        "walls": (
            [[x, 0] for x in range(11)]
            + [[x, 8] for x in range(11)]
            + [[0, y] for y in range(1, 8)]
            + [[10, y] for y in range(1, 8)]
        ),
        "checkpoints": [],
        "antenna": [5, 4],
    }
    robots = {"p1": {"x": 5, "y": 7, "facing": "N", "checkpoints_reached": 0}}
    programs = {"p1": [{"id": "1", "type": "move_3"}]}
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": robots,
        "register_order": ["p1"],
        "programs": programs,
    }
    _, log = execute_register(state)
    assert state["robots"]["p1"]["y"] == 4
    step_events = log[0]["robots"]
    assert len(step_events) == 3
    assert all(e["moved"] for e in step_events)


def test_turn_executes_in_priority_order():
    from app.games.roborally.simulation import execute_register

    board = {
        "width": 11,
        "height": 9,
        "walls": (
            [[x, 0] for x in range(11)]
            + [[x, 8] for x in range(11)]
            + [[0, y] for y in range(1, 8)]
            + [[10, y] for y in range(1, 8)]
        ),
        "checkpoints": [],
        "antenna": [5, 4],
    }
    robots = {
        "p1": {"x": 2, "y": 7, "facing": "N", "checkpoints_reached": 0},
        "p2": {"x": 4, "y": 7, "facing": "N", "checkpoints_reached": 0},
    }
    programs = {
        "p1": [{"id": "1", "type": "turn_right"}],
        "p2": [{"id": "2", "type": "turn_left"}],
    }
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": robots,
        "register_order": ["p1", "p2"],
        "programs": programs,
    }
    execute_register(state)
    assert state["robots"]["p1"]["facing"] == "E"
    assert state["robots"]["p2"]["facing"] == "W"
