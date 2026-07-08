"""Monte Carlo equity estimation for Texas Hold'em."""

from __future__ import annotations

import random
from typing import Any

from app.games.poker.deck import make_card, make_deck
from app.games.poker.hand_eval import evaluate_hand

Card = dict[str, str]


def _card_tuple(card: Card) -> tuple[str, str]:
    return (card["rank"], card["suit"])


def _remaining_deck(known_cards: list[Card]) -> list[Card]:
    known = {_card_tuple(c) for c in known_cards}
    return [c for c in make_deck() if _card_tuple(c) not in known]


def _complete_board(
    deck: list[Card], community: list[Card], rng: random.Random
) -> list[Card]:
    needed = 5 - len(community)
    if needed <= 0:
        return list(community)
    rng.shuffle(deck)
    return list(community) + deck[:needed]


def _showdown_result(
    hero_cards: list[Card],
    board: list[Card],
    villain_cards: list[list[Card]],
) -> float:
    """Return 1.0 for win, 0.5 for chop, 0.0 for loss against all villains."""
    hero_full = hero_cards + board
    hero_score = evaluate_hand(hero_full)

    beats_all = True
    tied_with_any = False
    lost = False

    for v_cards in villain_cards:
        v_score = evaluate_hand(v_cards + board)
        if v_score > hero_score:
            lost = True
            beats_all = False
        elif v_score == hero_score:
            tied_with_any = True
            beats_all = False

    if beats_all:
        return 1.0
    if lost:
        return 0.0
    if tied_with_any:
        return 0.5
    return 0.0


def estimate_equity(
    hole_cards: list[Card],
    community_cards: list[Card],
    num_opponents: int,
    *,
    iterations: int = 500,
    rng: random.Random | None = None,
) -> float:
    """Estimate hero win probability via Monte Carlo simulation."""
    if num_opponents <= 0:
        return _made_hand_strength(hole_cards, community_cards)

    rng = rng or random.Random()
    known = list(hole_cards) + list(community_cards)
    wins = 0.0

    for _ in range(iterations):
        deck = _remaining_deck(known)
        rng.shuffle(deck)

        villains: list[list[Card]] = []
        idx = 0
        for _ in range(num_opponents):
            villains.append([deck[idx], deck[idx + 1]])
            idx += 2

        board = _complete_board(deck[idx:], community_cards, rng)
        wins += _showdown_result(hole_cards, board, villains)

    return wins / iterations


def _made_hand_strength(hole_cards: list[Card], community: list[Card]) -> float:
    """Fallback strength when alone in the pot (no villains to simulate)."""
    if len(community) < 3:
        return 0.5
    score = evaluate_hand(hole_cards + community)
    category = score[0]
    kicker = score[1][0] if score[1] else 0
    return min(1.0, category / 8.0 + kicker / 14.0 * 0.1)


def estimate_equity_from_state(
    state: dict[str, Any],
    player_id: str,
    *,
    iterations: int = 500,
    rng: random.Random | None = None,
) -> float:
    """Estimate equity using live game state (hole cards, board, active opponents)."""
    player = state["players"][player_id]
    community = state.get("community_cards", [])
    num_opponents = sum(
        1
        for pid, p in state["players"].items()
        if pid != player_id and p["status"] in ("active", "all_in")
    )
    return estimate_equity(
        player["hole_cards"],
        community,
        num_opponents,
        iterations=iterations,
        rng=rng,
    )
