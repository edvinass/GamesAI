"""Simple heuristics for RoboRally AI programming."""

from __future__ import annotations

import random
from typing import Any

from app.games.roborally.simulation import simulate_card


def _next_checkpoint(board: dict[str, Any], robot: dict[str, Any]) -> tuple[int, int] | None:
    next_idx = robot["checkpoints_reached"]
    cps = board["checkpoints"]
    if next_idx >= len(cps):
        return None
    cx, cy, _ = cps[next_idx]
    return cx, cy


def _score_robot(robot: dict[str, Any], target: tuple[int, int] | None) -> float:
    if target is None:
        return 0.0
    tx, ty = target
    return -abs(robot["x"] - tx) - abs(robot["y"] - ty) - robot["checkpoints_reached"] * 100


def choose_program(
    state: dict[str, Any],
    player_id: str,
    difficulty: str = "medium",
) -> list[dict[str, str]]:
    """Pick cards for all register slots. Returns list of {slot_index, card_id}."""
    hand = list(state["hands"][player_id])
    register_size = state["settings"]["register_size"]
    board = state["board"]
    robots = state["robots"]
    register_order = state["register_order"]
    robot = robots[player_id]
    target = _next_checkpoint(board, robot)

    placements: list[dict[str, str]] = []
    sim_robot = dict(robot)

    rng = random.Random()

    for slot in range(register_size):
        if not hand:
            break
        if difficulty == "easy":
            card = rng.choice(hand)
            placements.append({"slot_index": slot, "card_id": card["id"]})
            hand = [c for c in hand if c["id"] != card["id"]]
            sim_robot = simulate_card(
                {player_id: sim_robot, **{p: robots[p] for p in robots if p != player_id}},
                board,
                player_id,
                card["type"],
                register_order,
            )
            continue

        best_card = hand[0]
        best_score = float("-inf")
        for card in hand:
            result = simulate_card(robots, board, player_id, card["type"], register_order)
            score = _score_robot(result, target)
            if difficulty == "medium":
                score += rng.uniform(-0.5, 0.5)
            if score > best_score:
                best_score = score
                best_card = card

        placements.append({"slot_index": slot, "card_id": best_card["id"]})
        hand = [c for c in hand if c["id"] != best_card["id"]]
        sim_robot = simulate_card(
            {player_id: sim_robot, **{p: robots[p] for p in robots if p != player_id}},
            board,
            player_id,
            best_card["type"],
            register_order,
        )

    return placements


def choose_ai_actions(state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
    """Return sequence of place_card actions followed by lock_program."""
    difficulty = state.get("settings", {}).get("ai_difficulty", "medium")
    placements = choose_program(state, player_id, difficulty)
    actions: list[dict[str, Any]] = [
        {"type": "place_card", "slot_index": p["slot_index"], "card_id": p["card_id"]}
        for p in placements
    ]
    actions.append({"type": "lock_program"})
    return actions
