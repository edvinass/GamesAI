"""Bomberman arena definitions — distinct layouts selectable from the lobby."""

from __future__ import annotations

import random
from typing import Any, Callable

TILE_EMPTY = 0
TILE_HARD = 1
TILE_SOFT = 2


def _border(grid: list[list[int]]) -> None:
    height = len(grid)
    width = len(grid[0])
    for x in range(width):
        grid[0][x] = TILE_HARD
        grid[height - 1][x] = TILE_HARD
    for y in range(height):
        grid[y][0] = TILE_HARD
        grid[y][width - 1] = TILE_HARD


def _empty_grid(width: int, height: int) -> list[list[int]]:
    grid = [[TILE_EMPTY for _ in range(width)] for _ in range(height)]
    _border(grid)
    return grid


def _scatter_soft(grid: list[list[int]], soft_fill: float, hard_cells: set[tuple[int, int]]) -> None:
    height = len(grid)
    width = len(grid[0])
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if (x, y) in hard_cells:
                continue
            if grid[y][x] != TILE_EMPTY:
                continue
            if random.random() < soft_fill:
                grid[y][x] = TILE_SOFT


def _set_hard(grid: list[list[int]], cells: set[tuple[int, int]]) -> None:
    height = len(grid)
    width = len(grid[0])
    for x, y in cells:
        if 0 < x < width - 1 and 0 < y < height - 1:
            grid[y][x] = TILE_HARD


def _classic_pillars(width: int, height: int) -> set[tuple[int, int]]:
    return {
        (x, y)
        for y in range(2, height - 1, 2)
        for x in range(2, width - 1, 2)
    }


