from app.games.roborally.ai import choose_ai_actions
from app.games.roborally.engine import RoboRallyEngine
from app.games.roborally.maps import MAPS, get_map, list_maps, validate_map_definition


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
    assert state["board"]["id"] == "factory_floor"


def test_all_maps_are_valid():
    assert len(MAPS) >= 4
    for map_id, map_def in MAPS.items():
        validate_map_definition(map_def)
        assert map_def["id"] == map_id


def test_list_maps_includes_preview_geometry():
    summaries = list_maps()
    assert {m["id"] for m in summaries} == set(MAPS)
    for summary in summaries:
        assert summary["width"] > 0
        assert summary["height"] > 0
        assert summary["checkpoint_count"] >= 1
        assert isinstance(summary["walls"], list)
        assert isinstance(summary["checkpoints"], list)


def test_settings_expose_available_maps_and_select_map():
    engine = RoboRallyEngine()
    defaults = engine.default_settings()
    assert any(m["id"] == "chop_shop" for m in defaults["available_maps"])

    settings = engine.validate_settings({"map_id": "open_grid"})
    assert settings["map_id"] == "open_grid"
    assert len(settings["available_maps"]) == len(MAPS)

    settings = engine.validate_settings({"map_id": "does_not_exist"})
    assert settings["map_id"] == "factory_floor"

    state = engine.create_initial_state(_players(2), {"map_id": "twin_lanes"})
    assert state["board"]["id"] == "twin_lanes"
    assert state["board"]["name"] == get_map("twin_lanes")["name"]
    assert state["robots"]["p1"]["x"] == get_map("twin_lanes")["starts"][0]["x"]


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


def test_swap_slots_and_move_to_empty():
    engine = RoboRallyEngine()
    state = engine.create_initial_state(_players(2), {"register_size": 3})
    hand = state["hands"]["p1"]
    card_a, card_b = hand[0], hand[1]
    state, _ = engine.apply_action(
        state,
        {"type": "place_card", "slot_index": 0, "card_id": card_a["id"]},
        {"id": "p1"},
    )
    state, _ = engine.apply_action(
        state,
        {"type": "place_card", "slot_index": 1, "card_id": card_b["id"]},
        {"id": "p1"},
    )

    state, events = engine.apply_action(
        state,
        {"type": "swap_slots", "from_index": 0, "to_index": 1},
        {"id": "p1"},
    )
    assert state["programs"]["p1"][0]["id"] == card_b["id"]
    assert state["programs"]["p1"][1]["id"] == card_a["id"]
    assert any(e["type"] == "slots_swapped" for e in events)

    state, _ = engine.apply_action(
        state,
        {"type": "swap_slots", "from_index": 1, "to_index": 2},
        {"id": "p1"},
    )
    assert state["programs"]["p1"][1] is None
    assert state["programs"]["p1"][2]["id"] == card_a["id"]


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


