import pytest

from app.games.gravity_master.engine import GravityMasterEngine


def make_players(count: int = 1) -> list[dict]:
    return [
        {
            "id": f"p{i}",
            "nickname": f"Player {i}",
            "team": None,
            "role": None,
            "is_ai": False,
            "is_connected": True,
        }
        for i in range(count)
    ]


@pytest.fixture
def engine() -> GravityMasterEngine:
    return GravityMasterEngine()


@pytest.fixture
def state(engine: GravityMasterEngine) -> dict:
    return engine.create_initial_state(make_players(1), {})


def test_lobby_validation(engine: GravityMasterEngine) -> None:
    assert engine.validate_lobby(make_players(1), {}) is None
    assert engine.validate_lobby(make_players(2), {}) is not None
    ai_player = make_players(1) + [
        {
            "id": "ai1",
            "nickname": "AI",
            "team": None,
            "role": None,
            "is_ai": True,
            "is_connected": True,
        }
    ]
    assert engine.validate_lobby(ai_player, {}) is not None


def test_initial_state(engine: GravityMasterEngine) -> None:
    game = engine.create_initial_state(make_players(1), {})
    assert game["phase"] == "drawing"
    assert game["level_index"] == 0
    assert game["levels_total"] == 50
    assert game["level"]["id"] == 1
    assert game["level"]["ball"]["radius"] == 14


def test_start_simulation(engine: GravityMasterEngine, state: dict) -> None:
    player = state["players"][0]
    state, events = engine.apply_action(state, {"type": "start_simulation"}, player)
    assert state["phase"] == "simulating"
    assert events[0]["type"] == "simulation_started"


def test_level_complete_advances(engine: GravityMasterEngine, state: dict) -> None:
    player = state["players"][0]
    state, _ = engine.apply_action(state, {"type": "start_simulation"}, player)
    state, events = engine.apply_action(state, {"type": "level_complete"}, player)
    assert state["phase"] == "drawing"
    assert state["level_index"] == 1
    assert state["level"]["id"] == 2
    assert events[0]["type"] == "level_advanced"


def test_all_levels_complete(engine: GravityMasterEngine, state: dict) -> None:
    player = state["players"][0]
    for _ in range(state["levels_total"]):
        state, _ = engine.apply_action(state, {"type": "start_simulation"}, player)
        state, _ = engine.apply_action(state, {"type": "level_complete"}, player)
    assert state["phase"] == "finished"
    assert state["winner"] == player["id"]
    assert engine.check_winner(state) == player["id"]


def test_retry_level(engine: GravityMasterEngine, state: dict) -> None:
    player = state["players"][0]
    state["ink_used"] = 100
    state, _ = engine.apply_action(state, {"type": "start_simulation"}, player)
    state, events = engine.apply_action(state, {"type": "retry_level"}, player)
    assert state["phase"] == "drawing"
    assert state["ink_used"] == 0
    assert events[0]["type"] == "level_retried"


def test_restart_game(engine: GravityMasterEngine, state: dict) -> None:
    player = state["players"][0]
    state["level_index"] = 3
    state, events = engine.apply_action(state, {"type": "restart_game"}, player)
    assert state["level_index"] == 0
    assert state["phase"] == "drawing"
    assert events[0]["type"] == "game_restarted"
