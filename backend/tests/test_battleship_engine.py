from app.games.battleship.engine import BattleshipEngine
from app.games.battleship.ai import choose_battleship_action, generate_random_fleet


def _players():
    return [
        {"id": "p1", "nickname": "Alice", "is_ai": False},
        {"id": "p2", "nickname": "Bot", "is_ai": True},
    ]


def _ready_both(engine: BattleshipEngine, state: dict) -> dict:
    for pid in ("p1", "p2"):
        state, _ = engine.apply_action(state, {"type": "auto_place"}, {"id": pid})
        state, _ = engine.apply_action(state, {"type": "ready"}, {"id": pid})
    return state


def test_initial_state_placing():
    engine = BattleshipEngine()
    state = engine.create_initial_state(_players(), {"solo_practice": True})
    assert state["phase"] == "placing"
    assert state["player_order"][0] == "p1"
    assert state["size"] == 10
    assert len(state["fleets"]["p1"]["ships"]) == 0


def test_auto_place_and_ready_starts_battle():
    engine = BattleshipEngine()
    state = engine.create_initial_state(_players(), {})
    state = _ready_both(engine, state)
    assert state["phase"] == "playing"
    assert state["current_actor_id"] == "p1"
    assert len(state["fleets"]["p1"]["ships"]) == 5
    assert len(state["fleets"]["p2"]["ships"]) == 5


def test_manual_place_ship():
    engine = BattleshipEngine()
    state = engine.create_initial_state(_players(), {})
    state, _ = engine.apply_action(
        state,
        {"type": "place_ship", "ship_id": "destroyer", "row": 0, "col": 0, "horizontal": True},
        {"id": "p1"},
    )
    assert len(state["fleets"]["p1"]["ships"]) == 1
    assert state["fleets"]["p1"]["cells"]["0,0"] == "destroyer"
    assert state["fleets"]["p1"]["cells"]["0,1"] == "destroyer"


def test_overlap_rejected():
    engine = BattleshipEngine()
    state = engine.create_initial_state(_players(), {})
    state, _ = engine.apply_action(
        state,
        {"type": "place_ship", "ship_id": "destroyer", "row": 0, "col": 0, "horizontal": True},
        {"id": "p1"},
    )
    try:
        engine.apply_action(
            state,
            {"type": "place_ship", "ship_id": "submarine", "row": 0, "col": 0, "horizontal": True},
            {"id": "p1"},
        )
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_fire_hit_miss_and_win():
    engine = BattleshipEngine()
    state = engine.create_initial_state(_players(), {})
    # Place a tiny known fleet manually for p2: only destroyer at 0,0-0,1
    # Use auto_place then overwrite for deterministic test.
    state, _ = engine.apply_action(state, {"type": "auto_place"}, {"id": "p1"})
    state, _ = engine.apply_action(state, {"type": "ready"}, {"id": "p1"})

    state["fleets"]["p2"]["ships"] = [
        {
            "id": "destroyer",
            "name": "Destroyer",
            "length": 2,
            "cells": [[0, 0], [0, 1]],
            "hits": 0,
            "sunk": False,
        }
    ]
    state["fleets"]["p2"]["cells"] = {"0,0": "destroyer", "0,1": "destroyer"}
    # Bypass full fleet requirement for ready by setting ready flags + phase.
    state["players"]["p2"]["ready"] = True
    state["fleets"]["p2"]["ready"] = True
    state["phase"] = "playing"
    state["current_actor_id"] = "p1"

    state, events = engine.apply_action(
        state, {"type": "fire", "row": 5, "col": 5}, {"id": "p1"}
    )
    assert state["last_shot"]["result"] == "miss"
    assert state["current_actor_id"] == "p2"

    state["current_actor_id"] = "p1"
    state, _ = engine.apply_action(state, {"type": "fire", "row": 0, "col": 0}, {"id": "p1"})
    assert state["last_shot"]["result"] == "hit"

    state["current_actor_id"] = "p1"
    state, events = engine.apply_action(
        state, {"type": "fire", "row": 0, "col": 1}, {"id": "p1"}
    )
    assert state["last_shot"]["result"] == "sunk"
    assert state["phase"] == "game_over"
    assert state["winner"] == "p1"
    assert state["win_reason"] == "fleet_sunk"
    assert any(e["type"] == "game_over" for e in events)


def test_resign():
    engine = BattleshipEngine()
    state = engine.create_initial_state(_players(), {})
    state, events = engine.apply_action(state, {"type": "resign"}, {"id": "p1"})
    assert state["winner"] == "p2"
    assert state["win_reason"] == "resign"
    assert any(e["type"] == "player_resigned" for e in events)


def test_public_state_hides_opponent_ships():
    engine = BattleshipEngine()
    state = engine.create_initial_state(_players(), {})
    state = _ready_both(engine, state)
    public = engine.get_public_state(state, {"id": "p1"})
    assert public["viewer_id"] == "p1"
    assert public["opponent_id"] == "p2"
    own_ships = public["fleets"]["p1"]["ships"]
    assert all(s.get("cells") for s in own_ships if s.get("placed"))
    opp_ships = [s for s in public["fleets"]["p2"]["ships"] if s.get("placed")]
    assert all(s.get("cells") is None for s in opp_ships)
    assert public["boards"]["p1"]["grid"][0][0]["state"] in ("empty", "ship")


def test_ai_auto_places_and_fires():
    engine = BattleshipEngine()
    state = engine.create_initial_state(_players(), {"ai_difficulty": "easy"})
    action = choose_battleship_action(state, "p2")
    assert action["type"] == "auto_place"
    state, _ = engine.apply_action(state, action, {"id": "p2"})
    action = choose_battleship_action(state, "p2")
    assert action["type"] == "ready"
    state, _ = engine.apply_action(state, action, {"id": "p2"})
    state, _ = engine.apply_action(state, {"type": "auto_place"}, {"id": "p1"})
    state, _ = engine.apply_action(state, {"type": "ready"}, {"id": "p1"})
    assert state["phase"] == "playing"
    # p1 shoots first; after miss/hit, AI fires.
    state, _ = engine.apply_action(state, {"type": "fire", "row": 0, "col": 0}, {"id": "p1"})
    action = choose_battleship_action(state, "p2")
    assert action["type"] == "fire"
    assert "row" in action and "col" in action


def test_generate_random_fleet_valid():
    ships = generate_random_fleet()
    assert len(ships) == 5
    cells = []
    for ship in ships:
        assert len(ship["cells"]) == ship["length"]
        cells.extend(tuple(c) for c in ship["cells"])
    assert len(cells) == len(set(cells))
