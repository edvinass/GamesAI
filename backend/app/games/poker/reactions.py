"""Poker emoji reactions — selection logic for AI players."""

import random
from typing import Any

POKER_REACTIONS = frozenset({"👍", "🔥", "😂", "😮", "👏", "🃏", "💰", "😎", "🫡", "💀"})


def _bb(state: dict) -> int:
    return int(state.get("settings", {}).get("big_blind", 10))


def choose_action_reaction(
    state: dict,
    player_id: str,
    action: dict[str, Any],
) -> str | None:
    player = state["players"].get(player_id)
    if not player or not player.get("is_ai"):
        return None

    action_type = action.get("type")
    roll = random.random()
    bb = _bb(state)

    if action_type == "all_in":
        return random.choice(["🔥", "💰", "😎"])

    if action_type == "raise":
        if roll < 0.7:
            return random.choice(["🔥", "😎", "🃏"])
        return None

    if action_type == "fold":
        if roll < 0.45:
            return random.choice(["💀", "🫡", "😂"])
        return None

    if action_type == "call":
        # Post-action state: bet_this_round already includes the call
        called = int(action.get("amount", 0))
        if called >= bb * 4 and roll < 0.5:
            return random.choice(["😮", "🔥", "🫡"])
        if roll < 0.18:
            return random.choice(["👍", "🫡"])

    if action_type == "check" and roll < 0.12:
        return random.choice(["👍", "🫡"])

    return None


def choose_winner_reaction(state: dict, winner: dict) -> str:
    amount = int(winner.get("amount", 0))
    bb = _bb(state)
    hand = winner.get("hand")
    won_by_fold = not hand

    if amount >= bb * 20:
        return random.choice(["🔥", "💰", "👏"])
    if won_by_fold:
        return random.choice(["😎", "🫡", "💰", "🃏"])
    if hand:
        hand_lower = hand.lower()
        if any(
            term in hand_lower
            for term in ("flush", "straight", "full house", "four of a kind", "royal")
        ):
            return random.choice(["🔥", "💰", "😎", "👏"])
    return random.choice(["😎", "👏", "🃏", "🫡", "👍"])


def choose_loser_reaction() -> str:
    return random.choice(["😮", "💀", "😂"])


def choose_game_winner_reaction() -> str:
    return random.choice(["🔥", "💰", "😎", "👏", "🃏"])
