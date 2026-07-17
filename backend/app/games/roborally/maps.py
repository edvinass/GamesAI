"""Map definitions for RoboRally with classic board elements."""

from __future__ import annotations

from typing import Any


def _border_edges(width: int, height: int) -> list[dict[str, Any]]:
    """Seal the playable grid with perimeter edge walls."""
    walls: list[dict[str, Any]] = []
    for x in range(width):
        walls.append({"x": x, "y": 0, "dir": "N"})
        walls.append({"x": x, "y": height - 1, "dir": "S"})
    for y in range(height):
        walls.append({"x": 0, "y": y, "dir": "W"})
        walls.append({"x": width - 1, "y": y, "dir": "E"})
    return walls


def _wall(x: int, y: int, *dirs: str) -> list[dict[str, Any]]:
    return [{"x": x, "y": y, "dir": d} for d in dirs]


def _belt(x: int, y: int, direction: str, *, express: bool = False, rotate: str = "none") -> dict[str, Any]:
    return {"x": x, "y": y, "dir": direction, "express": express, "rotate": rotate}


MAPS: dict[str, dict[str, Any]] = {
    "factory_floor": {
        "id": "factory_floor",
        "name": "Factory Floor",
        "description": "Conveyors, gears, and a workshop laser — classic race.",
        "difficulty": "standard",
        "width": 12,
        "height": 10,
        "walls": _border_edges(12, 10)
        + _wall(3, 2, "E", "S")
        + _wall(4, 2, "W", "S")
        + _wall(7, 2, "E", "S")
        + _wall(8, 2, "W", "S")
        + _wall(3, 7, "E", "N")
        + _wall(4, 7, "W", "N")
        + _wall(7, 7, "E", "N")
        + _wall(8, 7, "W", "N")
        + _wall(5, 4, "E")
        + _wall(6, 4, "W"),
        "conveyors": [
            _belt(1, 3, "S"),
            _belt(1, 4, "S"),
            _belt(1, 5, "E", rotate="left"),
            _belt(2, 5, "E"),
            _belt(3, 5, "E"),
            _belt(10, 3, "N"),
            _belt(10, 4, "N"),
            _belt(10, 5, "W", rotate="right"),
            _belt(9, 5, "W"),
            _belt(8, 5, "W"),
        ],
        "gears": [
            {"x": 4, "y": 4, "dir": "left"},
            {"x": 7, "y": 5, "dir": "right"},
        ],
        "pushers": [],
        "crushers": [],
        "pits": [[5, 3], [6, 6]],
        "lasers": [{"x": 2, "y": 1, "dir": "E", "strength": 1}],
        "repairs": [[9, 8]],
        "upgrades": [],
        "checkpoints": [
            [2, 2, 1],
            [9, 4, 2],
            [2, 8, 3],
        ],
        "antenna": [5, 5],
        "starts": [
            {"x": 2, "y": 9, "facing": "N", "priority": 0},
            {"x": 4, "y": 9, "facing": "N", "priority": 1},
            {"x": 7, "y": 9, "facing": "N", "priority": 2},
            {"x": 9, "y": 9, "facing": "N", "priority": 3},
        ],
    },
    "open_grid": {
        "id": "open_grid",
        "name": "Open Grid",
        "description": "Open plaza with light belts and pits — good first race.",
        "difficulty": "easy",
        "width": 11,
        "height": 9,
        "walls": _border_edges(11, 9)
        + _wall(5, 2, "S")
        + _wall(5, 6, "N"),
        "conveyors": [
            _belt(3, 4, "E"),
            _belt(4, 4, "E"),
            _belt(6, 4, "W"),
            _belt(7, 4, "W"),
        ],
        "gears": [{"x": 5, "y": 4, "dir": "right"}],
        "pushers": [],
        "crushers": [],
        "pits": [[3, 2], [7, 2], [3, 6], [7, 6]],
        "lasers": [],
        "repairs": [[1, 4]],
        "upgrades": [],
        "checkpoints": [
            [2, 1, 1],
            [8, 1, 2],
            [5, 7, 3],
        ],
        "antenna": [5, 3],
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
        "description": "Pushers, crushers, and tight walls — plan every turn.",
        "difficulty": "hard",
        "width": 11,
        "height": 11,
        "walls": _border_edges(11, 11)
        + _wall(2, 2, "E")
        + _wall(2, 3, "E")
        + _wall(2, 4, "E")
        + _wall(4, 5, "W", "E")
        + _wall(4, 6, "W", "E")
        + _wall(4, 7, "W", "E")
        + _wall(6, 2, "W", "E")
        + _wall(6, 3, "W", "E")
        + _wall(6, 4, "W", "E")
        + _wall(8, 5, "W")
        + _wall(8, 6, "W")
        + _wall(8, 7, "W")
        + _wall(3, 8, "N")
        + _wall(5, 8, "N")
        + _wall(7, 8, "N"),
        "conveyors": [
            _belt(1, 5, "S"),
            _belt(1, 6, "S"),
            _belt(9, 5, "N"),
            _belt(9, 6, "N"),
        ],
        "gears": [{"x": 5, "y": 3, "dir": "left"}],
        "pushers": [
            {"x": 3, "y": 4, "dir": "E", "registers": [1, 3, 5]},
            {"x": 7, "y": 6, "dir": "W", "registers": [2, 4]},
        ],
        "crushers": [
            {"x": 5, "y": 5, "registers": [2, 4]},
            {"x": 5, "y": 7, "registers": [3]},
        ],
        "pits": [[3, 2], [7, 2]],
        "lasers": [{"x": 1, "y": 1, "dir": "S", "strength": 1}],
        "repairs": [[9, 9]],
        "upgrades": [[1, 9]],
        "checkpoints": [
            [3, 3, 1],
            [9, 3, 2],
            [5, 6, 3],
            [3, 9, 4],
        ],
        "antenna": [5, 1],
        "starts": [
            {"x": 2, "y": 10, "facing": "N", "priority": 0},
            {"x": 4, "y": 10, "facing": "N", "priority": 1},
            {"x": 6, "y": 10, "facing": "N", "priority": 2},
            {"x": 8, "y": 10, "facing": "N", "priority": 3},
        ],
    },
    "twin_lanes": {
        "id": "twin_lanes",
        "name": "Twin Lanes",
        "description": "Dual express lanes with crossing lasers.",
        "difficulty": "standard",
        "width": 13,
        "height": 10,
        "walls": _border_edges(13, 10)
        + _wall(6, 1, "E", "W")
        + _wall(6, 2, "E", "W")
        + _wall(6, 3, "E", "W")
        + _wall(6, 6, "E", "W")
        + _wall(6, 7, "E", "W")
        + _wall(6, 8, "E", "W")
        + _wall(3, 3, "S")
        + _wall(9, 3, "S")
        + _wall(3, 6, "N")
        + _wall(9, 6, "N"),
        "conveyors": [
            # Left express lane northbound
            _belt(2, 8, "N", express=True),
            _belt(2, 7, "N", express=True),
            _belt(2, 6, "N", express=True),
            _belt(2, 5, "N", express=True),
            _belt(2, 4, "N", express=True),
            # Right express lane northbound
            _belt(10, 8, "N", express=True),
            _belt(10, 7, "N", express=True),
            _belt(10, 6, "N", express=True),
            _belt(10, 5, "N", express=True),
            _belt(10, 4, "N", express=True),
            # Merge conveyors
            _belt(4, 2, "E"),
            _belt(5, 2, "E"),
            _belt(7, 2, "W"),
            _belt(8, 2, "W"),
        ],
        "gears": [{"x": 6, "y": 4, "dir": "left"}],
        "pushers": [{"x": 6, "y": 5, "dir": "S", "registers": [1, 3, 5]}],
        "crushers": [],
        "pits": [[5, 7], [7, 7]],
        "lasers": [
            {"x": 1, "y": 3, "dir": "E", "strength": 1},
            {"x": 11, "y": 5, "dir": "W", "strength": 1},
        ],
        "repairs": [[1, 8]],
        "upgrades": [[11, 8]],
        "checkpoints": [
            [2, 2, 1],
            [10, 2, 2],
            [6, 4, 3],
            [11, 8, 4],
        ],
        "antenna": [1, 5],
        "starts": [
            {"x": 2, "y": 9, "facing": "N", "priority": 0},
            {"x": 4, "y": 9, "facing": "N", "priority": 1},
            {"x": 8, "y": 9, "facing": "N", "priority": 2},
            {"x": 10, "y": 9, "facing": "N", "priority": 3},
        ],
    },
    "grand_prix": {
        "id": "grand_prix",
        "name": "Grand Prix",
        "description": "Oval express loop with infield pits and upgrades.",
        "difficulty": "long",
        "width": 14,
        "height": 11,
        "walls": _border_edges(14, 11)
        # Inner oval walls (infield enclosure edges)
        + [{"x": x, "y": 3, "dir": "S"} for x in range(4, 10)]
        + [{"x": x, "y": 7, "dir": "N"} for x in range(4, 10)]
        + [{"x": 4, "y": y, "dir": "E"} for y in range(4, 7)]
        + [{"x": 9, "y": y, "dir": "W"} for y in range(4, 7)]
        + _wall(2, 5, "E")
        + _wall(11, 5, "W"),
        "conveyors": [
            # Outer express loop counterclockwise from bottom
            *[_belt(x, 9, "E", express=True) for x in range(2, 11)],
            _belt(11, 9, "N", express=True, rotate="left"),
            *[_belt(11, y, "N", express=True) for y in range(4, 9)],
            _belt(11, 3, "W", express=True, rotate="left"),
            *[_belt(x, 1, "W", express=True) for x in range(3, 11)],
            _belt(2, 1, "S", express=True, rotate="left"),
            *[_belt(2, y, "S", express=True) for y in range(2, 9)],
            _belt(2, 9, "E", express=True, rotate="left"),
        ],
        "gears": [{"x": 6, "y": 9, "dir": "right"}],
        "pushers": [{"x": 7, "y": 10, "dir": "N", "registers": [2, 4]}],
        "crushers": [{"x": 12, "y": 5, "registers": [3, 5]}],
        "pits": [[5, 5], [6, 5], [7, 5], [8, 5], [5, 6], [8, 6]],
        "lasers": [{"x": 0, "y": 4, "dir": "E", "strength": 2}],
        "repairs": [[12, 9]],
        "upgrades": [[1, 5]],
        "checkpoints": [
            [3, 1, 1],
            [12, 4, 2],
            [11, 9, 3],
            [1, 6, 4],
        ],
        "antenna": [12, 1],
        "starts": [
            {"x": 4, "y": 10, "facing": "N", "priority": 0},
            {"x": 5, "y": 10, "facing": "N", "priority": 1},
            {"x": 8, "y": 10, "facing": "N", "priority": 2},
            {"x": 9, "y": 10, "facing": "N", "priority": 3},
        ],
    },
    "sprint_line": {
        "id": "sprint_line",
        "name": "Sprint Line",
        "description": "Short open race — learn programming without heavy hazards.",
        "difficulty": "easy",
        "width": 10,
        "height": 8,
        "walls": _border_edges(10, 8)
        + _wall(4, 3, "E")
        + _wall(5, 3, "W")
        + _wall(4, 4, "E")
        + _wall(5, 4, "W"),
        "conveyors": [
            _belt(1, 2, "E"),
            _belt(2, 2, "E"),
            _belt(7, 2, "W"),
            _belt(8, 2, "W"),
        ],
        "gears": [{"x": 3, "y": 4, "dir": "right"}],
        "pushers": [],
        "crushers": [],
        "pits": [[4, 1], [5, 6]],
        "lasers": [],
        "repairs": [[8, 6]],
        "upgrades": [],
        "checkpoints": [
            [2, 1, 1],
            [7, 3, 2],
            [2, 6, 3],
        ],
        "antenna": [8, 1],
        "starts": [
            {"x": 2, "y": 7, "facing": "N", "priority": 0},
            {"x": 3, "y": 7, "facing": "N", "priority": 1},
            {"x": 6, "y": 7, "facing": "N", "priority": 2},
            {"x": 7, "y": 7, "facing": "N", "priority": 3},
        ],
    },
    "gear_yard": {
        "id": "gear_yard",
        "name": "Gear Yard",
        "description": "Turning puzzle — gears and corners punish bad facing.",
        "difficulty": "standard",
        "width": 12,
        "height": 10,
        "walls": _border_edges(12, 10)
        + _wall(3, 2, "S")
        + _wall(4, 2, "S")
        + _wall(7, 2, "S")
        + _wall(8, 2, "S")
        + _wall(3, 7, "N")
        + _wall(4, 7, "N")
        + _wall(7, 7, "N")
        + _wall(8, 7, "N")
        + _wall(5, 4, "E", "W")
        + _wall(6, 5, "E", "W"),
        "conveyors": [
            _belt(1, 3, "S"),
            _belt(1, 4, "S", rotate="left"),
            _belt(2, 4, "E"),
            _belt(3, 4, "E"),
            _belt(10, 3, "N"),
            _belt(10, 4, "N", rotate="right"),
            _belt(9, 4, "W"),
            _belt(8, 4, "W"),
        ],
        "gears": [
            {"x": 2, "y": 2, "dir": "left"},
            {"x": 9, "y": 2, "dir": "right"},
            {"x": 2, "y": 7, "dir": "right"},
            {"x": 9, "y": 7, "dir": "left"},
            {"x": 5, "y": 5, "dir": "left"},
            {"x": 6, "y": 4, "dir": "right"},
        ],
        "pushers": [],
        "crushers": [],
        "pits": [[5, 3], [6, 6]],
        "lasers": [{"x": 0, "y": 5, "dir": "E", "strength": 1}],
        "repairs": [[1, 8]],
        "upgrades": [[10, 8]],
        "checkpoints": [
            [4, 1, 1],
            [10, 5, 2],
            [1, 5, 3],
            [7, 8, 4],
        ],
        "antenna": [6, 1],
        "starts": [
            {"x": 2, "y": 9, "facing": "N", "priority": 0},
            {"x": 4, "y": 9, "facing": "N", "priority": 1},
            {"x": 7, "y": 9, "facing": "N", "priority": 2},
            {"x": 9, "y": 9, "facing": "N", "priority": 3},
        ],
    },
    "crossfire": {
        "id": "crossfire",
        "name": "Crossfire",
        "description": "Laser corridors and cover walls — tank damage or dodge.",
        "difficulty": "hard",
        "width": 12,
        "height": 11,
        "walls": _border_edges(12, 11)
        + _wall(3, 2, "E")
        + _wall(3, 3, "E")
        + _wall(3, 4, "E")
        + _wall(8, 2, "W")
        + _wall(8, 3, "W")
        + _wall(8, 4, "W")
        + _wall(3, 6, "E")
        + _wall(3, 7, "E")
        + _wall(3, 8, "E")
        + _wall(8, 6, "W")
        + _wall(8, 7, "W")
        + _wall(8, 8, "W")
        + _wall(5, 5, "N", "S")
        + _wall(6, 5, "N", "S"),
        "conveyors": [
            _belt(1, 5, "E"),
            _belt(2, 5, "E"),
            _belt(9, 5, "W"),
            _belt(10, 5, "W"),
        ],
        "gears": [{"x": 4, "y": 5, "dir": "right"}, {"x": 7, "y": 5, "dir": "left"}],
        "pushers": [{"x": 5, "y": 3, "dir": "S", "registers": [2, 4]}],
        "crushers": [],
        "pits": [[5, 1], [6, 1], [5, 9], [6, 9]],
        "lasers": [
            {"x": 0, "y": 2, "dir": "E", "strength": 1},
            {"x": 11, "y": 4, "dir": "W", "strength": 1},
            {"x": 0, "y": 6, "dir": "E", "strength": 1},
            {"x": 11, "y": 8, "dir": "W", "strength": 2},
        ],
        "repairs": [[1, 9]],
        "upgrades": [[10, 9]],
        "checkpoints": [
            [2, 1, 1],
            [9, 3, 2],
            [2, 7, 3],
            [9, 9, 4],
        ],
        "antenna": [10, 1],
        "starts": [
            {"x": 2, "y": 10, "facing": "N", "priority": 0},
            {"x": 4, "y": 10, "facing": "N", "priority": 1},
            {"x": 7, "y": 10, "facing": "N", "priority": 2},
            {"x": 9, "y": 10, "facing": "N", "priority": 3},
        ],
    },
    "maelstrom": {
        "id": "maelstrom",
        "name": "Maelstrom",
        "description": "Spiral conveyors suck you inward — ride or fight the current.",
        "difficulty": "hard",
        "width": 13,
        "height": 11,
        "walls": _border_edges(13, 11)
        + _wall(3, 3, "N", "W")
        + _wall(9, 3, "N", "E")
        + _wall(3, 7, "S", "W")
        + _wall(9, 7, "S", "E"),
        "conveyors": [
            # Outer ring clockwise
            _belt(2, 2, "E", rotate="right"),
            *[_belt(x, 2, "E") for x in range(3, 10)],
            _belt(10, 2, "S", rotate="right"),
            *[_belt(10, y, "S") for y in range(3, 8)],
            _belt(10, 8, "W", rotate="right"),
            *[_belt(x, 8, "W") for x in range(3, 10)],
            _belt(2, 8, "N", rotate="right"),
            *[_belt(2, y, "N") for y in range(3, 8)],
            # Inner express spiral
            _belt(4, 4, "E", express=True, rotate="right"),
            *[_belt(x, 4, "E", express=True) for x in range(5, 8)],
            _belt(8, 4, "S", express=True, rotate="right"),
            _belt(8, 5, "S", express=True),
            _belt(8, 6, "W", express=True, rotate="right"),
            *[_belt(x, 6, "W", express=True) for x in range(5, 8)],
            _belt(4, 6, "N", express=True, rotate="right"),
            _belt(4, 5, "N", express=True),
        ],
        "gears": [{"x": 6, "y": 5, "dir": "left"}],
        "pushers": [],
        "crushers": [{"x": 6, "y": 3, "registers": [3]}],
        "pits": [[6, 1], [1, 5], [11, 5]],
        "lasers": [{"x": 6, "y": 0, "dir": "S", "strength": 1}],
        "repairs": [[11, 9]],
        "upgrades": [[1, 9]],
        "checkpoints": [
            [4, 1, 1],
            [11, 4, 2],
            [6, 9, 3],
            [1, 4, 4],
        ],
        "antenna": [11, 1],
        "starts": [
            {"x": 3, "y": 10, "facing": "N", "priority": 0},
            {"x": 5, "y": 10, "facing": "N", "priority": 1},
            {"x": 7, "y": 10, "facing": "N", "priority": 2},
            {"x": 9, "y": 10, "facing": "N", "priority": 3},
        ],
    },
    "island_hop": {
        "id": "island_hop",
        "name": "Island Hop",
        "description": "Pit seas and narrow bridges — one misstep and you reboot.",
        "difficulty": "standard",
        "width": 13,
        "height": 10,
        "walls": _border_edges(13, 10)
        + _wall(4, 2, "E")
        + _wall(8, 4, "W")
        + _wall(4, 7, "E")
        + _wall(8, 7, "W"),
        "conveyors": [
            _belt(3, 4, "E"),
            _belt(4, 4, "E"),
            _belt(5, 4, "E"),
            _belt(7, 4, "W"),
            _belt(8, 4, "W"),
            _belt(9, 4, "W"),
            _belt(6, 2, "S", express=True),
            _belt(6, 3, "S", express=True),
            _belt(6, 5, "N", express=True),
            _belt(6, 6, "N", express=True),
        ],
        "gears": [{"x": 6, "y": 4, "dir": "right"}],
        "pushers": [{"x": 6, "y": 7, "dir": "N", "registers": [1, 3, 5]}],
        "crushers": [],
        "pits": [
            [2, 2], [3, 2], [2, 3],
            [9, 2], [10, 2], [10, 3],
            [2, 6], [2, 7], [3, 7],
            [9, 7], [10, 6], [10, 7],
            [5, 1], [7, 1],
            [5, 8], [7, 8],
        ],
        "lasers": [{"x": 0, "y": 4, "dir": "E", "strength": 1}],
        "repairs": [[1, 8]],
        "upgrades": [[11, 8]],
        "checkpoints": [
            [1, 1, 1],
            [11, 2, 2],
            [1, 5, 3],
            [11, 5, 4],
        ],
        "antenna": [11, 1],
        "starts": [
            {"x": 3, "y": 9, "facing": "N", "priority": 0},
            {"x": 5, "y": 9, "facing": "N", "priority": 1},
            {"x": 7, "y": 9, "facing": "N", "priority": 2},
            {"x": 9, "y": 9, "facing": "N", "priority": 3},
        ],
    },
    "vault_run": {
        "id": "vault_run",
        "name": "Vault Run",
        "description": "Long factory maze with pushers and a crusher choke point.",
        "difficulty": "long",
        "width": 14,
        "height": 12,
        "walls": _border_edges(14, 12)
        + [{"x": 3, "y": y, "dir": "E"} for y in range(1, 5)]
        + [{"x": 4, "y": y, "dir": "W"} for y in range(1, 5)]
        + [{"x": 9, "y": y, "dir": "E"} for y in range(3, 8)]
        + [{"x": 10, "y": y, "dir": "W"} for y in range(3, 8)]
        + [{"x": x, "y": 5, "dir": "S"} for x in range(5, 9)]
        + [{"x": x, "y": 6, "dir": "N"} for x in range(5, 9)]
        + _wall(6, 2, "S")
        + _wall(7, 8, "N")
        + _wall(2, 8, "E")
        + _wall(11, 3, "W"),
        "conveyors": [
            *[_belt(1, y, "S") for y in range(2, 7)],
            _belt(1, 7, "E", rotate="left"),
            *[_belt(x, 7, "E") for x in range(2, 5)],
            *[_belt(12, y, "N") for y in range(4, 9)],
            _belt(12, 3, "W", rotate="right"),
            *[_belt(x, 3, "W") for x in range(10, 12)],
            _belt(5, 9, "W", express=True),
            _belt(6, 9, "W", express=True),
            _belt(7, 9, "E", express=True),
            _belt(8, 9, "E", express=True),
        ],
        "gears": [
            {"x": 5, "y": 3, "dir": "left"},
            {"x": 8, "y": 7, "dir": "right"},
        ],
        "pushers": [
            {"x": 4, "y": 6, "dir": "E", "registers": [1, 3, 5]},
            {"x": 9, "y": 2, "dir": "S", "registers": [2, 4]},
        ],
        "crushers": [{"x": 6, "y": 6, "registers": [2, 4]}],
        "pits": [[6, 4], [7, 4], [6, 10], [7, 1]],
        "lasers": [
            {"x": 0, "y": 9, "dir": "E", "strength": 1},
            {"x": 13, "y": 5, "dir": "W", "strength": 1},
        ],
        "repairs": [[2, 10]],
        "upgrades": [[11, 10]],
        "checkpoints": [
            [2, 1, 1],
            [11, 1, 2],
            [11, 8, 3],
            [2, 6, 4],
            [7, 10, 5],
        ],
        "antenna": [12, 1],
        "starts": [
            {"x": 3, "y": 11, "facing": "N", "priority": 0},
            {"x": 5, "y": 11, "facing": "N", "priority": 1},
            {"x": 8, "y": 11, "facing": "N", "priority": 2},
            {"x": 10, "y": 11, "facing": "N", "priority": 3},
        ],
    },
    "pit_row": {
        "id": "pit_row",
        "name": "Pit Row",
        "description": "Parallel pit trenches and side belts — choose your lane.",
        "difficulty": "standard",
        "width": 12,
        "height": 10,
        "walls": _border_edges(12, 10)
        + _wall(2, 3, "S")
        + _wall(5, 3, "S")
        + _wall(8, 3, "S")
        + _wall(2, 6, "N")
        + _wall(5, 6, "N")
        + _wall(8, 6, "N"),
        "conveyors": [
            *[_belt(1, y, "N") for y in range(4, 8)],
            *[_belt(4, y, "S") for y in range(2, 6)],
            *[_belt(7, y, "N", express=True) for y in range(4, 8)],
            *[_belt(10, y, "S", express=True) for y in range(2, 6)],
        ],
        "gears": [{"x": 3, "y": 5, "dir": "left"}, {"x": 6, "y": 4, "dir": "right"}],
        "pushers": [],
        "crushers": [],
        "pits": [
            [2, 4], [2, 5],
            [5, 4], [5, 5],
            [8, 4], [8, 5],
            [3, 1], [9, 8],
        ],
        "lasers": [{"x": 6, "y": 0, "dir": "S", "strength": 1}],
        "repairs": [[1, 8]],
        "upgrades": [[10, 1]],
        "checkpoints": [
            [3, 2, 1],
            [9, 2, 2],
            [3, 7, 3],
            [9, 7, 4],
        ],
        "antenna": [6, 8],
        "starts": [
            {"x": 1, "y": 9, "facing": "N", "priority": 0},
            {"x": 4, "y": 9, "facing": "N", "priority": 1},
            {"x": 7, "y": 9, "facing": "N", "priority": 2},
            {"x": 10, "y": 9, "facing": "N", "priority": 3},
        ],
    },
}


