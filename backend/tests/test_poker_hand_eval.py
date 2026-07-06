import pytest

from app.games.poker.deck import make_card
from app.games.poker.hand_eval import (
    CATEGORY_FLUSH,
    CATEGORY_FOUR_KIND,
    CATEGORY_FULL_HOUSE,
    CATEGORY_HIGH_CARD,
    CATEGORY_PAIR,
    CATEGORY_STRAIGHT,
    CATEGORY_STRAIGHT_FLUSH,
    CATEGORY_THREE_KIND,
    CATEGORY_TWO_PAIR,
    evaluate_hand,
    hand_category_name,
)


def test_high_card() -> None:
    cards = [
        make_card("2", "hearts"),
        make_card("5", "clubs"),
        make_card("7", "diamonds"),
        make_card("9", "spades"),
        make_card("K", "hearts"),
    ]
    score = evaluate_hand(cards)
    assert score[0] == CATEGORY_HIGH_CARD


def test_pair() -> None:
    cards = [
        make_card("A", "hearts"),
        make_card("A", "clubs"),
        make_card("K", "hearts"),
        make_card("7", "diamonds"),
        make_card("2", "spades"),
    ]
    score = evaluate_hand(cards)
    assert score[0] == CATEGORY_PAIR


def test_two_pair() -> None:
    cards = [
        make_card("A", "hearts"),
        make_card("A", "clubs"),
        make_card("K", "hearts"),
        make_card("K", "diamonds"),
        make_card("2", "spades"),
    ]
    score = evaluate_hand(cards)
    assert score[0] == CATEGORY_TWO_PAIR


def test_three_of_a_kind() -> None:
    cards = [
        make_card("Q", "hearts"),
        make_card("Q", "clubs"),
        make_card("Q", "diamonds"),
        make_card("4", "spades"),
        make_card("2", "hearts"),
    ]
    score = evaluate_hand(cards)
    assert score[0] == CATEGORY_THREE_KIND


def test_straight() -> None:
    cards = [
        make_card("5", "hearts"),
        make_card("6", "clubs"),
        make_card("7", "diamonds"),
        make_card("8", "spades"),
        make_card("9", "hearts"),
    ]
    score = evaluate_hand(cards)
    assert score[0] == CATEGORY_STRAIGHT


def test_wheel_straight() -> None:
    cards = [
        make_card("A", "hearts"),
        make_card("2", "clubs"),
        make_card("3", "diamonds"),
        make_card("4", "spades"),
        make_card("5", "hearts"),
    ]
    score = evaluate_hand(cards)
    assert score[0] == CATEGORY_STRAIGHT
    assert score[1][0] == 5


def test_flush() -> None:
    cards = [make_card("2", "spades"), make_card("5", "spades"), make_card("7", "spades"), make_card("9", "spades"), make_card("K", "spades")]
    score = evaluate_hand(cards)
    assert score[0] == CATEGORY_FLUSH


def test_full_house() -> None:
    cards = [
        make_card("J", "hearts"),
        make_card("J", "clubs"),
        make_card("J", "diamonds"),
        make_card("4", "spades"),
        make_card("4", "hearts"),
    ]
    score = evaluate_hand(cards)
    assert score[0] == CATEGORY_FULL_HOUSE


def test_four_of_a_kind() -> None:
    cards = [
        make_card("8", "hearts"),
        make_card("8", "clubs"),
        make_card("8", "diamonds"),
        make_card("8", "spades"),
        make_card("2", "hearts"),
    ]
    score = evaluate_hand(cards)
    assert score[0] == CATEGORY_FOUR_KIND


def test_straight_flush() -> None:
    cards = [make_card(r, "hearts") for r in ("4", "5", "6", "7", "8")]
    score = evaluate_hand(cards)
    assert score[0] == CATEGORY_STRAIGHT_FLUSH


def test_best_five_of_seven() -> None:
    hole = [make_card("A", "hearts"), make_card("A", "clubs")]
    board = [
        make_card("A", "diamonds"),
        make_card("K", "hearts"),
        make_card("K", "clubs"),
        make_card("2", "spades"),
        make_card("3", "diamonds"),
    ]
    score = evaluate_hand(hole + board)
    assert hand_category_name(score) == "full_house"