def _default_spawns(width: int, height: int) -> list[tuple[int, int]]:
    return [
        (1, 1),
        (width - 2, 1),
        (1, height - 2),
        (width - 2, height - 2),
        (width // 2, 1),
        (width // 2, height - 2),
        (1, height // 2),
        (width - 2, height // 2),
    ]


def clear_spawn_zone(grid: list[list[int]], sx: int, sy: int) -> None:
    height = len(grid)
    width = len(grid[0])
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            x, y = sx + dx, sy + dy
            if 0 < x < width - 1 and 0 < y < height - 1:
                if grid[y][x] != TILE_HARD:
                    grid[y][x] = TILE_EMPTY
    grid[sy][sx] = TILE_EMPTY
    cx, cy = width // 2, height // 2
    step_x = 0 if sx == cx else (1 if sx < cx else -1)
    step_y = 0 if sy == cy else (1 if sy < cy else -1)
    if step_x and grid[sy][sx + step_x] != TILE_HARD:
        grid[sy][sx + step_x] = TILE_EMPTY
    if step_y and grid[sy + step_y][sx] != TILE_HARD:
        grid[sy + step_y][sx] = TILE_EMPTY


def _build_classic(width: int, height: int, soft_fill: float) -> list[list[int]]:
    hard = _classic_pillars(width, height)
    grid = _empty_grid(width, height)
    _set_hard(grid, hard)
    _scatter_soft(grid, soft_fill, hard)
    return grid


def _build_open_field(width: int, height: int, soft_fill: float) -> list[list[int]]:
    """Sparse pillars — wide sightlines and chaotic mid fights."""
    hard: set[tuple[int, int]] = set()
    for y in range(3, height - 2, 3):
        for x in range(3, width - 2, 3):
            hard.add((x, y))
    # A few extra anchors
    hard.add((width // 2, height // 2))
    grid = _empty_grid(width, height)
    _set_hard(grid, hard)
    _scatter_soft(grid, soft_fill * 0.75, hard)
    return grid


def _build_crossroads(width: int, height: int, soft_fill: float) -> list[list[int]]:
    """Open cross through the center; denser soft blocks in the four quadrants."""
    hard = _classic_pillars(width, height)
    # Carve a clear cross (remove pillars on mid row/col)
    mx, my = width // 2, height // 2
    hard = {(x, y) for x, y in hard if x != mx and y != my}
    grid = _empty_grid(width, height)
    _set_hard(grid, hard)
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if (x, y) in hard:
                continue
            if x == mx or y == my:
                grid[y][x] = TILE_EMPTY
                continue
            if random.random() < soft_fill * 1.05:
                grid[y][x] = TILE_SOFT
    return grid


def _build_fortress(width: int, height: int, soft_fill: float) -> list[list[int]]:
    """Central keep with gated entrances — control the middle."""
    hard = _classic_pillars(width, height)
    mx, my = width // 2, height // 2
    # Inner ring
    for x in range(mx - 3, mx + 4):
        hard.add((x, my - 3))
        hard.add((x, my + 3))
    for y in range(my - 3, my + 4):
        hard.add((mx - 3, y))
        hard.add((mx + 3, y))
    # Gates (openings)
    for gate in [(mx, my - 3), (mx, my + 3), (mx - 3, my), (mx + 3, my)]:
        hard.discard(gate)
    # Clear interior floor pillars
    hard = {
        (x, y)
        for x, y in hard
        if not (mx - 2 <= x <= mx + 2 and my - 2 <= y <= my + 2)
    }
    grid = _empty_grid(width, height)
    _set_hard(grid, hard)
    _scatter_soft(grid, soft_fill, hard)
    # Keep the keep interior mostly open
    for y in range(my - 2, my + 3):
        for x in range(mx - 2, mx + 3):
            if grid[y][x] != TILE_HARD:
                grid[y][x] = TILE_EMPTY
    return grid


def _build_labyrinth(width: int, height: int, soft_fill: float) -> list[list[int]]:
    """Dense soft maze with classic pillars — slow, tactical clears."""
    hard = _classic_pillars(width, height)
    grid = _empty_grid(width, height)
    _set_hard(grid, hard)
    _scatter_soft(grid, min(0.88, soft_fill + 0.22), hard)
    return grid


def _build_islands(width: int, height: int, soft_fill: float) -> list[list[int]]:
    """Four corner pockets linked by narrow bridges."""
    hard: set[tuple[int, int]] = set()
    mx, my = width // 2, height // 2
    # Thick hard walls dividing into quadrants, with bridge gaps
    for x in range(1, width - 1):
        if abs(x - mx) > 1:
            hard.add((x, my))
    for y in range(1, height - 1):
        if abs(y - my) > 1:
            hard.add((mx, y))
    # Extra pillars inside each island
    for ox, oy in [(0, 0), (mx, 0), (0, my), (mx, my)]:
        for y in range(oy + 2, oy + my - 1, 2):
            for x in range(ox + 2, ox + mx - 1, 2):
                if 0 < x < width - 1 and 0 < y < height - 1:
                    hard.add((x, y))
    grid = _empty_grid(width, height)
    _set_hard(grid, hard)
    _scatter_soft(grid, soft_fill, hard)
    # Ensure bridges stay clear
    for x in range(mx - 1, mx + 2):
        for y in range(my - 1, my + 2):
            if 0 < x < width - 1 and 0 < y < height - 1 and (x, y) not in hard:
                grid[y][x] = TILE_EMPTY
    return grid


def _build_diamond(width: int, height: int, soft_fill: float) -> list[list[int]]:
    """Diamond hard-wall ring around center with open outer ring."""
    hard: set[tuple[int, int]] = set()
    mx, my = width // 2, height // 2
    radius = min(mx, my) - 2
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            d = abs(x - mx) + abs(y - my)
            if d == radius or d == radius - 2:
                hard.add((x, y))
    # Card openings on the outer diamond
    for gate in [
        (mx, my - radius),
        (mx, my + radius),
        (mx - radius, my),
        (mx + radius, my),
    ]:
        hard.discard(gate)
    grid = _empty_grid(width, height)
    _set_hard(grid, hard)
    _scatter_soft(grid, soft_fill * 0.9, hard)
    return grid


def _build_narrows(width: int, height: int, soft_fill: float) -> list[list[int]]:
    """Horizontal choke corridors — bombs are extremely deadly."""
    hard: set[tuple[int, int]] = set()
    for y in range(2, height - 1, 2):
        for x in range(1, width - 1):
            # Leave 1-cell gaps every few columns
            if (x + y) % 4 != 1:
                hard.add((x, y))
    # Vertical struts
    for x in range(3, width - 2, 4):
        for y in range(1, height - 1):
            if y % 2 == 1:
                hard.add((x, y))
    grid = _empty_grid(width, height)
    _set_hard(grid, hard)
    _scatter_soft(grid, soft_fill * 0.55, hard)
    return grid


def _build_arena(width: int, height: int, soft_fill: float) -> list[list[int]]:
    """Coliseum: open center circle, soft ring, outer classic pillars."""
    hard = _classic_pillars(width, height)
    mx, my = width // 2, height // 2
    # Remove pillars from center arena
    hard = {
        (x, y)
        for x, y in hard
        if abs(x - mx) + abs(y - my) > 4
    }
    grid = _empty_grid(width, height)
    _set_hard(grid, hard)
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if (x, y) in hard:
                continue
            dist = abs(x - mx) + abs(y - my)
            if dist <= 3:
                grid[y][x] = TILE_EMPTY
            elif dist <= 5:
                if random.random() < soft_fill * 1.1:
                    grid[y][x] = TILE_SOFT
            else:
                if random.random() < soft_fill:
                    grid[y][x] = TILE_SOFT
    return grid


Builder = Callable[[int, int, float], list[list[int]]]

MAPS: dict[str, dict[str, Any]] = {
    "classic": {
        "id": "classic",
        "name": "Classic",
        "description": "Standard pillar grid — balanced and familiar.",
        "difficulty": "standard",
        "width": 15,
        "height": 13,
        "soft_fill": 0.62,
        "builder": _build_classic,
    },
    "open_field": {
        "id": "open_field",
        "name": "Open Field",
        "description": "Sparse cover and long sightlines — raw duels.",
        "difficulty": "standard",
        "width": 15,
        "height": 13,
        "soft_fill": 0.45,
        "builder": _build_open_field,
    },
    "crossroads": {
        "id": "crossroads",
        "name": "Crossroads",
        "description": "Clear mid lanes with packed quadrants.",
        "difficulty": "standard",
        "width": 15,
        "height": 13,
        "soft_fill": 0.68,
        "builder": _build_crossroads,
    },
    "fortress": {
        "id": "fortress",
        "name": "Fortress",
        "description": "A gated keep in the center — hold or siege.",
        "difficulty": "hard",
        "width": 15,
        "height": 13,
        "soft_fill": 0.58,
        "builder": _build_fortress,
    },
    "labyrinth": {
        "id": "labyrinth",
        "name": "Labyrinth",
        "description": "Dense soft walls — carve your path slowly.",
        "difficulty": "hard",
        "width": 15,
        "height": 13,
        "soft_fill": 0.82,
        "builder": _build_labyrinth,
    },
    "islands": {
        "id": "islands",
        "name": "Islands",
        "description": "Four pockets linked by narrow bridges.",
        "difficulty": "hard",
        "width": 15,
        "height": 13,
        "soft_fill": 0.6,
        "builder": _build_islands,
    },
    "diamond": {
        "id": "diamond",
        "name": "Diamond",
        "description": "Concentric diamond walls with choke openings.",
        "difficulty": "standard",
        "width": 15,
        "height": 13,
        "soft_fill": 0.55,
        "builder": _build_diamond,
    },
    "narrows": {
        "id": "narrows",
        "name": "The Narrows",
        "description": "Tight corridors where one bomb ends everything.",
        "difficulty": "brutal",
        "width": 15,
        "height": 13,
        "soft_fill": 0.4,
        "builder": _build_narrows,
    },
    "arena": {
        "id": "arena",
        "name": "Arena",
        "description": "Open coliseum center with a soft outer ring.",
        "difficulty": "standard",
        "width": 15,
        "height": 13,
        "soft_fill": 0.58,
        "builder": _build_arena,
    },
}


def list_maps() -> list[dict[str, Any]]:
    return [
        {
            "id": m["id"],
            "name": m["name"],
            "description": m["description"],
            "difficulty": m["difficulty"],
            "width": m["width"],
            "height": m["height"],
        }
        for m in MAPS.values()
    ]


def get_map(map_id: str) -> dict[str, Any]:
    if map_id not in MAPS:
        raise ValueError(f"Unknown map: {map_id}")
    return MAPS[map_id]


def build_map_grid(map_id: str, soft_fill: float | None = None) -> tuple[list[list[int]], list[tuple[int, int]], dict[str, Any]]:
    """Return (grid, spawns, map_meta)."""
    meta = get_map(map_id)
    width = int(meta["width"])
    height = int(meta["height"])
    fill = float(soft_fill if soft_fill is not None else meta["soft_fill"])
    builder: Builder = meta["builder"]
    spawns = _default_spawns(width, height)
    grid = builder(width, height, fill)
    for sx, sy in spawns:
        clear_spawn_zone(grid, sx, sy)
    return grid, spawns, meta
