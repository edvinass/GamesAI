"""Map definitions for RoboRally."""

from __future__ import annotations

from typing import Any


def _border(width: int, height: int) -> list[list[int]]:
    walls = (
        [[x, 0] for x in range(width)]
        + [[x, height - 1] for x in range(width)]
        + [[0, y] for y in range(1, height - 1)]
        + [[width - 1, y] for y in range(1, height - 1)]
    )
    return walls


def _dedupe(cells: list[list[int]]) -> list[list[int]]:
    seen: set[tuple[int, int]] = set()
    out: list[list[int]] = []
    for x, y in cells:
        key = (x, y)
        if key in seen:
            continue
        seen.add(key)
        out.append([x, y])
    return out


MAPS: dict[str, dict[str, Any]] = {
    "factory_floor": {
        "id": "factory_floor",
        "name": "Factory Floor",
        "description": "Winding halls with mid-board chokepoints — classic race.",
        "difficulty": "standard",
        "width": 13,
        "height": 11,
        "walls": _dedupe(
            _border(13, 11)
            + [
                # Upper machine banks
                [3, 2],
                [4, 2],
                [5, 2],
                [7, 2],
                [8, 2],
                [9, 2],
                [3, 3],
                [9, 3],
                # Center pillars / antenna plaza
                [5, 4],
                [7, 4],
                [5, 5],
                [7, 5],
                [5, 6],
                [7, 6],
                # Lower machine banks
                [3, 7],
                [4, 7],
                [5, 7],
                [7, 7],
                [8, 7],
                [9, 7],
                [3, 8],
                [9, 8],
            ]
        ),
        "checkpoints": [
            [2, 2, 1],
            [10, 5, 2],
            [2, 8, 3],
        ],
        "antenna": [6, 5],
        "starts": [
            {"x": 3, "y": 9, "facing": "N", "priority": 0},
            {"x": 5, "y": 9, "facing": "N", "priority": 1},
            {"x": 8, "y": 9, "facing": "N", "priority": 2},
            {"x": 10, "y": 9, "facing": "N", "priority": 3},
        ],
    },
    "open_grid": {
        "id": "open_grid",
        "name": "Open Grid",
        "description": "Short board with a few pillars — good for first races.",
        "difficulty": "easy",
        "width": 11,
        "height": 9,
        "walls": _dedupe(
            _border(11, 9)
            + [
                [3, 3],
                [7, 3],
                [3, 5],
                [7, 5],
            ]
        ),
        "checkpoints": [
            [2, 1, 1],
            [8, 1, 2],
            [5, 6, 3],
        ],
        "antenna": [5, 4],
        "starts": [
            {"x": 2, "y": 7, "facing": "N", "priority": 0},
            {"x": 4, "y": 7, "facing": "N", "priority": 1},
            {"x": 6, "y": 7, "facing": "N", "priority": 2},
            {"x": 8, "y": 7, "facing": "N", "priority": 3},
        ],
    },
    "chop_shop": {
        "id": "chop_shop",
        "name": "Chop Shop",
        "description": "Tight corridors and dead ends — plan every turn.",
        "difficulty": "hard",
        "width": 12,
        "height": 12,
        "walls": _dedupe(
            _border(12, 12)
            + [
                # Vertical maze ribs
                [2, 2],
                [2, 3],
                [2, 4],
                [2, 5],
                [4, 4],
                [4, 5],
                [4, 6],
                [4, 7],
                [4, 8],
                [6, 2],
                [6, 3],
                [6, 4],
                [6, 5],
                [6, 6],
                [8, 5],
                [8, 6],
                [8, 7],
                [8, 8],
                [8, 9],
                [9, 2],
                [9, 3],
                # Horizontal shelves
                [3, 2],
                [5, 2],
                [7, 2],
                [3, 9],
                [5, 9],
                [7, 9],
                [9, 9],
            ]
        ),
        "checkpoints": [
            [3, 3, 1],
            [10, 4, 2],
            [5, 7, 3],
            [3, 10, 4],
        ],
        "antenna": [7, 6],
        "starts": [
            {"x": 2, "y": 10, "facing": "N", "priority": 0},
            {"x": 5, "y": 10, "facing": "N", "priority": 1},
            {"x": 7, "y": 10, "facing": "N", "priority": 2},
            {"x": 10, "y": 10, "facing": "N", "priority": 3},
        ],
    },
    "twin_lanes": {
        "id": "twin_lanes",
        "name": "Twin Lanes",
        "description": "Two side routes that meet at the finish — bumping is common.",
        "difficulty": "standard",
        "width": 13,
        "height": 10,
        "walls": _dedupe(
            _border(13, 10)
            + [
                # Center divider with gaps
                [6, 1],
                [6, 2],
                [6, 3],
                [6, 5],
                [6, 6],
                [6, 7],
                [6, 8],
                # Lane obstacles
                [3, 3],
                [3, 4],
                [9, 3],
                [9, 4],
                [3, 6],
                [3, 7],
                [9, 6],
                [9, 7],
            ]
        ),
        "checkpoints": [
            [2, 2, 1],
            [10, 2, 2],
            [6, 4, 3],
            [11, 8, 4],
        ],
        "antenna": [1, 5],
        "starts": [
            {"x": 2, "y": 8, "facing": "N", "priority": 0},
            {"x": 4, "y": 8, "facing": "N", "priority": 1},
            {"x": 8, "y": 8, "facing": "N", "priority": 2},
            {"x": 10, "y": 8, "facing": "N", "priority": 3},
        ],
    },
    "grand_prix": {
        "id": "grand_prix",
        "name": "Grand Prix",
        "description": "Large loop track for longer races and bigger crowds.",
        "difficulty": "long",
        "width": 15,
        "height": 12,
        "walls": _dedupe(
            _border(15, 12)
            + [
                # Inner oval (infield blocked; race the outer lane)
                *[[x, 3] for x in range(4, 11)],
                *[[x, 8] for x in range(4, 11)],
                *[[4, y] for y in range(4, 8)],
                *[[10, y] for y in range(4, 8)],
                # Lane obstacles
                [2, 5],
                [12, 5],
                [7, 1],
                [2, 2],
                [12, 2],
                [2, 9],
                [12, 9],
            ]
        ),
        "checkpoints": [
            [3, 1, 1],
            [13, 4, 2],
            [12, 10, 3],
            [1, 6, 4],
        ],
        "antenna": [7, 5],
        "starts": [
            {"x": 5, "y": 10, "facing": "N", "priority": 0},
            {"x": 6, "y": 10, "facing": "N", "priority": 1},
            {"x": 8, "y": 10, "facing": "N", "priority": 2},
            {"x": 9, "y": 10, "facing": "N", "priority": 3},
        ],
    },
}


