"""Program card deck and hand management for classic RoboRally."""

from __future__ import annotations

import random
import uuid
from typing import Any

CARD_TYPES = (
    "move_1",
    "move_2",
    "move_3",
    "turn_left",
    "turn_right",
    "u_turn",
    "backup",
)

# Classic Avalon Hill priority bands (higher acts first within a register).
_PRIORITY_BANDS: dict[str, list[int]] = {
    "u_turn": [10, 20, 30, 40, 50, 60],
    "turn_left": list(range(70, 430, 20)),  # 18: 70..410
    "turn_right": list(range(80, 440, 20)),  # 18: 80..420
    "backup": [430, 440, 450, 460, 470, 480],
    "move_1": list(range(490, 670, 10)),  # 18: 490..660
    "move_2": list(range(670, 790, 10)),  # 12: 670..780
    "move_3": [790, 800, 810, 820, 830, 840],
}

DECK_COMPOSITION: dict[str, int] = {k: len(v) for k, v in _PRIORITY_BANDS.items()}

CARD_LABELS: dict[str, str] = {
    "move_1": "Move 1",
    "move_2": "Move 2",
    "move_3": "Move 3",
    "turn_left": "Turn Left",
    "turn_right": "Turn Right",
    "u_turn": "U-Turn",
    "backup": "Back Up",
}


def new_deck(rng: random.Random | None = None) -> list[dict[str, Any]]:
    rng = rng or random.Random()
    deck: list[dict[str, Any]] = []
    for card_type, priorities in _PRIORITY_BANDS.items():
        for priority in priorities:
            deck.append(
                {
                    "id": uuid.uuid4().hex[:12],
                    "type": card_type,
                    "priority": priority,
                }
            )
    rng.shuffle(deck)
    return deck


def draw_cards(deck: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    drawn: list[dict[str, Any]] = []
    for _ in range(count):
        if not deck:
            break
        drawn.append(deck.pop())
    return drawn


def refill_hand(
    hand: list[dict[str, Any]],
    deck: list[dict[str, Any]],
    target_size: int,
) -> list[dict[str, Any]]:
    need = target_size - len(hand)
    if need > 0:
        hand.extend(draw_cards(deck, need))
    return hand


def card_in_hand(hand: list[dict[str, Any]], card_id: str) -> dict[str, Any] | None:
    return next((c for c in hand if c["id"] == card_id), None)


def remove_card_from_hand(hand: list[dict[str, Any]], card_id: str) -> dict[str, Any] | None:
    for i, card in enumerate(hand):
        if card["id"] == card_id:
            return hand.pop(i)
    return None


def reshuffle_discard_into_deck(
    deck: list[dict[str, Any]],
    discard: list[dict[str, Any]],
    rng: random.Random | None = None,
) -> None:
    """When the draw pile is empty, shuffle discard back in (classic shared deck)."""
    if deck or not discard:
        return
    rng = rng or random.Random()
    deck.extend(discard)
    discard.clear()
    rng.shuffle(deck)


def draw_cards_reshuffling(
    deck: list[dict[str, Any]],
    discard: list[dict[str, Any]],
    count: int,
    rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    drawn: list[dict[str, Any]] = []
    for _ in range(count):
        if not deck:
            reshuffle_discard_into_deck(deck, discard, rng)
        if not deck:
            break
        drawn.append(deck.pop())
    return drawn
