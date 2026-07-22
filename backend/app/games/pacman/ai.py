"""Ghost personalities and Pac-Man seat AI for multiplayer Pac-Man."""

from __future__ import annotations

import random
from typing import Any

from app.games.pacman.maps import is_passable, wrap_through_tunnel

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

DIR_ORDER = ("up", "left", "down", "right")  # classic tie-break preference


def _manhattan(ax: int, ay: int, bx: int, by: int) -> int:
    return abs(ax - bx) + abs(ay - by)


def _living_pacmen(state: dict) -> list[tuple[str, dict]]:
    return [
        (pid, p)
        for pid, p in (state.get("pacmen") or {}).items()
        if p.get("alive") and int(p.get("lives", 0)) > 0 and not p.get("respawn_ticks")
    ]


def _nearest_target_pac(state: dict, x: int, y: int) -> dict | None:
    living = _living_pacmen(state)
    if not living:
        return None
    # Prefer non-powered; fall back to any living.
    non_powered = [(pid, p) for pid, p in living if int(p.get("powered_ticks", 0)) <= 0]
    pool = non_powered or living
    pool.sort(key=lambda item: _manhattan(x, y, item[1]["x"], item[1]["y"]))
    return pool[0][1]


def _ahead(pac: dict, tiles: int, width: int, height: int) -> tuple[int, int]:
    facing = pac.get("facing") or pac.get("direction") or "left"
    dx, dy = DIRECTIONS.get(facing, (-1, 0))
    return (
        max(0, min(width - 1, pac["x"] + dx * tiles)),
        max(0, min(height - 1, pac["y"] + dy * tiles)),
    )