def list_maps() -> list[dict[str, Any]]:
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
                "walls": list(m["walls"]),
                "conveyors": list(m.get("conveyors", [])),
                "gears": list(m.get("gears", [])),
                "pushers": list(m.get("pushers", [])),
                "crushers": list(m.get("crushers", [])),
                "pits": [list(p) for p in m.get("pits", [])],
                "lasers": list(m.get("lasers", [])),
                "repairs": [list(r) for r in m.get("repairs", [])],
                "upgrades": [list(u) for u in m.get("upgrades", [])],
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
        "walls": [dict(w) for w in m["walls"]],
        "conveyors": [dict(c) for c in m.get("conveyors", [])],
        "gears": [dict(g) for g in m.get("gears", [])],
        "pushers": [dict(p) for p in m.get("pushers", [])],
        "crushers": [dict(c) for c in m.get("crushers", [])],
        "pits": [list(p) for p in m.get("pits", [])],
        "lasers": [dict(laser) for laser in m.get("lasers", [])],
        "repairs": [list(r) for r in m.get("repairs", [])],
        "upgrades": [list(u) for u in m.get("upgrades", [])],
        "checkpoints": [list(c) for c in m["checkpoints"]],
        "antenna": list(m["antenna"]),
    }


def validate_map_definition(map_def: dict[str, Any]) -> None:
    """Raise ValueError if a map has invalid / conflicting key cells."""
    from app.games.roborally.board import DIRECTIONS, in_bounds, pit_set

    width = int(map_def["width"])
    height = int(map_def["height"])
    pits = pit_set(map_def)
    reserved: dict[tuple[int, int], str] = {}

    def _kind(label: str) -> str:
        return label.split()[0]

    def claim(x: int, y: int, label: str, *, allow: tuple[str, ...] = ()) -> None:
        if not in_bounds(x, y, width, height):
            raise ValueError(f"{label} out of bounds at ({x},{y})")
        if (x, y) in pits and label not in ("pit",):
            raise ValueError(f"{label} sits on a pit at ({x},{y})")
        if (x, y) in reserved:
            other = reserved[(x, y)]
            if _kind(other) not in allow and _kind(label) not in allow:
                raise ValueError(f"{label} overlaps {other} at ({x},{y})")
        reserved[(x, y)] = label

    for w in map_def.get("walls", []):
        if isinstance(w, dict):
            if w.get("dir") not in DIRECTIONS:
                raise ValueError(f"Invalid wall dir {w}")
            if not in_bounds(int(w["x"]), int(w["y"]), width, height):
                raise ValueError(f"Wall out of bounds {w}")

    ax, ay = int(map_def["antenna"][0]), int(map_def["antenna"][1])
    claim(ax, ay, "antenna", allow=("antenna", "conveyor", "gear"))

    seen_nums: set[int] = set()
    checkpoints: list[tuple[int, int, int]] = []
    for raw in map_def["checkpoints"]:
        x, y, num = int(raw[0]), int(raw[1]), int(raw[2])
        if num in seen_nums:
            raise ValueError(f"Duplicate checkpoint number {num}")
        seen_nums.add(num)
        claim(x, y, f"checkpoint {num}", allow=("antenna", "conveyor", "gear", "repair", "upgrade"))
        checkpoints.append((x, y, num))

    if seen_nums != set(range(1, len(seen_nums) + 1)):
        raise ValueError("Checkpoints must be numbered 1..N without gaps")

    for c in map_def.get("conveyors", []):
        claim(int(c["x"]), int(c["y"]), "conveyor", allow=("antenna", "checkpoint", "conveyor"))
        if c.get("dir") not in DIRECTIONS:
            raise ValueError(f"Bad conveyor dir {c}")

    for g in map_def.get("gears", []):
        claim(int(g["x"]), int(g["y"]), "gear", allow=("antenna", "checkpoint", "conveyor"))
        if g.get("dir") not in ("left", "right"):
            raise ValueError(f"Bad gear dir {g}")

    for p in map_def.get("pushers", []):
        claim(int(p["x"]), int(p["y"]), "pusher")
        if p.get("dir") not in DIRECTIONS:
            raise ValueError(f"Bad pusher dir {p}")

    for c in map_def.get("crushers", []):
        claim(int(c["x"]), int(c["y"]), "crusher")

    for p in map_def.get("pits", []):
        claim(int(p[0]), int(p[1]), "pit")

    for laser in map_def.get("lasers", []):
        if not in_bounds(int(laser["x"]), int(laser["y"]), width, height):
            raise ValueError(f"Laser out of bounds {laser}")
        if laser.get("dir") not in DIRECTIONS:
            raise ValueError(f"Bad laser dir {laser}")

    for r in map_def.get("repairs", []):
        claim(int(r[0]), int(r[1]), "repair", allow=("checkpoint",))

    for u in map_def.get("upgrades", []):
        claim(int(u[0]), int(u[1]), "upgrade", allow=("checkpoint",))

    starts = map_def["starts"]
    if len(starts) < 4:
        raise ValueError("Maps need at least 4 start pads")
    start_cells: list[tuple[int, int]] = []
    for i, start in enumerate(starts):
        sx, sy = int(start["x"]), int(start["y"])
        claim(sx, sy, f"start {i}")
        if start["facing"] not in DIRECTIONS:
            raise ValueError(f"Invalid facing on start {i}")
        start_cells.append((sx, sy))

    reachable = _flood_fill(width, height, pits, start_cells, map_def)
    for x, y, num in checkpoints:
        if (x, y) not in reachable:
            raise ValueError(f"Checkpoint {num} unreachable from start pads")


