"""Aggressive Bomberman AI — survival first, then hunt, trap, and power up."""

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
ESCAPE_MARGIN = 3
MAX_ESCAPE_STEPS = DEFAULT_FUSE - ESCAPE_MARGIN
THROW_LAND_DISTANCE = 3

# Aggressive bomb rates (still gated by timed escape checks).
BOMB_CHANCE_SOFT = 0.62
BOMB_CHANCE_ENEMY = 0.92
BOMB_CHANCE_TRAP = 1.0


def _bomb_cells(state: dict) -> dict[tuple[int, int], dict]:
    return {(b["x"], b["y"]): b for b in state.get("bombs") or []}


def _powerup_cells(state: dict) -> set[tuple[int, int]]:
    return {(p["x"], p["y"]) for p in state.get("powerups") or []}


def _alive_enemies(state: dict, player_id: str) -> list[tuple[str, dict]]:
    return [
        (pid, b)
        for pid, b in state["bombers"].items()
        if pid != player_id and b.get("alive")
    ]


def _manhattan(ax: int, ay: int, bx: int, by: int) -> int:
    return abs(ax - bx) + abs(ay - by)


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


def _detonation_times(
    bombs: list[dict], grid: list[list[int]], width: int, height: int
) -> dict[str, int]:
    if not bombs:
        return {}
    by_id = {b["id"]: b for b in bombs}
    det_at = {b["id"]: max(0, int(b.get("fuse", DEFAULT_FUSE))) for b in bombs}
    changed = True
    while changed:
        changed = False
        for bid, bomb in by_id.items():
            t = det_at[bid]
            cell_set = set(
                _blast_cells_for(
                    grid, width, height, bomb["x"], bomb["y"], int(bomb.get("range", 1))
                )
            )
            for other in bombs:
                oid = other["id"]
                if oid == bid:
                    continue
                if (other["x"], other["y"]) not in cell_set:
                    continue
                if t < det_at[oid]:
                    det_at[oid] = t
                    changed = True
    return det_at


def _danger_times(
    state: dict,
    extra_bomb: dict | None = None,
) -> dict[tuple[int, int], int]:
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
        # Airborne thrown / carried bombs do not block the floor.
        if bomb.get("flight") in ("throw", "carried"):
            return True
        # Kick holders can path through bombs (they'll push them when adjacent).
        if bomber.get("can_kick") and not bomb.get("flight"):
            return True
        passable = set(bomber.get("passable_bomb_ids") or [])
        if passable_extra:
            passable |= passable_extra
        if bomb["id"] not in passable:
            return False
    return True


def _throw_cell_landable(state: dict, x: int, y: int) -> bool:
    width = state["grid_width"]
    height = state["grid_height"]
    if not (0 <= x < width and 0 <= y < height):
        return False
    if state["grid"][y][x] != TILE_EMPTY:
        return False
    bomb = _bomb_cells(state).get((x, y))
    if bomb is not None and bomb.get("flight") not in ("throw", "carried"):
        return False
    return True


def _throw_landing(
    state: dict, start_x: int, start_y: int, direction: str
) -> tuple[int, int] | None:
    """Match engine: land 3 tiles away, or next empty further if that tile is blocked."""
    if direction not in DIRECTIONS:
        return None
    dx, dy = DIRECTIONS[direction]
    width = state["grid_width"]
    height = state["grid_height"]
    short_empty: tuple[int, int] | None = None
    x, y = start_x, start_y
    for dist in range(1, max(width, height) + 1):
        x, y = x + dx, y + dy
        if not (0 <= x < width and 0 <= y < height):
            break
        if not _throw_cell_landable(state, x, y):
            continue
        if dist < THROW_LAND_DISTANCE:
            short_empty = (x, y)
            continue
        return (x, y)
    return short_empty


def _exit_count(
    state: dict,
    bomber: dict,
    x: int,
    y: int,
    passable_extra: set[str] | None = None,
) -> int:
    return sum(
        1
        for dx, dy in DIRECTIONS.values()
        if _walkable(state, x + dx, y + dy, bomber, passable_extra)
    )


def _move_rate(bomber: dict) -> float:
    level = max(0, min(5, int(bomber.get("speed_level", 0))))
    return 1.0 + 0.28 * level


def _steps_per_tick(bomber: dict) -> float:
    return max(1.0, _move_rate(bomber))


