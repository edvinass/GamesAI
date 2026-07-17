"""Board-element and damage-loop tests for classic RoboRally."""

from app.games.roborally import board as rb
from app.games.roborally.engine import RoboRallyEngine
from app.games.roborally.maps import MAPS, registry_element_coverage, validate_map_definition
from app.games.roborally.simulation import execute_register


def _blank_board(**extra):
    board = {
        "width": 7,
        "height": 7,
        "walls": [
            {"x": x, "y": 0, "dir": "N"} for x in range(7)
        ]
        + [{"x": x, "y": 6, "dir": "S"} for x in range(7)]
        + [{"x": 0, "y": y, "dir": "W"} for y in range(7)]
        + [{"x": 6, "y": y, "dir": "E"} for y in range(7)],
        "conveyors": [],
        "gears": [],
        "pushers": [],
        "crushers": [],
        "pits": [],
        "lasers": [],
        "repairs": [],
        "upgrades": [],
        "checkpoints": [[3, 1, 1]],
        "antenna": [3, 3],
    }
    board.update(extra)
    return board


def _robot(x=3, y=5, facing="N", **extra):
    base = {
        "x": x,
        "y": y,
        "facing": facing,
        "checkpoints_reached": 0,
        "damage": 0,
        "lives": 3,
        "archive": {"x": x, "y": y},
        "options": [],
        "powered_down": False,
        "pending_power_down": False,
        "pending_reboot": False,
        "eliminated": False,
    }
    base.update(extra)
    return base


def test_all_maps_valid_and_cover_elements():
    for map_def in MAPS.values():
        validate_map_definition(map_def)
    coverage = registry_element_coverage()
    assert all(coverage.values()), coverage


def test_edge_wall_blocks_step():
    board = _blank_board(walls=[{"x": 3, "y": 4, "dir": "N"}])
    assert rb.blocked_step(board, 3, 4, "N")
    assert not rb.blocked_step(board, 3, 4, "E")


def test_express_then_normal_conveyor_and_gear():
    board = _blank_board(
        conveyors=[
            {"x": 3, "y": 4, "dir": "N", "express": True, "rotate": "none"},
            {"x": 3, "y": 3, "dir": "N", "express": False, "rotate": "none"},
            {"x": 3, "y": 2, "dir": "E", "express": False, "rotate": "none"},
        ],
        gears=[{"x": 4, "y": 2, "dir": "right"}],
    )
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": {"p1": _robot(3, 4, "N")},
        "programs": {"p1": [{"id": "c1", "type": "turn_left", "priority": 70}]},
        "register_order": ["p1"],
        "player_order": ["p1"],
        "start_priorities": {"p1": 0},
        "option_deck": [],
        "option_discard": [],
    }
    execute_register(state)
    # Turn left to W, then express N to (3,3), then all belts: from (3,3) N to (3,2),
    # enter east belt facing E, then gear at end? Actually after conveyors robot is on (3,2)
    # facing E from dest belt; gears run — not on gear. So end at (3,2) facing E.
    r = state["robots"]["p1"]
    assert (r["x"], r["y"]) == (3, 2)
    assert r["facing"] == "E"


def test_pusher_and_crusher_register_gating():
    board = _blank_board(
        pushers=[{"x": 3, "y": 4, "dir": "E", "registers": [1]}],
        crushers=[{"x": 4, "y": 4, "registers": [1]}],
    )
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": {"p1": _robot(3, 4, "N", archive={"x": 1, "y": 1})},
        "programs": {"p1": [{"id": "c1", "type": "turn_right", "priority": 100}]},
        "register_order": ["p1"],
        "player_order": ["p1"],
        "start_priorities": {"p1": 0},
        "option_deck": [],
        "option_discard": [],
    }
    execute_register(state)
    r = state["robots"]["p1"]
    # Destroyed for the rest of the turn; respawns next turn at archive.
    assert r["lives"] == 2
    assert r["pending_reboot"] is True
    from app.games.roborally.simulation import respawn_pending_robots

    respawn_pending_robots(state["robots"], board)
    r = state["robots"]["p1"]
    assert r["pending_reboot"] is False
    assert r["damage"] == rb.REBOOT_DAMAGE
    assert (r["x"], r["y"]) == (1, 1)


def test_pit_destroys_and_reboots():
    board = _blank_board(pits=[[3, 3]])
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": {"p1": _robot(3, 4, "N", archive={"x": 5, "y": 5})},
        "programs": {"p1": [{"id": "c1", "type": "move_1", "priority": 500}]},
        "register_order": ["p1"],
        "player_order": ["p1"],
        "start_priorities": {"p1": 0},
        "option_deck": [],
        "option_discard": [],
    }
    execute_register(state)
    r = state["robots"]["p1"]
    assert r["lives"] == 2
    assert r["pending_reboot"] is True
    from app.games.roborally.simulation import respawn_pending_robots

    respawn_pending_robots(state["robots"], board)
    r = state["robots"]["p1"]
    assert r["damage"] == 2
    assert (r["x"], r["y"]) == (5, 5)


