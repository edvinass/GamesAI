import random
from typing import Any

DIRECTIONS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

OPPOSITE = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
}


def wrap_pos(x: int, y: int, grid_width: int, grid_height: int) -> tuple[int, int]:
    return x % grid_width, y % grid_height


def _valid_directions(facing: str) -> list[str]:
    opposite = OPPOSITE[facing]
    return [d for d in DIRECTIONS if d != opposite]


def _is_safe(
    x: int,
    y: int,
    grid_width: int,
    grid_height: int,
    occupied: set[tuple[int, int]],
) -> bool:
    wx, wy = wrap_pos(x, y, grid_width, grid_height)
    return (wx, wy) not in occupied


def choose_ai_direction(
    state: dict,
    player_id: str,
    snake: dict[str, Any],
) -> str:
    """Pick a direction for an AI snake: prefer safe moves toward food, else random safe."""
    grid_width = state["grid_width"]
    grid_height = state["grid_height"]
    facing = snake.get("next_direction", snake["direction"])
    head = snake["body"][0]
    food = state.get("food")

    occupied: set[tuple[int, int]] = set()
    for pid, s in state["snakes"].items():
        if not s.get("alive"):
            continue
        body = s["body"]
        for i, seg in enumerate(body):
            if pid != player_id or i > 0:
                occupied.add((seg[0], seg[1]))

    candidates = _valid_directions(facing)
    safe_moves: list[tuple[str, tuple[int, int]]] = []
    for direction in candidates:
        dx, dy = DIRECTIONS[direction]
        nx, ny = wrap_pos(head[0] + dx, head[1] + dy, grid_width, grid_height)
        if _is_safe(nx, ny, grid_width, grid_height, occupied):
            safe_moves.append((direction, (nx, ny)))

    if not safe_moves:
        return facing

    if food and random.random() < 0.7:
        fx, fy = food
        safe_moves.sort(
            key=lambda m: abs(m[1][0] - fx) + abs(m[1][1] - fy),
        )
        return safe_moves[0][0]

    return random.choice(safe_moves)[0]
