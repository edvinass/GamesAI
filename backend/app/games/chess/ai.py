"""Heuristic chess AI with difficulty-based search depth."""

from __future__ import annotations

import random
from typing import Any

from app.games.chess import board as chess

# Piece-square tables (white perspective; flip for black)
PST_PAWN = [
    [0, 0, 0, 0, 0, 0, 0, 0],
    [50, 50, 50, 50, 50, 50, 50, 50],
    [10, 10, 20, 30, 30, 20, 10, 10],
    [5, 5, 10, 25, 25, 10, 5, 5],
    [0, 0, 0, 20, 20, 0, 0, 0],
    [5, -5, -10, 0, 0, -10, -5, 5],
    [5, 10, 10, -20, -20, 10, 10, 5],
    [0, 0, 0, 0, 0, 0, 0, 0],
]

PST_KNIGHT = [
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20, 0, 0, 0, 0, -20, -40],
    [-30, 0, 10, 15, 15, 10, 0, -30],
    [-30, 5, 15, 20, 20, 15, 5, -30],
    [-30, 0, 15, 20, 20, 15, 0, -30],
    [-30, 5, 10, 15, 15, 10, 5, -30],
    [-40, -20, 0, 5, 5, 0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50],
]

PST_BISHOP = [
    [-20, -10, -10, -10, -10, -10, -10, -20],
    [-10, 0, 0, 0, 0, 0, 0, -10],
    [-10, 0, 5, 10, 10, 5, 0, -10],
    [-10, 5, 5, 10, 10, 5, 5, -10],
    [-10, 0, 10, 10, 10, 10, 0, -10],
    [-10, 10, 10, 10, 10, 10, 10, -10],
    [-10, 5, 0, 0, 0, 0, 5, -10],
    [-20, -10, -10, -10, -10, -10, -10, -20],
]

PST_ROOK = [
    [0, 0, 0, 0, 0, 0, 0, 0],
    [5, 10, 10, 10, 10, 10, 10, 5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [-5, 0, 0, 0, 0, 0, 0, -5],
    [0, 0, 0, 5, 5, 0, 0, 0],
]

PST_QUEEN = [
    [-20, -10, -10, -5, -5, -10, -10, -20],
    [-10, 0, 0, 0, 0, 0, 0, -10],
    [-10, 0, 5, 5, 5, 5, 0, -10],
    [-5, 0, 5, 5, 5, 5, 0, -5],
    [0, 0, 5, 5, 5, 5, 0, -5],
    [-10, 5, 5, 5, 5, 5, 0, -10],
    [-10, 0, 5, 0, 0, 0, 0, -10],
    [-20, -10, -10, -5, -5, -10, -10, -20],
]

PST_KING = [
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-30, -40, -40, -50, -50, -40, -40, -30],
    [-20, -30, -30, -40, -40, -30, -30, -20],
    [-10, -20, -20, -20, -20, -20, -20, -10],
    [20, 20, 0, 0, 0, 0, 20, 20],
    [20, 30, 10, 0, 0, 10, 30, 20],
]

PST = {
    "P": PST_PAWN,
    "N": PST_KNIGHT,
    "B": PST_BISHOP,
    "R": PST_ROOK,
    "Q": PST_QUEEN,
    "K": PST_KING,
}

DIFFICULTY_DEPTH = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
}


def _pst_value(piece: str, file_i: int, rank_i: int) -> int:
    table = PST[piece.upper()]
    if chess.is_white(piece):
        return table[7 - rank_i][file_i]
    return table[rank_i][file_i]


def evaluate(state: dict[str, Any]) -> int:
    """White-positive evaluation in centipawns."""
    score = 0
    for rank_i in range(8):
        for file_i in range(8):
            piece = state["board"][rank_i][file_i]
            if not piece:
                continue
            value = chess.PIECE_VALUES[piece.upper()] + _pst_value(piece, file_i, rank_i)
            score += value if chess.is_white(piece) else -value

    status = chess.status(state)
    if status["result"] == "checkmate":
        return 100000 if status["winner_color"] == "w" else -100000
    if status["result"] in ("stalemate", "draw"):
        return 0
    if status["in_check"]:
        score += -35 if state["turn"] == "w" else 35
    return score


def _order_moves(moves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(m: dict[str, Any]) -> int:
        score = 0
        if m.get("capture") or m.get("en_passant"):
            score += 100
        if m.get("promotion"):
            score += 80
        if m.get("castle"):
            score += 20
        return -score

    return sorted(moves, key=key)


def minimax(
    state: dict[str, Any],
    depth: int,
    alpha: int,
    beta: int,
    maximizing_white: bool,
) -> int:
    status = chess.status(state)
    if depth == 0 or status["result"]:
        return evaluate(state)

    moves = _order_moves(chess.generate_legal_moves(state))
    if maximizing_white:
        best = -10**9
        for move in moves:
            child = chess.apply_move_raw(state, move)
            best = max(best, minimax(child, depth - 1, alpha, beta, False))
            alpha = max(alpha, best)
            if beta <= alpha:
                break
        return best

    best = 10**9
    for move in moves:
        child = chess.apply_move_raw(state, move)
        best = min(best, minimax(child, depth - 1, alpha, beta, True))
        beta = min(beta, best)
        if beta <= alpha:
            break
    return best


def choose_chess_move(game_state: dict[str, Any], player_id: str) -> dict[str, Any]:
    """Pick a legal move for the AI seat. Returns an apply_action payload."""
    position = game_state["position"]
    moves = chess.generate_legal_moves(position)
    if not moves:
        raise ValueError("No legal moves for AI")

    difficulty = str(game_state.get("settings", {}).get("ai_difficulty", "medium")).lower()
    if difficulty not in DIFFICULTY_DEPTH:
        difficulty = "medium"

    # Easy: often random / lightly biased
    if difficulty == "easy" and random.random() < 0.45:
        move = random.choice(moves)
        action: dict[str, Any] = {"type": "move", "from": move["from"], "to": move["to"]}
        if move.get("promotion"):
            action["promotion"] = move["promotion"].lower()
        return action

    depth = DIFFICULTY_DEPTH[difficulty]
    ai_color = game_state["players"][player_id]["color"]
    maximizing = ai_color == "w"

    scored: list[tuple[int, dict[str, Any]]] = []
    for move in _order_moves(moves):
        child = chess.apply_move_raw(position, move)
        score = minimax(child, depth - 1, -10**9, 10**9, not maximizing)
        # Prefer from AI's perspective
        ai_score = score if maximizing else -score
        scored.append((ai_score, move))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score = scored[0][0]
    # Pick randomly among near-best to avoid always the same line
    threshold = 15 if difficulty == "hard" else 40
    candidates = [m for s, m in scored if s >= best_score - threshold]
    move = random.choice(candidates)

    action = {"type": "move", "from": move["from"], "to": move["to"]}
    if move.get("promotion"):
        action["promotion"] = move["promotion"].lower()
    return action
