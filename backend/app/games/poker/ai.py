import random
from typing import Any

from app.games.poker.hand_eval import CATEGORY_PAIR, evaluate_hand

RANK_VALUES = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
    "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
}


def _rank_value(rank: str) -> int:
    return RANK_VALUES[rank]


def _preflop_strength(hole_cards: list[dict[str, str]]) -> float:
    r1 = _rank_value(hole_cards[0]["rank"])
    r2 = _rank_value(hole_cards[1]["rank"])
    high, low = max(r1, r2), min(r1, r2)
    suited = hole_cards[0]["suit"] == hole_cards[1]["suit"]
    pair = r1 == r2

    if pair:
        return 0.5 + high / 28.0
    score = high / 14.0 * 0.35 + low / 14.0 * 0.15
    if suited:
        score += 0.08
    if high - low <= 4:
        score += 0.05
    if high >= 12 and low >= 10:
        score += 0.12
    return score


def _postflop_strength(hole_cards: list[dict[str, str]], community: list[dict[str, str]]) -> float:
    if len(community) == 0:
        return _preflop_strength(hole_cards)
    all_cards = hole_cards + community
    category, tiebreakers = evaluate_hand(all_cards)
    base = category / 8.0
    kicker = tiebreakers[0] / 14.0 * 0.1 if tiebreakers else 0
    return min(1.0, base + kicker)


def _bet_to_call(state: dict, player_id: str) -> int:
    p = state["players"][player_id]
    return max(0, state["current_bet"] - p["bet_this_round"])


def _pot_odds(state: dict, to_call: int) -> float:
    pot = sum(p["total_bet_hand"] for p in state["players"].values())
    if to_call <= 0:
        return 0.0
    return to_call / max(1, pot + to_call)


def _legal_raise_targets(state: dict, player_id: str) -> list[int]:
    from app.games.poker.engine import PokerEngine

    return PokerEngine()._legal_raise_to_amounts(state, player_id)


def choose_poker_action(state: dict, player_id: str) -> dict[str, Any]:
    p = state["players"][player_id]
    to_call = _bet_to_call(state, player_id)
    strength = _postflop_strength(p["hole_cards"], state.get("community_cards", []))
    pot_odds = _pot_odds(state, to_call)
    bluff = random.random() < 0.1

    max_raise_to = p["bet_this_round"] + p["chips"]
    legal_raises = _legal_raise_targets(state, player_id)

    if to_call == 0:
        if strength >= 0.65 or bluff:
            if legal_raises:
                preferred = p["bet_this_round"] + state["settings"]["big_blind"] * 3
                target = min(legal_raises, key=lambda amount: abs(amount - preferred))
                if target > p["bet_this_round"]:
                    return {"type": "raise", "amount": target}
        return {"type": "check"}

    if strength < 0.25 and to_call > state["settings"]["big_blind"] * 2:
        return {"type": "fold"}

    if strength >= pot_odds + 0.15 or strength >= 0.55:
        if strength >= 0.75 and legal_raises and random.random() < 0.35:
            target = legal_raises[min(1, len(legal_raises) - 1)]
            if target > p["bet_this_round"]:
                return {"type": "raise", "amount": target}
        if to_call >= p["chips"]:
            return {"type": "all_in"}
        return {"type": "call"}

    if to_call <= state["settings"]["big_blind"] and strength >= 0.2:
        return {"type": "call"}

    if p["chips"] <= to_call:
        return {"type": "all_in"} if strength >= 0.3 else {"type": "fold"}

    return {"type": "fold"}
