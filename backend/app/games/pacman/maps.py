"""Pac-Man maze definitions — walls, pellets, spawns, ghost house, tunnels."""

from __future__ import annotations

from typing import Any, Callable

TILE_PATH = 0
TILE_WALL = 1

# Legend for ASCII mazes:
#   # wall
#   . pellet path
#   o power pellet
#   = empty path (no pellet) — ghost house interior / spawn clears
#   G ghost house gate (path, no pellet)
#   P pac-man spawn (path, no pellet)
#   H ghost home cell (path, no pellet)


def _parse_ascii(rows: list[str]) -> dict[str, Any]:
    height = len(rows)
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ValueError("Maze rows must be equal width")

    grid = [[TILE_WALL for _ in range(width)] for _ in range(height)]
    pellets = [[False for _ in range(width)] for _ in range(height)]
    power_pellets = [[False for _ in range(width)] for _ in range(height)]
    pac_spawns: list[tuple[int, int]] = []
    ghost_homes: list[tuple[int, int]] = []
    gate: tuple[int, int] | None = None

    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                grid[y][x] = TILE_WALL
            elif ch in ".o=GPH":
                grid[y][x] = TILE_PATH
                if ch == ".":
                    pellets[y][x] = True
                elif ch == "o":
                    power_pellets[y][x] = True
                elif ch == "P":
                    pac_spawns.append((x, y))
                elif ch == "H":
                    ghost_homes.append((x, y))
                elif ch == "G":
                    gate = (x, y)
            else:
                raise ValueError(f"Unknown maze char {ch!r} at {(x, y)}")

    # Side tunnels: path cells on left/right edges of the same row.
    tunnels: list[dict[str, int]] = []
    for y in range(height):
        if grid[y][0] == TILE_PATH and grid[y][width - 1] == TILE_PATH:
            tunnels.append({"y": y, "left_x": 0, "right_x": width - 1})

    if not pac_spawns:
        raise ValueError("Maze needs at least one P spawn")
    if not ghost_homes:
        raise ValueError("Maze needs at least one H ghost home")
    if gate is None:
        # Default gate = cell above the first ghost home if path.
        hx, hy = ghost_homes[0]
        if hy > 0 and grid[hy - 1][hx] == TILE_PATH:
            gate = (hx, hy - 1)
        else:
            gate = ghost_homes[0]

    # Scatter corners (nearest path cells to each corner).
    corners = [
        _nearest_path(grid, 1, 1),
        _nearest_path(grid, width - 2, 1),
        _nearest_path(grid, 1, height - 2),
        _nearest_path(grid, width - 2, height - 2),
    ]

    return {
        "grid": grid,
        "pellets": pellets,
        "power_pellets": power_pellets,
        "pac_spawns": pac_spawns,
        "ghost_homes": ghost_homes,
        "gate": gate,
        "tunnels": tunnels,
        "scatter_corners": corners,
        "width": width,
        "height": height,
    }


def _nearest_path(grid: list[list[int]], tx: int, ty: int) -> tuple[int, int]:
    height = len(grid)
    width = len(grid[0])
    best: tuple[int, int] | None = None
    best_d = 10**9
    for y in range(height):
        for x in range(width):
            if grid[y][x] != TILE_PATH:
                continue
            d = abs(x - tx) + abs(y - ty)
            if d < best_d:
                best_d = d
                best = (x, y)
    assert best is not None
    return best


def _classic_rows() -> list[str]:
    # Compact classic-inspired maze (19×21). Outer ring stays rectangular;
    # side tunnels are single-cell openings that connect through (no wing stubs).
    return [
        "###################",
        "#........#........#",
        "#o##.###.#.###.##o#",
        "#.................#",
        "#.##.#.#####.#.##.#",
        "#....#...#...#....#",
        "####.###.#.###.####",
        "=.................=",
        "####.#.##G##.#.####",
        "#......#HHH#......#",
        "####.#.#####.#.####",
        "=.................=",
        "####.#.#####.#.####",
        "#........#........#",
        "#.##.###.#.###.##.#",
        "#o.#.....P.....#.o#",
        "##.#.#.#####.#.#.##",
        "#....#...#...#....#",
        "#.######.#.######.#",
        "#.................#",
        "###################",
    ]


def _open_rows() -> list[str]:
    return [
        "###################",
        "#o...............o#",
        "#.###.#######.###.#",
        "#.................#",
        "#.##.#.#####.#.##.#",
        "#....#...P...#....#",
        "####.###.#.###.####",
        "=........G........=",
        "####.###HHH###.####",
        "#.................#",
        "#.##.#########.##.#",
        "#....#.......#....#",
        "#.####.#####.####.#",
        "#o...............o#",
        "###################",
    ]


