"""Postflop board texture analysis and bet sizing candidates."""

from __future__ import annotations

from typing import Any

from app.games.poker.deck import RANK_TO_VALUE

Card = dict[str, str]


def board_texture(community: list[Card]) -> dict[str, float | bool]:
    """Classify board wetness and connectivity."""
    if len(community) < 3:
        return {"wet": 0.3, "paired": False, "monotone": False, "high_card": 0.5}

    suits = [c["suit"] for c in community]
    ranks = sorted(RANK_TO_VALUE[c["rank"]] for c in community)
    suit_counts: dict[str, int] = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    max_suit = max(suit_counts.values())
    paired = len(set(ranks)) < len(ranks)
    monotone = max_suit >= 3
    connected = (ranks[-1] - ranks[0]) <= 4

    wet = 0.25
    if max_suit >= 2:
        wet += 0.2
    if monotone:
        wet += 0.25
    if connected:
        wet += 0.15
    if paired:
        wet += 0.1
    high_card = ranks[-1] / 14.0

    return {
        "wet": min(1.0, wet),
        "paired": paired,
        "monotone": monotone,
        "high_card": high_card,
    }


def spr(state: dict[str, Any], player_id: str) -> float:
    """Stack-to-pot ratio for the acting player."""
    pot = sum(p["total_bet_hand"] for p in state["players"].values())
    stack = state["players"][player_id]["chips"]
    return stack / max(1, pot)


def value_bet_fraction(texture: dict[str, float | bool], equity: float) -> float:
    wet = float(texture["wet"])
    if equity >= 0.75:
        return 0.65 + wet * 0.1
    if equity >= 0.6:
        return 0.55 + wet * 0.05
    return 0.45


def bluff_bet_fraction(texture: dict[str, float | bool], position: float) -> float:
    wet = float(texture["wet"])
    base = 0.4 + position * 0.1
    if wet > 0.6:
        base += 0.1
    return min(0.7, base)


def candidate_pot_fractions(
    *,
    equity: float,
    texture: dict[str, float | bool],
    position: float,
    to_call: int,
    is_bluff: bool,
) -> list[float]:
    """Return pot-fraction targets to evaluate for bet sizing."""
    if to_call > 0:
        if is_bluff:
            return [0.55, 0.75]
        if equity >= 0.7:
            return [0.45, 0.65, 0.85]
        return [0.4, 0.55]

    if is_bluff:
        return [0.33, 0.5, 0.65]
    if equity >= 0.75:
        return [0.5, 0.67, 0.85]
    if equity >= 0.55:
        return [0.33, 0.5, 0.67]
    return [0.33, 0.5]
