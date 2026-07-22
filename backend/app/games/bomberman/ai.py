"""Simple Bomberman AI: flee danger, break soft blocks, chase enemies."""

from __future__ import annotations

import random
from collections import deque
from typing import Any

DIRECTIONS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

TILE_EMPTY = 0
TILE_HARD = 1
TILE_SOFT = 2


def _bomb_cells(state: dict) -> dict[tuple[int, int], dict]:
    return {(b["x"], b["y"]): b for b in state.get("bombs") or []}


def _powerup_cells(state: dict) -> set[tuple[int, int]]:
    return {(p["x"], p["y"]) for p in state.get("powerups") or []}


def _blast_preview(state: dict, horizon: int = 20) -> set[tuple[int, int]]:
    """Cells that will explode within `horizon` ticks (including active blasts)."""
    danger: set[tuple[int, int]] = set()
    for cell in state.get("explosions") or []:
        if int(cell.get("ttl", 0)) > 0:
            danger.add((cell["x"], cell["y"]))

    grid = state["grid"]
    width = state["grid_width"]
    height = state["grid_height"]
    bombs = list(state.get("bombs") or [])
    pending = [
        (b["x"], b["y"], int(b.get("range", 1)), int(b.get("fuse", 0)))
        for b in bombs
        if int(b.get("fuse", 0)) <= horizon
    ]
    # Chain reaction approximation: any bomb hit by an earlier blast also detonates.
    detonated: set[tuple[int, int]] = set()
    queue = deque(sorted(pending, key=lambda t: t[3]))
    while queue:
        bx, by, brange, _fuse = queue.popleft()
        if (bx, by) in detonated:
            continue
        detonated.add((bx, by))
        danger.add((bx, by))
        for dx, dy in DIRECTIONS.values():
            for step in range(1, brange + 1):
                x, y = bx + dx * step, by + dy * step
                if not (0 <= x < width and 0 <= y < height):
                    break
                tile = grid[y][x]
                if tile == TILE_HARD:
                    break
                danger.add((x, y))
                if tile == TILE_SOFT:
                    break
                for other in bombs:
                    if other["x"] == x and other["y"] == y:
                        key = (x, y)
                        if key not in detonated:
                            queue.append(
                                (x, y, int(other.get("range", 1)), int(other.get("fuse", 0)))
                            )
                # Soft stop already handled; hard handled above.
    return danger


def _walkable(
    state: dict,
    x: int,
    y: int,
    player_id: str,
    bomber: dict,
    allow_soft: bool = False,
) -> bool:
    width = state["grid_width"]
    height = state["grid_height"]
    if not (0 <= x < width and 0 <= y < height):
        return False
    tile = state["grid"][y][x]
    if tile == TILE_HARD:
        return False
    if tile == TILE_SOFT and not allow_soft:
        return False
    bombs = _bomb_cells(state)
    if (x, y) in bombs:
        bomb = bombs[(x, y)]
        passable = set(bomber.get("passable_bomb_ids") or [])
        if bomb["id"] not in passable:
            return False
    return True


def _bfs_safe_move(
    state: dict,
    player_id: str,
    bomber: dict,
    danger: set[tuple[int, int]],
) -> str | None:
    """Return a first-step direction toward the nearest safe cell, or stop if already safe."""
    start = (bomber["x"], bomber["y"])
    if start not in danger:
        return None  # already safe — caller decides chase/bomb

    queue: deque[tuple[int, int, str | None]] = deque([(start[0], start[1], None)])
    seen = {start}
    while queue:
        x, y, first = queue.popleft()
        for direction, (dx, dy) in DIRECTIONS.items():
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen:
                continue
            if not _walkable(state, nx, ny, player_id, bomber):
                continue
            seen.add((nx, ny))
            step_first = first or direction
            if (nx, ny) not in danger:
                return step_first
            queue.append((nx, ny, step_first))
    return "stop"


def _nearest_target_direction(
    state: dict,
    player_id: str,
    bomber: dict,
    danger: set[tuple[int, int]],
    targets: set[tuple[int, int]],
) -> str | None:
    if not targets:
        return None
    start = (bomber["x"], bomber["y"])
    if start in targets and start not in danger:
        return "stop"

    queue: deque[tuple[int, int, str | None]] = deque([(start[0], start[1], None)])
    seen = {start}
    while queue:
        x, y, first = queue.popleft()
        for direction, (dx, dy) in DIRECTIONS.items():
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen:
                continue
            if not _walkable(state, nx, ny, player_id, bomber):
                continue
            if (nx, ny) in danger:
                continue
            seen.add((nx, ny))
            step_first = first or direction
            if (nx, ny) in targets:
                return step_first
            queue.append((nx, ny, step_first))
    return None


