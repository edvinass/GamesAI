"""Deliberate Bomberman AI — survival first, then trap, hunt, and power up."""

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
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}

TILE_EMPTY = 0
TILE_HARD = 1
TILE_SOFT = 2

# Must match engine.DEFAULT_FUSE — keep a local copy to avoid import cycles.
DEFAULT_FUSE = 14
ESCAPE_MARGIN = 3
MAX_ESCAPE_STEPS = DEFAULT_FUSE - ESCAPE_MARGIN
THROW_LAND_DISTANCE = 3
# Longer lookahead so we plant on where the player is going, not was.
PREDICT_STEPS = 4

# Bomb rates (still gated by timed escape checks). Soft clears are patient.
BOMB_CHANCE_SOFT = 0.48
BOMB_CHANCE_ENEMY = 1.0
BOMB_CHANCE_TRAP = 1.0
# Don't soft-farm while an enemy is this close (manhattan).
SOFT_FARM_MIN_ENEMY_DIST = 7

# Power-up preference when missing that capability.
POWERUP_BASE = {
    "throw": 12,
    "kick": 10,
    "bomb": 9,
    "range": 8,
    "speed": 7,
    "skull": -50,
}


def _bomb_cells(state: dict) -> dict[tuple[int, int], dict]:
    cells: dict[tuple[int, int], dict] = {}
    for b in state.get("bombs") or []:
        # Carried / mid-throw bombs don't occupy the floor for pathing.
        if b.get("flight") in ("throw", "carried"):
            continue
        cells[(b["x"], b["y"])] = b
    return cells


def _alive_enemies(state: dict, player_id: str) -> list[tuple[str, dict]]:
    return [
        (pid, b)
        for pid, b in state["bombers"].items()
        if pid != player_id and b.get("alive")
    ]


def _manhattan(ax: int, ay: int, bx: int, by: int) -> int:
    return abs(ax - bx) + abs(ay - by)


def _enemy_move_dir(enemy: dict) -> str | None:
    nxt = enemy.get("next_direction")
    if nxt == "stop":
        return None
    if nxt in DIRECTIONS:
        return nxt
    for key in ("direction", "facing"):
        value = enemy.get(key)
        if value in DIRECTIONS:
            return value
    return None


def _predicted_enemy_cells(state: dict, enemy: dict) -> set[tuple[int, int]]:
    """Current tile plus a short lookahead along facing / next_direction."""
    cells: set[tuple[int, int]] = {(enemy["x"], enemy["y"])}
    move = _enemy_move_dir(enemy)
    if move is None:
        return cells
    dx, dy = DIRECTIONS[move]
    x, y = enemy["x"], enemy["y"]
    width, height = state["grid_width"], state["grid_height"]
    for _ in range(PREDICT_STEPS):
        x, y = x + dx, y + dy
        if not (0 <= x < width and 0 <= y < height):
            break
        if state["grid"][y][x] != TILE_EMPTY:
            break
        # Don't predict through grounded bombs.
        blocked = False
        for bomb in state.get("bombs") or []:
            if bomb.get("flight") in ("throw", "carried"):
                continue
            if bomb["x"] == x and bomb["y"] == y:
                blocked = True
                break
        if blocked:
            break
        cells.add((x, y))
    return cells


def _enemy_threat_cells(state: dict, player_id: str) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for _pid, enemy in _alive_enemies(state, player_id):
        cells |= _predicted_enemy_cells(state, enemy)
    return cells


