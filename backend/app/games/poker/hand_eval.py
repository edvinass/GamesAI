from collections import Counter
from itertools import combinations
from typing import Any

from app.games.poker.deck import RANK_TO_VALUE, RANKS

CATEGORY_HIGH_CARD = 0
CATEGORY_PAIR = 1
CATEGORY_TWO_PAIR = 2
CATEGORY_THREE_KIND = 3
CATEGORY_STRAIGHT = 4
CATEGORY_FLUSH = 5
CATEGORY_FULL_HOUSE = 6
CATEGORY_FOUR_KIND = 7
CATEGORY_STRAIGHT_FLUSH = 8

CATEGORY_NAMES = (
    "high_card",
    "pair",
    "two_pair",
    "three_of_a_kind",
    "straight",
    "flush",
    "full_house",
    "four_of_a_kind",
    "straight_flush",
)


def _card_value(card: dict[str, str]) -> int:
    return RANK_TO_VALUE[card["rank"]]


def _values(cards: list[dict[str, str]]) -> list[int]:
    return sorted((_card_value(c) for c in cards), reverse=True)


def _is_straight(values: list[int]) -> tuple[bool, int]:
    unique = sorted(set(values), reverse=True)
    if len(unique) < 5:
        return False, 0
    # Wheel: A-2-3-4-5
    if {14, 5, 4, 3, 2}.issubset(set(unique)):
        return True, 5
    for i in range(len(unique) - 4):
        window = unique[i : i + 5]
        if window[0] - window[4] == 4 and len(window) == 5:
            return True, window[0]
    return False, 0


def _evaluate_five(cards: list[dict[str, str]]) -> tuple[int, tuple[int, ...]]:
    if len(cards) != 5:
        raise ValueError("Need exactly 5 cards")

    values = _values(cards)
    suits = [c["suit"] for c in cards]
    is_flush = len(set(suits)) == 1
    is_straight, straight_high = _is_straight(values)

    counts = Counter(values)
    ordered_counts = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    count_pattern = sorted(counts.values(), reverse=True)

    if is_flush and is_straight:
        return CATEGORY_STRAIGHT_FLUSH, (straight_high,)

    if count_pattern == [4, 1]:
        quad = next(v for v, c in counts.items() if c == 4)
        kicker = next(v for v, c in counts.items() if c == 1)
        return CATEGORY_FOUR_KIND, (quad, kicker)

    if count_pattern == [3, 2]:
        trips = next(v for v, c in counts.items() if c == 3)
        pair = next(v for v, c in counts.items() if c == 2)
        return CATEGORY_FULL_HOUSE, (trips, pair)

    if is_flush:
        return CATEGORY_FLUSH, tuple(values)

    if is_straight:
        return CATEGORY_STRAIGHT, (straight_high,)

    if count_pattern == [3, 1, 1]:
        trips = next(v for v, c in counts.items() if c == 3)
        kickers = sorted((v for v, c in counts.items() if c == 1), reverse=True)
        return CATEGORY_THREE_KIND, (trips, *kickers)

    if count_pattern == [2, 2, 1]:
        pairs = sorted((v for v, c in counts.items() if c == 2), reverse=True)
        kicker = next(v for v, c in counts.items() if c == 1)
        return CATEGORY_TWO_PAIR, (pairs[0], pairs[1], kicker)

    if count_pattern == [2, 1, 1, 1]:
        pair = next(v for v, c in counts.items() if c == 2)
        kickers = sorted((v for v, c in counts.items() if c == 1), reverse=True)
        return CATEGORY_PAIR, (pair, *kickers)

    return CATEGORY_HIGH_CARD, tuple(values)


def evaluate_hand(cards: list[dict[str, str]]) -> tuple[int, tuple[int, ...]]:
    if len(cards) == 5:
        return _evaluate_five(cards)
    if len(cards) < 5:
        raise ValueError("Need at least 5 cards")
    best: tuple[int, tuple[int, ...]] | None = None
    for combo in combinations(cards, 5):
        score = _evaluate_five(list(combo))
        if best is None or score > best:
            best = score
    if best is None:
        raise ValueError("Could not evaluate hand")
    return best


def hand_category_name(score: tuple[int, tuple[int, ...]]) -> str:
    return CATEGORY_NAMES[score[0]]


def compare_hands(
    cards_a: list[dict[str, str]], cards_b: list[dict[str, str]]
) -> int:
    score_a = evaluate_hand(cards_a)
    score_b = evaluate_hand(cards_b)
    if score_a > score_b:
        return 1
    if score_a < score_b:
        return -1
    return 0


def rank_to_display(rank: str) -> str:
    display = {"T": "10", "J": "J", "Q": "Q", "K": "K", "A": "A"}
    return display.get(rank, rank)


def value_to_rank(value: int) -> str:
    for rank, rank_value in RANK_TO_VALUE.items():
        if rank_value == value:
            return rank_to_display(rank)
    return str(value)


def value_to_name(value: int, *, plural: bool = False) -> str:
    names = {
        14: ("Ace", "Aces"),
        13: ("King", "Kings"),
        12: ("Queen", "Queens"),
        11: ("Jack", "Jacks"),
        10: ("Ten", "Tens"),
        9: ("Nine", "Nines"),
        8: ("Eight", "Eights"),
        7: ("Seven", "Sevens"),
        6: ("Six", "Sixes"),
        5: ("Five", "Fives"),
        4: ("Four", "Fours"),
        3: ("Three", "Threes"),
        2: ("Two", "Twos"),
    }
    singular, plural_name = names.get(value, (str(value), f"{value}s"))
    return plural_name if plural else singular


def describe_hand(cards: list[dict[str, str]]) -> str:
    score = evaluate_hand(cards)
    category = hand_category_name(score)
    kickers = score[1]

    if category == "high_card":
        return f"High Card, {value_to_name(kickers[0])}"
    if category == "pair":
        return f"Pair of {value_to_name(kickers[0], plural=True)}"
    if category == "two_pair":
        return (
            f"Two Pair, {value_to_name(kickers[0], plural=True)} "
            f"and {value_to_name(kickers[1], plural=True)}"
        )
    if category == "three_of_a_kind":
        return f"Three of a Kind, {value_to_name(kickers[0], plural=True)}"
    if category == "straight":
        return f"Straight, {value_to_name(kickers[0])} high"
    if category == "flush":
        return f"Flush, {value_to_name(kickers[0])} high"
    if category == "full_house":
        return (
            f"Full House, {value_to_name(kickers[0], plural=True)} "
            f"full of {value_to_name(kickers[1], plural=True)}"
        )
    if category == "four_of_a_kind":
        return f"Four of a Kind, {value_to_name(kickers[0], plural=True)}"
    if category == "straight_flush":
        return f"Straight Flush, {value_to_name(kickers[0])} high"

    return category.replace("_", " ").title()
