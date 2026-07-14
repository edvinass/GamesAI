"""Hand strength scoring and opponent range weighting for poker AI."""

from __future__ import annotations

import random
from typing import Any

from app.games.poker.deck import RANK_TO_VALUE, make_deck

Card = dict[str, str]


def preflop_hand_strength(hole_cards: list[Card]) -> float:
    """Return 0.0-1.0 preflop hand strength score."""
    if len(hole_cards) != 2:
        return 0.0

    r1 = RANK_TO_VALUE[hole_cards[0]["rank"]]
    r2 = RANK_TO_VALUE[hole_cards[1]["rank"]]
    high, low = max(r1, r2), min(r1, r2)
    suited = hole_cards[0]["suit"] == hole_cards[1]["suit"]

    if r1 == r2:
        return 0.52 + high / 30.0

    score = high / 14.0 * 0.42 + low / 14.0 * 0.18
    if suited:
        score += 0.08
    gap = high - low
    if gap <= 4:
        score += 0.04
    if gap == 1:
        score += 0.03
    if high >= 12 and low >= 10:
        score += 0.06
    if high == 14:
        score += 0.04
    return min(1.0, score)


def _card_tuple(card: Card) -> tuple[str, str]:
    return (card["rank"], card["suit"])


def _remaining_combos(known_cards: list[Card]) -> list[tuple[Card, Card]]:
    known = {_card_tuple(c) for c in known_cards}
    deck = [c for c in make_deck() if _card_tuple(c) not in known]
    combos: list[tuple[Card, Card]] = []
    for i in range(len(deck)):
        for j in range(i + 1, len(deck)):
            combos.append((deck[i], deck[j]))
    return combos


def hand_in_range_weight(hole: tuple[Card, Card], tightness: float) -> float:
    """Probability weight for a combo given range tightness (0=wide, 1=nit)."""
    strength = preflop_hand_strength(list(hole))
    cutoff = 0.28 + tightness * 0.42
    if strength < cutoff:
        return max(0.02, 0.15 - tightness * 0.1)
    return min(1.0, 0.3 + strength * 0.7)


def estimate_villain_tightness(
    state: dict[str, Any],
    villain_id: str,
    *,
    opponents: dict[str, float] | None = None,
) -> float:
    """Estimate how tight a villain's range is (0=wide, 1=premium)."""
    p = state["players"][villain_id]
    bb = state["settings"]["big_blind"]
    tightness = 0.45

    if opponents:
        pfr = opponents.get("pfr_rate", 0.12)
        vpip = opponents.get("vpip_rate", 0.28)
        tightness = 0.25 + (1.0 - min(0.35, pfr)) * 1.2
        if opponents.get("is_nit"):
            tightness += 0.15
        if opponents.get("is_station"):
            tightness -= 0.12
        tightness += max(0.0, 0.3 - vpip)

    bet_ratio = p["total_bet_hand"] / max(1, bb)
    if state["phase"] == "preflop":
        if bet_ratio >= 8:
            tightness += 0.2
        elif bet_ratio >= 4:
            tightness += 0.12
        elif bet_ratio >= 2:
            tightness += 0.05
    else:
        if p["total_bet_hand"] > state["settings"]["big_blind"] * 3:
            tightness += 0.08

    return max(0.1, min(0.9, tightness))


def sample_weighted_villain_hands(
    known_cards: list[Card],
    num_villains: int,
    tightness: float,
    rng: random.Random,
) -> list[list[Card]]:
    """Sample villain hole cards biased toward villain's estimated range."""
    combos = _remaining_combos(known_cards)
    weights = [hand_in_range_weight(c, tightness) for c in combos]
    total = sum(weights)
    if total <= 0:
        rng.shuffle(combos)
        idx = 0
        villains: list[list[Card]] = []
        for _ in range(num_villains):
            villains.append([combos[idx][0], combos[idx][1]])
            idx += 1
        return villains

    villains = []
    used: set[tuple[str, str]] = set()
    for _ in range(num_villains):
        for _attempt in range(80):
            pick = rng.choices(combos, weights=weights, k=1)[0]
            keys = (_card_tuple(pick[0]), _card_tuple(pick[1]))
            if keys[0] in used or keys[1] in used:
                continue
            villains.append([pick[0], pick[1]])
            used.add(keys[0])
            used.add(keys[1])
            break
        else:
            for combo in combos:
                keys = (_card_tuple(combo[0]), _card_tuple(combo[1]))
                if keys[0] not in used and keys[1] not in used:
                    villains.append([combo[0], combo[1]])
                    used.add(keys[0])
                    used.add(keys[1])
                    break
    return villains
