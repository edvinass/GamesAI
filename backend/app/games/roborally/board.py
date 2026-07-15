"""Grid board helpers for RoboRally."""

from __future__ import annotations

from typing import Any

DIRECTIONS = ("N", "E", "S", "W")
DELTA: dict[str, tuple[int, int]] = {
    "N": (0, -1),
    "E": (1, 0),
    "S": (0, 1),
    "W": (-1, 0),
}

ROBOT_COLORS = ("#ef4444", "#3b82f6", "#22c55e", "#eab308", "#a855f7", "#f97316", "#06b6d4", "#ec4899")


def turn_left(facing: str) -> str:
    idx = DIRECTIONS.index(facing)
    return DIRECTIONS[(idx - 1) % 4]


def turn_right(facing: str) -> str:
    idx = DIRECTIONS.index(facing)
    return DIRECTIONS[(idx + 1) % 4]


def turn_around(facing: str) -> str:
    idx = DIRECTIONS.index(facing)
    return DIRECTIONS[(idx + 2) % 4]


def in_bounds(x: int, y: int, width: int, height: int) -> bool:
    return 0 <= x < width and 0 <= y < height


def is_wall(board: dict[str, Any], x: int, y: int) -> bool:
    if not in_bounds(x, y, board["width"], board["height"]):
        return True
    return (x, y) in {tuple(w) for w in board.get("walls", [])}


def checkpoint_at(board: dict[str, Any], x: int, y: int) -> int | None:
    for cx, cy, num in board["checkpoints"]:
        if cx == x and cy == y:
            return num
    return None


def manhattan_to_antenna(board: dict[str, Any], x: int, y: int) -> int:
    ax, ay = board["antenna"]
    return abs(x - ax) + abs(y - ay)


def robot_positions(robots: dict[str, dict[str, Any]], exclude: str | None = None) -> set[tuple[int, int]]:
    positions: set[tuple[int, int]] = set()
    for pid, robot in robots.items():
        if exclude and pid == exclude:
            continue
        positions.add((robot["x"], robot["y"]))
    return positions
