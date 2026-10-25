from app.games.chess.engine import ChessEngine
from app.games.chess import board as chess


def _players():
    return [
        {"id": "p1", "nickname": "Alice", "is_ai": False},
        {"id": "p2", "nickname": "Bot", "is_ai": True},
    ]


def test_initial_state_and_opening_moves():
    engine = ChessEngine()
    state = engine.create_initial_state(_players(), {"solo_practice": True})
    assert state["current_color"] == "w"
    assert state["white_player_id"] == "p1"
    assert state["black_player_id"] == "p2"
    assert any(m["from"] == "e2" and m["to"] == "e4" for m in state["legal_moves"])


def test_legal_move_and_turn_swap():
    engine = ChessEngine()
    state = engine.create_initial_state(_players(), {})
    state, events = engine.apply_action(
        state, {"type": "move", "from": "e2", "to": "e4"}, {"id": "p1"}
    )
    assert state["current_color"] == "b"
    assert state["current_actor_id"] == "p2"
    assert any(e["type"] == "move_made" for e in events)


def test_illegal_move_rejected():
    engine = ChessEngine()
    state = engine.create_initial_state(_players(), {})
    try:
        engine.apply_action(state, {"type": "move", "from": "e2", "to": "e5"}, {"id": "p1"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_scholars_mate_checkmate():
    engine = ChessEngine()
    state = engine.create_initial_state(_players(), {})
    moves = [
        ("p1", "e2", "e4"),
        ("p2", "e7", "e5"),
        ("p1", "f1", "c4"),
        ("p2", "b8", "c6"),
        ("p1", "d1", "h5"),
        ("p2", "g8", "f6"),
        ("p1", "h5", "f7"),
    ]
    for pid, frm, to in moves:
        state, _ = engine.apply_action(state, {"type": "move", "from": frm, "to": to}, {"id": pid})
    assert state["win_reason"] == "checkmate"
    assert state["winner"] == "p1"


def test_resign():
    engine = ChessEngine()
    state = engine.create_initial_state(_players(), {})
    state, events = engine.apply_action(state, {"type": "resign"}, {"id": "p1"})
    assert state["winner"] == "p2"
    assert state["win_reason"] == "resign"
    assert any(e["type"] == "player_resigned" for e in events)


def test_ai_returns_legal_move():
    from app.games.chess.ai import choose_chess_move

    engine = ChessEngine()
    state = engine.create_initial_state(_players(), {"ai_difficulty": "easy"})
    state, _ = engine.apply_action(
        state, {"type": "move", "from": "e2", "to": "e4"}, {"id": "p1"}
    )
    action = choose_chess_move(state, "p2")
    assert action["type"] == "move"
    assert any(
        m["from"] == action["from"] and m["to"] == action["to"] for m in state["legal_moves"]
    )


def test_board_view_setting():
    engine = ChessEngine()
    assert engine.validate_settings({})["board_view"] == "clay"
    assert engine.validate_settings({"board_view": "3D"})["board_view"] == "3d"
    assert engine.validate_settings({"board_view": "Clay"})["board_view"] == "clay"
    assert engine.validate_settings({"board_view": "vr"})["board_view"] == "clay"
    state = engine.create_initial_state(_players(), {"board_view": "3d"})
    assert engine.get_public_state(state, {"id": "p1"})["settings"]["board_view"] == "3d"


def test_undo_own_move_before_reply():
    engine = ChessEngine()
    state = engine.create_initial_state(_players(), {})
    state, _ = engine.apply_action(
        state, {"type": "move", "from": "e2", "to": "e4"}, {"id": "p1"}
    )
    state["draw_offer_from"] = "p2"
    assert engine.get_public_state(state, {"id": "p1"})["can_undo"] is True

    state, events = engine.apply_action(state, {"type": "undo"}, {"id": "p1"})
    assert state["move_history"] == []
    assert state["last_move"] is None
    assert state["current_actor_id"] == "p1"
    assert state["current_color"] == "w"
    assert state["draw_offer_from"] is None
    assert state["fen"].startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w")
    assert any(e["type"] == "move_undone" and e["plies"] == 1 for e in events)


def test_undo_restores_capture():
    engine = ChessEngine()
    humans = [
        {"id": "p1", "nickname": "Alice", "is_ai": False},
        {"id": "p2", "nickname": "Bob", "is_ai": False},
    ]
    state = engine.create_initial_state(humans, {})
    for pid, frm, to in (("p1", "e2", "e4"), ("p2", "d7", "d5"), ("p1", "e4", "d5")):
        state, _ = engine.apply_action(state, {"type": "move", "from": frm, "to": to}, {"id": pid})
    assert state["board"][4][3] == "P"

    state, _ = engine.apply_action(state, {"type": "undo"}, {"id": "p1"})
    assert state["board"][4][3] == "p"
    assert state["board"][3][4] == "P"
    assert state["current_actor_id"] == "p1"
    assert len(state["move_history"]) == 2


def test_undo_against_ai_removes_reply():
    engine = ChessEngine()
    state = engine.create_initial_state(_players(), {"solo_practice": True})
    state, _ = engine.apply_action(
        state, {"type": "move", "from": "e2", "to": "e4"}, {"id": "p1"}
    )
    state, _ = engine.apply_action(
        state, {"type": "move", "from": "e7", "to": "e5"}, {"id": "p2"}
    )
    assert engine.get_public_state(state, {"id": "p1"})["can_undo"] is True
    assert engine.get_public_state(state, {"id": "p2"})["can_undo"] is False

    state, events = engine.apply_action(state, {"type": "undo"}, {"id": "p1"})
    assert state["move_history"] == []
    assert state["current_actor_id"] == "p1"
    assert any(e["plies"] == 2 for e in events)


def test_undo_blocked_after_human_reply():
    engine = ChessEngine()
    humans = [
        {"id": "p1", "nickname": "Alice", "is_ai": False},
        {"id": "p2", "nickname": "Bob", "is_ai": False},
    ]
    state = engine.create_initial_state(humans, {})
    state, _ = engine.apply_action(
        state, {"type": "move", "from": "e2", "to": "e4"}, {"id": "p1"}
    )
    state, _ = engine.apply_action(
        state, {"type": "move", "from": "e7", "to": "e5"}, {"id": "p2"}
    )
    public = engine.get_public_state(state, {"id": "p1"})
    assert public["can_undo"] is False
    assert engine.get_public_state(state, {"id": "p2"})["can_undo"] is True
    try:
        engine.apply_action(state, {"type": "undo"}, {"id": "p1"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_undo_with_no_moves():
    engine = ChessEngine()
    state = engine.create_initial_state(_players(), {})
    assert engine.get_public_state(state, {"id": "p1"})["can_undo"] is False
    try:
        engine.apply_action(state, {"type": "undo"}, {"id": "p1"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_castling_rights_and_fen():
    position = chess.parse_fen(chess.START_FEN)
    assert position["castling"] == "KQkq"
    fen = chess.board_to_fen(position)
    assert fen.startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq")
