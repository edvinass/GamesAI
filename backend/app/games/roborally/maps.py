"""Map definitions for RoboRally."""

from __future__ import annotations

from typing import Any

MAPS: dict[str, dict[str, Any]] = {
    "factory_floor": {
        "id": "factory_floor",
        "name": "Factory Floor",
        "width": 13,
        "height": 11,
        "walls": (
            # Border
            *[[x, 0] for x in range(13)],
            *[[x, 10] for x in range(13)],
            *[[0, y] for y in range(1, 10)],
            *[[12, y] for y in range(1, 10)],
            # Inner obstacles
            [3, 2], [4, 2], [5, 2],
            [7, 2], [8, 2], [9, 2],
            [3, 3], [5, 3], [7, 3], [9, 3],
            [3, 4], [5, 4], [7, 4], [9, 4],
            [5, 5], [7, 5],
            [3, 6], [4, 6], [5, 6],
            [7, 6], [8, 6], [9, 6],
            [5, 7], [7, 7],
        ),
        "checkpoints": [
            [2, 1, 1],
            [10, 4, 2],
            [2, 8, 3],
        ],
        "antenna": [6, 5],
        "starts": [
            {"x": 2, "y": 9, "facing": "N", "priority": 0},
            {"x": 5, "y": 9, "facing": "N", "priority": 1},
            {"x": 8, "y": 9, "facing": "N", "priority": 2},
            {"x": 10, "y": 9, "facing": "N", "priority": 3},
        ],
    },
    "open_grid": {
        "id": "open_grid",
        "name": "Open Grid",
        "width": 11,
        "height": 9,
        "walls": (
            *[[x, 0] for x in range(11)],
            *[[x, 8] for x in range(11)],
            *[[0, y] for y in range(1, 8)],
            *[[10, y] for y in range(1, 8)],
            [5, 3], [5, 4], [5, 5],
        ),
        "checkpoints": [
            [2, 1, 1],
            [8, 1, 2],
            [5, 7, 3],
        ],
        "antenna": [5, 4],
        "starts": [
            {"x": 2, "y": 6, "facing": "N", "priority": 0},
            {"x": 5, "y": 6, "facing": "N", "priority": 1},
            {"x": 8, "y": 6, "facing": "N", "priority": 2},
            {"x": 9, "y": 6, "facing": "N", "priority": 3},
        ],
    },
}


def list_maps() -> list[dict[str, str]]:
    return [{"id": m["id"], "name": m["name"]} for m in MAPS.values()]


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
