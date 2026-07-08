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


def test_castling_rights_and_fen():
    position = chess.parse_fen(chess.START_FEN)
    assert position["castling"] == "KQkq"
    fen = chess.board_to_fen(position)
    assert fen.startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq")