def _find_escape(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
    *,
    passable_extra: set[str] | None = None,
    max_steps: int = MAX_ESCAPE_STEPS,
) -> tuple[str | None, int | None]:
    """Timed BFS to a cell outside the danger map. Prefers roomier safe tiles."""
    start = (bomber["x"], bomber["y"])
    if danger.get(start) is None:
        return None, 0

    speed = _steps_per_tick(bomber)
    queue: deque[tuple[int, int, int, str | None]] = deque(
        [(start[0], start[1], 0, None)]
    )
    seen: dict[tuple[int, int], int] = {start: 0}
    best: tuple[str, int, int] | None = None  # dir, steps, exits

    while queue:
        x, y, steps, first = queue.popleft()
        if steps > 0 and (x, y) not in danger:
            exits = _exit_count(state, bomber, x, y, passable_extra)
            candidate = (first or "stop", steps, exits)
            if best is None or exits > best[2] or (exits == best[2] and steps < best[1]):
                best = candidate
            continue
        if steps >= max_steps:
            continue

        for direction, (dx, dy) in DIRECTIONS.items():
            nx, ny = x + dx, y + dy
            nsteps = steps + 1
            arrive_t = nsteps / speed
            lethal = danger.get((nx, ny))
            if lethal is not None and arrive_t >= lethal:
                continue
            if not _walkable(state, nx, ny, bomber, passable_extra):
                continue
            prev = seen.get((nx, ny))
            if prev is not None and prev <= nsteps:
                continue
            seen[(nx, ny)] = nsteps
            queue.append((nx, ny, nsteps, first or direction))

    if best is None:
        return "stop", None
    return best[0], best[1]


def _safe_step_ok(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
    nx: int,
    ny: int,
    *,
    min_lethal: int = 3,
) -> bool:
    if not _walkable(state, nx, ny, bomber):
        return False
    lethal = danger.get((nx, ny))
    if lethal is not None and lethal <= min_lethal:
        return False
    return True


def _score_step(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
    nx: int,
    ny: int,
) -> int:
    """Higher is better — prefer open tiles away from imminent blasts."""
    score = _exit_count(state, bomber, nx, ny) * 3
    lethal = danger.get((nx, ny))
    if lethal is None:
        score += 8
    else:
        score += min(6, lethal)
    # Slightly prefer not standing on bombs' future lanes near fuse end
    return score


def _best_safe_direction(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
    preferred: str | None = None,
) -> str:
    start = (bomber["x"], bomber["y"])
    scored: list[tuple[int, str]] = []
    for direction, (dx, dy) in DIRECTIONS.items():
        nx, ny = start[0] + dx, start[1] + dy
        if not _safe_step_ok(state, bomber, danger, nx, ny):
            continue
        score = _score_step(state, bomber, danger, nx, ny)
        if direction == preferred:
            score += 4
        momentum = bomber.get("direction")
        if direction == momentum:
            score += 2
        scored.append((score, direction))
    if not scored:
        return "stop"
    scored.sort(key=lambda t: -t[0])
    # Small random among top ties for less predictability
    top = scored[0][0]
    choices = [d for s, d in scored if s >= top - 1]
    return random.choice(choices)


def _bfs_to_targets(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
    targets: set[tuple[int, int]],
    *,
    max_dist: int = 40,
) -> tuple[str | None, int | None]:
    """Return (first_direction, distance) to nearest target on a safe path."""
    if not targets:
        return None, None
    start = (bomber["x"], bomber["y"])
    if start in targets:
        lethal = danger.get(start)
        if lethal is None or lethal > ESCAPE_MARGIN:
            return "stop", 0

    queue: deque[tuple[int, int, str | None, int]] = deque([(start[0], start[1], None, 0)])
    seen = {start}
    while queue:
        x, y, first, steps = queue.popleft()
        if steps >= max_dist:
            continue
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
            # Avoid near-term death lanes
            if lethal is not None and lethal <= 2:
                continue
            seen.add((nx, ny))
            step_first = first or direction
            if (nx, ny) in targets:
                return step_first, nsteps
            queue.append((nx, ny, step_first, nsteps))
    return None, None


def _adjacent_soft(state: dict, x: int, y: int) -> bool:
    for dx, dy in DIRECTIONS.values():
        nx, ny = x + dx, y + dy
        if 0 <= nx < state["grid_width"] and 0 <= ny < state["grid_height"]:
            if state["grid"][ny][nx] == TILE_SOFT:
                return True
    return False


def _clear_line(
    state: dict, x0: int, y0: int, x1: int, y1: int
) -> bool:
    """True if axis-aligned path between cells is free of hard/soft (exclusive)."""
    if x0 != x1 and y0 != y1:
        return False
    if x0 == x1:
        step = 1 if y1 > y0 else -1
        for y in range(y0 + step, y1, step):
            if state["grid"][y][x0] != TILE_EMPTY:
                return False
        return True
    step = 1 if x1 > x0 else -1
    for x in range(x0 + step, x1, step):
        if state["grid"][y0][x] != TILE_EMPTY:
            return False
    return True


