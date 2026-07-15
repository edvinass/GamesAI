"""Small option / upgrade card set for RoboRally."""

from __future__ import annotations

import random
import uuid
from typing import Any

# Keep intentionally small — not the full retail catalog.
OPTION_DECK: list[dict[str, Any]] = [
    {
        "type": "rear_laser",
        "name": "Rear-Firing Laser",
        "description": "Also fires a laser backward when robot lasers fire.",
    },
    {
        "type": "extra_memory",
        "name": "Extra Memory",
        "description": "Draw one extra program card each round.",
    },
    {
        "type": "abort_switch",
        "name": "Abort Switch",
        "description": "Once per round, ignore the next conveyor move that would hit you.",
    },
    {
        "type": "ramming_gear",
        "name": "Ramming Gear",
        "description": "When you push another robot, that robot takes 1 damage.",
    },
    {
        "type": "fire_control",
        "name": "Fire Control",
        "description": "Your robot laser deals +1 damage.",
    },
    {
        "type": "mechanize",
        "name": "Double-Barreled Laser",
        "description": "Your robot laser deals +1 damage.",
    },
]


def new_option_deck(rng: random.Random | None = None) -> list[dict[str, Any]]:
    rng = rng or random.Random()
    deck = []
    for template in OPTION_DECK:
        for _ in range(2):
            deck.append(
                {
                    "id": uuid.uuid4().hex[:12],
                    "type": template["type"],
                    "name": template["name"],
                    "description": template["description"],
                }
            )
    rng.shuffle(deck)
    return deck


def draw_option(
    deck: list[dict[str, Any]],
    discard: list[dict[str, Any]] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any] | None:
    rng = rng or random.Random()
    if not deck:
        if discard:
            deck.extend(discard)
            discard.clear()
            rng.shuffle(deck)
        else:
            return None
    if not deck:
        return None
    return deck.pop()


def has_option(robot: dict[str, Any], option_type: str) -> bool:
    return any(o.get("type") == option_type for o in robot.get("options", []))


def laser_bonus(robot: dict[str, Any]) -> int:
    bonus = 0
    for o in robot.get("options", []):
        if o.get("type") in ("fire_control", "mechanize"):
            bonus += 1
    return bonus
