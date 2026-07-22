"""Bomberman AI with timed danger maps — prioritize survival over aggression."""

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

# Must match engine.DEFAULT_FUSE — keep a local copy to avoid import cycles.
DEFAULT_FUSE = 14
# Require this many spare ticks after reaching safety before a blast lands.
ESCAPE_MARGIN = 4
# Don't place if escape path is longer than fuse - margin.
MAX_ESCAPE_STEPS = DEFAULT_FUSE - ESCAPE_MARGIN
# How often to bomb when a safe opportunity exists.
BOMB_CHANCE_SOFT = 0.28
BOMB_CHANCE_ENEMY = 0.42


def _bomb_cells(state: dict) -> dict[tuple[int, int], dict]:
    return {(b["x"], b["y"]): b for b in state.get("bombs") or []}


def _powerup_cells(state: dict) -> set[tuple[int, int]]:
    return {(p["x"], p["y"]) for p in state.get("powerups") or []}


def _blast_cells_for(
    grid: list[list[int]],
    width: int,
    height: int,
    bx: int,
    by: int,
    brange: int,
) -> list[tuple[int, int]]:
    cells = [(bx, by)]
    for dx, dy in DIRECTIONS.values():
        for step in range(1, brange + 1):
            x, y = bx + dx * step, by + dy * step
            if not (0 <= x < width and 0 <= y < height):
                break
            tile = grid[y][x]
            if tile == TILE_HARD:
                break
            cells.append((x, y))
            if tile == TILE_SOFT:
                break
    return cells


def _detonation_times(bombs: list[dict], grid: list[list[int]], width: int, height: int) -> dict[str, int]:
    """Earliest tick (from now) each bomb will explode, including chain reactions."""
    if not bombs:
        return {}
    by_id = {b["id"]: b for b in bombs}
    det_at = {b["id"]: max(0, int(b.get("fuse", DEFAULT_FUSE))) for b in bombs}
    changed = True
    while changed:
        changed = False
        for bid, bomb in by_id.items():
            t = det_at[bid]
            cells = _blast_cells_for(
                grid, width, height, bomb["x"], bomb["y"], int(bomb.get("range", 1))
            )
            cell_set = set(cells)
            for other in bombs:
                oid = other["id"]
                if oid == bid:
                    continue
                if (other["x"], other["y"]) not in cell_set:
                    continue
                # Other bomb is caught in this blast → chains at time t.
                if t < det_at[oid]:
                    det_at[oid] = t
                    changed = True
    return det_at


def _danger_times(
    state: dict,
    extra_bomb: dict | None = None,
) -> dict[tuple[int, int], int]:
    """Earliest tick when each cell becomes lethal. Missing key = never."""
    grid = state["grid"]
    width = state["grid_width"]
    height = state["grid_height"]
    danger: dict[tuple[int, int], int] = {}

    for cell in state.get("explosions") or []:
        if int(cell.get("ttl", 0)) > 0:
            danger[(cell["x"], cell["y"])] = 0

    bombs = list(state.get("bombs") or [])
    if extra_bomb is not None:
        bombs = bombs + [extra_bomb]

    det_at = _detonation_times(bombs, grid, width, height)
    for bomb in bombs:
        t = det_at.get(bomb["id"], max(0, int(bomb.get("fuse", DEFAULT_FUSE))))
        for x, y in _blast_cells_for(
            grid, width, height, bomb["x"], bomb["y"], int(bomb.get("range", 1))
        ):
            prev = danger.get((x, y))
            if prev is None or t < prev:
                danger[(x, y)] = t
    return danger


def _walkable(
    state: dict,
    x: int,
    y: int,
    bomber: dict,
    passable_extra: set[str] | None = None,
) -> bool:
    width = state["grid_width"]
    height = state["grid_height"]
    if not (0 <= x < width and 0 <= y < height):
        return False
    if state["grid"][y][x] != TILE_EMPTY:
        return False
    bombs = _bomb_cells(state)
    if (x, y) in bombs:
        bomb = bombs[(x, y)]
        passable = set(bomber.get("passable_bomb_ids") or [])
        if passable_extra:
            passable |= passable_extra
        if bomb["id"] not in passable:
            return False
    return True


def _move_rate(bomber: dict) -> float:
    level = max(0, min(5, int(bomber.get("speed_level", 0))))
    return 1.0 + 0.28 * level


