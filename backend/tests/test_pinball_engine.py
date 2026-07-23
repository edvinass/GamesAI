from app.games.pinball.engine import PinballEngine


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


def test_listed_in_registry() -> None:
    from app.games.registry import list_games

    ids = {g["id"] for g in list_games()}
    assert "pinball" in ids


def test_lobby_validation() -> None:
    engine = PinballEngine()
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


def test_initial_state() -> None:
    engine = PinballEngine()
    state = engine.create_initial_state(make_players(1), {})
    assert state["phase"] == "playing"
    assert state["score"] == 0
    assert state["balls_remaining"] == 3
    assert state["winner"] is None


def test_game_over_and_restart() -> None:
    engine = PinballEngine()
    player = make_players(1)[0]
    state = engine.create_initial_state([player], {})
    state, events = engine.apply_action(
        state, {"type": "game_over", "score": 1200}, player
    )
    assert state["phase"] == "finished"
    assert state["score"] == 1200
    assert state["high_score"] == 1200
    assert events[0]["type"] == "game_over"
    assert engine.check_winner(state) == player["id"]

    state, events = engine.apply_action(state, {"type": "restart_game"}, player)
    assert state["phase"] == "playing"
    assert state["score"] == 0
    assert state["balls_remaining"] == 3
    assert state["high_score"] == 1200
    assert events[0]["type"] == "game_restarted"
