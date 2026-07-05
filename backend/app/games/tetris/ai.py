"""Heuristic AI for Multiplier Tetris."""

from __future__ import annotations

import random
from typing import Any

from app.games.tetris.pieces import piece_cells

BOARD_WIDTH = 10

AI_DIFFICULTIES = ("easy", "normal", "hard")

AI_DIFFICULTY_CONFIG: dict[str, dict[str, int | float]] = {
    # tick = 50ms — delay between rotate/move inputs; piece locks instantly on hard drop
    "easy": {"think_ticks": 16, "action_delay_ticks": 10, "mistake_rate": 0.4},
    "normal": {"think_ticks": 10, "action_delay_ticks": 6, "mistake_rate": 0.12},
    "hard": {"think_ticks": 6, "action_delay_ticks": 4, "mistake_rate": 0.0},
}


def normalize_ai_difficulty(value: str | None) -> str:
    if value in AI_DIFFICULTY_CONFIG:
        return value
    return "normal"


def get_ai_config(difficulty: str | None) -> dict[str, int | float]:
    return AI_DIFFICULTY_CONFIG[normalize_ai_difficulty(difficulty)]


def _clone_grid(grid: list[list[str | None]]) -> list[list[str | None]]:
    return [row[:] for row in grid]


def _cells_valid(
    grid: list[list[str | None]],
    cells: list[tuple[int, int]],
    width: int,
    height: int,
) -> bool:
    for x, y in cells:
        if x < 0 or x >= width or y >= height:
            return False
        if y >= 0 and grid[y][x] is not None:
            return False
    return True


def _lock_piece(
    grid: list[list[str | None]],
    cells: list[tuple[int, int]],
    color: str,
) -> list[list[str | None]]:
    locked = _clone_grid(grid)
    for x, y in cells:
        if y >= 0:
            locked[y][x] = color
    return locked


def _clear_lines(grid: list[list[str | None]]) -> tuple[list[list[str | None]], int]:
    remaining = [row for row in grid if any(cell is not None for cell in row)]
    cleared = len(grid) - len(remaining)
    while len(remaining) < len(grid):
        remaining.insert(0, [None] * BOARD_WIDTH)
    return remaining, cleared


def _column_heights(grid: list[list[str | None]]) -> list[int]:
    heights = [0] * BOARD_WIDTH
    for x in range(BOARD_WIDTH):
        for y in range(len(grid)):
            if grid[y][x] is not None:
                heights[x] = len(grid) - y
                break
    return heights


def _aggregate_height(heights: list[int]) -> int:
    return sum(heights)


def _holes(grid: list[list[str | None]]) -> int:
    count = 0
    for x in range(BOARD_WIDTH):
        blocked = False
        for y in range(len(grid)):
            if grid[y][x] is not None:
                blocked = True
            elif blocked:
                count += 1
    return count


def _bumpiness(heights: list[int]) -> int:
    return sum(abs(heights[i] - heights[i + 1]) for i in range(len(heights) - 1))


def _score_board(grid: list[list[str | None]], lines: int) -> float:
    heights = _column_heights(grid)
    return (
        lines * 1000
        - _aggregate_height(heights) * 2
        - _holes(grid) * 50
        - _bumpiness(heights) * 5
    )


def _drop_simulation(
    grid: list[list[str | None]],
    piece_type: str,
    rotation: int,
    x: int,
    height: int,
    color: str,
) -> tuple[list[list[str | None]], int] | None:
    y = 0
    cells = piece_cells(piece_type, rotation, x, y)
    if not _cells_valid(grid, cells, BOARD_WIDTH, height):
        return None

    while True:
        next_cells = piece_cells(piece_type, rotation, x, y + 1)
        if not _cells_valid(grid, next_cells, BOARD_WIDTH, height):
            break
        y += 1
        cells = next_cells

    locked = _lock_piece(grid, cells, color)
    cleared_grid, lines = _clear_lines(locked)
    return cleared_grid, lines


def _rank_placements(
    grid: list[list[str | None]],
    piece_type: str,
    width: int,
    height: int,
    color: str,
) -> list[tuple[int, int, float]]:
    ranked: list[tuple[int, int, float]] = []
    for rotation in range(4):
        for x in range(-2, width):
            result = _drop_simulation(grid, piece_type, rotation, x, height, color)
            if result is None:
                continue
            cleared_grid, lines = result
            ranked.append((x, rotation, _score_board(cleared_grid, lines)))
    ranked.sort(key=lambda item: item[2], reverse=True)
    return ranked


def choose_ai_actions(
    board: dict[str, Any],
    width: int,
    height: int,
    difficulty: str | None = "normal",
) -> list[dict[str, str]]:
    """Return a short action sequence for the AI to reach a placement."""
    active = board.get("active")
    if not active or not board.get("alive"):
        return []

    cfg = get_ai_config(difficulty)
    piece_type = active["type"]
    current_x = active["x"]
    current_rot = active["rotation"]
    color = board["color"]
    grid = board["grid"]

    ranked = _rank_placements(grid, piece_type, width, height, color)
    if not ranked:
        if random.random() < 0.3:
            return [{"type": "rotate", "direction": "cw"}]
        return [{"type": "move", "direction": random.choice(["left", "right"])}]

    mistake_rate = float(cfg["mistake_rate"])
    if mistake_rate > 0 and random.random() < mistake_rate:
        pool_size = min(len(ranked), 5)
        target_x, target_rot, _ = random.choice(ranked[:pool_size])
    else:
        target_x, target_rot, _ = ranked[0]

    actions: list[dict[str, str]] = []
    rot_diff = (target_rot - current_rot) % 4
    for _ in range(rot_diff):
        actions.append({"type": "rotate", "direction": "cw"})

    dx = target_x - current_x
    direction = "right" if dx > 0 else "left"
    for _ in range(abs(dx)):
        actions.append({"type": "move", "direction": direction})

    actions.append({"type": "hard_drop"})
    return actions
