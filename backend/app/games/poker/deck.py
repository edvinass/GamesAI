import random
from typing import Any

RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A")
SUITS = ("hearts", "diamonds", "clubs", "spades")

RANK_TO_VALUE = {rank: index + 2 for index, rank in enumerate(RANKS)}


def make_card(rank: str, suit: str) -> dict[str, str]:
    return {"rank": rank, "suit": suit}


def card_key(card: dict[str, str]) -> str:
    return f"{card['rank']}{card['suit'][0]}"


def make_deck() -> list[dict[str, str]]:
    return [make_card(rank, suit) for suit in SUITS for rank in RANKS]


class Deck:
    def __init__(self, cards: list[dict[str, str]] | None = None) -> None:
        self.cards = list(cards) if cards is not None else make_deck()

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def deal(self, count: int = 1) -> list[dict[str, str]]:
        if count > len(self.cards):
            raise ValueError("Not enough cards in deck")
        dealt = self.cards[:count]
        self.cards = self.cards[count:]
        return dealt

    def burn(self) -> None:
        if not self.cards:
            raise ValueError("Not enough cards in deck")
        self.cards.pop(0)

    def to_list(self) -> list[dict[str, str]]:
        return list(self.cards)

    @classmethod
    def from_list(cls, cards: list[dict[str, Any]]) -> "Deck":
        return cls([make_card(c["rank"], c["suit"]) for c in cards])