def ghost_target_tile(state: dict, ghost: dict) -> tuple[int, int]:
    """Return the tile this ghost is trying to reach."""
    width = state["grid_width"]
    height = state["grid_height"]
    corners = state.get("scatter_corners") or [(1, 1), (width - 2, 1), (1, height - 2), (width - 2, height - 2)]
    name = ghost.get("name", "blinky")
    mode = ghost.get("mode") or state.get("mode") or "scatter"

    if ghost.get("eaten"):
        home = ghost.get("home") or (state.get("ghost_homes") or [[width // 2, height // 2]])[0]
        return int(home[0]), int(home[1])

    if mode == "frightened" or int(ghost.get("frightened_ticks", 0)) > 0:
        # Random-ish: pick a far corner for a stable wander target.
        return random.choice(corners)

    if mode == "scatter":
        idx = {"blinky": 0, "pinky": 1, "inky": 2, "clyde": 3}.get(name, 0)
        return corners[idx % len(corners)]

    # Chase
    target_pac = _nearest_target_pac(state, ghost["x"], ghost["y"])
    if target_pac is None:
        return corners[0]

    if name == "blinky":
        return target_pac["x"], target_pac["y"]

    if name == "pinky":
        return _ahead(target_pac, 4, width, height)

    if name == "inky":
        # Classic-ish: 2 ahead of pac, then mirror from blinky.
        ax, ay = _ahead(target_pac, 2, width, height)
        blinky = next((g for g in state.get("ghosts") or [] if g.get("name") == "blinky"), None)
        if blinky is None:
            return ax, ay
        return ax + (ax - blinky["x"]), ay + (ay - blinky["y"])

    # Clyde: chase if far, scatter if near.
    dist = _manhattan(ghost["x"], ghost["y"], target_pac["x"], target_pac["y"])
    if dist > 8:
        return target_pac["x"], target_pac["y"]
    return corners[3 % len(corners)]


def _neighbor(
    state: dict, x: int, y: int, direction: str
) -> tuple[int, int] | None:
    dx, dy = DIRECTIONS[direction]
    nx, ny = wrap_through_tunnel(
        x,
        y,
        dx,
        dy,
        state["grid_width"],
        state["grid_height"],
        state.get("tunnels") or [],
    )
    if (nx, ny) == (x, y) and (dx or dy):
        # No movement (blocked edge without tunnel).
        return None
    if not is_passable(state["grid"], nx, ny):
        return None
    # Ghosts may not enter the house unless eaten (eyes).
    return nx, ny


def valid_ghost_dirs(
    state: dict, ghost: dict, *, allow_reverse: bool = False
) -> list[str]:
    facing = ghost.get("direction") or "left"
    opts: list[str] = []
    for d in DIR_ORDER:
        if not allow_reverse and d == OPPOSITE.get(facing):
            continue
        nxt = _neighbor(state, ghost["x"], ghost["y"], d)
        if nxt is None:
            continue
        # Block entering house when not eaten (except leaving via gate outward is ok).
        homes = {(h[0], h[1]) for h in state.get("ghost_homes") or []}
        gate = tuple(state.get("gate") or (-1, -1))
        if (
            not ghost.get("eaten")
            and nxt in homes
            and (ghost["x"], ghost["y"]) not in homes
            and nxt != gate
        ):
            continue
        opts.append(d)
    if not opts:
        # Dead-end: allow reverse.
        rev = OPPOSITE.get(facing)
        if rev and _neighbor(state, ghost["x"], ghost["y"], rev) is not None:
            return [rev]
    return opts


def choose_ghost_direction(state: dict, ghost: dict) -> str:
    mode = ghost.get("mode") or state.get("mode") or "scatter"
    frightened = mode == "frightened" or int(ghost.get("frightened_ticks", 0)) > 0
    allow_reverse = bool(ghost.get("_force_reverse"))
    options = valid_ghost_dirs(state, ghost, allow_reverse=allow_reverse)
    if not options:
        return ghost.get("direction") or "left"

    if frightened and not ghost.get("eaten"):
        return random.choice(options)

    tx, ty = ghost_target_tile(state, ghost)
    best_d = options[0]
    best_dist = 10**9
    for d in options:
        nxt = _neighbor(state, ghost["x"], ghost["y"], d)
        if nxt is None:
            continue
        dist = _manhattan(nxt[0], nxt[1], tx, ty)
        if dist < best_dist:
            best_dist = dist
            best_d = d
    return best_d


def choose_pacman_direction(state: dict, player_id: str, pac: dict[str, Any]) -> str:
    """Heuristic AI: flee nearby ghosts unless powered; else chase pellets / vulnerable ghosts."""
    grid = state["grid"]
    width = state["grid_width"]
    height = state["grid_height"]
    tunnels = state.get("tunnels") or []
    facing = pac.get("facing") or pac.get("direction") or "left"
    powered = int(pac.get("powered_ticks", 0)) > 0

    def step(x: int, y: int, d: str) -> tuple[int, int] | None:
        dx, dy = DIRECTIONS[d]
        nx, ny = wrap_through_tunnel(x, y, dx, dy, width, height, tunnels)
        if (nx, ny) == (x, y) and (dx or dy):
            return None
        if not is_passable(grid, nx, ny):
            return None
        return nx, ny

    options = [d for d in DIRECTIONS if step(pac["x"], pac["y"], d) is not None]
    if not options:
        return facing

    ghosts = [
        g
        for g in state.get("ghosts") or []
        if not g.get("eaten")
    ]
    danger = [
        g
        for g in ghosts
        if int(g.get("frightened_ticks", 0)) <= 0
        and (g.get("mode") or state.get("mode")) != "frightened"
    ]

    def score_dir(d: str) -> float:
        nxt = step(pac["x"], pac["y"], d)
        if nxt is None:
            return -1e9
        nx, ny = nxt
        s = 0.0
        # Prefer not reversing unless necessary.
        if d == OPPOSITE.get(facing):
            s -= 2.0

        if powered:
            for g in ghosts:
                if int(g.get("frightened_ticks", 0)) > 0 or g.get("mode") == "frightened":
                    dist = _manhattan(nx, ny, g["x"], g["y"])
                    s += max(0, 12 - dist) * 3
        else:
            for g in danger:
                dist = _manhattan(nx, ny, g["x"], g["y"])
                if dist <= 1:
                    s -= 100
                elif dist <= 4:
                    s -= (5 - dist) * 8

        pellets = state.get("pellets") or []
        power = state.get("power_pellets") or []
        if 0 <= ny < height and 0 <= nx < width:
            if power[ny][nx]:
                s += 25
            elif pellets[ny][nx]:
                s += 8

        # Soft pull toward nearest pellet.
        best_pellet = 10**9
        for y in range(height):
            for x in range(width):
                if (y < len(pellets) and x < len(pellets[y]) and pellets[y][x]) or (
                    y < len(power) and x < len(power[y]) and power[y][x]
                ):
                    best_pellet = min(best_pellet, _manhattan(nx, ny, x, y))
        if best_pellet < 10**9:
            s += max(0, 20 - best_pellet) * 0.4

        # Opportunistically bump non-powered rivals when powered.
        if powered:
            for pid, other in _living_pacmen(state):
                if pid == player_id:
                    continue
                if int(other.get("powered_ticks", 0)) > 0:
                    continue
                dist = _manhattan(nx, ny, other["x"], other["y"])
                s += max(0, 8 - dist) * 2

        return s + random.random() * 0.2

    return max(options, key=score_dir)
