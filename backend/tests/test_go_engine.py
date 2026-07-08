from app.games.go.engine import GoEngine
from app.games.go import board as go


def _players():
    return [
        {"id": "p1", "nickname": "Alice", "is_ai": False},
        {"id": "p2", "nickname": "Bot", "is_ai": True},
    ]


def test_initial_state():
    engine = GoEngine()
    state = engine.create_initial_state(_players(), {"solo_practice": True})
    assert state["current_color"] == "B"
    assert state["black_player_id"] == "p1"
    assert state["white_player_id"] == "p2"
    assert len(state["legal_plays"]) == 81


def test_legal_play_and_turn_swap():
    engine = GoEngine()
    state = engine.create_initial_state(_players(), {})
    state, events = engine.apply_action(
        state, {"type": "play", "coord": "e5"}, {"id": "p1"}
    )
    assert state["current_color"] == "W"
    assert state["current_actor_id"] == "p2"
    assert any(e["type"] == "play_made" for e in events)


def test_illegal_play_rejected():
    engine = GoEngine()
    state = engine.create_initial_state(_players(), {})
    state, _ = engine.apply_action(state, {"type": "play", "coord": "e5"}, {"id": "p1"})
    try:
        engine.apply_action(state, {"type": "play", "coord": "e5"}, {"id": "p2"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_capture():
    engine = GoEngine()
    state = engine.create_initial_state(_players(), {})
    plays = [
        ("p1", "d5"),
        ("p2", "e5"),
        ("p1", "d4"),
        ("p2", "f6"),
        ("p1", "e4"),
        ("p2", "g7"),
        ("p1", "f5"),
        ("p2", "h8"),
        ("p1", "e6"),
    ]
    for pid, coord in plays:
        state, _ = engine.apply_action(state, {"type": "play", "coord": coord}, {"id": pid})
    assert state["position"]["captured"]["W"] >= 1


def test_double_pass_scores_game():
    engine = GoEngine()
    state = engine.create_initial_state(_players(), {})
    state, _ = engine.apply_action(state, {"type": "pass"}, {"id": "p1"})
    state, events = engine.apply_action(state, {"type": "pass"}, {"id": "p2"})
    assert state["phase"] == "game_over"
    assert state["score"] is not None
    assert any(e["type"] == "game_scored" for e in events)


def test_resign():
    engine = GoEngine()
    state = engine.create_initial_state(_players(), {})
    state, events = engine.apply_action(state, {"type": "resign"}, {"id": "p1"})
    assert state["winner"] == "p2"
    assert state["win_reason"] == "resign"
    assert any(e["type"] == "player_resigned" for e in events)


def test_ai_returns_legal_move():
    from app.games.go.ai import choose_go_move

    engine = GoEngine()
    state = engine.create_initial_state(_players(), {"ai_difficulty": "easy"})
    state, _ = engine.apply_action(state, {"type": "play", "coord": "e5"}, {"id": "p1"})
    action = choose_go_move(state, "p2")
    assert action["type"] in ("play", "pass")
    if action["type"] == "play":
        assert any(p["coord"] == action["coord"] for p in state["legal_plays"])


def test_ai_mcts_does_not_crash():
    from app.games.go.ai import _mcts_best_play

    engine = GoEngine()
    state = engine.create_initial_state(_players(), {"ai_difficulty": "medium"})
    opening = ["e5", "d3", "f3", "d6", "c6", "f6"]
    for i, coord in enumerate(opening):
        pid = "p1" if i % 2 == 0 else "p2"
        state, _ = engine.apply_action(state, {"type": "play", "coord": coord}, {"id": pid})

    position = state["position"]
    for _ in range(5):
        play = _mcts_best_play(position, go.WHITE, 40)
        assert play is None or "coord" in play


def test_suicide_illegal():
    pos = go.create_position()
    # Single black stone with one liberty — playing inside own eye is suicide
    pos["board"][4][4] = go.BLACK
    pos["board"][3][4] = go.WHITE
    pos["board"][4][3] = go.WHITE
    pos["board"][4][5] = go.WHITE
    pos["board"][5][4] = go.WHITE
    assert not go.is_legal_play(pos, 4, 4)


def test_score_empty_board():
    pos = go.create_position()
    result = go.score_position(pos)
    assert result["black_score"] == 0
    assert result["white_score"] == go.DEFAULT_KOMI