def _adjacent_soft(state: dict, x: int, y: int) -> bool:
    for dx, dy in DIRECTIONS.values():
        nx, ny = x + dx, y + dy
        if 0 <= nx < state["grid_width"] and 0 <= ny < state["grid_height"]:
            if state["grid"][ny][nx] == TILE_SOFT:
                return True
    return False


def _enemy_in_blast_line(state: dict, bomber: dict, player_id: str) -> bool:
    brange = int(bomber.get("bomb_range", 1))
    bx, by = bomber["x"], bomber["y"]
    enemies = {
        (b["x"], b["y"])
        for pid, b in state["bombers"].items()
        if pid != player_id and b.get("alive")
    }
    if (bx, by) in enemies:
        return True
    for dx, dy in DIRECTIONS.values():
        for step in range(1, brange + 1):
            x, y = bx + dx * step, by + dy * step
            if not (0 <= x < state["grid_width"] and 0 <= y < state["grid_height"]):
                break
            tile = state["grid"][y][x]
            if tile == TILE_HARD:
                break
            if (x, y) in enemies:
                return True
            if tile == TILE_SOFT:
                break
    return False


def _can_escape_after_bomb(state: dict, player_id: str, bomber: dict) -> bool:
    """Simulate placing a bomb at current cell and check if a safe tile is reachable."""
    fake = {
        **state,
        "bombs": list(state.get("bombs") or [])
        + [
            {
                "id": "__ai_probe__",
                "x": bomber["x"],
                "y": bomber["y"],
                "owner_id": player_id,
                "range": int(bomber.get("bomb_range", 1)),
                "fuse": 12,
            }
        ],
    }
    # Allow walking off the probe bomb like a freshly placed bomb.
    probe_bomber = {
        **bomber,
        "passable_bomb_ids": list(bomber.get("passable_bomb_ids") or []) + ["__ai_probe__"],
    }
    danger = _blast_preview(fake, horizon=20)
    escape = _bfs_safe_move(fake, player_id, probe_bomber, danger)
    return escape is not None and escape != "stop"


def choose_ai_action(
    state: dict,
    player_id: str,
    bomber: dict[str, Any],
) -> tuple[str, bool]:
    """Return (direction, place_bomb)."""
    danger = _blast_preview(state, horizon=18)
    flee = _bfs_safe_move(state, player_id, bomber, danger)
    if flee is not None:
        return flee, False

    # Prefer powerups, then soft-block adjacency cells, then enemies.
    powerups = _powerup_cells(state)
    move = _nearest_target_direction(state, player_id, bomber, danger, powerups)
    if move is None:
        soft_adj: set[tuple[int, int]] = set()
        for y in range(state["grid_height"]):
            for x in range(state["grid_width"]):
                if state["grid"][y][x] != TILE_EMPTY:
                    continue
                if (x, y) in danger:
                    continue
                if _adjacent_soft(state, x, y):
                    soft_adj.add((x, y))
        move = _nearest_target_direction(state, player_id, bomber, danger, soft_adj)

    if move is None:
        enemies = {
            (b["x"], b["y"])
            for pid, b in state["bombers"].items()
            if pid != player_id and b.get("alive")
        }
        # Approach tiles adjacent to enemies
        approach: set[tuple[int, int]] = set()
        for ex, ey in enemies:
            for dx, dy in DIRECTIONS.values():
                approach.add((ex + dx, ey + dy))
        move = _nearest_target_direction(state, player_id, bomber, danger, approach)

    direction = move or random.choice([*DIRECTIONS.keys(), "stop"])

    place = False
    active = sum(
        1 for b in state.get("bombs") or [] if b.get("owner_id") == player_id
    )
    max_bombs = int(bomber.get("max_bombs", 1))
    if active < max_bombs and random.random() < 0.55:
        useful = _adjacent_soft(state, bomber["x"], bomber["y"]) or _enemy_in_blast_line(
            state, bomber, player_id
        )
        if useful and _can_escape_after_bomb(state, player_id, bomber):
            place = True

    return direction, place