def list_maps() -> list[dict[str, Any]]:
    """Lobby-facing map summaries, including geometry for mini-previews."""
    summaries: list[dict[str, Any]] = []
    for m in MAPS.values():
        summaries.append(
            {
                "id": m["id"],
                "name": m["name"],
                "description": m.get("description", ""),
                "difficulty": m.get("difficulty", "standard"),
                "width": m["width"],
                "height": m["height"],
                "checkpoint_count": len(m["checkpoints"]),
                "walls": [list(w) for w in m["walls"]],
                "checkpoints": [list(c) for c in m["checkpoints"]],
                "antenna": list(m["antenna"]),
                "starts": [
                    {"x": s["x"], "y": s["y"], "facing": s["facing"]} for s in m["starts"]
                ],
            }
        )
    return summaries


def get_map(map_id: str) -> dict[str, Any]:
    if map_id not in MAPS:
        raise ValueError(f"Unknown map: {map_id}")
    return MAPS[map_id]


def board_for_map(map_id: str) -> dict[str, Any]:
    m = get_map(map_id)
    return {
        "id": m["id"],
        "name": m["name"],
        "width": m["width"],
        "height": m["height"],
        "walls": [list(w) for w in m["walls"]],
        "checkpoints": [list(c) for c in m["checkpoints"]],
        "antenna": list(m["antenna"]),
    }


def validate_map_definition(map_def: dict[str, Any]) -> None:
    """Raise ValueError if a map has overlapping / blocked key cells."""
    width = int(map_def["width"])
    height = int(map_def["height"])
    walls = {(int(x), int(y)) for x, y in map_def["walls"]}
    reserved: dict[tuple[int, int], str] = {}

    def claim(x: int, y: int, label: str, *, allow_overlap_antenna: bool = False) -> None:
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"{label} out of bounds at ({x},{y})")
        if (x, y) in walls:
            raise ValueError(f"{label} sits on a wall at ({x},{y})")
        if (x, y) in reserved:
            other = reserved[(x, y)]
            if allow_overlap_antenna and other == "antenna":
                return
            raise ValueError(f"{label} overlaps {other} at ({x},{y})")
        reserved[(x, y)] = label

    ax, ay = int(map_def["antenna"][0]), int(map_def["antenna"][1])
    claim(ax, ay, "antenna")

    seen_nums: set[int] = set()
    checkpoints: list[tuple[int, int, int]] = []
    for raw in map_def["checkpoints"]:
        x, y, num = int(raw[0]), int(raw[1]), int(raw[2])
        if num in seen_nums:
            raise ValueError(f"Duplicate checkpoint number {num}")
        seen_nums.add(num)
        # Antenna is decorative for priority; a checkpoint may share its cell.
        claim(x, y, f"checkpoint {num}", allow_overlap_antenna=True)
        checkpoints.append((x, y, num))

    if seen_nums != set(range(1, len(seen_nums) + 1)):
        raise ValueError("Checkpoints must be numbered 1..N without gaps")

    starts = map_def["starts"]
    if len(starts) < 4:
        raise ValueError("Maps need at least 4 start pads")
    start_cells: list[tuple[int, int]] = []
    for i, start in enumerate(starts):
        sx, sy = int(start["x"]), int(start["y"])
        claim(sx, sy, f"start {i}")
        if start["facing"] not in ("N", "E", "S", "W"):
            raise ValueError(f"Invalid facing on start {i}")
        start_cells.append((sx, sy))

    reachable = _flood_fill(width, height, walls, start_cells)
    for x, y, num in checkpoints:
        if (x, y) not in reachable:
            raise ValueError(f"Checkpoint {num} unreachable from start pads")


def _flood_fill(
    width: int,
    height: int,
    walls: set[tuple[int, int]],
    starts: list[tuple[int, int]],
) -> set[tuple[int, int]]:
    stack = list(starts)
    seen: set[tuple[int, int]] = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or (x, y) in walls:
            continue
        if not (0 <= x < width and 0 <= y < height):
            continue
        seen.add((x, y))
        stack.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])
    return seen