def _labyrinth_rows() -> list[str]:
    return [
        "#####################",
        "#.........#.........#",
        "#o###.###.#.###.###o#",
        "#.#...............#.#",
        "#...###.#.#.#.###...#",
        "###.#.#.......#.#.###",
        "#...#.#.#####.#.#...#",
        "#.###.#...P...#.###.#",
        "#.....###.#.###.....#",
        "###.#=====G=====#.###",
        "=.....###HHH###.....=",
        "###.#===========#.###",
        "#.....###.#.###.....#",
        "#.###.#.......#.###.#",
        "#...#.#.#####.#.#...#",
        "###.#.#.......#.#.###",
        "#...###.#.#.#.###...#",
        "#.#...............#.#",
        "#o###.###.#.###.###o#",
        "#.........#.........#",
        "#####################",
    ]


def _build_from_rows(rows: list[str]) -> dict[str, Any]:
    return _parse_ascii(rows)


def _extra_pac_spawns(grid: list[list[int]], primary: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Pad spawn list up to 4 using corner-ish path cells."""
    height = len(grid)
    width = len(grid[0])
    used = set(primary)
    candidates = [
        _nearest_path(grid, 2, 2),
        _nearest_path(grid, width - 3, 2),
        _nearest_path(grid, 2, height - 3),
        _nearest_path(grid, width - 3, height - 3),
        _nearest_path(grid, width // 2, height - 3),
        _nearest_path(grid, width // 2, 2),
    ]
    out = list(primary)
    for c in candidates:
        if c in used:
            continue
        out.append(c)
        used.add(c)
        if len(out) >= 4:
            break
    return out


Builder = Callable[[], dict[str, Any]]


def _wrap_builder(rows_fn: Callable[[], list[str]]) -> Builder:
    def build() -> dict[str, Any]:
        data = _build_from_rows(rows_fn())
        data["pac_spawns"] = _extra_pac_spawns(data["grid"], data["pac_spawns"])
        return data

    return build


MAPS: dict[str, dict[str, Any]] = {
    "classic": {
        "id": "classic",
        "name": "Classic",
        "description": "Compact arcade maze with side tunnels and a central ghost house.",
        "difficulty": "standard",
        "width": 19,
        "height": 21,
        "builder": _wrap_builder(_classic_rows),
    },
    "open": {
        "id": "open",
        "name": "Open Field",
        "description": "Wider corridors — faster chases, less cover.",
        "difficulty": "standard",
        "width": 19,
        "height": 15,
        "builder": _wrap_builder(_open_rows),
    },
    "labyrinth": {
        "id": "labyrinth",
        "name": "Labyrinth",
        "description": "Tighter corridors and longer paths — brutal for the hunted.",
        "difficulty": "hard",
        "width": 21,
        "height": 21,
        "builder": _wrap_builder(_labyrinth_rows),
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


def build_map(map_id: str) -> dict[str, Any]:
    try:
        meta = get_map(map_id)
    except ValueError:
        meta = get_map("classic")
        map_id = "classic"
    built = meta["builder"]()
    return {
        **built,
        "map_id": map_id,
        "map_name": meta["name"],
    }


def wrap_through_tunnel(
    x: int,
    y: int,
    dx: int,
    dy: int,
    width: int,
    height: int,
    tunnels: list[dict[str, int]],
) -> tuple[int, int]:
    """Apply one-step movement with horizontal tunnel wrap."""
    nx, ny = x + dx, y + dy
    if dy == 0 and dx != 0:
        for t in tunnels:
            if y != t["y"]:
                continue
            if nx < 0 or (x == t["left_x"] and dx < 0):
                return t["right_x"], y
            if nx >= width or (x == t["right_x"] and dx > 0):
                return t["left_x"], y
    if 0 <= nx < width and 0 <= ny < height:
        return nx, ny
    return x, y  # blocked / no wrap


def is_passable(grid: list[list[int]], x: int, y: int) -> bool:
    if y < 0 or y >= len(grid) or x < 0 or x >= len(grid[0]):
        return False
    return grid[y][x] == TILE_PATH


def pellet_count(pellets: list[list[bool]], power: list[list[bool]]) -> int:
    total = 0
    for row in pellets:
        total += sum(1 for c in row if c)
    for row in power:
        total += sum(1 for c in row if c)
    return total