def _enemy_in_blast_line(state: dict, bomber: dict, player_id: str) -> bool:
    brange = int(bomber.get("bomb_range", 1))
    bx, by = bomber["x"], bomber["y"]
    enemies = {(b["x"], b["y"]) for _, b in _alive_enemies(state, player_id)}
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


def _open_exits(
    state: dict, bomber: dict, x: int, y: int, passable_extra: set[str]
) -> int:
    return sum(
        1
        for dx, dy in DIRECTIONS.values()
        if _walkable(state, x + dx, y + dy, bomber, passable_extra)
    )


def _can_escape_after_bomb(
    state: dict, player_id: str, bomber: dict
) -> tuple[bool, str | None]:
    """Return (ok, first_escape_direction). Direction is set when ok."""
    ok, direction, _steps = _can_escape_after_bomb_with_steps(state, player_id, bomber)
    return ok, direction


def _can_escape_after_bomb_with_steps(
    state: dict, player_id: str, bomber: dict
) -> tuple[bool, str | None, int | None]:
    probe = {
        "id": "__ai_probe__",
        "x": bomber["x"],
        "y": bomber["y"],
        "owner_id": player_id,
        "range": int(bomber.get("bomb_range", 1)),
        "fuse": DEFAULT_FUSE,
    }
    passable_extra = {"__ai_probe__"}
    fake = {
        **state,
        "bombs": list(state.get("bombs") or []) + [probe],
    }
    danger = _danger_times(fake)
    if _open_exits(fake, bomber, bomber["x"], bomber["y"], passable_extra) < 1:
        return False, None, None

    direction, steps = _find_escape(
        fake,
        bomber,
        danger,
        passable_extra=passable_extra,
        max_steps=MAX_ESCAPE_STEPS,
    )
    if direction is None or direction == "stop" or steps is None:
        return False, None, None
    if steps > MAX_ESCAPE_STEPS:
        return False, None, None
    return True, direction, steps


def _enemy_escape_after_our_bomb(
    state: dict, player_id: str, bomber: dict, enemy: dict
) -> bool:
    """True if the enemy still has a timed escape after we plant at our feet."""
    probe = {
        "id": "__ai_probe__",
        "x": bomber["x"],
        "y": bomber["y"],
        "owner_id": player_id,
        "range": int(bomber.get("bomb_range", 1)),
        "fuse": DEFAULT_FUSE,
    }
    fake = {**state, "bombs": list(state.get("bombs") or []) + [probe]}
    danger = _danger_times(fake)
    # Enemy not even threatened → not a trap
    if danger.get((enemy["x"], enemy["y"])) is None:
        return True
    flee, _steps = _find_escape(fake, enemy, danger, max_steps=MAX_ESCAPE_STEPS + 2)
    return flee is not None and flee != "stop"


def _is_trap_bomb(state: dict, player_id: str, bomber: dict) -> bool:
    if not _enemy_in_blast_line(state, bomber, player_id):
        return False
    for _pid, enemy in _alive_enemies(state, player_id):
        if (enemy["x"], enemy["y"]) not in set(
            _blast_cells_for(
                state["grid"],
                state["grid_width"],
                state["grid_height"],
                bomber["x"],
                bomber["y"],
                int(bomber.get("bomb_range", 1)),
            )
        ):
            continue
        if not _enemy_escape_after_our_bomb(state, player_id, bomber, enemy):
            return True
    return False


def _hunting_positions(
    state: dict,
    player_id: str,
    bomber: dict,
    danger: dict[tuple[int, int], int],
) -> set[tuple[int, int]]:
    """Cells from which a bomb would hit an enemy along a clear lane."""
    brange = int(bomber.get("bomb_range", 1))
    targets: set[tuple[int, int]] = set()
    width, height = state["grid_width"], state["grid_height"]

    for _pid, enemy in _alive_enemies(state, player_id):
        ex, ey = enemy["x"], enemy["y"]
        # Stand on same row/col within range with clear line
        for dist in range(1, brange + 1):
            for dx, dy in DIRECTIONS.values():
                sx, sy = ex - dx * dist, ey - dy * dist
                if not (0 <= sx < width and 0 <= sy < height):
                    continue
                if state["grid"][sy][sx] != TILE_EMPTY:
                    continue
                if danger.get((sx, sy)) is not None and danger[(sx, sy)] <= ESCAPE_MARGIN:
                    continue
                if not _clear_line(state, sx, sy, ex, ey):
                    continue
                # Prefer tiles with an escape hatch
                if _exit_count(state, bomber, sx, sy) >= 2:
                    targets.add((sx, sy))
                elif _exit_count(state, bomber, sx, sy) >= 1:
                    targets.add((sx, sy))
        # Also approach adjacent tiles for close pressure
        for dx, dy in DIRECTIONS.values():
            ax, ay = ex + dx, ey + dy
            if 0 <= ax < width and 0 <= ay < height and state["grid"][ay][ax] == TILE_EMPTY:
                if danger.get((ax, ay)) is None or danger[(ax, ay)] > ESCAPE_MARGIN:
                    targets.add((ax, ay))
    return targets


