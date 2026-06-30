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


def _valid_directions(current: str) -> list[str]:
    opposite = OPPOSITE[current]
    return [d for d in DIRECTIONS if d != opposite]


def _is_safe(
    x: int,
    y: int,
    grid_width: int,
    grid_height: int,
    occupied: set[tuple[int, int]],
) -> bool:
    if x < 0 or x >= grid_width or y < 0 or y >= grid_height:
        return False
    return (x, y) not in occupied


def choose_ai_direction(
    state: dict,
    player_id: str,
    snake: dict[str, Any],
) -> str:
    """Pick a direction for an AI snake: prefer safe moves toward food, else random safe."""
    grid_width = state["grid_width"]
    grid_height = state["grid_height"]
    current = snake["direction"]
    head = snake["body"][0]
    food = state.get("food")

    occupied: set[tuple[int, int]] = set()
    for pid, s in state["snakes"].items():
        if not s.get("alive"):
            continue
        body = s["body"]
        segments = body if pid == player_id else body
        for i, seg in enumerate(segments):
            if pid != player_id or i > 0:
                occupied.add((seg[0], seg[1]))

    candidates = _valid_directions(current)
    safe_moves: list[tuple[str, tuple[int, int]]] = []
    for direction in candidates:
        dx, dy = DIRECTIONS[direction]
        nx, ny = head[0] + dx, head[1] + dy
        if _is_safe(nx, ny, grid_width, grid_height, occupied):
            safe_moves.append((direction, (nx, ny)))

    if not safe_moves:
        return current

    if food and random.random() < 0.7:
        fx, fy = food
        safe_moves.sort(
            key=lambda m: abs(m[1][0] - fx) + abs(m[1][1] - fy),
        )
        return safe_moves[0][0]

    return random.choice(safe_moves)[0]