def test_board_and_robot_lasers():
    board = _blank_board(
        lasers=[{"x": 1, "y": 3, "dir": "E", "strength": 1}],
    )
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": {
            "p1": _robot(2, 3, "E"),
            "p2": _robot(5, 3, "W"),
        },
        "programs": {
            "p1": [{"id": "c1", "type": "turn_left", "priority": 70}],
            "p2": [{"id": "c2", "type": "turn_left", "priority": 90}],
        },
        "register_order": ["p1", "p2"],
        "player_order": ["p1", "p2"],
        "start_priorities": {"p1": 0, "p2": 1},
        "option_deck": [],
        "option_discard": [],
    }
    execute_register(state)
    # Board laser from (1,3) east hits p1 at (2,3) for 1.
    # Robot lasers: after turns p1 faces N, p2 faces S — no hit on each other.
    assert state["robots"]["p1"]["damage"] >= 1


def test_locked_registers_and_hand_size():
    engine = RoboRallyEngine()
    players = [
        {"id": "p1", "nickname": "A", "is_ai": False},
        {"id": "p2", "nickname": "B", "is_ai": True},
    ]
    state = engine.create_initial_state(players, {"register_size": 5})
    assert len(state["hands"]["p1"]) == 9
    assert rb.locked_slot_indices(5, 5) == {4}
    assert rb.hand_size_for_damage(5) == 4

    # Program all five slots, then take damage and advance round artificially.
    hand = state["hands"]["p1"]
    for i in range(5):
        state, _ = engine.apply_action(
            state,
            {"type": "place_card", "slot_index": i, "card_id": hand[i]["id"]},
            {"id": "p1"},
        )
        hand = state["hands"]["p1"]
    locked_card = dict(state["programs"]["p1"][4])
    state["robots"]["p1"]["damage"] = 5
    state["phase"] = "programming"
    state["locked_players"] = []
    engine._start_next_round(state)
    assert state["programs"]["p1"][4]["id"] == locked_card["id"]
    assert len(state["hands"]["p1"]) == 4

    try:
        engine.apply_action(
            state,
            {"type": "clear_slot", "slot_index": 4},
            {"id": "p1"},
        )
        assert False, "expected locked clear to fail"
    except ValueError:
        pass


def test_checkpoint_still_wins_after_board_phases():
    board = _blank_board(
        checkpoints=[[3, 4, 1]],
        conveyors=[{"x": 3, "y": 5, "dir": "N", "express": False, "rotate": "none"}],
    )
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": {"p1": _robot(3, 5, "N")},
        "programs": {"p1": [{"id": "c1", "type": "turn_right", "priority": 80}]},
        "register_order": ["p1"],
        "player_order": ["p1"],
        "start_priorities": {"p1": 0},
        "option_deck": [],
        "option_discard": [],
        "phase": "executing",
    }
    execute_register(state)
    assert state["robots"]["p1"]["checkpoints_reached"] == 1
    assert state.get("winner") == "p1"


def test_checkpoint_not_claimed_mid_move():
    """Classic: only ending a register on the flag counts."""
    board = _blank_board(
        checkpoints=[[3, 3, 1]],
        pits=[],
    )
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": {"p1": _robot(3, 5, "N")},
        "programs": {"p1": [{"id": "c1", "type": "move_3", "priority": 840}]},
        "register_order": ["p1"],
        "player_order": ["p1"],
        "start_priorities": {"p1": 0},
        "option_deck": [],
        "option_discard": [],
    }
    execute_register(state)
    # Move 3: (3,5)->(3,4)->(3,3)->(3,2). Passes through flag but ends on (3,2).
    r = state["robots"]["p1"]
    assert (r["x"], r["y"]) == (3, 2)
    assert r["checkpoints_reached"] == 0


def test_powered_down_still_moved_by_conveyor():
    board = _blank_board(
        conveyors=[{"x": 3, "y": 4, "dir": "N", "express": False, "rotate": "none"}],
    )
    state = {
        "settings": {"register_size": 1},
        "board": board,
        "robots": {"p1": _robot(3, 4, "N", powered_down=True)},
        "programs": {"p1": [{"id": "c1", "type": "move_1", "priority": 500}]},
        "register_order": ["p1"],
        "player_order": ["p1"],
        "start_priorities": {"p1": 0},
        "option_deck": [],
        "option_discard": [],
    }
    execute_register(state)
    r = state["robots"]["p1"]
    # Skips programmed move, but belt still carries north.
    assert (r["x"], r["y"]) == (3, 3)


def test_repair_only_at_end_of_turn():
    board = _blank_board(repairs=[[3, 4]], checkpoints=[[0, 0, 1]])
    state = {
        "settings": {"register_size": 2},
        "board": board,
        "robots": {"p1": _robot(3, 4, "N", damage=3)},
        "programs": {
            "p1": [
                {"id": "c1", "type": "turn_left", "priority": 70},
                {"id": "c2", "type": "turn_right", "priority": 80},
            ]
        },
        "register_order": ["p1"],
        "player_order": ["p1"],
        "start_priorities": {"p1": 0},
        "option_deck": [],
        "option_discard": [],
    }
    from app.games.roborally.simulation import _execute_register_slot, compute_register_order

    cards = {"p1": state["programs"]["p1"][0]}
    order = compute_register_order(
        state["robots"], board, ["p1"], {"p1": 0}, cards
    )
    _execute_register_slot(state, 0, order, end_of_turn=False)
    assert state["robots"]["p1"]["damage"] == 3
    _execute_register_slot(state, 1, order, end_of_turn=True)
    assert state["robots"]["p1"]["damage"] == 2