def _steps_per_tick(bomber: dict) -> float:
    """Approximate cells moved per game tick."""
    return max(1.0, _move_rate(bomber))


def _find_escape(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
    *,
    passable_extra: set[str] | None = None,
    max_steps: int = MAX_ESCAPE_STEPS,
) -> tuple[str | None, int | None]:
    """
    Timed BFS escape. Returns (first_direction, path_length).
    Direction is None if already safe, "stop" if trapped.

    Goal: any cell that is not in the danger map. Paths may cross blast lanes
    only if we pass through before that cell's detonation time.
    """
    start = (bomber["x"], bomber["y"])
    if danger.get(start) is None:
        return None, 0  # already safe

    speed = _steps_per_tick(bomber)
    queue: deque[tuple[int, int, int, str | None]] = deque(
        [(start[0], start[1], 0, None)]
    )
    seen: dict[tuple[int, int], int] = {start: 0}

    while queue:
        x, y, steps, first = queue.popleft()
        if steps > 0 and (x, y) not in danger:
            return first or "stop", steps
        if steps >= max_steps:
            continue

        for direction, (dx, dy) in DIRECTIONS.items():
            nx, ny = x + dx, y + dy
            nsteps = steps + 1
            arrive_t = nsteps / speed
            lethal = danger.get((nx, ny))
            # Cannot sit on / enter a cell that explodes on or before arrival.
            if lethal is not None and arrive_t >= lethal:
                continue
            if not _walkable(state, nx, ny, bomber, passable_extra):
                continue
            prev = seen.get((nx, ny))
            if prev is not None and prev <= nsteps:
                continue
            seen[(nx, ny)] = nsteps
            queue.append((nx, ny, nsteps, first or direction))

    return "stop", None


def _safe_wander_direction(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
) -> str:
    """Pick a safe adjacent step; prefer continuing momentum; never walk into imminent blast."""
    start = (bomber["x"], bomber["y"])
    candidates: list[str] = []
    for direction, (dx, dy) in DIRECTIONS.items():
        nx, ny = start[0] + dx, start[1] + dy
        if not _walkable(state, nx, ny, bomber):
            continue
        lethal = danger.get((nx, ny))
        if lethal is not None and lethal <= 2:
            continue
        candidates.append(direction)
    if not candidates:
        return "stop"
    momentum = bomber.get("direction")
    if momentum in candidates and random.random() < 0.55:
        return momentum
    return random.choice(candidates)


def _nearest_safe_target(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
    targets: set[tuple[int, int]],
) -> str | None:
    if not targets:
        return None
    start = (bomber["x"], bomber["y"])
    if start in targets:
        lethal = danger.get(start)
        if lethal is None or lethal > ESCAPE_MARGIN:
            return "stop"

    queue: deque[tuple[int, int, str | None, int]] = deque([(start[0], start[1], None, 0)])
    seen = {start}
    while queue:
        x, y, first, steps = queue.popleft()
        for direction, (dx, dy) in DIRECTIONS.items():
            nx, ny = x + dx, y + dy
            if (nx, ny) in seen:
                continue
            if not _walkable(state, nx, ny, bomber):
                continue
            nsteps = steps + 1
            lethal = danger.get((nx, ny))
            if lethal is not None and nsteps >= lethal:
                continue
            seen.add((nx, ny))
            step_first = first or direction
            if (nx, ny) in targets:
                return step_first
            queue.append((nx, ny, step_first, nsteps))
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


def _open_exits(state: dict, bomber: dict, x: int, y: int, passable_extra: set[str]) -> int:
    """How many walkable neighbors from (x,y), treating a new bomb on (x,y) as passable only via extra."""
    count = 0
    for dx, dy in DIRECTIONS.values():
        nx, ny = x + dx, y + dy
        if _walkable(state, nx, ny, bomber, passable_extra):
            count += 1
    return count


