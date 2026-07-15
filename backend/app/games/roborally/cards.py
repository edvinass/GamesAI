"""Program card deck and hand management for RoboRally."""

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
    "backup",
)

# Simplified deck composition (enough for 4 players × 9-card hands).
DECK_COMPOSITION: dict[str, int] = {
    "move_1": 18,
    "move_2": 12,
    "move_3": 6,
    "turn_left": 18,
    "turn_right": 18,
    "backup": 6,
}

CARD_LABELS: dict[str, str] = {
    "move_1": "Move 1",
    "move_2": "Move 2",
    "move_3": "Move 3",
    "turn_left": "Turn Left",
    "turn_right": "Turn Right",
    "backup": "Backup",
}


def new_deck(rng: random.Random | None = None) -> list[dict[str, str]]:
    rng = rng or random.Random()
    deck: list[dict[str, str]] = []
    for card_type, count in DECK_COMPOSITION.items():
        for _ in range(count):
            deck.append({"id": uuid.uuid4().hex[:12], "type": card_type})
    rng.shuffle(deck)
    return deck


def draw_cards(deck: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    drawn: list[dict[str, str]] = []
    for _ in range(count):
        if not deck:
            break
        drawn.append(deck.pop())
    return drawn


def refill_hand(
    hand: list[dict[str, str]],
    deck: list[dict[str, str]],
    target_size: int,
) -> list[dict[str, str]]:
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