def _blast_origin(bomb: dict) -> tuple[int, int]:
    """Prefer planned throw landing when scoring future blasts."""
    if bomb.get("flight") == "throw":
        lx, ly = bomb.get("land_x"), bomb.get("land_y")
        if lx is not None and ly is not None:
            return int(lx), int(ly)
    return int(bomb["x"]), int(bomb["y"])


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
    grounded = [b for b in bombs if b.get("flight") != "carried"]
    by_id = {b["id"]: b for b in grounded}
    det_at = {b["id"]: max(0, int(b.get("fuse", DEFAULT_FUSE))) for b in grounded}
    changed = True
    while changed:
        changed = False
        for bid, bomb in by_id.items():
            t = det_at[bid]
            ox, oy = _blast_origin(bomb)
            cell_set = set(
                _blast_cells_for(
                    grid, width, height, ox, oy, int(bomb.get("range", 1))
                )
            )
            for other in grounded:
                oid = other["id"]
                if oid == bid:
                    continue
                opos = _blast_origin(other)
                if opos not in cell_set:
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

    # Carried bombs explode with the carrier; treat origin as current x/y.
    # Thrown bombs are scored from their planned landing for pathing foresight.
    det_at = _detonation_times(bombs, grid, width, height)
    for bomb in bombs:
        if bomb.get("flight") == "carried":
            continue
        t = det_at.get(bomb["id"], max(0, int(bomb.get("fuse", DEFAULT_FUSE))))
        ox, oy = _blast_origin(bomb)
        for x, y in _blast_cells_for(
            grid, width, height, ox, oy, int(bomb.get("range", 1))
        ):
            prev = danger.get((x, y))
            if prev is None or t < prev:
                danger[(x, y)] = t
        # Mid-throw: also mark current tile blast if fuse is short.
        if bomb.get("flight") == "throw" and t <= ESCAPE_MARGIN:
            for x, y in _blast_cells_for(
                grid,
                width,
                height,
                int(bomb["x"]),
                int(bomb["y"]),
                int(bomb.get("range", 1)),
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


def _throw_cell_landable(
    state: dict, x: int, y: int, *, ignore_bomb_id: str | None = None
) -> bool:
    width = state["grid_width"]
    height = state["grid_height"]
    if not (0 <= x < width and 0 <= y < height):
        return False
    if state["grid"][y][x] != TILE_EMPTY:
        return False
    for other in state.get("bombs") or []:
        if ignore_bomb_id and other.get("id") == ignore_bomb_id:
            continue
        if other.get("x") != x or other.get("y") != y:
            continue
        if other.get("flight") == "carried":
            continue
        return False
    return True


def _throw_landing(
    state: dict,
    start_x: int,
    start_y: int,
    direction: str,
    *,
    ignore_bomb_id: str | None = None,
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
        if not _throw_cell_landable(state, x, y, ignore_bomb_id=ignore_bomb_id):
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


def _momentum_dir(bomber: dict) -> str | None:
    for key in ("direction", "next_direction", "facing"):
        value = bomber.get(key)
        if value in DIRECTIONS:
            return value
    return None


def _best_safe_direction(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
    preferred: str | None = None,
) -> str:
    start = (bomber["x"], bomber["y"])
    momentum = _momentum_dir(bomber)
    scored: list[tuple[int, str]] = []
    for direction, (dx, dy) in DIRECTIONS.items():
        nx, ny = start[0] + dx, start[1] + dy
        if not _safe_step_ok(state, bomber, danger, nx, ny):
            continue
        score = _score_step(state, bomber, danger, nx, ny)
        if direction == preferred:
            score += 4
        if direction == momentum:
            score += 3
        # Avoid pointless U-turns when safer options exist.
        if momentum and direction == OPPOSITE.get(momentum):
            score -= 4
        scored.append((score, direction))
    if not scored:
        return "stop"
    scored.sort(key=lambda t: -t[0])
    # Prefer the top score; only randomize exact ties.
    top = scored[0][0]
    choices = [d for s, d in scored if s == top]
    return random.choice(choices)


def _bfs_to_targets(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
    targets: set[tuple[int, int]],
    *,
    max_dist: int = 40,
) -> tuple[str | None, int | None]:
    """Return (first_direction, distance) to nearest target on a safe path.

    Among equal-length paths, prefer continuing current momentum and avoid
    immediate U-turns so movement looks committed rather than twitchy.
    """
    if not targets:
        return None, None
    start = (bomber["x"], bomber["y"])
    if start in targets:
        lethal = danger.get(start)
        if lethal is None or lethal > ESCAPE_MARGIN:
            return "stop", 0

    momentum = _momentum_dir(bomber)
    queue: deque[tuple[int, int, str | None, int]] = deque([(start[0], start[1], None, 0)])
    seen = {start}
    best: tuple[int, int, str] | None = None  # dist, rank, direction
    while queue:
        x, y, first, steps = queue.popleft()
        if steps >= max_dist:
            continue
        if best is not None and steps > best[0]:
            break
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
                rank = 0
                if step_first == momentum:
                    rank += 2
                if momentum and step_first == OPPOSITE.get(momentum):
                    rank -= 2
                # Prefer roomier arrival tiles among equal paths.
                rank += min(3, _exit_count(state, bomber, nx, ny))
                candidate = (nsteps, -rank, step_first)
                if best is None or candidate[:2] < best[:2]:
                    best = (nsteps, -rank, step_first)
                continue
            queue.append((nx, ny, step_first, nsteps))
    if best is None:
        return None, None
    return best[2], best[0]


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


def _blast_from(
    state: dict, bx: int, by: int, brange: int
) -> set[tuple[int, int]]:
    return set(
        _blast_cells_for(
            state["grid"],
            state["grid_width"],
            state["grid_height"],
            bx,
            by,
            brange,
        )
    )


def _enemy_in_blast_line(
    state: dict,
    bomber: dict,
    player_id: str,
    *,
    at: tuple[int, int] | None = None,
) -> bool:
    brange = int(bomber.get("bomb_range", 1))
    bx, by = at if at is not None else (bomber["x"], bomber["y"])
    threats = _enemy_threat_cells(state, player_id)
    return bool(_blast_from(state, bx, by, brange) & threats)


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
    state: dict,
    player_id: str,
    bomber: dict,
    *,
    at: tuple[int, int] | None = None,
) -> tuple[bool, str | None, int | None]:
    px, py = at if at is not None else (bomber["x"], bomber["y"])
    probe = {
        "id": "__ai_probe__",
        "x": px,
        "y": py,
        "owner_id": player_id,
        "range": int(bomber.get("bomb_range", 1)),
        "fuse": DEFAULT_FUSE,
    }
    passable_extra = {"__ai_probe__"}
    fake = {
        **state,
        "bombs": list(state.get("bombs") or []) + [probe],
    }
    standing = {**bomber, "x": px, "y": py}
    danger = _danger_times(fake)
    if _open_exits(fake, standing, px, py, passable_extra) < 1:
        return False, None, None

    direction, steps = _find_escape(
        fake,
        standing,
        danger,
        passable_extra=passable_extra,
        max_steps=MAX_ESCAPE_STEPS,
    )
    if direction is None or direction == "stop" or steps is None:
        return False, None, None
    if steps > MAX_ESCAPE_STEPS:
        return False, None, None
    return True, direction, steps


def _enemy_escape_after_bomb_at(
    state: dict,
    player_id: str,
    bomber: dict,
    enemy: dict,
    bx: int,
    by: int,
) -> bool:
    """True if the enemy still has a timed escape after we plant at (bx, by)."""
    probe = {
        "id": "__ai_probe__",
        "x": bx,
        "y": by,
        "owner_id": player_id,
        "range": int(bomber.get("bomb_range", 1)),
        "fuse": DEFAULT_FUSE,
    }
    fake = {**state, "bombs": list(state.get("bombs") or []) + [probe]}
    danger = _danger_times(fake)
    # Threatened if current or predicted cells are in the blast.
    threatened = False
    for cell in _predicted_enemy_cells(state, enemy):
        if danger.get(cell) is not None:
            threatened = True
            break
    if not threatened:
        return True
    flee, _steps = _find_escape(fake, enemy, danger, max_steps=MAX_ESCAPE_STEPS + 2)
    return flee is not None and flee != "stop"


def _is_trap_at(
    state: dict, player_id: str, bomber: dict, bx: int, by: int
) -> bool:
    brange = int(bomber.get("bomb_range", 1))
    blast = _blast_from(state, bx, by, brange)
    if not blast & _enemy_threat_cells(state, player_id):
        return False
    for _pid, enemy in _alive_enemies(state, player_id):
        if not (_predicted_enemy_cells(state, enemy) & blast):
            continue
        if not _enemy_escape_after_bomb_at(state, player_id, bomber, enemy, bx, by):
            return True
    return False


def _is_trap_bomb(state: dict, player_id: str, bomber: dict) -> bool:
    return _is_trap_at(state, player_id, bomber, bomber["x"], bomber["y"])


def _score_landing_blast(
    state: dict,
    player_id: str,
    bomber: dict,
    lx: int,
    ly: int,
    brange: int,
) -> int:
    """Higher is better for throwing / kicking a bomb onto (lx, ly)."""
    blast = _blast_from(state, lx, ly, brange)
    score = 0
    threats = _enemy_threat_cells(state, player_id)
    hits = blast & threats
    score += 50 * len(hits)
    if hits:
        # Trap check is expensive; only run when we already threaten someone.
        if _is_trap_at(state, player_id, bomber, lx, ly):
            score += 60
    # Soft clears are a mild bonus.
    for x, y in blast:
        if (x, y) == (lx, ly):
            continue
        if 0 <= x < state["grid_width"] and 0 <= y < state["grid_height"]:
            if state["grid"][y][x] == TILE_SOFT:
                score += 3
    # Never "throw" onto our own tile; mild penalty if we're still in the lane
    # (fuse leaves time to walk off after a glove toss).
    if (lx, ly) == (bomber["x"], bomber["y"]):
        score -= 80
    elif (bomber["x"], bomber["y"]) in blast:
        score -= 6
    # Prefer landings farther from us so we keep escape room.
    score += min(6, _manhattan(bomber["x"], bomber["y"], lx, ly))
    return score


def _best_throw_direction(
    state: dict,
    player_id: str,
    bomber: dict,
    *,
    avoid_dir: str | None = None,
) -> str | None:
    """Pick a throw direction that maximizes enemy blast / trap value."""
    brange = int(bomber.get("bomb_range", 1))
    pos = (bomber["x"], bomber["y"])
    ignore_id = bomber.get("carrying_bomb_id")
    scored: list[tuple[int, str]] = []
    for direction in DIRECTIONS:
        landing = _throw_landing(
            state, pos[0], pos[1], direction, ignore_bomb_id=ignore_id
        )
        if landing is None:
            continue
        score = _score_landing_blast(
            state, player_id, bomber, landing[0], landing[1], brange
        )
        if direction == avoid_dir:
            score -= 15  # don't throw into our flee path if we can help it
        if direction == bomber.get("facing"):
            score += 1
        scored.append((score, direction))
    if not scored:
        return None
    scored.sort(key=lambda t: -t[0])
    return scored[0][1]


def _kick_bomb_stop(
    state: dict, bx: int, by: int, direction: str
) -> tuple[int, int] | None:
    """Approximate where a kicked bomb comes to rest along a lane."""
    if direction not in DIRECTIONS:
        return None
    dx, dy = DIRECTIONS[direction]
    width, height = state["grid_width"], state["grid_height"]
    x, y = bx + dx, by + dy
    if not (0 <= x < width and 0 <= y < height):
        return None
    if state["grid"][y][x] != TILE_EMPTY:
        return None
    last = (x, y)
    while True:
        nx, ny = x + dx, y + dy
        if not (0 <= nx < width and 0 <= ny < height):
            return last
        if state["grid"][ny][nx] != TILE_EMPTY:
            return last
        for other in state.get("bombs") or []:
            if other.get("flight") in ("throw", "carried"):
                continue
            if other["x"] == nx and other["y"] == ny:
                return last
        x, y = nx, ny
        last = (x, y)
        # Cap scan so we don't walk the whole map every tick.
        if _manhattan(bx, by, x, y) > 12:
            return last


def _best_kick_direction(
    state: dict, player_id: str, bomber: dict, danger: dict[tuple[int, int], int]
) -> str | None:
    """If adjacent to a kickable bomb, walk into it toward a strong landing."""
    if not bomber.get("can_kick"):
        return None
    pos = (bomber["x"], bomber["y"])
    brange = 1
    # Use the bomb's own range when known.
    best: tuple[int, str] | None = None
    for direction, (dx, dy) in DIRECTIONS.items():
        nx, ny = pos[0] + dx, pos[1] + dy
        bomb = _bomb_cells(state).get((nx, ny))
        if bomb is None or bomb.get("flight") or bomb.get("sliding"):
            continue
        if not _safe_step_ok(state, bomber, danger, nx, ny, min_lethal=2):
            # Walking onto the bomb tile is required to kick; allow slightly hotter tiles.
            if not _walkable(state, nx, ny, bomber):
                continue
        stop = _kick_bomb_stop(state, nx, ny, direction)
        if stop is None:
            continue
        bomb_range = int(bomb.get("range", brange))
        score = _score_landing_blast(
            state, player_id, bomber, stop[0], stop[1], bomb_range
        )
        # Only kick when it creates real pressure.
        if score < 40:
            continue
        if best is None or score > best[0]:
            best = (score, direction)
    return best[1] if best else None


def _hunting_positions(
    state: dict,
    player_id: str,
    bomber: dict,
    danger: dict[tuple[int, int], int],
) -> set[tuple[int, int]]:
    """Cells from which a bomb would hit an enemy (current or predicted)."""
    brange = int(bomber.get("bomb_range", 1))
    targets: set[tuple[int, int]] = set()
    width, height = state["grid_width"], state["grid_height"]

    threat_cells = _enemy_threat_cells(state, player_id)
    for ex, ey in threat_cells:
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
                if _exit_count(state, bomber, sx, sy) >= 1:
                    targets.add((sx, sy))
        for dx, dy in DIRECTIONS.values():
            ax, ay = ex + dx, ey + dy
            if 0 <= ax < width and 0 <= ay < height and state["grid"][ay][ax] == TILE_EMPTY:
                if danger.get((ax, ay)) is None or danger[(ax, ay)] > ESCAPE_MARGIN:
                    targets.add((ax, ay))
    return targets


def _trap_positions(
    state: dict,
    player_id: str,
    bomber: dict,
    danger: dict[tuple[int, int], int],
) -> set[tuple[int, int]]:
    """Hunt tiles where planting would deny the enemy an escape."""
    traps: set[tuple[int, int]] = set()
    for sx, sy in _hunting_positions(state, player_id, bomber, danger):
        if _is_trap_at(state, player_id, bomber, sx, sy):
            # Must be able to escape after planting there.
            ok, _, _ = _can_escape_after_bomb_with_steps(
                state, player_id, bomber, at=(sx, sy)
            )
            if ok:
                traps.add((sx, sy))
    return traps


def _best_plant_approach(
    state: dict,
    player_id: str,
    bomber: dict,
    danger: dict[tuple[int, int], int],
) -> str | None:
    """One-ply: step onto an adjacent tile that yields a trap / kill plant next tick."""
    pos = (bomber["x"], bomber["y"])
    best: tuple[int, str] | None = None
    for direction, (dx, dy) in DIRECTIONS.items():
        nx, ny = pos[0] + dx, pos[1] + dy
        if not _safe_step_ok(state, bomber, danger, nx, ny):
            continue
        ok, _, esc_steps = _can_escape_after_bomb_with_steps(
            state, player_id, bomber, at=(nx, ny)
        )
        if not ok:
            continue
        trap = _is_trap_at(state, player_id, bomber, nx, ny)
        hit = _enemy_in_blast_line(state, bomber, player_id, at=(nx, ny))
        if not trap and not hit:
            continue
        score = 100 if trap else 50
        if esc_steps is not None:
            score += max(0, 8 - esc_steps)
        if best is None or score > best[0]:
            best = (score, direction)
    return best[1] if best else None


def _priority_powerup_targets(
    state: dict,
    bomber: dict,
    danger: dict[tuple[int, int], int],
) -> set[tuple[int, int]]:
    """Prefer combat power-ups the bomber still lacks."""
    scored: list[tuple[int, tuple[int, int]]] = []
    for p in state.get("powerups") or []:
        cell = (p["x"], p["y"])
        if danger.get(cell) is not None and danger.get(cell, 0) <= ESCAPE_MARGIN:
            continue
        ptype = p.get("type")
        if ptype == "skull":
            continue
        score = POWERUP_BASE.get(ptype, 4)
        if ptype == "throw" and bomber.get("can_throw"):
            score = 2
        elif ptype == "kick" and bomber.get("can_kick"):
            score = 2
        elif ptype == "bomb" and int(bomber.get("max_bombs", 1)) >= 4:
            score = 3
        elif ptype == "range" and int(bomber.get("bomb_range", 1)) >= 5:
            score = 3
        elif ptype == "speed" and int(bomber.get("speed_level", 0)) >= 4:
            score = 3
        scored.append((score, cell))
    if not scored:
        return set()
    scored.sort(key=lambda t: -t[0])
    top = scored[0][0]
    # Take the best tier (and near-ties) so BFS still has options.
    return {c for s, c in scored if s >= top - 2}


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
    *,
    danger: dict[tuple[int, int], int] | None = None,
    heavy_think: bool = True,
) -> tuple[str, bool]:
    """Return (direction, place_bomb).

    Pass a shared ``danger`` map when multiple AIs act in the same tick.
    The engine throttles calls; when invoked, ``heavy_think=True`` runs full
    trap / soft-farm scans. Survival and combat planting always run.
    """
    if danger is None:
        danger = _danger_times(state)
    pos = (bomber["x"], bomber["y"])
    here_lethal = danger.get(pos)

    # 1) Flee any blast covering us — never bomb while threatened.
    #    Power Glove: if carrying, throw (aimed); if standing on a bomb, pick it up.
    if here_lethal is not None:
        if bomber.get("can_throw") and bomber.get("carrying_bomb_id"):
            flee_dir, _ = _find_escape(
                state, bomber, danger, max_steps=MAX_ESCAPE_STEPS + 3
            )
            avoid = flee_dir if flee_dir in DIRECTIONS else None
            throw_dir = _best_throw_direction(
                state, player_id, bomber, avoid_dir=avoid
            )
            if throw_dir:
                return throw_dir, True
            # Fallback: throw opposite of flee, then any legal dir.
            preferred: list[str] = []
            if flee_dir in DIRECTIONS:
                preferred.append(OPPOSITE[flee_dir])
            for key in ("facing", "direction", "next_direction"):
                value = bomber.get(key)
                if value in DIRECTIONS and value not in preferred:
                    preferred.append(value)
            for d in DIRECTIONS:
                if d not in preferred:
                    preferred.append(d)
            for d in preferred:
                if _throw_landing(state, pos[0], pos[1], d) is not None:
                    return d, True
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

    # Aimed throw while safe — don't wander holding a bomb.
    if bomber.get("can_throw") and bomber.get("carrying_bomb_id"):
        throw_dir = _best_throw_direction(state, player_id, bomber)
        if throw_dir:
            return throw_dir, True
        for key in ("facing", "direction", "next_direction", *DIRECTIONS):
            value = key if key in DIRECTIONS else bomber.get(key)
            if value in DIRECTIONS and _throw_landing(state, pos[0], pos[1], value):
                return value, True

    active = sum(1 for b in state.get("bombs") or [] if b.get("owner_id") == player_id)
    max_bombs = int(bomber.get("max_bombs", 1))
    bomb_here = _bomb_cells(state).get(pos)
    can_bomb = (
        active < max_bombs
        and bomb_here is None
        and not bomber.get("carrying_bomb_id")
    )

    enemies = _alive_enemies(state, player_id)
    nearest_enemy_dist = min(
        (_manhattan(pos[0], pos[1], e["x"], e["y"]) for _, e in enemies),
        default=99,
    )

    # Kick a bomb toward enemies when it creates real pressure.
    kick_dir = _best_kick_direction(state, player_id, bomber, danger)
    if kick_dir:
        return kick_dir, False

    # Glove: pick up underfoot/facing bombs mainly for combat or escape utility.
    if bomber.get("can_throw") and not bomber.get("carrying_bomb_id"):
        pick_target = bomb_here
        face = bomber.get("facing") if bomber.get("facing") in DIRECTIONS else "right"
        if pick_target is None or pick_target.get("flight") in ("throw", "kick", "carried"):
            dx, dy = DIRECTIONS[face]
            pick_target = _bomb_cells(state).get((pos[0] + dx, pos[1] + dy))
        if (
            pick_target
            and pick_target.get("flight") not in ("throw", "kick", "carried")
            and nearest_enemy_dist <= 8
            and random.random() < 0.55
        ):
            return face, True

    # 2) Bombing decisions — traps / kills first; soft clears only when safe.
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
                # Plant when escape is comfortable; still plant on longer escapes
                # if the enemy is boxed in nearby.
                if esc_steps is not None and esc_steps <= 5:
                    chance = BOMB_CHANCE_ENEMY
                elif nearest_enemy_dist <= 3:
                    chance = 0.85
                else:
                    chance = 0.7
            elif hit_soft and nearest_enemy_dist >= SOFT_FARM_MIN_ENEMY_DIST:
                chance = BOMB_CHANCE_SOFT
                if int(bomber.get("bomb_range", 1)) <= 2:
                    chance = max(chance, 0.6)
                # Prefer clearing softs that open toward the fight.
                if nearest_enemy_dist <= SOFT_FARM_MIN_ENEMY_DIST + 3:
                    chance *= 0.75

            if active > 0:
                chance *= 0.9 if (trap or hit_enemy) else 0.4

            if chance > 0 and random.random() < chance:
                return esc, True

    # 2b) One-ply plant: step onto a tile that yields a trap/kill next tick.
    if heavy_think:
        approach = _best_plant_approach(state, player_id, bomber, danger)
        if approach:
            return approach, False

    # 3) Trap tiles before power-ups when an enemy is in play.
    if heavy_think and enemies:
        traps = _trap_positions(state, player_id, bomber, danger)
        move, dist = _bfs_to_targets(state, bomber, danger, traps, max_dist=28)
        if move and move != "stop":
            if dist == 0:
                # Already on a trap tile — plant was gated above; hold position.
                return "stop", False
            return move, False

    # 4) Power-ups when not mid-fight (or when missing combat tools).
    missing_tool = not bomber.get("can_throw") or not bomber.get("can_kick")
    if nearest_enemy_dist > 5 or missing_tool:
        powerups = _priority_powerup_targets(state, bomber, danger)
        max_pu = 14 if nearest_enemy_dist > 5 else 8
        move, dist = _bfs_to_targets(state, bomber, danger, powerups, max_dist=18)
        if move and move != "stop" and dist is not None and dist <= max_pu:
            return move, False

    # 5) Hunt enemies — get onto a bombing line (uses predicted positions).
    hunt = _hunting_positions(state, player_id, bomber, danger)
    move, dist = _bfs_to_targets(state, bomber, danger, hunt, max_dist=28)
    if move and move != "stop":
        if dist == 0:
            # On a fire line: if we somehow didn't plant, stay put when roomy.
            if can_bomb:
                ok, esc, _ = _can_escape_after_bomb_with_steps(state, player_id, bomber)
                if ok and esc and _enemy_in_blast_line(state, bomber, player_id):
                    return esc, True
            if _exit_count(state, bomber, pos[0], pos[1]) < 2:
                return _best_safe_direction(state, bomber, danger), False
            return "stop", False
        return move, False

    # 6) Soft-wall farming when enemies are far or we need range.
    if nearest_enemy_dist >= SOFT_FARM_MIN_ENEMY_DIST or int(bomber.get("bomb_range", 1)) < 2:
        if heavy_think or nearest_enemy_dist > 9:
            soft = _soft_targets(state, danger)
            move, _ = _bfs_to_targets(state, bomber, danger, soft, max_dist=20)
            if move and move != "stop":
                return move, False

    # 7) Close the gap — path toward enemy neighborhood (incl. predicted).
    if enemies:
        approach_cells: set[tuple[int, int]] = set()
        for _pid, enemy in enemies:
            for cell in _predicted_enemy_cells(state, enemy):
                for dx, dy in DIRECTIONS.values():
                    approach_cells.add((cell[0] + dx, cell[1] + dy))
                    approach_cells.add((cell[0] + dx * 2, cell[1] + dy * 2))
        # Prefer cells with an escape exit so we don't corner ourselves.
        approach_cells = {
            c
            for c in approach_cells
            if 0 <= c[0] < state["grid_width"]
            and 0 <= c[1] < state["grid_height"]
            and state["grid"][c[1]][c[0]] == TILE_EMPTY
            and _exit_count(state, bomber, c[0], c[1]) >= 1
            and (danger.get(c) is None or danger[c] > ESCAPE_MARGIN)
        }
        move, _ = _bfs_to_targets(state, bomber, danger, approach_cells, max_dist=30)
        if move and move != "stop":
            return move, False

    # 8) Soft walls as fallback (heavy ticks only — full-map scan).
    if heavy_think:
        soft = _soft_targets(state, danger)
        move, _ = _bfs_to_targets(state, bomber, danger, soft, max_dist=25)
        if move and move != "stop":
            return move, False

    return _best_safe_direction(state, bomber, danger), False
