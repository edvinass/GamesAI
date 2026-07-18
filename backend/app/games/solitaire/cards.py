import random
from typing import TypedDict


SUITS = ["hearts", "diamonds", "clubs", "spades"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

RED_SUITS = {"hearts", "diamonds"}
BLACK_SUITS = {"clubs", "spades"}


class Card(TypedDict):
    rank: str
    suit: str
    face_up: bool


def create_deck() -> list[Card]:
    """Create a standard 52-card deck, all face down."""
    deck: list[Card] = []
    for suit in SUITS:
        for rank in RANKS:
            deck.append({"rank": rank, "suit": suit, "face_up": False})
    return deck


def shuffle_deck(deck: list[Card]) -> list[Card]:
    """Return a shuffled copy of the deck."""
    shuffled = list(deck)
    random.shuffle(shuffled)
    return shuffled


def rank_value(rank: str) -> int:
    """Get numeric value of a rank (A=1, K=13)."""
    return RANKS.index(rank) + 1


def is_red(card: Card) -> bool:
    """Check if a card is red (hearts or diamonds)."""
    return card["suit"] in RED_SUITS


def is_black(card: Card) -> bool:
    """Check if a card is black (clubs or spades)."""
    return card["suit"] in BLACK_SUITS


def can_stack_on_tableau(card: Card, target: Card) -> bool:
    """
    Check if card can be placed on target in tableau.
    Rules: alternating colors, descending rank (target must be one higher).
    """
    if is_red(card) == is_red(target):
        return False
    return rank_value(target["rank"]) == rank_value(card["rank"]) + 1


def is_valid_tableau_run(cards: list[Card]) -> bool:
    """Return True if cards form a face-up descending alternating-color build."""
    if not cards:
        return False
    if any(not card["face_up"] for card in cards):
        return False
    for i in range(len(cards) - 1):
        if not can_stack_on_tableau(cards[i + 1], cards[i]):
            return False
    return True


def can_stack_on_foundation(card: Card, foundation: list[Card]) -> bool:
    """
    Check if card can be placed on foundation pile.
    Rules: same suit, ascending rank (A first, then 2, 3, ... K).
    """
    if not foundation:
        return card["rank"] == "A"
    top_card = foundation[-1]
    if card["suit"] != top_card["suit"]:
        return False
    return rank_value(card["rank"]) == rank_value(top_card["rank"]) + 1


def card_to_dict(card: Card) -> dict:
    """Convert a card to a serializable dict."""
    return {"rank": card["rank"], "suit": card["suit"], "face_up": card["face_up"]}


def cards_to_list(cards: list[Card]) -> list[dict]:
    """Convert a list of cards to serializable dicts."""
    return [card_to_dict(c) for c in cards]
