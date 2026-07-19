from app.games.connect4.ai import get_ai_move, get_valid_columns
from app.games.connect4.engine import Connect4Engine


def _players():
    return [
        {"id": "p1", "nickname": "Alice", "is_ai": False},
        {"id": "p2", "nickname": "Bot", "is_ai": True},
    ]


def test_initial_state_solo_human_is_red():
    engine = Connect4Engine()
    state = engine.create_initial_state(_players(), {"solo_practice": True})
    assert state["current_color"] == "red"
    assert state["red_player_id"] == "p1"
    assert state["yellow_player_id"] == "p2"
    assert state["current_actor_id"] == "p1"
    assert state["players"][1]["is_ai"] is True


def test_drop_and_turn_swap():
    engine = Connect4Engine()
    state = engine.create_initial_state(_players(), {})
    state, _ = engine.apply_action(state, {"type": "drop", "col": 3}, {"id": "p1"})
    assert state["board"][5][3] == "red"
    assert state["current_color"] == "yellow"
    assert state["current_actor_id"] == "p2"


def test_illegal_drop_rejected():
    engine = Connect4Engine()
    state = engine.create_initial_state(_players(), {})
    try:
        engine.apply_action(state, {"type": "drop", "col": 3}, {"id": "p2"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "turn" in str(exc).lower()


def test_ai_actor_only_on_ai_turn():
    engine = Connect4Engine()
    state = engine.create_initial_state(_players(), {})
    assert engine.get_current_actor(state) is None

    state, _ = engine.apply_action(state, {"type": "drop", "col": 3}, {"id": "p1"})
    actor = engine.get_current_actor(state)
    assert actor is not None
    assert actor["id"] == "p2"
    assert actor["is_ai"] is True


def test_ai_returns_legal_column():
    engine = Connect4Engine()
    state = engine.create_initial_state(_players(), {"ai_difficulty": "easy"})
    state, _ = engine.apply_action(state, {"type": "drop", "col": 3}, {"id": "p1"})
    col = get_ai_move(state, "easy")
    assert col in get_valid_columns(state["board"])


def test_no_tick_interval():
    engine = Connect4Engine()
    assert engine.tick_interval_ms() is None


def test_max_players_setting():
    engine = Connect4Engine()
    settings = engine.validate_settings({})
    assert settings["max_players"] == 2
