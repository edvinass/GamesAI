"""Pick a legal Scrabble action for an AI seat."""

from __future__ import annotations

import random

from app.games.scrabble.board import LETTER_VALUES
from app.games.scrabble.moves import generate_moves


def choose_action(state: dict, difficulty: str = "medium") -> dict:
    actor_id = state["current_actor_id"]
    rack = list(state["racks"].get(actor_id, []))
    moves = generate_moves(state["board"], rack)
    if moves:
        moves.sort(key=lambda move: (move["score"], len(move["placements"])), reverse=True)
        chosen = _pick(moves, difficulty)
        return {
            "type": "play",
            "placements": _bind_tiles(rack, chosen["placements"]),
        }
    if len(state["bag"]) >= 7 and rack:
        ranked = sorted(
            rack,
            key=lambda tile: 0 if tile["b"] else LETTER_VALUES.get(tile["l"], 0),
            reverse=True,
        )
        count = min(len(ranked), 3 if difficulty == "easy" else 5)
        return {"type": "exchange", "tile_ids": [tile["id"] for tile in ranked[:count]]}
    return {"type": "pass"}


def _pick(moves: list[dict], difficulty: str) -> dict:
    if difficulty == "easy":
        pool = moves[len(moves) // 2 :] or moves
        return random.choice(pool)
    if difficulty == "medium":
        pool = moves[: min(6, len(moves))]
        return random.choice(pool)
    return moves[0]


def _bind_tiles(rack: list[dict], placements: list[dict]) -> list[dict]:
    pool = list(rack)
    bound = []
    for placement in placements:
        if placement["blank"]:
            index = next(i for i, tile in enumerate(pool) if tile["b"])
        else:
            index = next(
                i
                for i, tile in enumerate(pool)
                if not tile["b"] and tile["l"] == placement["letter"]
            )
        tile = pool.pop(index)
        bound.append(
            {
                "row": placement["row"],
                "col": placement["col"],
                "tile_id": tile["id"],
                "letter": placement["letter"],
            }
        )
    return bound