def _soft_targets(
    state: dict, danger: dict[tuple[int, int], int]
) -> set[tuple[int, int]]:
    soft_adj: set[tuple[int, int]] = set()
    for y in range(state["grid_height"]):
        for x in range(state["grid_width"]):
            if state["grid"][y][x] != TILE_EMPTY:
                continue
            if danger.get((x, y)) is not None and danger[(x, y)] <= ESCAPE_MARGIN:
                continue
            if _adjacent_soft(state, x, y) and _exit_count(
                state, {"passable_bomb_ids": []}, x, y
            ) >= 2:
                soft_adj.add((x, y))
    return soft_adj


def choose_ai_action(
    state: dict,
    player_id: str,
    bomber: dict[str, Any],
) -> tuple[str, bool]:
    """Return (direction, place_bomb)."""
    danger = _danger_times(state)
    pos = (bomber["x"], bomber["y"])
    here_lethal = danger.get(pos)

    # 1) Flee any blast covering us — never bomb while threatened.
    #    Power Glove: if carrying, throw away from escape; if standing on a bomb, pick it up.
    if here_lethal is not None:
        if bomber.get("can_throw") and bomber.get("carrying_bomb_id"):
            flee_dir, _ = _find_escape(
                state, bomber, danger, max_steps=MAX_ESCAPE_STEPS + 3
            )
            opposite = {"up": "down", "down": "up", "left": "right", "right": "left"}
            preferred: list[str] = []
            if flee_dir in DIRECTIONS:
                preferred.append(opposite[flee_dir])
            for key in ("facing", "direction", "next_direction"):
                value = bomber.get(key)
                if value in DIRECTIONS and value not in preferred:
                    preferred.append(value)
            for d in DIRECTIONS:
                if d not in preferred:
                    preferred.append(d)
            for throw_dir in preferred:
                if _throw_landing(state, pos[0], pos[1], throw_dir) is None:
                    continue
                return throw_dir, True
        bomb_here = _bomb_cells(state).get(pos)
        if (
            bomb_here
            and bomber.get("can_throw")
            and not bomber.get("carrying_bomb_id")
            and bomb_here.get("flight") not in ("throw", "kick", "carried")
        ):
            return bomber.get("facing") if bomber.get("facing") in DIRECTIONS else "right", True
        # Face an adjacent bomb and pick it up to escape the blast.
        if bomber.get("can_throw") and not bomber.get("carrying_bomb_id"):
            for face in (
                bomber.get("facing"),
                bomber.get("direction"),
                bomber.get("next_direction"),
                *DIRECTIONS,
            ):
                if face not in DIRECTIONS:
                    continue
                dx, dy = DIRECTIONS[face]
                adj = _bomb_cells(state).get((pos[0] + dx, pos[1] + dy))
                if adj and adj.get("flight") not in ("throw", "kick", "carried"):
                    return face, True
        flee_dir, _ = _find_escape(
            state, bomber, danger, max_steps=MAX_ESCAPE_STEPS + 3
        )
        if flee_dir and flee_dir != "stop":
            return flee_dir, False
        return _best_safe_direction(state, bomber, danger), False

    # Avoid stepping into enemy bomb lanes that are about to go (lookahead).
    # If a neighbor is safer and current tile will be hit soon by a distant bomb...
    # (already handled when here_lethal is set)

    # Throw a carried bomb promptly (classic glove — don't walk around holding forever).
    if bomber.get("can_throw") and bomber.get("carrying_bomb_id"):
        preferred: list[str] = []
        for key in ("facing", "direction", "next_direction"):
            value = bomber.get(key)
            if value in DIRECTIONS and value not in preferred:
                preferred.append(value)
        for d in DIRECTIONS:
            if d not in preferred:
                preferred.append(d)
        for throw_dir in preferred:
            if _throw_landing(state, pos[0], pos[1], throw_dir) is None:
                continue
            return throw_dir, True

    active = sum(1 for b in state.get("bombs") or [] if b.get("owner_id") == player_id)
    max_bombs = int(bomber.get("max_bombs", 1))
    bomb_here = _bomb_cells(state).get(pos)
    can_bomb = (
        active < max_bombs
        and bomb_here is None
        and not bomber.get("carrying_bomb_id")
    )
    # Glove: pick up a bomb underfoot or facing when useful.
    if bomber.get("can_throw") and not bomber.get("carrying_bomb_id"):
        pick_target = bomb_here
        face = bomber.get("facing") if bomber.get("facing") in DIRECTIONS else "right"
        if pick_target is None or pick_target.get("flight") in ("throw", "kick", "carried"):
            dx, dy = DIRECTIONS[face]
            pick_target = _bomb_cells(state).get((pos[0] + dx, pos[1] + dy))
        if (
            pick_target
            and pick_target.get("flight") not in ("throw", "kick", "carried")
            and random.random() < 0.45
        ):
            return face, True

    # 2) Bombing decisions — traps first, then enemy line, then soft.
    if can_bomb:
        ok, esc, esc_steps = _can_escape_after_bomb_with_steps(state, player_id, bomber)
        if ok and esc:
            trap = _is_trap_bomb(state, player_id, bomber)
            hit_enemy = _enemy_in_blast_line(state, bomber, player_id)
            hit_soft = _adjacent_soft(state, bomber["x"], bomber["y"])

            chance = 0.0
            if trap:
                chance = BOMB_CHANCE_TRAP
            elif hit_enemy:
                chance = BOMB_CHANCE_ENEMY
                # Prefer bombing when escape is short (safer aggression)
                if esc_steps is not None and esc_steps <= 4:
                    chance = min(1.0, chance + 0.08)
            elif hit_soft:
                chance = BOMB_CHANCE_SOFT
                # Early game: clear space faster
                if int(bomber.get("bomb_range", 1)) <= 2:
                    chance = max(chance, 0.7)

            if active > 0:
                # Still chain aggressively for traps / kills
                chance *= 0.85 if (trap or hit_enemy) else 0.55

            if chance > 0 and random.random() < chance:
                return esc, True

    # 3) Power-ups — race to them hard (especially speed/bomb).
    powerups = {
        c
        for c in _powerup_cells(state)
        if danger.get(c) is None or danger.get(c, 0) > ESCAPE_MARGIN
    }
    move, dist = _bfs_to_targets(state, bomber, danger, powerups, max_dist=18)
    if move and move != "stop" and dist is not None and dist <= 12:
        return move, False

    # 4) Hunt enemies — get onto a bombing line.
    enemies = _alive_enemies(state, player_id)
    nearest_enemy_dist = min(
        (_manhattan(pos[0], pos[1], e["x"], e["y"]) for _, e in enemies),
        default=99,
    )

    hunt = _hunting_positions(state, player_id, bomber, danger)
    move, dist = _bfs_to_targets(state, bomber, danger, hunt, max_dist=24)
    if move and move != "stop":
        # If already on a hunt tile, hold / micro-adjust then bomb next ticks
        if dist == 0:
            # Stay ready; nudge toward more exits if current is cramped
            if _exit_count(state, bomber, pos[0], pos[1]) < 2:
                return _best_safe_direction(state, bomber, danger), False
            return "stop", False
        return move, False

    # 5) Soft-wall farming when enemies are far or map is clogged.
    if nearest_enemy_dist > 6 or int(bomber.get("bomb_range", 1)) < 2:
        soft = _soft_targets(state, danger)
        move, _ = _bfs_to_targets(state, bomber, danger, soft, max_dist=20)
        if move and move != "stop":
            return move, False

    # 6) Close the gap — path toward enemy tile neighborhood.
    if enemies:
        approach: set[tuple[int, int]] = set()
        for _pid, enemy in enemies:
            for dx, dy in DIRECTIONS.values():
                approach.add((enemy["x"] + dx, enemy["y"] + dy))
                approach.add((enemy["x"] + dx * 2, enemy["y"] + dy * 2))
        move, _ = _bfs_to_targets(state, bomber, danger, approach, max_dist=30)
        if move and move != "stop":
            return move, False

    # 7) Soft walls as fallback
    soft = _soft_targets(state, danger)
    move, _ = _bfs_to_targets(state, bomber, danger, soft, max_dist=25)
    if move and move != "stop":
        return move, False

    return _best_safe_direction(state, bomber, danger), False