def _flood_fill(
    width: int,
    height: int,
    pits: set[tuple[int, int]],
    starts: list[tuple[int, int]],
    map_def: dict[str, Any],
) -> set[tuple[int, int]]:
    from app.games.roborally.board import DELTA, DIRECTIONS, edge_wall_set, in_bounds

    walls = edge_wall_set(map_def)
    stack = list(starts)
    seen: set[tuple[int, int]] = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or (x, y) in pits:
            continue
        if not in_bounds(x, y, width, height):
            continue
        seen.add((x, y))
        for d in DIRECTIONS:
            if (x, y, d) in walls:
                continue
            dx, dy = DELTA[d]
            stack.append((x + dx, y + dy))
    return seen


def registry_element_coverage() -> dict[str, bool]:
    """Return whether each classic element appears on at least one map."""
    flags = {
        "walls": False,
        "conveyors": False,
        "express": False,
        "gears": False,
        "pushers": False,
        "crushers": False,
        "pits": False,
        "lasers": False,
        "repairs": False,
        "upgrades": False,
        "checkpoints": False,
        "antenna": False,
    }
    for m in MAPS.values():
        if m.get("walls"):
            flags["walls"] = True
        if m.get("conveyors"):
            flags["conveyors"] = True
            if any(c.get("express") for c in m["conveyors"]):
                flags["express"] = True
        if m.get("gears"):
            flags["gears"] = True
        if m.get("pushers"):
            flags["pushers"] = True
        if m.get("crushers"):
            flags["crushers"] = True
        if m.get("pits"):
            flags["pits"] = True
        if m.get("lasers"):
            flags["lasers"] = True
        if m.get("repairs"):
            flags["repairs"] = True
        if m.get("upgrades"):
            flags["upgrades"] = True
        if m.get("checkpoints"):
            flags["checkpoints"] = True
        if m.get("antenna"):
            flags["antenna"] = True
    return flags