def test_move_cards_resolve_full_card_by_priority():
    """Higher priority completes its entire move before the next robot acts."""
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
        "conveyors": [],
        "gears": [],
        "pushers": [],
        "crushers": [],
        "pits": [],
        "lasers": [],
        "repairs": [],
        "upgrades": [],
    }
    # p1 behind p2, both facing north. p1 has higher priority Move 1 and pushes p2.
    robots = {
        "p1": {
            "x": 2,
            "y": 7,
            "facing": "N",
            "checkpoints_reached": 0,
            "damage": 0,
            "lives": 3,
            "eliminated": False,
            "pending_reboot": False,
            "powered_down": False,
        },
        "p2": {
            "x": 2,
            "y": 6,
            "facing": "N",
            "checkpoints_reached": 0,
            "damage": 0,
            "lives": 3,
            "eliminated": False,
            "pending_reboot": False,
            "powered_down": False,
        },
    }
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": {k: dict(v) for k, v in robots.items()},
        "register_order": ["p1", "p2"],
        "programs": {
            "p1": [{"id": "1", "type": "move_1", "priority": 600}],
            "p2": [{"id": "2", "type": "move_1", "priority": 500}],
        },
        "player_order": ["p1", "p2"],
        "start_priorities": {"p1": 0, "p2": 1},
    }
    execute_register(state)
    # p1 (higher priority) moves first onto p2's square, pushing p2 north; then p2's Move 1.
    assert state["robots"]["p1"]["y"] == 6
    assert state["robots"]["p2"]["y"] == 4

    # Lower priority cannot be pushed through a wall ahead of them.
    board2 = {
        **board,
        "walls": list(board["walls"]) + [{"x": 2, "y": 6, "dir": "N"}],
    }
    robots2 = {
        "p1": {
            "x": 2,
            "y": 7,
            "facing": "N",
            "checkpoints_reached": 0,
            "damage": 0,
            "lives": 3,
            "eliminated": False,
            "pending_reboot": False,
            "powered_down": False,
        },
        "p2": {
            "x": 2,
            "y": 6,
            "facing": "N",
            "checkpoints_reached": 0,
            "damage": 0,
            "lives": 3,
            "eliminated": False,
            "pending_reboot": False,
            "powered_down": False,
        },
    }
    state_push = {
        "settings": {"register_size": 1},
        "board": board2,
        "robots": {k: dict(v) for k, v in robots2.items()},
        "register_order": ["p1", "p2"],
        "programs": {
            "p1": [{"id": "1", "type": "move_1", "priority": 600}],
            "p2": [{"id": "2", "type": "move_1", "priority": 500}],
        },
        "player_order": ["p1", "p2"],
        "start_priorities": {"p1": 0, "p2": 1},
    }
    execute_register(state_push)
    # p1's push is blocked by the wall in front of p2; p2's own move is also blocked.
    assert state_push["robots"]["p1"]["y"] == 7
    assert state_push["robots"]["p2"]["y"] == 6


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
        "conveyors": [],
        "gears": [],
        "pushers": [],
        "crushers": [],
        "pits": [],
        "lasers": [],
        "repairs": [],
        "upgrades": [],
    }
    robots = {
        "p1": {
            "x": 5,
            "y": 7,
            "facing": "N",
            "checkpoints_reached": 0,
            "damage": 0,
            "lives": 3,
            "eliminated": False,
            "pending_reboot": False,
            "powered_down": False,
        }
    }
    programs = {"p1": [{"id": "1", "type": "move_3", "priority": 840}]}
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": robots,
        "register_order": ["p1"],
        "programs": programs,
        "player_order": ["p1"],
        "start_priorities": {"p1": 0},
    }
    _, log = execute_register(state)
    assert state["robots"]["p1"]["y"] == 4
    step_events = log[0]["robots"]
    assert len(step_events) == 3
    assert all(e["moved"] for e in step_events)


def test_card_priority_orders_turns():
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
        "conveyors": [],
        "gears": [],
        "pushers": [],
        "crushers": [],
        "pits": [],
        "lasers": [],
        "repairs": [],
        "upgrades": [],
    }
    robots = {
        "p1": {
            "x": 2,
            "y": 7,
            "facing": "N",
            "checkpoints_reached": 0,
            "damage": 0,
            "lives": 3,
            "eliminated": False,
            "pending_reboot": False,
            "powered_down": False,
        },
        "p2": {
            "x": 4,
            "y": 7,
            "facing": "N",
            "checkpoints_reached": 0,
            "damage": 0,
            "lives": 3,
            "eliminated": False,
            "pending_reboot": False,
            "powered_down": False,
        },
    }
    programs = {
        "p1": [{"id": "1", "type": "turn_right", "priority": 80}],
        "p2": [{"id": "2", "type": "turn_left", "priority": 410}],
    }
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": robots,
        "register_order": ["p1", "p2"],
        "programs": programs,
        "player_order": ["p1", "p2"],
        "start_priorities": {"p1": 0, "p2": 1},
    }
    _, log = execute_register(state)
    assert state["robots"]["p1"]["facing"] == "E"
    assert state["robots"]["p2"]["facing"] == "W"
    # Higher priority (p2's 410) should appear first in the register log.
    order = [e["player_id"] for e in log[0]["robots"]]
    assert order == ["p2", "p1"]


def test_deck_includes_u_turns_and_priorities():
    from app.games.roborally import cards as card_lib

    deck = card_lib.new_deck()
    assert len(deck) == 84
    assert sum(1 for c in deck if c["type"] == "u_turn") == 6
    assert all("priority" in c for c in deck)
