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

# Lower is more desirable when chasing.
_FOOD_CHASE_RANK = {
    "golden": 0,
    "ammo": 1,
    "ghost": 2,
    "apple": 3,
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


def _manhattan(ax: int, ay: int, bx: int, by: int, grid_width: int, grid_height: int) -> int:
    dx = abs(ax - bx)
    dy = abs(ay - by)
    return min(dx, grid_width - dx) + min(dy, grid_height - dy)


def _pick_food_target(foods: list[dict], head: list[int], grid_width: int, grid_height: int) -> dict | None:
    chase = [f for f in foods if f.get("type") in _FOOD_CHASE_RANK]
    if chase:
        chase.sort(
            key=lambda f: (
                _FOOD_CHASE_RANK.get(f.get("type"), 9),
                _manhattan(head[0], head[1], f["x"], f["y"], grid_width, grid_height),
            )
        )
        return chase[0]

    # Only poison left — steer away from the nearest one.
    poisons = [f for f in foods if f.get("type") == "poison"]
    if not poisons:
        return None
    nearest = min(
        poisons,
        key=lambda f: _manhattan(head[0], head[1], f["x"], f["y"], grid_width, grid_height),
    )
    return {"x": nearest["x"], "y": nearest["y"], "type": "poison", "flee": True}


def choose_ai_direction(
    state: dict,
    player_id: str,
    snake: dict[str, Any],
) -> str:
    """Pick a direction for an AI snake: prefer safe moves toward good food, else random safe."""
    grid_width = state["grid_width"]
    grid_height = state["grid_height"]
    facing = snake.get("next_direction", snake["direction"])
    head = snake["body"][0]
    foods = list(state.get("foods") or [])
    # Legacy single-food states
    if not foods and state.get("food"):
        legacy = state["food"]
        if isinstance(legacy, dict):
            foods = [legacy]
        elif isinstance(legacy, (list, tuple)) and len(legacy) >= 2:
            foods = [{"x": legacy[0], "y": legacy[1], "type": "apple"}]

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

    target = _pick_food_target(foods, head, grid_width, grid_height) if foods else None
    if target and random.random() < 0.7:
        fx, fy = target["x"], target["y"]
        flee = bool(target.get("flee"))

        def score(move: tuple[str, tuple[int, int]]) -> int:
            dist = _manhattan(move[1][0], move[1][1], fx, fy, grid_width, grid_height)
            return -dist if flee else dist

        safe_moves.sort(key=score)
        return safe_moves[0][0]

    return random.choice(safe_moves)[0]


def _enemy_in_line_of_fire(
    state: dict,
    player_id: str,
    snake: dict[str, Any],
    max_range: int = 16,
) -> bool:
    grid_width = state["grid_width"]
    grid_height = state["grid_height"]
    direction = snake.get("next_direction", snake["direction"])
    if direction not in DIRECTIONS:
        return False
    dx, dy = DIRECTIONS[direction]
    x, y = snake["body"][0]
    enemy_cells: set[tuple[int, int]] = set()
    for pid, other in state["snakes"].items():
        if pid == player_id or not other.get("alive"):
            continue
        for seg in other["body"]:
            enemy_cells.add((seg[0], seg[1]))

    for _ in range(max_range):
        x, y = wrap_pos(x + dx, y + dy, grid_width, grid_height)
        if (x, y) in enemy_cells:
            return True
        # Stop if we hit our own body first (would waste a shot visually, still ok).
        for seg in snake["body"]:
            if seg[0] == x and seg[1] == y:
                return False
    return False


def choose_ai_shoot(
    state: dict,
    player_id: str,
    snake: dict[str, Any],
) -> bool:
    if int(snake.get("ammo", 0)) <= 0:
        return False
    if not _enemy_in_line_of_fire(state, player_id, snake):
        return False
    return random.random() < 0.85
