"""Connect Four AI using minimax with alpha-beta pruning."""

from __future__ import annotations

import random
from typing import Any

ROWS = 6
COLS = 7
WIN_LENGTH = 4

DEPTH_BY_DIFFICULTY = {
    "easy": 2,
    "medium": 4,
    "hard": 6,
}


def get_ai_move(state: dict, difficulty: str = "medium") -> int | None:
    """Get the best move for the AI player."""
    board = state["board"]
    ai_color = state["current_color"]

    valid_cols = get_valid_columns(board)
    if not valid_cols:
        return None

    depth = DEPTH_BY_DIFFICULTY.get(difficulty, 4)

    if difficulty == "easy":
        if random.random() < 0.3:
            return random.choice(valid_cols)

    best_col = minimax_decision(board, ai_color, depth)
    return best_col


def get_valid_columns(board: list[list]) -> list[int]:
    """Get columns that can accept a piece."""
    return [col for col in range(COLS) if board[0][col] is None]


def drop_piece(board: list[list], col: int, color: str) -> list[list]:
    """Drop a piece and return new board state."""
    new_board = [row[:] for row in board]
    for row in range(ROWS - 1, -1, -1):
        if new_board[row][col] is None:
            new_board[row][col] = color
            break
    return new_board


def check_winner(board: list[list]) -> str | None:
    """Check if there's a winner. Returns color or None."""
    for row in range(ROWS):
        for col in range(COLS):
            if board[row][col] is None:
                continue
            color = board[row][col]
            if check_win_from(board, row, col, color):
                return color
    return None


def check_win_from(board: list[list], row: int, col: int, color: str) -> bool:
    """Check if there's a winning line starting from this position."""
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]

    for dr, dc in directions:
        count = 1
        for sign in [1, -1]:
            r, c = row + dr * sign, col + dc * sign
            while 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == color:
                count += 1
                r += dr * sign
                c += dc * sign
        if count >= WIN_LENGTH:
            return True
    return False


def is_terminal(board: list[list]) -> bool:
    """Check if the game is over."""
    if check_winner(board):
        return True
    return all(board[0][col] is not None for col in range(COLS))


def evaluate_board(board: list[list], ai_color: str) -> int:
    """Evaluate the board position for the AI."""
    opponent_color = "yellow" if ai_color == "red" else "red"

    winner = check_winner(board)
    if winner == ai_color:
        return 100000
    if winner == opponent_color:
        return -100000

    score = 0
    score += evaluate_position_scores(board, ai_color) - evaluate_position_scores(board, opponent_color)
    score += evaluate_center(board, ai_color) * 3

    return score


def evaluate_center(board: list[list], color: str) -> int:
    """Evaluate center control."""
    center_col = COLS // 2
    count = 0
    for row in range(ROWS):
        if board[row][center_col] == color:
            count += 1
    return count


def evaluate_position_scores(board: list[list], color: str) -> int:
    """Evaluate potential winning positions for a color."""
    score = 0

    for row in range(ROWS):
        for col in range(COLS - 3):
            window = [board[row][col + i] for i in range(4)]
            score += evaluate_window(window, color)

    for row in range(ROWS - 3):
        for col in range(COLS):
            window = [board[row + i][col] for i in range(4)]
            score += evaluate_window(window, color)

    for row in range(ROWS - 3):
        for col in range(COLS - 3):
            window = [board[row + i][col + i] for i in range(4)]
            score += evaluate_window(window, color)

    for row in range(3, ROWS):
        for col in range(COLS - 3):
            window = [board[row - i][col + i] for i in range(4)]
            score += evaluate_window(window, color)

    return score


def evaluate_window(window: list, color: str) -> int:
    """Evaluate a window of 4 cells."""
    opponent = "yellow" if color == "red" else "red"

    count = window.count(color)
    empty = window.count(None)
    opp_count = window.count(opponent)

    if count == 4:
        return 100
    if count == 3 and empty == 1:
        return 10
    if count == 2 and empty == 2:
        return 2

    if opp_count == 3 and empty == 1:
        return -8

    return 0


def minimax_decision(board: list[list], ai_color: str, depth: int) -> int:
    """Get the best column using minimax with alpha-beta pruning."""
    valid_cols = get_valid_columns(board)
    if not valid_cols:
        return 0

    random.shuffle(valid_cols)

    center_cols = sorted(valid_cols, key=lambda c: abs(c - COLS // 2))

    best_score = float("-inf")
    best_col = center_cols[0]

    for col in center_cols:
        new_board = drop_piece(board, col, ai_color)
        score = minimax(
            new_board,
            depth - 1,
            float("-inf"),
            float("inf"),
            False,
            ai_color,
        )
        if score > best_score:
            best_score = score
            best_col = col

    return best_col


def minimax(
    board: list[list],
    depth: int,
    alpha: float,
    beta: float,
    maximizing: bool,
    ai_color: str,
) -> int:
    """Minimax algorithm with alpha-beta pruning."""
    opponent_color = "yellow" if ai_color == "red" else "red"

    if depth == 0 or is_terminal(board):
        return evaluate_board(board, ai_color)

    valid_cols = get_valid_columns(board)
    if not valid_cols:
        return evaluate_board(board, ai_color)

    center_cols = sorted(valid_cols, key=lambda c: abs(c - COLS // 2))

    if maximizing:
        max_eval = float("-inf")
        for col in center_cols:
            new_board = drop_piece(board, col, ai_color)
            eval_score = minimax(new_board, depth - 1, alpha, beta, False, ai_color)
            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = float("inf")
        for col in center_cols:
            new_board = drop_piece(board, col, opponent_color)
            eval_score = minimax(new_board, depth - 1, alpha, beta, True, ai_color)
            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval
