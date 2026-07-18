"""Battleship AI — random placement and hunt/target shooting."""

from __future__ import annotations

import random
from typing import Any

BOARD_SIZE = 10

SHIP_DEFS = [
    {"id": "carrier", "name": "Carrier", "length": 5},
    {"id": "battleship", "name": "Battleship", "length": 4},
    {"id": "cruiser", "name": "Cruiser", "length": 3},
    {"id": "submarine", "name": "Submarine", "length": 3},
    {"id": "destroyer", "name": "Destroyer", "length": 2},
]


def choose_battleship_action(state: dict, player_id: str) -> dict[str, Any]:
    """Return the next AI action for placement or combat."""
    phase = state.get("phase")
    if phase == "placing":
        fleet = state["fleets"][player_id]
        if not fleet.get("ready"):
            if len(fleet.get("ships") or []) < len(SHIP_DEFS):
                return {"type": "auto_place"}
            return {"type": "ready"}
        return {"type": "ready"}

    if phase != "playing":
        raise ValueError("Game is not in a playable phase")

    difficulty = str(
        (state.get("settings") or {}).get("ai_difficulty")
        or state["players"][player_id].get("ai_difficulty")
        or "medium"
    ).lower()
    row, col = choose_shot(state, player_id, difficulty)
    return {"type": "fire", "row": row, "col": col}


def choose_shot(state: dict, player_id: str, difficulty: str = "medium") -> tuple[int, int]:
    """Pick a cell to fire at based on difficulty."""
    my_shots = state["fleets"][player_id].get("shots") or {}
    available = [
        (r, c)
        for r in range(BOARD_SIZE)
        for c in range(BOARD_SIZE)
        if f"{r},{c}" not in my_shots
    ]
    if not available:
        return 0, 0

    if difficulty == "easy":
        return random.choice(available)

    targets = _hunt_targets(my_shots, available)
    if targets:
        if difficulty == "hard":
            scored = [( _score_target(r, c, my_shots, available), r, c) for r, c in targets]
            scored.sort(reverse=True)
            return scored[0][1], scored[0][2]
        return random.choice(targets)

    if difficulty == "hard":
        # Prefer checkerboard / denser unknown regions.
        scored = [(_score_open(r, c, my_shots), r, c) for r, c in available]
        scored.sort(reverse=True)
        top = scored[: max(1, len(scored) // 4)]
        _, r, c = random.choice(top)
        return r, c

    # Medium: slight preference for checkerboard.
    parity = [cell for cell in available if (cell[0] + cell[1]) % 2 == 0]
    pool = parity or available
    return random.choice(pool)


def generate_random_fleet(rng: random.Random | None = None) -> list[dict]:
    """Generate a valid non-overlapping fleet placement."""
    rng = rng or random.Random()
    occupied: set[tuple[int, int]] = set()
    ships: list[dict] = []

    for ship_def in SHIP_DEFS:
        placed = False
        for _ in range(200):
            horizontal = rng.choice([True, False])
            length = ship_def["length"]
            if horizontal:
                row = rng.randrange(BOARD_SIZE)
                col = rng.randrange(BOARD_SIZE - length + 1)
                cells = [(row, col + i) for i in range(length)]
            else:
                row = rng.randrange(BOARD_SIZE - length + 1)
                col = rng.randrange(BOARD_SIZE)
                cells = [(row + i, col) for i in range(length)]

            if any(cell in occupied for cell in cells):
                continue
            for cell in cells:
                occupied.add(cell)
            ships.append(
                {
                    "id": ship_def["id"],
                    "name": ship_def["name"],
                    "length": length,
                    "cells": [[r, c] for r, c in cells],
                    "hits": 0,
                    "sunk": False,
                }
            )
            placed = True
            break
        if not placed:
            raise RuntimeError(f"Failed to place ship {ship_def['id']}")
    return ships


def _hunt_targets(
    my_shots: dict[str, str], available: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    available_set = set(available)
    hits = [
        (int(k.split(",")[0]), int(k.split(",")[1]))
        for k, v in my_shots.items()
        if v == "hit"
    ]
    if not hits:
        return []

    # Prefer continuing a line of 2+ hits.
    line_targets: list[tuple[int, int]] = []
    for r, c in hits:
        for dr, dc in ((0, 1), (1, 0)):
            neighbors = []
            for sign in (1, -1):
                nr, nc = r + dr * sign, c + dc * sign
                key = f"{nr},{nc}"
                if my_shots.get(key) == "hit":
                    neighbors.append((nr, nc))
            if neighbors:
                for sign in (1, -1):
                    nr, nc = r + dr * sign, c + dc * sign
                    while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
                        key = f"{nr},{nc}"
                        if my_shots.get(key) == "hit":
                            nr += dr * sign
                            nc += dc * sign
                            continue
                        if (nr, nc) in available_set:
                            line_targets.append((nr, nc))
                        break
    if line_targets:
        return list(dict.fromkeys(line_targets))

    adjacent: list[tuple[int, int]] = []
    for r, c in hits:
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if (nr, nc) in available_set:
                adjacent.append((nr, nc))
    return list(dict.fromkeys(adjacent))


def _score_target(
    row: int, col: int, my_shots: dict[str, str], available: list[tuple[int, int]]
) -> int:
    available_set = set(available)
    score = 0
    for dr, dc in ((0, 1), (1, 0)):
        for sign in (1, -1):
            nr, nc = row + dr * sign, col + dc * sign
            if my_shots.get(f"{nr},{nc}") == "hit":
                score += 5
            elif (nr, nc) in available_set:
                score += 1
    return score


def _score_open(row: int, col: int, my_shots: dict[str, str]) -> int:
    score = 2 if (row + col) % 2 == 0 else 0
    for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nr, nc = row + dr, col + dc
        if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
            if f"{nr},{nc}" not in my_shots:
                score += 1
    return score
