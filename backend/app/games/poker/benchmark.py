"""Headless poker AI simulation for regression benchmarks."""

from __future__ import annotations

import random
from typing import Any

from app.games.poker.ai import choose_poker_action
from app.games.poker.engine import PokerEngine


def _make_players(count: int) -> list[dict[str, Any]]:
    return [
        {
            "id": f"p{i}",
            "nickname": f"AI {i}",
            "team": None,
            "role": None,
            "is_ai": True,
            "is_connected": True,
        }
        for i in range(count)
    ]


def _apply_ai_action(engine: PokerEngine, state: dict, actor_id: str) -> dict:
    action = choose_poker_action(state, actor_id)
    actor = {"id": actor_id, "nickname": actor_id, "is_ai": True}
    try:
        state, _ = engine.apply_action(state, action, actor)
    except ValueError:
        p = state["players"][actor_id]
        to_call = max(0, state["current_bet"] - p["bet_this_round"])
        fallback = {"type": "call"} if to_call > 0 else {"type": "check"}
        state, _ = engine.apply_action(state, fallback, actor)
    return state


def play_hand_to_completion(
    engine: PokerEngine,
    state: dict,
    *,
    max_actions: int = 200,
) -> dict:
    actions = 0
    while actions < max_actions:
        if state.get("phase") in ("hand_complete", "game_over", "showdown"):
            break
        if state.get("phase") not in engine.BETTING_PHASES:
            break
        actor_id = state.get("current_actor_id")
        if not actor_id:
            break
        state = _apply_ai_action(engine, state, actor_id)
        actions += 1
    return state


def run_ai_benchmark(
    *,
    hands: int = 50,
    num_players: int = 3,
    difficulty: str = "medium",
    seed: int | None = None,
) -> dict[str, Any]:
    """Play AI-vs-AI hands and return chip-delta summary."""
    rng = random.Random(seed)
    engine = PokerEngine()
    players = _make_players(num_players)
    settings = {
        "host_id": "p0",
        "ai_difficulty": difficulty,
        "small_blind": 5,
        "big_blind": 10,
        "starting_chips": 1000,
    }
    state = engine.create_initial_state(players, settings)
    starting = {pid: state["players"][pid]["chips"] for pid in state["seat_order"]}
    completed_hands = 0
    illegal_actions = 0

    for _ in range(hands):
        if state.get("winner") or state.get("phase") == "game_over":
            break
        if state.get("phase") == "hand_complete":
            host = {"id": state["host_id"], "nickname": "host", "is_ai": True}
            try:
                state, _ = engine.apply_action(state, {"type": "next_hand"}, host)
            except ValueError:
                break
            completed_hands += 1
            continue

        before_phase = state.get("phase")
        state = play_hand_to_completion(engine, state)
        if state.get("phase") != before_phase:
            completed_hands += 1

        if state.get("phase") == "hand_complete":
            host = {"id": state["host_id"], "nickname": "host", "is_ai": True}
            try:
                state, _ = engine.apply_action(state, {"type": "next_hand"}, host)
            except ValueError:
                break

    ending = {pid: state["players"][pid]["chips"] for pid in state["seat_order"]}
    chip_delta = {pid: ending[pid] - starting[pid] for pid in starting}

    return {
        "hands_requested": hands,
        "hands_completed": completed_hands,
        "illegal_actions": illegal_actions,
        "starting_chips": starting,
        "ending_chips": ending,
        "chip_delta": chip_delta,
        "total_chips": sum(ending.values()),
        "game_over": bool(state.get("winner")),
    }
