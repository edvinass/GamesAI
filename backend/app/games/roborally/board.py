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
OPPOSITE: dict[str, str] = {"N": "S", "S": "N", "E": "W", "W": "E"}

ROBOT_COLORS = (
    "#ef4444",
    "#3b82f6",
    "#22c55e",
    "#eab308",
    "#a855f7",
    "#f97316",
    "#06b6d4",
    "#ec4899",
)

MAX_DAMAGE = 9  # 10th point destroys
STARTING_LIVES = 3
REBOOT_DAMAGE = 2
BASE_HAND_SIZE = 9


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


def edge_wall_set(board: dict[str, Any]) -> set[tuple[int, int, str]]:
    """Normalized edge walls as (x, y, dir) on the cell that owns the edge."""
    walls: set[tuple[int, int, str]] = set()
    for w in board.get("walls", []):
        if isinstance(w, dict):
            x, y, d = int(w["x"]), int(w["y"]), str(w["dir"])
            walls.add((x, y, d))
            # Mirror onto neighbor for bidirectional blocking
            dx, dy = DELTA[d]
            nx, ny = x + dx, y + dy
            walls.add((nx, ny, OPPOSITE[d]))
        elif isinstance(w, (list, tuple)) and len(w) >= 2:
            # Legacy solid-cell walls: treat as four-sided block.
            x, y = int(w[0]), int(w[1])
            for d in DIRECTIONS:
                walls.add((x, y, d))
                dx, dy = DELTA[d]
                walls.add((x + dx, y + dy, OPPOSITE[d]))
    return walls


def has_edge_wall(
    board: dict[str, Any],
    x: int,
    y: int,
    direction: str,
    walls: set[tuple[int, int, str]] | None = None,
) -> bool:
    wall_set = walls if walls is not None else edge_wall_set(board)
    return (x, y, direction) in wall_set


def blocked_step(
    board: dict[str, Any],
    x: int,
    y: int,
    direction: str,
    walls: set[tuple[int, int, str]] | None = None,
) -> bool:
    """True if moving from (x,y) one step in direction is blocked by an edge wall."""
    return has_edge_wall(board, x, y, direction, walls)


def pit_set(board: dict[str, Any]) -> set[tuple[int, int]]:
    return {(int(p[0]), int(p[1])) for p in board.get("pits", [])}


def is_pit(board: dict[str, Any], x: int, y: int, pits: set[tuple[int, int]] | None = None) -> bool:
    pset = pits if pits is not None else pit_set(board)
    return (x, y) in pset


def conveyor_at(board: dict[str, Any], x: int, y: int) -> dict[str, Any] | None:
    for c in board.get("conveyors", []):
        if int(c["x"]) == x and int(c["y"]) == y:
            return c
    return None


def gear_at(board: dict[str, Any], x: int, y: int) -> dict[str, Any] | None:
    for g in board.get("gears", []):
        if int(g["x"]) == x and int(g["y"]) == y:
            return g
    return None


def pusher_at(board: dict[str, Any], x: int, y: int) -> dict[str, Any] | None:
    for p in board.get("pushers", []):
        if int(p["x"]) == x and int(p["y"]) == y:
            return p
    return None


def crusher_at(board: dict[str, Any], x: int, y: int) -> dict[str, Any] | None:
    for c in board.get("crushers", []):
        if int(c["x"]) == x and int(c["y"]) == y:
            return c
    return None


def is_repair(board: dict[str, Any], x: int, y: int) -> bool:
    return any(int(r[0]) == x and int(r[1]) == y for r in board.get("repairs", []))


def is_upgrade(board: dict[str, Any], x: int, y: int) -> bool:
    return any(int(u[0]) == x and int(u[1]) == y for u in board.get("upgrades", []))


def checkpoint_at(board: dict[str, Any], x: int, y: int) -> int | None:
    for cx, cy, num in board["checkpoints"]:
        if cx == x and cy == y:
            return int(num)
    return None


def manhattan_to_antenna(board: dict[str, Any], x: int, y: int) -> int:
    ax, ay = board["antenna"]
    return abs(x - ax) + abs(y - ay)


def facing_away_from_antenna(board: dict[str, Any], x: int, y: int) -> str:
    ax, ay = board["antenna"]
    best = "S"
    best_dist = -1
    for d in DIRECTIONS:
        dx, dy = DELTA[d]
        dist = abs((x + dx) - ax) + abs((y + dy) - ay)
        if dist > best_dist:
            best_dist = dist
            best = d
    return best


def robot_positions(
    robots: dict[str, dict[str, Any]], exclude: str | None = None
) -> set[tuple[int, int]]:
    positions: set[tuple[int, int]] = set()
    for pid, robot in robots.items():
        if exclude and pid == exclude:
            continue
        if robot.get("eliminated"):
            continue
        positions.add((robot["x"], robot["y"]))
    return positions


def hand_size_for_damage(damage: int, base: int = BASE_HAND_SIZE) -> int:
    return max(0, base - int(damage))


def locked_register_count(damage: int, register_size: int) -> int:
    """Classic: with 5 registers, damage 5 locks #5; damage 6 locks #4-5; ..."""
    return max(0, min(register_size, int(damage) - (BASE_HAND_SIZE - register_size)))


def locked_slot_indices(damage: int, register_size: int) -> set[int]:
    count = locked_register_count(damage, register_size)
    if count <= 0:
        return set()
    return set(range(register_size - count, register_size))
