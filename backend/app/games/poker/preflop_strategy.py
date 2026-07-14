"""Position-aware preflop opening and re-raise guidance."""

from __future__ import annotations

from typing import Any

from app.games.poker.ranges import preflop_hand_strength

POSITION_NAMES = ("utg", "mp", "co", "btn", "sb", "bb")

OPEN_THRESHOLDS: dict[str, float] = {
    "utg": 0.62,
    "mp": 0.58,
    "co": 0.54,
    "btn": 0.48,
    "sb": 0.52,
    "bb": 0.42,
}

THREE_BET_THRESHOLDS: dict[str, float] = {
    "utg": 0.78,
    "mp": 0.76,
    "co": 0.74,
    "btn": 0.72,
    "sb": 0.74,
    "bb": 0.70,
}


def position_label(position_score: float) -> str:
    """Map 0-1 position score to a named position."""
    if position_score >= 0.9:
        return "btn"
    if position_score >= 0.7:
        return "co"
    if position_score >= 0.5:
        return "mp"
    if position_score >= 0.25:
        return "utg"
    if position_score >= 0.1:
        return "sb"
    return "bb"


def open_threshold(
    position_score: float,
    *,
    stack_bb: float,
    opponents: dict[str, float] | None = None,
) -> float:
    pos = position_label(position_score)
    base = OPEN_THRESHOLDS[pos]
    if stack_bb <= 15:
        base -= 0.06
    if opponents:
        if opponents.get("is_nit"):
            base -= 0.04
        if opponents.get("is_station"):
            base += 0.03
    return base


def three_bet_threshold(position_score: float, *, facing_3bet: bool = False) -> float:
    pos = position_label(position_score)
    base = THREE_BET_THRESHOLDS[pos]
    if facing_3bet:
        base += 0.06
    return base


def preflop_open_size_bb(position_score: float, *, stack_bb: float) -> float:
    pos = position_label(position_score)
    sizes = {"utg": 2.5, "mp": 2.3, "co": 2.2, "btn": 2.0, "sb": 2.5, "bb": 3.0}
    size = sizes[pos]
    if stack_bb <= 20:
        size = min(size, 2.2)
    return size


def preflop_reraise_multiplier(
    *,
    hand_strength: float,
    facing_3bet: bool,
    value_threshold: float,
) -> float:
    if facing_3bet:
        return 2.2 if hand_strength >= value_threshold + 0.08 else 0.0
    if hand_strength >= value_threshold:
        return 3.0
    if hand_strength >= value_threshold - 0.06:
        return 2.5
    return 0.0


def should_open_preflop(
    hole_cards: list[dict[str, str]],
    position_score: float,
    *,
    stack_bb: float,
    opponents: dict[str, float] | None = None,
) -> bool:
    strength = preflop_hand_strength(hole_cards)
    return strength >= open_threshold(position_score, stack_bb=stack_bb, opponents=opponents)


def should_three_bet_preflop(
    hole_cards: list[dict[str, str]],
    position_score: float,
    *,
    facing_3bet: bool = False,
) -> bool:
    strength = preflop_hand_strength(hole_cards)
    return strength >= three_bet_threshold(position_score, facing_3bet=facing_3bet)