def _can_escape_after_bomb(
    state: dict, player_id: str, bomber: dict
) -> tuple[bool, str | None]:
    """Return (ok, first_escape_direction). Direction is set when ok."""
    probe = {
        "id": "__ai_probe__",
        "x": bomber["x"],
        "y": bomber["y"],
        "owner_id": player_id,
        "range": int(bomber.get("bomb_range", 1)),
        "fuse": DEFAULT_FUSE,
    }
    # Future bombs on this cell block re-entry once we leave; probe is passable only while leaving.
    passable_extra = {"__ai_probe__"}
    # Also mark probe in a fake bomb list for walkability of OTHER bombs — probe sits on us.
    fake = {
        **state,
        "bombs": list(state.get("bombs") or []) + [probe],
    }
    danger = _danger_times(fake)
    # Dead-end check: need at least one exit off the bomb cell.
    if _open_exits(fake, bomber, bomber["x"], bomber["y"], passable_extra) < 1:
        return False, None

    direction, steps = _find_escape(
        fake,
        bomber,
        danger,
        passable_extra=passable_extra,
        max_steps=MAX_ESCAPE_STEPS,
    )
    if direction is None:
        # Already "safe" under probe danger? Shouldn't happen — bomb makes current cell lethal.
        return False, None
    if direction == "stop" or steps is None:
        return False, None
    if steps > MAX_ESCAPE_STEPS:
        return False, None
    return True, direction


def choose_ai_action(
    state: dict,
    player_id: str,
    bomber: dict[str, Any],
) -> tuple[str, bool]:
    """Return (direction, place_bomb). Survival first, then objectives."""
    danger = _danger_times(state)
    pos = (bomber["x"], bomber["y"])
    here_lethal = danger.get(pos)

    # 1) Imminent danger — flee, never bomb.
    if here_lethal is not None and here_lethal <= DEFAULT_FUSE:
        flee_dir, _ = _find_escape(state, bomber, danger, max_steps=MAX_ESCAPE_STEPS + 2)
        if flee_dir is None:
            # Safe somehow
            pass
        elif flee_dir != "stop":
            return flee_dir, False
        else:
            # Trapped — still try any non-instant-death step.
            return _safe_wander_direction(state, bomber, danger), False

    # Upcoming danger on current tile (own/enemy bomb) — start moving out early.
    if here_lethal is not None:
        flee_dir, _ = _find_escape(state, bomber, danger, max_steps=MAX_ESCAPE_STEPS + 2)
        if flee_dir and flee_dir != "stop":
            return flee_dir, False

    # 2) Consider bombing only with a verified timed escape, and flee that way immediately.
    active = sum(1 for b in state.get("bombs") or [] if b.get("owner_id") == player_id)
    max_bombs = int(bomber.get("max_bombs", 1))
    place = False
    escape_after: str | None = None

    if active < max_bombs and _bomb_cells(state).get(pos) is None:
        useful_soft = _adjacent_soft(state, bomber["x"], bomber["y"])
        useful_enemy = _enemy_in_blast_line(state, bomber, player_id)
        chance = BOMB_CHANCE_ENEMY if useful_enemy else (BOMB_CHANCE_SOFT if useful_soft else 0.0)
        # Don't stack bombs aggressively until the first has cleared.
        if active > 0:
            chance *= 0.35
        if chance > 0 and random.random() < chance:
            ok, esc = _can_escape_after_bomb(state, player_id, bomber)
            if ok and esc:
                place = True
                escape_after = esc

    if place and escape_after:
        return escape_after, True

    # 3) Hunt powerups / soft walls / enemies on safe paths only.
    powerups = {
        c
        for c in _powerup_cells(state)
        if danger.get(c) is None or danger.get(c, 0) > ESCAPE_MARGIN
    }
    move = _nearest_safe_target(state, bomber, danger, powerups)

    if move is None:
        soft_adj: set[tuple[int, int]] = set()
        for y in range(state["grid_height"]):
            for x in range(state["grid_width"]):
                if state["grid"][y][x] != TILE_EMPTY:
                    continue
                if danger.get((x, y)) is not None and danger[(x, y)] <= ESCAPE_MARGIN:
                    continue
                if _adjacent_soft(state, x, y):
                    soft_adj.add((x, y))
        move = _nearest_safe_target(state, bomber, danger, soft_adj)

    if move is None:
        approach: set[tuple[int, int]] = set()
        for pid, other in state["bombers"].items():
            if pid == player_id or not other.get("alive"):
                continue
            for dx, dy in DIRECTIONS.values():
                tx, ty = other["x"] + dx, other["y"] + dy
                if danger.get((tx, ty)) is not None and danger[(tx, ty)] <= ESCAPE_MARGIN:
                    continue
                approach.add((tx, ty))
        move = _nearest_safe_target(state, bomber, danger, approach)

    if move and move != "stop":
        return move, False

    return _safe_wander_direction(state, bomber, danger), False
